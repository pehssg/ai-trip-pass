"""
오피넷 공공데이터 API로 전국 평균 유가를 가져와 fuel_prices.json에 저장합니다.
GitHub Actions에서 매일 실행됩니다.
필요 환경변수: OPINET_API_KEY
"""

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re, json, datetime, os, sys, time

# ── 설정 ──────────────────────────────────────
API_KEY  = os.environ.get("OPINET_API_KEY", "")
BASE_URL = "http://www.opinet.co.kr/api"
OUTPUT   = "fuel_prices.json"
FALLBACK = {"휘발유": 1652, "경유": 1498, "LPG": 963}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.opinet.co.kr/",
}

FUEL_CODES = {
    "휘발유": "B027",
    "경유":   "D047",
    "LPG":   "K015",
}


# ── 방법 1: 오피넷 공공데이터 API (인증키) ────────────────────
def method_api_key() -> dict:
    """오피넷 공공데이터 API — 전국 평균가격 조회"""
    if not API_KEY:
        print("  ⚠️ OPINET_API_KEY 환경변수 없음")
        return {}

    result = {}
    for fuel, code in FUEL_CODES.items():
        # XML 방식
        for fmt in ["xml", "json"]:
            try:
                url = (
                    f"{BASE_URL}/avgAllPrice.do"
                    f"?out={fmt}&prodcd={code}&apikey={API_KEY}"
                )
                r = requests.get(url, headers=HEADERS, timeout=10)
                print(f"  [API/{fmt}] {fuel}: HTTP {r.status_code}")

                if r.status_code == 200:
                    if fmt == "xml":
                        root = ET.fromstring(r.content)
                        # 다양한 태그 시도
                        for tag in ["PRICE", "avgPrice", "price", "OIL_PRICE"]:
                            el = root.find(f".//{tag}")
                            if el is not None and el.text:
                                val = int(float(el.text.replace(",", "")))
                                if 400 < val < 5000:
                                    result[fuel] = val
                                    print(f"  [API/xml] {fuel}: {val}원")
                                    break
                    else:
                        try:
                            data = r.json()
                            raw  = json.dumps(data, ensure_ascii=False)
                            print(f"  [API/json] 응답: {raw[:200]}")
                            # 숫자 패턴에서 유가 추출
                            prices = re.findall(r'"(?:PRICE|price|avgPrice)"\s*:\s*"?([\d.]+)"?', raw)
                            for p in prices:
                                val = int(float(p))
                                if 400 < val < 5000 and fuel not in result:
                                    result[fuel] = val
                                    print(f"  [API/json] {fuel}: {val}원")
                        except Exception as e:
                            print(f"  [API/json] 파싱 오류: {e}")
                            print(f"  응답 내용: {r.text[:300]}")

                    if fuel in result:
                        break

            except Exception as e:
                print(f"  [API] {fuel}/{fmt} 오류: {e}")
            time.sleep(0.3)

    return result


# ── 방법 2: 오피넷 일별 시도 API ─────────────────────────────
def method_api_date() -> dict:
    """오피넷 날짜별 전국 평균가격"""
    if not API_KEY:
        return {}

    result = {}
    today = datetime.date.today().strftime("%Y%m%d")

    try:
        url = (
            f"{BASE_URL}/avgRecentMonthPriceInfo.do"
            f"?out=xml&apikey={API_KEY}&date={today}"
        )
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  [날짜API] HTTP {r.status_code}")
        print(f"  응답: {r.text[:400]}")

        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for oil in root.findall(".//OIL"):
                code_el  = oil.find("PRODCD")
                price_el = oil.find("PRICE")
                if code_el is not None and price_el is not None:
                    code = code_el.text
                    for fuel, fcode in FUEL_CODES.items():
                        if code == fcode:
                            val = int(float(price_el.text.replace(",", "")))
                            if 400 < val < 5000:
                                result[fuel] = val
                                print(f"  [날짜API] {fuel}: {val}원")

    except Exception as e:
        print(f"  [날짜API] 오류: {e}")

    return result


