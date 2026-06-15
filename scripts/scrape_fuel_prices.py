"""
오피넷 전국 평균 유가 스크래핑 스크립트
GitHub Actions에서 매일 실행 → fuel_prices.json 저장
"""

import requests
from bs4 import BeautifulSoup
import re, json, datetime, sys, time
import xml.etree.ElementTree as ET

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.opinet.co.kr/",
}

FALLBACK = {"휘발유": 1652, "경유": 1498, "LPG": 963}


def method1_xml_api() -> dict:
    """방법 1: 오피넷 공식 XML API"""
    result = {}
    codes = {"휘발유": "B027", "경유": "D047", "LPG": "K015"}
    for fuel, code in codes.items():
        try:
            url = f"https://www.opinet.co.kr/api/avgAllPrice.do?out=xml&prodcd={code}"
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                el = root.find(".//PRICE")
                if el is not None and el.text:
                    val = int(float(el.text))
                    if 500 < val < 4000:
                        result[fuel] = val
            time.sleep(0.5)
        except Exception as e:
            print(f"  XML API [{fuel}] 실패: {e}")
    return result


def method2_main_scraping() -> dict:
    """방법 2: 오피넷 메인 페이지 스크래핑"""
    result = {}
    try:
        r = requests.get(
            "https://www.opinet.co.kr/user/main/mainView.do",
            headers=HEADERS, timeout=12
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # 다양한 선택자로 가격 탐색
        selectors = [
            "#priceReport", ".priceInfo", ".oil_price_wrap",
            "#national_oil_price", ".avg_price", "li.on .num",
            "strong.num", "em.num", ".today_oil .num",
        ]
        for sel in selectors:
            tags = soup.select(sel)
            for tag in tags:
                txt = tag.get_text(strip=True).replace(",", "")
                nums = re.findall(r"\d{3,4}(?:\.\d{1,2})?", txt)
                for n in nums:
                    val = int(float(n))
                    if 800 < val < 4000 and "휘발유" not in result:
                        result["휘발유"] = val
                    elif 700 < val < 3000 and "경유" not in result and val != result.get("휘발유"):
                        result["경유"] = val

        # 텍스트 전체에서 패턴 매칭
        all_text = soup.get_text()
        patterns = {
            "휘발유": r"휘발유[^\d]{0,30}(1[,\s]?\d{3}(?:[,.]\d{1,2})?)",
            "경유":   r"경유[^\d]{0,30}(1[,\s]?\d{3}(?:[,.]\d{1,2})?)",
            "LPG":   r"LPG[^\d]{0,20}([89]\d{2}|1[,\s]?\d{3})(?:[,.]\d{1,2})?",
        }
        for fuel, pattern in patterns.items():
            if fuel not in result:
                m = re.search(pattern, all_text)
                if m:
                    val = int(float(m.group(1).replace(",", "").replace(" ", "")))
                    if 400 < val < 4000:
                        result[fuel] = val

    except Exception as e:
        print(f"  메인 스크래핑 실패: {e}")
    return result


def method3_ajax() -> dict:
    """방법 3: 오피넷 AJAX/JSON 엔드포인트"""
    result = {}
    ajax_urls = [
        "https://www.opinet.co.kr/user/main/getAverageRecentPrice.do",
        "https://www.opinet.co.kr/user/chart/getChartNationAvgPrice.do",
        "https://www.opinet.co.kr/api/avgAllPrice.do?out=json",
    ]
    for url in ajax_urls:
        try:
            r = requests.get(url, headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
                             timeout=8)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                data = r.json()
                # JSON 구조에서 유가 추출 시도
                text = json.dumps(data, ensure_ascii=False)
                for fuel, kw in [("휘발유", "B027"), ("경유", "D047"), ("LPG", "K015")]:
                    m = re.search(rf'"{kw}"[^}}]+"PRICE"\s*:\s*"?([\d.]+)"?', text)
                    if m:
                        val = int(float(m.group(1)))
                        if 400 < val < 4000:
                            result[fuel] = val
        except Exception as e:
            print(f"  AJAX [{url[-30:]}] 실패: {e}")
    return result


def validate(result: dict) -> bool:
    """결과 유효성 검사"""
    for fuel in ["휘발유", "경유", "LPG"]:
        if fuel not in result:
            return False
        val = result[fuel]
        ranges = {"휘발유": (1200, 2500), "경유": (1000, 2300), "LPG": (700, 1500)}
        lo, hi = ranges[fuel]
        if not (lo <= val <= hi):
            print(f"  ⚠️ {fuel} 값 범위 이상: {val}원")
            return False
    return True


def scrape_opinet() -> dict:
    """오피넷 유가 스크래핑 메인 함수 (3단계 폴백)"""
    today = datetime.date.today().strftime("%Y-%m-%d")

    print("▶ 방법 1: XML API 시도...")
    result = method1_xml_api()
    if validate(result):
        print(f"  ✅ XML API 성공: {result}")
        return {**result, "updated": today, "source": "오피넷 XML API"}

    print("▶ 방법 2: 메인 페이지 스크래핑 시도...")
    result = {**result, **method2_main_scraping()}
    if validate(result):
        print(f"  ✅ 스크래핑 성공: {result}")
        return {**result, "updated": today, "source": "오피넷 스크래핑"}

    print("▶ 방법 3: AJAX 엔드포인트 시도...")
    result = {**result, **method3_ajax()}
    if validate(result):
        print(f"  ✅ AJAX 성공: {result}")
        return {**result, "updated": today, "source": "오피넷 AJAX"}

    # 부분 결과 + 폴백 병합
    for fuel, fallback_val in FALLBACK.items():
        if fuel not in result:
            result[fuel] = fallback_val
            print(f"  ⚠️ {fuel} 폴백 값 사용: {fallback_val}원")

    source = "오피넷 부분 스크래핑" if len([k for k in result if k in FALLBACK]) > 0 else "예비 데이터"
    print(f"  ⚠️ 최종 결과 (부분/폴백): {result}")
    return {**result, "updated": today, "source": source}


if __name__ == "__main__":
    print("=" * 50)
    print(f"오피넷 유가 스크래핑 시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    data = scrape_opinet()

    # fuel_prices.json 저장
    output_path = "fuel_prices.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 저장 완료: {output_path}")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # 실패 시 exit code 1 (GitHub Actions에서 알림)
    if data.get("source") == "예비 데이터":
        print("\n⚠️ 모든 스크래핑 방법 실패 — 예비 데이터 사용")
        sys.exit(0)  # 0으로 유지 (실패해도 파일은 저장)
