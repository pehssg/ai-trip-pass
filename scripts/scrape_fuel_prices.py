"""
오피넷 공공데이터 API 유가 수집 스크립트
"""

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re, json, datetime, os, sys, time

API_KEY  = os.environ.get("OPINET_API_KEY", "")
OUTPUT   = "fuel_prices.json"
FALLBACK = {"휘발유": 1652, "경유": 1498, "LPG": 963}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.opinet.co.kr/",
}

FUEL_CODES = {"휘발유": "B027", "경유": "D047", "LPG": "K015"}


def debug_api():
    """API 응답 구조 파악용 — 다양한 엔드포인트와 파라미터 시도"""
    base = "http://www.opinet.co.kr/api"
    results = {}

    # 시도할 엔드포인트 목록
    endpoints = [
        # 전국 평균가격
        f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}",
        f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}&prodcd=B027",
        f"{base}/avgAllPrice.do?out=xml&apikey={API_KEY}&oil_cd=B027",
        # 오늘 평균가
        f"{base}/avgSidoPrice.do?out=xml&apikey={API_KEY}&sido=01&prodcd=B027",
        f"{base}/avgSidoPrice.do?out=xml&apikey={API_KEY}&area=01&prodcd=B027",
        # 최근 가격
        f"{base}/avgRecentMonthPriceInfo.do?out=xml&apikey={API_KEY}",
        f"{base}/avgRecentMonthPriceInfo.do?out=xml&apikey={API_KEY}&prodcd=B027",
        # 주유소 평균
        f"{base}/searchStnInfo.do?out=xml&apikey={API_KEY}&prodcd=B027&cnt=1",
        # 다른 형식
        f"{base}/avgAllPrice.do?apikey={API_KEY}&out=xml",
        f"{base}/avgAllPrice.do?ServiceKey={API_KEY}&out=xml",
    ]

    for url in endpoints:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            clean_url = url.replace(API_KEY, "API_KEY")
            print(f"\n[{r.status_code}] {clean_url}")
            if r.status_code == 200:
                print(f"응답: {r.text[:400]}")
            time.sleep(0.5)
        except Exception as e:
            print(f"오류: {e}")

    return results


def extract_prices_from_xml(xml_text: str) -> dict:
    """XML에서 유가 추출 — 다양한 태그 구조 시도"""
    result = {}
    try:
        root = ET.fromstring(xml_text)
        print(f"  XML 루트 태그: {root.tag}")
        print(f"  XML 전체: {xml_text[:600]}")

        # 모든 하위 요소 출력
        for child in root.iter():
            if child.text and child.text.strip():
                print(f"    태그: {child.tag} = {child.text.strip()}")

        # 유종 코드로 매핑
        for el in root.iter():
            text = (el.text or "").strip().replace(",", "")
            if text and re.match(r"^\d{3,4}(\.\d+)?$", text):
                val = int(float(text))
                if 400 < val < 5000:
                    # 부모 태그에서 유종 코드 찾기
                    parent_text = ET.tostring(el, encoding="unicode")
                    for fuel, code in FUEL_CODES.items():
                        if code in parent_text and fuel not in result:
                            result[fuel] = val
                            print(f"  → {fuel}: {val}원")

    except Exception as e:
        print(f"  XML 파싱 오류: {e}")
    return result


def method_scrape_detailed() -> dict:
    """오피넷 메인 페이지 상세 스크래핑"""
    result = {}
    try:
        r = requests.get(
            "https://www.opinet.co.kr/user/main/mainView.do",
            headers=HEADERS, timeout=15
        )
        print(f"  메인 HTTP {r.status_code}, 길이={len(r.text)}")

        if r.status_code == 200:
            # HTML 전체 저장해서 구조 파악
            soup = BeautifulSoup(r.text, "html.parser")
            print(f"  타이틀: {soup.title.text if soup.title else '없음'}")

            # 모든 숫자 패턴
            text = soup.get_text()
            all_prices = re.findall(r"(\d{1,2},\d{3}(?:\.\d{1,2})?)", text)
            print(f"  천단위 숫자 목록: {all_prices[:20]}")

            # 스크립트 태그에서 유가 데이터 찾기
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and any(k in script.string for k in ["유가", "price", "B027", "gasoline"]):
                    print(f"  스크립트 발견: {script.string[:300]}")

            # 특정 클래스/ID 탐색
            for sel in ["#priceReport", ".oil-price", ".gas-price",
                        "table", ".price", ".avg", "[class*=price]",
                        "[class*=oil]", "[id*=price]", "[id*=oil]"]:
                found = soup.select(sel)
                if found:
                    texts = [f.get_text(strip=True)[:50] for f in found[:3]]
                    print(f"  선택자 '{sel}': {texts}")

    except Exception as e:
        print(f"  오류: {e}")

    return result


def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"오피넷 API 구조 진단: {datetime.datetime.now()}")
    print(f"API 키: {'있음 (' + API_KEY[:8] + '...)' if API_KEY else '없음'}")
    print(f"{'='*55}")

    print("\n▶ API 엔드포인트 전수 조사")
    debug_api()

    print("\n▶ 메인 페이지 상세 분석")
    method_scrape_detailed()

    # 임시로 폴백 저장
    data = {**FALLBACK, "updated": today, "source": "진단 중 — 예비 데이터"}
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {OUTPUT} (진단 완료 후 재실행 필요)")


if __name__ == "__main__":
    main()
