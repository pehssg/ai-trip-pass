"""
오피넷 유가 자동 수집 (GitHub Actions에서 매일 실행)

- 최근 7일간 전국 일일 평균가격(avgRecentPrice.do)을 받아 fuel_price_history.json에 날짜별로 쌓습니다.
- 가장 최근 값은 fuel_prices.json에도 저장합니다.
- 인증키: 저장소 Secrets의 OPINET_API_KEY (요청 파라미터 이름은 code, 실패 시 apikey로 재시도)
"""
import datetime, json, os, sys
import requests
import xml.etree.ElementTree as ET

KEY = os.environ.get("OPINET_API_KEY", "").strip()
CODES = {"휘발유": "B027", "경유": "D047", "LPG": "K015"}
HIST, LATEST = "fuel_price_history.json", "fuel_prices.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (AI-Trip Pass fuel collector)"}


def items(payload: str):
    out = []
    try:
        data = json.loads(payload)
        oil = data.get("RESULT", {}).get("OIL", [])
        oil = oil if isinstance(oil, list) else [oil]
        for it in oil:
            out.append((str(it.get("DATE") or it.get("TRADE_DT") or ""), str(it.get("PRODCD", "")),
                        float(str(it.get("PRICE", "0")).replace(",", ""))))
        return out
    except (ValueError, AttributeError):
        pass
    try:
        for o in ET.fromstring(payload).iter("OIL"):
            t = lambda k: (o.findtext(k) or "").strip()
            out.append((t("DATE") or t("TRADE_DT"), t("PRODCD"), float(t("PRICE").replace(",", "") or 0)))
    except Exception:
        pass
    return out


def recent(prodcd: str) -> dict:
    for param in ("code", "apikey"):
        try:
            r = requests.get("https://www.opinet.co.kr/api/avgRecentPrice.do",
                             params={"out": "json", "prodcd": prodcd, param: KEY}, headers=HEADERS, timeout=15)
            print(f"  [{prodcd}/{param}] HTTP {r.status_code} · {r.text[:160]!r}")
            got = {}
            for d, code, price in items(r.text):
                if (not code or code == prodcd) and len(d) == 8 and 400 < price < 4000:
                    got[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = round(price)
            if got:
                return got
        except Exception as e:
            print(f"  [{prodcd}/{param}] 오류: {e}")
    return {}


def main():
    print(f"오피넷 유가 수집 {datetime.datetime.now():%Y-%m-%d %H:%M} · 인증키 {'있음' if KEY else '없음'}")
    try:
        hist = json.load(open(HIST, encoding="utf-8"))
    except Exception:
        hist = {}
    added = 0
    for fuel, code in CODES.items():
        got = recent(code)
        table = hist.setdefault(fuel, {})
        for d, p in got.items():
            if table.get(d) != p:
                table[d] = p
                added += 1
        hist[fuel] = dict(sorted(table.items()))
        print(f"  {fuel}: {len(got)}일 수신, 누적 {len(hist[fuel])}일")
    hist["updated"] = datetime.date.today().isoformat()
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    latest = {}
    for fuel in CODES:
        if hist.get(fuel):
            d = max(hist[fuel])
            latest[fuel] = hist[fuel][d]
            latest["updated"] = d
    if len([k for k in latest if k in CODES]) == len(CODES):
        latest["source"] = "오피넷 API"
        json.dump(latest, open(LATEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("최신 유가:", latest)
    else:
        print("⚠️ 유가를 받지 못했습니다. 인증키 승인 상태와 위 응답 내용을 확인하세요.")
    print(f"새로 추가·변경된 일별 값: {added}건")


if __name__ == "__main__":
    main()