# ── 방법 3: 오피넷 메인 스크래핑 (API 키 불필요) ──────────────
def method_scrape() -> dict:
    """오피넷 메인 페이지 스크래핑"""
    result = {}
    try:
        r = requests.get(
            "https://www.opinet.co.kr/user/main/mainView.do",
            headers=HEADERS, timeout=12
        )
        print(f"  [스크래핑] HTTP {r.status_code}, 길이={len(r.text)}")

        if r.status_code != 200:
            return result

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        for fuel, pattern in [
            ("휘발유", r"휘발유[^\d]{0,40}(1[,\s]?\d{3}(?:[,.]\d{1,2})?)"),
            ("경유",   r"경유[^\d]{0,40}(1[,\s]?\d{3}(?:[,.]\d{1,2})?)"),
            ("LPG",   r"LPG[^\d]{0,40}([89]\d{2}|1[,\s]?\d{3})"),
        ]:
            m = re.search(pattern, text)
            if m:
                val = int(float(m.group(1).replace(",","").replace(" ","")))
                if 400 < val < 5000:
                    result[fuel] = val
                    print(f"  [스크래핑] {fuel}: {val}원")

    except Exception as e:
        print(f"  [스크래핑] 오류: {e}")

    return result


# ── 방법 4: avgAllPrice 전체 목록 API ────────────────────────
def method_api_all() -> dict:
    """오피넷 전체 유종 평균가격 한 번에 조회"""
    if not API_KEY:
        return {}

    result = {}
    try:
        url = f"{BASE_URL}/avgAllPrice.do?out=xml&apikey={API_KEY}"
        r   = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  [전체API] HTTP {r.status_code}")
        print(f"  응답: {r.text[:500]}")

        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for oil in root.findall(".//OIL"):
                code_el  = oil.find("PRODCD")
                price_el = oil.find("PRICE")
                if code_el is None or price_el is None:
                    continue
                for fuel, fcode in FUEL_CODES.items():
                    if code_el.text == fcode:
                        val = int(float(price_el.text.replace(",", "")))
                        if 400 < val < 5000:
                            result[fuel] = val
                            print(f"  [전체API] {fuel}: {val}원")

    except Exception as e:
        print(f"  [전체API] 오류: {e}")

    return result


# ── 유효성 검사 ───────────────────────────────────────────────
def is_valid(r: dict) -> bool:
    ranges = {"휘발유": (1200,2500), "경유": (1000,2300), "LPG": (600,1600)}
    return all(
        fuel in r and ranges[fuel][0] <= r[fuel] <= ranges[fuel][1]
        for fuel in ["휘발유","경유","LPG"]
    )


# ── 메인 ─────────────────────────────────────────────────────
def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"오피넷 유가 스크래핑: {datetime.datetime.now()}")
    print(f"API 키: {'있음 (' + API_KEY[:8] + '...)' if API_KEY else '없음 ❌'}")
    print(f"{'='*55}")

    merged = {}
    source = "예비 데이터"

    # 방법 1: 개별 유종 API
    print("\n▶ 방법 1: 오피넷 공공데이터 API (개별 유종)")
    merged.update(method_api_key())
    if is_valid(merged):
        source = "오피넷 공공데이터 API"
        print(f"✅ 성공!")
    else:
        # 방법 2: 전체 목록 API
        print("\n▶ 방법 2: 오피넷 전체 유종 API")
        merged.update(method_api_all())
        if is_valid(merged):
            source = "오피넷 전체 유종 API"
            print(f"✅ 성공!")
        else:
            # 방법 3: 날짜별 API
            print("\n▶ 방법 3: 오피넷 날짜별 API")
            merged.update(method_api_date())
            if is_valid(merged):
                source = "오피넷 날짜별 API"
                print(f"✅ 성공!")
            else:
                # 방법 4: 메인 스크래핑
                print("\n▶ 방법 4: 오피넷 메인 스크래핑")
                merged.update(method_scrape())
                if is_valid(merged):
                    source = "오피넷 스크래핑"
                    print(f"✅ 성공!")
                else:
                    # 폴백
                    for fuel, val in FALLBACK.items():
                        if fuel not in merged:
                            merged[fuel] = val
                    source = "예비 데이터 (모든 방법 실패)"
                    print(f"⚠️ 모든 방법 실패 — 예비 데이터 사용")

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
    print(f"✅ 저장 완료: {OUTPUT}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
