"""
오피넷 API 유가 수집 스크립트
GitHub Actions에서 매일 실행 → fuel_prices.json 저장
"""

import requests
import xml.etree.ElementTree as ET
import json, datetime, os, re, time

API_KEY  = os.environ.get("OPINET_API_KEY", "")
OUTPUT   = "fuel_prices.json"
FALLBACK = {"휘발유": 1652, "경유": 1498, "LPG": 963}
HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.opinet.co.kr/",
}
FUEL_CODES = {"휘발유": "B027", "경유": "D047", "LPG": "K015"}


def try_endpoint(url: str, label: str) -> str:
    """엔드포인트 호출 후 응답 텍스트 반환"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        safe_url = url.replace(API_KEY, "***")
        print(f"  [{r.status_code}] {label}")
        if r.status_code == 200:
            print(f"  응답: {r.text[:300]}")
            return r.text
    except Exception as e:
        print(f"  [ERR] {label}: {str(e)[:80]}")
    return ""


def extract_price(xml_or_json: str, fuel_code: str) -> int:
    """XML 또는 JSON 응답에서 유가 추출"""
    # XML 파싱
    try:
        root = ET.fromstring(xml_or_json)
        for el in root.iter():
            if el.tag in ("PRICE", "price", "AVG_PRICE", "avgPrice"):
                val = int(float((el.text or "0").replace(",", "")))
                if 400 < val < 5000:
                    return val
            # OIL 블록에서 유종 코드 매칭
            if el.tag in ("OIL", "RESULT_OIL", "item"):
                code_el  = el.find("PRODCD") or el.find("prodcd") or el.find("OIL_CD")
                price_el = el.find("PRICE")  or el.find("price")
                if code_el is not None and price_el is not None:
                    if code_el.text == fuel_code:
                        val = int(float(price_el.text.replace(",", "")))
                        if 400 < val < 5000:
                            return val
    except Exception:
        pass

    # JSON 파싱
    try:
        data = json.loads(xml_or_json)
        raw  = json.dumps(data)
        nums = re.findall(r'"(?:PRICE|price|avgPrice|AVG_PRICE)"\s*:\s*"?([\d.]+)"?', raw)
        for n in nums:
            val = int(float(n))
            if 400 < val < 5000:
                return val
    except Exception:
        pass

    return 0


def fetch_all_fuels() -> dict:
    """다양한 엔드포인트로 전체 유종 유가 수집"""
    result = {}
    base   = "http://www.opinet.co.kr/api"

    # ── 전체 유종 한 번에 ────────────────────────
    print("\n[전체 유종 API]")
    endpoints_all = [
        (f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}",              "avgAllPrice xml"),
        (f"{base}/avgAllPrice.do?out=json&apikey={API_KEY}",             "avgAllPrice json"),
        (f"{base}/avgOilPrice.do?out=xml&apikey={API_KEY}",              "avgOilPrice xml"),
        (f"{base}/getAvgRecentMonthOilPriceInfo.do?out=xml&apikey={API_KEY}", "getAvgRecent xml"),
        (f"{base}/GasStationSearchSingl.do?out=xml&apikey={API_KEY}",   "GasStationSearch xml"),
    ]
    for url, label in endpoints_all:
        text = try_endpoint(url, label)
        if text and "<RESULT>" in text and len(text) > 50:
            for fuel, code in FUEL_CODES.items():
                if fuel not in result:
                    val = extract_price(text, code)
                    if val:
                        result[fuel] = val
                        print(f"  → {fuel}: {val}원")
        if len(result) == 3:
            return result
        time.sleep(0.3)

    # ── 유종별 개별 조회 ─────────────────────────
    print("\n[개별 유종 API]")
    for fuel, code in FUEL_CODES.items():
        if fuel in result:
            continue
        endpoints_single = [
            (f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}&prodcd={code}",      f"{fuel} prodcd"),
            (f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}&oil_cd={code}",      f"{fuel} oil_cd"),
            (f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}&oilCd={code}",       f"{fuel} oilCd"),
            (f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}&fuel={code}",        f"{fuel} fuel"),
            (f"{base}/avgOilPrice.do?out=xml&apikey={API_KEY}&prodcd={code}",      f"{fuel} avgOil"),
            (f"{base}/getAvgPrice.do?out=xml&apikey={API_KEY}&prodcd={code}",      f"{fuel} getAvg"),
            (f"{base}/getNationalAvgPrice.do?out=xml&apikey={API_KEY}&prodcd={code}", f"{fuel} national"),
        ]
        for url, label in endpoints_single:
            text = try_endpoint(url, label)
            if text:
                val = extract_price(text, code)
                if val:
                    result[fuel] = val
                    print(f"  → {fuel}: {val}원")
                    break
            time.sleep(0.3)

    return result


def is_valid(r: dict) -> bool:
    ranges = {"휘발유":(1200,2500), "경유":(1000,2300), "LPG":(600,1600)}
    return all(fuel in r and ranges[fuel][0] <= r[fuel] <= ranges[fuel][1]
               for fuel in ["휘발유","경유","LPG"])


def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"오피넷 유가 수집: {datetime.datetime.now()}")
    print(f"API 키: {'있음 (' + API_KEY[:8] + '...)' if API_KEY else '없음 ❌'}")
    print(f"{'='*55}")

    merged = fetch_all_fuels()

    if is_valid(merged):
        source = "오피넷 API"
        print(f"\n✅ 수집 성공!")
    else:
        print(f"\n⚠️ API 수집 실패 — 예비 데이터 사용")
        for fuel, val in FALLBACK.items():
            if fuel not in merged:
                merged[fuel] = val
        source = "예비 데이터"

    data = {
        "휘발유": merged.get("휘발유", FALLBACK["휘발유"]),
        "경유":   merged.get("경유",   FALLBACK["경유"]),
        "LPG":   merged.get("LPG",   FALLBACK["LPG"]),
        "updated": today,
        "source":  source,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"✅ 저장: {OUTPUT}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
