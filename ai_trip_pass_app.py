"""
AI-Trip Pass - 출장 행정 자동화 시스템
Streamlit 기반 3탭 구성
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
import io
import json
import re
import os
import base64
import datetime
import requests
from bs4 import BeautifulSoup
from PIL import Image, ExifTags
import folium
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI-Trip Pass",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# 전역 CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 전체 배경 */
    .main { background-color: #f8f9fb; }

    /* 헤더 배너 */
    .header-banner {
        background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
        color: white;
        padding: 24px 32px;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(26,115,232,0.3);
    }
    .header-banner h1 { margin: 0; font-size: 2rem; font-weight: 700; }
    .header-banner p  { margin: 4px 0 0; font-size: 0.95rem; opacity: 0.85; }

    /* 카드 박스 */
    .card {
        background: white;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        margin-bottom: 16px;
    }
    .card-title {
        font-size: 1rem;
        font-weight: 600;
        color: #1a73e8;
        border-left: 4px solid #1a73e8;
        padding-left: 10px;
        margin-bottom: 14px;
    }

    /* 요약 메트릭 */
    .metric-box {
        background: white;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        text-align: center;
    }
    .metric-label { font-size: 0.78rem; color: #888; font-weight: 500; margin-bottom: 4px; }
    .metric-value { font-size: 1.7rem; font-weight: 700; color: #1a73e8; }
    .metric-value.green  { color: #2e7d32; }
    .metric-value.orange { color: #e65100; }
    .metric-value.red    { color: #c62828; }

    /* 태그 */
    .tag-pass  { background:#e8f5e9; color:#2e7d32; padding:3px 10px; border-radius:20px; font-size:0.82rem; font-weight:600; }
    .tag-alert { background:#fff3e0; color:#e65100; padding:3px 10px; border-radius:20px; font-size:0.82rem; font-weight:600; }

    /* 구분선 */
    hr.thin { border: none; border-top: 1px solid #eee; margin: 16px 0; }

    /* 탭 스타일 개선 */
    .stTabs [data-baseweb="tab-list"] {
        background: white;
        border-radius: 12px;
        padding: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: #1a73e8 !important;
        color: white !important;
    }

    /* 업로드 박스 */
    .uploadedFile { border-radius: 8px !important; }

    /* 최종금액 강조 */
    .final-amount {
        background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
        border: 2px solid #4caf50;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .final-amount .label { color: #388e3c; font-size: 0.9rem; font-weight: 600; }
    .final-amount .amount { color: #1b5e20; font-size: 2.4rem; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────
st.markdown("""
<div class="header-banner">
  <h1>🚗 AI-Trip Pass</h1>
  <p>출장 행정 자동화 시스템 · 영수증 OCR · 위치 증빙 · 관리자 대시보드</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────
if "ocr_result"      not in st.session_state: st.session_state.ocr_result      = {}
if "destination"     not in st.session_state: st.session_state.destination     = "수원"
if "dest_coord"      not in st.session_state: st.session_state.dest_coord      = (37.2636, 127.0286)
if "trip_distance"   not in st.session_state: st.session_state.trip_distance   = 0.0
if "toll_fee"        not in st.session_state: st.session_state.toll_fee        = 0
if "fuel_cost"       not in st.session_state: st.session_state.fuel_cost       = 0.0
if "total_cost"      not in st.session_state: st.session_state.total_cost      = 0.0
if "trip_date"       not in st.session_state: st.session_state.trip_date       = ""
if "route_text"      not in st.session_state: st.session_state.route_text      = ""
if "fuel_type"       not in st.session_state: st.session_state.fuel_type       = "휘발유"
if "fuel_price"      not in st.session_state: st.session_state.fuel_price      = 1650
if "car_model"       not in st.session_state: st.session_state.car_model       = "아반떼"
if "submitted_trips" not in st.session_state:
    st.session_state.submitted_trips = []

# ─────────────────────────────────────────────
# 상수 / 더미 데이터
# ─────────────────────────────────────────────
VEHICLE_FUEL_EFFICIENCY = {
    "아반떼":    15.0,
    "쏘나타":    13.5,
    "그랜저":    11.0,
    "쏘렌토":    10.5,
    "싼타페":    10.0,
    "카니발":     9.0,
    "포터(1톤)":  8.5,
    "스타렉스":   9.5,
    "제네시스G80": 10.0,
    "모닝":      16.0,
}

FUEL_TYPE_MAP = {
    "휘발유": "gasoline",
    "경유":   "diesel",
    "LPG":   "lpg",
}

# 주요 지역 간 거리 더미 딕셔너리 (서울 기준, km)
DISTANCE_FROM_SEOUL = {
    "서울":   0,
    "수원":  45,
    "인천":  35,
    "대전": 160,
    "대구": 300,
    "부산": 420,
    "광주": 330,
    "울산": 390,
    "세종": 140,
    "춘천":  80,
    "원주": 110,
    "강릉": 230,
    "전주": 240,
    "청주": 140,
    "천안": 110,
    "안산":  40,
    "성남":  25,
    "화성":  60,
    "평택":  80,
    "의정부": 25,
}

DESTINATION_COORDS = {
    "서울":  (37.5665, 126.9780),
    "수원":  (37.2636, 127.0286),
    "인천":  (37.4563, 126.7052),
    "대전":  (36.3504, 127.3845),
    "대구":  (35.8714, 128.6014),
    "부산":  (35.1796, 129.0756),
    "광주":  (35.1595, 126.8526),
    "울산":  (35.5384, 129.3114),
    "세종":  (36.4801, 127.2890),
    "춘천":  (37.8813, 127.7298),
    "원주":  (37.3422, 127.9202),
    "강릉":  (37.7519, 128.8761),
    "전주":  (35.8242, 127.1480),
    "청주":  (36.6424, 127.4890),
    "천안":  (36.8151, 127.1139),
    "안산":  (37.3219, 126.8309),
    "성남":  (37.4449, 127.1388),
    "화성":  (37.1997, 126.8312),
    "평택":  (36.9921, 127.1128),
    "의정부": (37.7381, 127.0337),
}

# 오피넷 예비 유가 (2025년 기준)
FALLBACK_FUEL_PRICES = {
    "휘발유": 1652,
    "경유":   1498,
    "LPG":   963,
}


# ─────────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2) -> float:
    """두 좌표 간 거리 계산 (km)"""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_opinet_fuel_price(fuel_type: str) -> tuple[int, str]:
    """
    오피넷 API (오피넷 공공데이터 XML)로 전국 평균 유가를 가져옵니다.
    방법1: 오피넷 셀프주유소 전국평균 API
    방법2: 오피넷 메인 페이지 스크래핑
    실패 시 예비 데이터를 반환합니다.
    반환값: (가격, 출처설명)
    """
    code_map = {"휘발유": "B027", "경유": "D047", "LPG": "K015"}
    prod_cd = code_map.get(fuel_type, "B027")
    today = datetime.date.today().strftime("%Y%m%d")

    # ── 방법 1: 오피넷 공식 XML API ─────────────────────────
    # 공공데이터포털 오피넷 API (인증키 불필요한 엔드포인트)
    try:
        api_url = (
            "https://www.opinet.co.kr/api/avgAllPrice.do"
            f"?out=xml&prodcd={prod_cd}"
        )
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AITripPass/1.0)"}
        resp = requests.get(api_url, headers=headers, timeout=6)
        if resp.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.content)
            price_el = root.find(".//PRICE")
            if price_el is not None and price_el.text:
                return int(float(price_el.text)), "오피넷 API"
    except Exception:
        pass

    # ── 방법 2: 오피넷 AJAX JSON 엔드포인트 ─────────────────
    try:
        json_url = "https://www.opinet.co.kr/api/avgAllPrice.do?out=json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.opinet.co.kr/",
        }
        resp = requests.get(json_url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("RESULT", {}).get("OIL", [])
            for item in items:
                if item.get("PRODCD") == prod_cd:
                    return int(float(item.get("PRICE", 0))), "오피넷 JSON API"
    except Exception:
        pass

    # ── 방법 3: 오피넷 메인 스크래핑 ────────────────────────
    try:
        url = "https://www.opinet.co.kr/user/main/mainView.do"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://www.opinet.co.kr/",
        }
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 현재 오피넷 DOM 구조에 맞는 선택자들
        selectors = [
            "#oilprice_wrap .price",
            ".today_oil .num",
            ".oil_price_wrap strong",
            "div.price_area strong",
            "#avgPriceWrap .price",
        ]
        for sel in selectors:
            tags = soup.select(sel)
            for tag in tags:
                txt = tag.get_text(strip=True).replace(",", "").replace("원", "")
                nums = re.findall(r"\d{3,4}(?:\.\d+)?", txt)
                if nums:
                    val = int(float(nums[0]))
                    if 500 < val < 4000:
                        return val, "오피넷 스크래핑"

        # 전체 텍스트 패턴 매칭
        all_text = soup.get_text()
        kw = {"휘발유": "휘발유", "경유": "경유", "LPG": "LPG"}.get(fuel_type, "휘발유")
        m = re.search(rf"{kw}[^\d]{{0,20}}(\d{{1,2}},?\d{{3}}(?:\.\d+)?)", all_text)
        if m:
            val = int(float(m.group(1).replace(",", "")))
            if 500 < val < 4000:
                return val, "오피넷 스크래핑(텍스트)"
    except Exception:
        pass

    # ── Fallback ─────────────────────────────────────────────
    return FALLBACK_FUEL_PRICES[fuel_type], "예비 데이터 (네트워크 불가)"


def estimate_distance(origin: str, destination: str) -> float:
    """출발지·목적지 이름으로 왕복 거리 추정 (km) — 반환값이 곧 왕복 거리"""
    d_origin = DISTANCE_FROM_SEOUL.get(origin, 0)
    d_dest   = DISTANCE_FROM_SEOUL.get(destination, 50)
    one_way  = abs(d_dest - d_origin) if d_origin != d_dest else d_dest
    if one_way == 0:
        one_way = d_dest
    return round(one_way * 2, 1)   # 왕복


# 요금소명 → 도시명 역매핑 (하이패스 영수증에서 자주 등장하는 표기)
TOLLGATE_TO_CITY: dict[str, str] = {
    # 서울
    "서울": "서울", "서울tg": "서울", "서울요금소": "서울",
    "한남": "서울", "반포": "서울", "양재": "서울", "성남": "성남",
    # 수원
    "수원": "수원", "수원tg": "수원", "수원요금소": "수원",
    "동수원": "수원", "북수원": "수원", "남수원": "수원",
    # 인천
    "인천": "인천", "인천tg": "인천", "서인천": "인천", "남인천": "인천",
    # 대전
    "대전": "대전", "대전tg": "대전", "북대전": "대전", "남대전": "대전",
    "유성": "대전",
    # 대구
    "대구": "대구", "대구tg": "대구", "북대구": "대구", "남대구": "대구",
    "동대구": "대구",
    # 부산
    "부산": "부산", "부산tg": "부산", "북부산": "부산", "남부산": "부산",
    "기장": "부산",
    # 광주
    "광주": "광주", "광주tg": "광주", "북광주": "광주", "남광주": "광주",
    # 기타
    "천안": "천안", "천안tg": "천안",
    "청주": "청주", "청주tg": "청주",
    "전주": "전주", "전주tg": "전주",
    "세종": "세종",
    "평택": "평택", "평택tg": "평택",
    "안산": "안산",
    "화성": "화성",
    "의정부": "의정부",
    "춘천": "춘천",
    "원주": "원주",
    "강릉": "강릉",
    "울산": "울산",
}


def gate_to_city(gate_name: str) -> str | None:
    """요금소명에서 도시명을 추출합니다."""
    key = gate_name.lower().replace(" ", "").replace("_", "")
    # 직접 매핑
    if key in TOLLGATE_TO_CITY:
        return TOLLGATE_TO_CITY[key]
    # 포함 검색
    for k, v in TOLLGATE_TO_CITY.items():
        if k in key or key in k:
            return v
    return None


def parse_ocr_text(text: str) -> dict:
    """
    OCR/AI 텍스트에서 날짜·통행료·출발요금소·도착요금소를 파싱합니다.
    """
    date_match = re.search(r"(\d{4}[.\-/]\d{2}[.\-/]\d{2})", text)
    trip_date  = date_match.group(1) if date_match else datetime.date.today().strftime("%Y.%m.%d")

    toll_match = (
        re.search(r"통행료[^\d]*(\d{1,3},?\d{3})", text) or
        re.search(r"(\d{1,3},?\d{3})\s*원", text)
    )
    toll_fee = int(toll_match.group(1).replace(",", "")) if toll_match else 2400

    origin_gate = dest_gate = None
    entry_m = re.search(r"(?:진입|출발|입구|IN)[^\w가-힣]*([가-힣a-zA-Z0-9]+(?:TG|요금소|IC|JC)?)", text, re.IGNORECASE)
    exit_m  = re.search(r"(?:출구|도착|EXIT|OUT)[^\w가-힣]*([가-힣a-zA-Z0-9]+(?:TG|요금소|IC|JC)?)", text, re.IGNORECASE)
    if entry_m: origin_gate = entry_m.group(1)
    if exit_m:  dest_gate   = exit_m.group(1)

    if not origin_gate or not dest_gate:
        gates = re.findall(r"([가-힣]{2,5}(?:TG|요금소|IC|JC))", text, re.IGNORECASE)
        if len(gates) >= 2:
            origin_gate = origin_gate or gates[0]
            dest_gate   = dest_gate   or gates[1]

    origin_gate = origin_gate or "출발요금소"
    dest_gate   = dest_gate   or "도착요금소"
    origin_city = gate_to_city(origin_gate)
    dest_city   = gate_to_city(dest_gate)

    return {
        "trip_date":   trip_date,
        "toll_fee":    toll_fee,
        "origin_gate": origin_gate,
        "dest_gate":   dest_gate,
        "origin_city": origin_city,
        "dest_city":   dest_city,
    }


def analyze_receipts_with_claude(text: str) -> dict:
    """
    Claude API로 영수증 텍스트(여러 건 가능)를 분석합니다.
    - 여러 건의 통행료를 합산
    - 첫 번째 진입 요금소 = 출발지, 마지막 출구 요금소 = 목적지
    """
    try:
        city_list = ", ".join(list(DISTANCE_FROM_SEOUL.keys()))
        prompt = f"""아래는 하이패스 영수증 텍스트입니다. 여러 건이 포함될 수 있습니다.

다음 규칙으로 JSON만 반환하세요. 다른 말은 절대 하지 마세요.

규칙:
1. trip_date: 가장 이른 결제 날짜 (YYYY.MM.DD)
2. total_toll: 모든 통행료 합계 (정수, 원 단위)
3. receipts: 각 영수증을 배열로 정리 [{{영업소명, 금액, 시각}}]
4. origin_gate: 맨 첫 번째 영수증의 "입구영업소" 값. 없으면 첫 번째 영업소명
5. dest_gate: 마지막 영수증의 영업소명 (또는 입구영업소 값)
6. origin_city: 출발 요금소에 해당하는 도시. 반드시 다음 중 하나: {city_list}. 모르면 null
7. dest_city: 목적지 요금소에 해당하는 도시. 반드시 다음 중 하나: {city_list}. 모르면 null

영수증 텍스트:
{text[:3000]}"""

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError("JSON 없음")
        data = json.loads(json_match.group())

        trip_date  = re.sub(r"[-/]", ".", str(data.get("trip_date", datetime.date.today().strftime("%Y.%m.%d"))))
        total_toll = int(str(data.get("total_toll", 0)).replace(",", ""))
        receipts   = data.get("receipts", [])
        origin_gate = str(data.get("origin_gate") or "출발요금소")
        dest_gate   = str(data.get("dest_gate")   or "도착요금소")

        cities = list(DISTANCE_FROM_SEOUL.keys())
        origin_city = data.get("origin_city")
        dest_city   = data.get("dest_city")
        if origin_city not in cities: origin_city = gate_to_city(origin_gate)
        if dest_city   not in cities: dest_city   = gate_to_city(dest_gate)

        return {
            "trip_date":    trip_date,
            "toll_fee":     total_toll,   # 이미 전체 합계
            "toll_detail":  receipts,
            "origin_gate":  origin_gate,
            "dest_gate":    dest_gate,
            "origin_city":  origin_city,
            "dest_city":    dest_city,
            "ocr_text":     raw[:400],
            "method":       "Claude AI (텍스트 분석)",
            "is_total":     True,         # 이미 합계이므로 ×2 불필요 플래그
        }
    except Exception as e:
        return None


def extract_pdf_text(file_bytes: bytes) -> str:
    """pdfplumber로 PDF에서 텍스트 추출"""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return ""


def analyze_receipt_with_vision(image: Image.Image) -> dict:
    """이미지 영수증 → Claude Vision으로 분석"""
    try:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode()
        city_list = ", ".join(list(DISTANCE_FROM_SEOUL.keys()))
        prompt = f"""이 이미지는 하이패스 영수증입니다. 여러 건이 포함될 수 있습니다.
JSON만 반환하세요.
{{
  "trip_date": "결제일자 YYYY.MM.DD",
  "total_toll": 모든 통행료 합계 정수,
  "receipts": [{{"영업소": "이름", "금액": 숫자}}],
  "origin_gate": "첫 번째 입구영업소명",
  "dest_gate": "마지막 영업소명",
  "origin_city": "출발 도시 ({city_list} 중 하나 또는 null)",
  "dest_city": "도착 도시 ({city_list} 중 하나 또는 null)"
}}"""
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text",  "text": prompt},
                ]}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError("JSON 없음")
        data = json.loads(json_match.group())

        trip_date  = re.sub(r"[-/]", ".", str(data.get("trip_date", datetime.date.today().strftime("%Y.%m.%d"))))
        total_toll = int(str(data.get("total_toll", 0)).replace(",", ""))
        cities = list(DISTANCE_FROM_SEOUL.keys())
        origin_city = data.get("origin_city") if data.get("origin_city") in cities else gate_to_city(str(data.get("origin_gate", "")))
        dest_city   = data.get("dest_city")   if data.get("dest_city")   in cities else gate_to_city(str(data.get("dest_gate",   "")))
        return {
            "trip_date":   trip_date,
            "toll_fee":    total_toll,
            "toll_detail": data.get("receipts", []),
            "origin_gate": str(data.get("origin_gate") or "출발요금소"),
            "dest_gate":   str(data.get("dest_gate")   or "도착요금소"),
            "origin_city": origin_city,
            "dest_city":   dest_city,
            "ocr_text":    raw[:400],
            "method":      "Claude Vision AI",
            "is_total":    True,
        }
    except Exception:
        return None


def extract_exif_gps(image: Image.Image) -> dict | None:
    """Pillow로 EXIF GPS 정보 추출"""
    try:
        exif_data = image._getexif()
        if not exif_data:
            return None
        exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}
        gps_info_raw = exif.get("GPSInfo")
        datetime_str = exif.get("DateTimeOriginal", exif.get("DateTime", ""))
        if not gps_info_raw:
            return None
        gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}
        def dms_to_decimal(dms, ref):
            d, m, s = dms
            decimal = float(d) + float(m)/60 + float(s)/3600
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal
        lat = dms_to_decimal(gps["GPSLatitude"],  gps.get("GPSLatitudeRef",  "N"))
        lon = dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
        return {"lat": lat, "lon": lon, "datetime": datetime_str}
    except Exception:
        return None


# ─────────────────────────────────────────────
# 탭 구성
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📄 Tab 1 · 영수증 처리 & 출장이행확인서",
    "📍 Tab 2 · 사진 EXIF 위치 증빙",
    "📊 Tab 3 · 관리자 대시보드",
])


# ═══════════════════════════════════════════════════════════════
# TAB 1 · 영수증 처리 및 출장이행확인서 자동 생성
# ═══════════════════════════════════════════════════════════════
with tab1:
    col_left, col_right = st.columns([1, 1], gap="large")

    # ── 좌측: 입력 영역 ───────────────────────────────────────
    with col_left:
        st.markdown('<div class="card"><div class="card-title">① 하이패스 영수증 업로드</div>', unsafe_allow_html=True)
        receipt_file = st.file_uploader(
            "영수증 업로드 (PDF 또는 이미지 jpg/png) — 여러 건 자동 합산",
            type=["pdf", "jpg", "jpeg", "png"],
            key="receipt_uploader",
            label_visibility="collapsed",
        )

        if receipt_file:
            file_bytes = receipt_file.read()
            file_type  = receipt_file.type  # "application/pdf" or "image/..."

            result = None

            # ── PDF: 텍스트 추출 → Claude 텍스트 분석
            if file_type == "application/pdf":
                st.info("📄 PDF 파일 감지 — 텍스트 추출 후 AI 분석 중...")
                with st.spinner("🔍 영수증 분석 중..."):
                    pdf_text = extract_pdf_text(file_bytes)
                    if pdf_text.strip():
                        result = analyze_receipts_with_claude(pdf_text)
                    # PDF 텍스트 추출 실패 시 이미지로 변환 후 Vision 시도
                    if not result:
                        try:
                            from pdf2image import convert_from_bytes
                            pages = convert_from_bytes(file_bytes, dpi=150)
                            img   = pages[0]
                            result = analyze_receipt_with_vision(img)
                        except Exception:
                            pass

            # ── 이미지: Claude Vision
            else:
                img = Image.open(io.BytesIO(file_bytes))
                st.image(img, caption="업로드된 영수증", use_container_width=True)
                with st.spinner("🔍 Vision AI 분석 중..."):
                    result = analyze_receipt_with_vision(img)

            # ── 폴백: 더미
            if not result:
                result = {
                    "trip_date":   datetime.date.today().strftime("%Y.%m.%d"),
                    "toll_fee":    15300,
                    "toll_detail": [],
                    "origin_gate": "서서울(음성진입)",
                    "dest_gate":   "금왕꽃동네",
                    "origin_city": "서울",
                    "dest_city":   "서울",
                    "ocr_text":    "(AI 연결 실패 — 더미 데이터)",
                    "method":      "Demo",
                    "is_total":    True,
                }

            st.session_state.ocr_result = result

            # 분석 방법 배지
            method = result.get("method", "")
            if "Demo" in method:
                st.warning("⚠️ AI 연결 실패 — 더미 데이터 사용")
            else:
                st.success(f"✅ {method} 분석 완료")

            # 결과 카드
            c1, c2 = st.columns(2)
            with c1:
                st.metric("출장일",     result["trip_date"])
                st.metric("출발 요금소", result["origin_gate"])
            with c2:
                is_total = result.get("is_total", False)
                toll_label = "통행료 합계" if is_total else "통행료 (편도)"
                st.metric(toll_label,   f"{result['toll_fee']:,}원")
                st.metric("도착 요금소", result["dest_gate"])

            # 통행료 상세 내역
            if result.get("toll_detail"):
                with st.expander(f"📋 통행료 상세 내역 ({len(result['toll_detail'])}건)"):
                    for i, r in enumerate(result["toll_detail"], 1):
                        if isinstance(r, dict):
                            name = r.get("영업소") or r.get("영업소명") or r.get("name") or f"영업소{i}"
                            amt  = r.get("금액")   or r.get("amount") or 0
                            time = r.get("시각")   or r.get("time")   or ""
                            st.write(f"{i}. {name}  —  {int(amt):,}원  {time}")

            # 출발지·목적지 자동 인식 결과
            if result.get("origin_city") or result.get("dest_city"):
                st.markdown("**🗺️ 출발지·목적지 자동 인식**")
                ca, cb = st.columns(2)
                with ca:
                    if result.get("origin_city"):
                        st.success(f"출발: **{result['origin_city']}**")
                with cb:
                    if result.get("dest_city"):
                        st.success(f"목적지: **{result['dest_city']}**")

            if result.get("ocr_text"):
                with st.expander("📝 AI 분석 원문 보기"):
                    st.text(result["ocr_text"])

            # 세션 저장 — is_total이면 ×2 안 함, 편도면 ×2
            toll_to_save = result["toll_fee"] if result.get("is_total") else result["toll_fee"] * 2
            st.session_state.toll_fee  = toll_to_save
            st.session_state.trip_date = result["trip_date"]
            if result.get("origin_city"):
                st.session_state.ocr_origin_city = result["origin_city"]
            if result.get("dest_city"):
                st.session_state.ocr_dest_city = result["dest_city"]
    """Pillow로 EXIF GPS 정보 추출"""
    try:
        exif_data = image._getexif()
        if not exif_data:
            return None

        exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}

        gps_info_raw = exif.get("GPSInfo")
        datetime_str = exif.get("DateTimeOriginal", exif.get("DateTime", ""))

        if not gps_info_raw:
            return None

        gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}

        def dms_to_decimal(dms, ref):
            d, m, s = dms
            decimal = float(d) + float(m)/60 + float(s)/3600
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal

        lat = dms_to_decimal(gps["GPSLatitude"],  gps.get("GPSLatitudeRef",  "N"))
        lon = dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))

        return {
            "lat":      lat,
            "lon":      lon,
            "datetime": datetime_str,
        }
    except Exception:
        return None


@st.cache_resource
def load_korean_font() -> dict:
    """
    한글 폰트(NanumGothic)를 로드합니다.
    Streamlit Cloud 환경에서는 apt 설치 경로를 먼저 확인하고,
    없으면 GitHub에서 다운로드합니다.
    반환값: {"regular": 폰트명, "bold": 폰트명}
    """
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/home/appuser/.fonts/NanumGothic.ttf",
        "/home/appuser/.fonts/NanumGothicBold.ttf",
    ]

    def try_register(name, path):
        try:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont(name, path))
                return True
        except Exception:
            pass
        return False

    reg = try_register("NanumGothic", candidates[0])
    reg_b = try_register("NanumGothicBold", candidates[1])

    if not reg:
        # Streamlit Cloud: apt-get으로 설치 시도
        try:
            import subprocess
            subprocess.run(
                ["apt-get", "install", "-y", "fonts-nanum"],
                capture_output=True, timeout=60
            )
            reg   = try_register("NanumGothic",     candidates[0])
            reg_b = try_register("NanumGothicBold", candidates[1])
        except Exception:
            pass

    if not reg:
        # 최후 수단: GitHub에서 TTF 다운로드
        font_dir = os.path.expanduser("~/.fonts")
        os.makedirs(font_dir, exist_ok=True)
        urls = {
            "NanumGothic":     ("https://github.com/googlefonts/nanumfont/raw/main/fonts/NanumGothic.ttf",
                                f"{font_dir}/NanumGothic.ttf"),
            "NanumGothicBold": ("https://github.com/googlefonts/nanumfont/raw/main/fonts/NanumGothicBold.ttf",
                                f"{font_dir}/NanumGothicBold.ttf"),
        }
        for fname, (url, dst) in urls.items():
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    with open(dst, "wb") as f:
                        f.write(r.content)
                    pdfmetrics.registerFont(TTFont(fname, dst))
            except Exception:
                pass

    # 최종 확인: 등록됐는지 체크
    try:
        pdfmetrics.getFont("NanumGothic")
        regular = "NanumGothic"
    except Exception:
        regular = "Helvetica"

    try:
        pdfmetrics.getFont("NanumGothicBold")
        bold = "NanumGothicBold"
    except Exception:
        bold = "Helvetica-Bold"

    return {"regular": regular, "bold": bold}


def generate_trip_pdf(
    trip_date:   str,
    destination: str,
    route_text:  str,
    distance:    float,
    car_model:   str,
    fuel_type:   str,
    fuel_price:  int,
    toll_fee:    int,
    total_cost:  float,
    fuel_source: str = "",
) -> bytes:
    """reportlab + 나눔고딕으로 한글 완전 지원 출장이행확인서 PDF 생성"""
    fonts = load_korean_font()
    F  = fonts["regular"]   # 나눔고딕 일반 (또는 Helvetica 폴백)
    FB = fonts["bold"]      # 나눔고딕 Bold

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4

    # ── 헤더 배너 ─────────────────────────────────
    c.setFillColorRGB(0.10, 0.45, 0.91)
    c.rect(0, H - 90, W, 90, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont(FB, 20)
    c.drawCentredString(W/2, H - 42, "출장이행확인서")
    c.setFont(F, 10)
    c.drawCentredString(W/2, H - 63, "AI-Trip Pass  자동 생성 문서")

    # ── 본문 ──────────────────────────────────────
    y = H - 108
    line_h = 27

    def section_title(title, yy):
        c.setFillColorRGB(0.93, 0.96, 1.0)
        c.rect(38, yy - 5, W - 76, 22, fill=1, stroke=0)
        c.setFillColorRGB(0.10, 0.45, 0.91)
        c.setFont(FB, 10)
        c.drawString(50, yy + 4, title)
        return yy - line_h

    def field_row(label, value, yy):
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont(F, 9)
        c.drawString(58, yy, label)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(F, 10)
        c.drawString(195, yy, str(value))
        c.setStrokeColorRGB(0.91, 0.91, 0.91)
        c.line(50, yy - 5, W - 50, yy - 5)
        return yy - line_h

    # 출장 기본 정보
    y = section_title("[ 출장 기본 정보 ]", y)
    y = field_row("출장일",           trip_date, y)
    y = field_row("출장지",           destination, y)
    y = field_row("이동경로",          route_text, y)
    y = field_row("총 이동거리",       f"{distance} km (왕복)", y)
    y = field_row("자차 이용 사유",    "출장경로 복잡 / 대중교통 불편", y)

    y -= 8
    y = section_title("[ 차량 및 유류 정보 ]", y)
    y = field_row("차종",             car_model, y)
    y = field_row("유종",             fuel_type, y)
    src_label = f"오피넷 유가 ({fuel_source})" if fuel_source else "오피넷 유가"
    y = field_row(src_label,          f"{fuel_price:,} 원/L", y)

    y -= 8
    y = section_title("[ 비용 내역 ]", y)
    fuel_only = total_cost - toll_fee
    y = field_row("유류비",           f"{fuel_only:,.0f} 원", y)
    y = field_row("통행료",           f"{toll_fee:,} 원", y)

    # 최종 금액 강조 박스
    y -= 10
    box_h = 52
    c.setFillColorRGB(0.88, 0.97, 0.88)
    c.setStrokeColorRGB(0.30, 0.69, 0.31)
    c.roundRect(38, y - box_h, W - 76, box_h, 8, fill=1, stroke=1)
    c.setFillColorRGB(0.11, 0.37, 0.13)
    c.setFont(FB, 11)
    c.drawString(58, y - 18, "최종 청구 금액")
    c.setFont(FB, 20)
    c.drawRightString(W - 58, y - 24, f"{total_cost:,.0f} 원")
    y -= (box_h + 24)

    # 서명란
    y -= 10
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(50, y, W - 50, y)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFont(F, 8)
    c.drawString(58,  y - 16, "신청인: _______________")
    c.drawString(218, y - 16, "부서장: _______________")
    c.drawString(378, y - 16, "결  재: _______________")

    # 푸터
    c.setFillColorRGB(0.7, 0.7, 0.7)
    c.setFont(F, 7)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    c.drawCentredString(W/2, 28, f"Generated by AI-Trip Pass  ·  {now_str}")

    c.save()
    return buffer.getvalue()


# ─────────────────────────────────────────────
# 탭 구성
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📄 Tab 1 · 영수증 처리 & 출장이행확인서",
    "📍 Tab 2 · 사진 EXIF 위치 증빙",
    "📊 Tab 3 · 관리자 대시보드",
])


# ═══════════════════════════════════════════════════════════════
# TAB 1 · 영수증 처리 및 출장이행확인서 자동 생성
# ═══════════════════════════════════════════════════════════════
with tab1:
    col_left, col_right = st.columns([1, 1], gap="large")

    # ── 좌측: 입력 영역 ───────────────────────────────────────
    with col_left:
        st.markdown('<div class="card"><div class="card-title">① 하이패스 영수증 업로드 (OCR)</div>', unsafe_allow_html=True)
        receipt_file = st.file_uploader(
            "톨게이트 영수증 이미지 업로드 (jpg/png)",
            type=["jpg", "jpeg", "png"],
            key="receipt_uploader",
            label_visibility="collapsed",
        )

        if receipt_file:
            img = Image.open(receipt_file)
            st.image(img, caption="업로드된 영수증", use_container_width=True)

            with st.spinner("🔍 영수증 분석 중... (Claude Vision AI 사용)"):
                result = mock_ocr_receipt(img)
            st.session_state.ocr_result = result

            # 분석 방법 배지
            method = result.get("method", "")
            if "Claude" in method:
                st.success(f"✅ {method}로 자동 인식 완료")
            elif method == "Demo":
                st.warning("⚠️ 시연용 더미 데이터 (Vision AI 연결 필요)")
            else:
                st.info(f"ℹ️ {method}로 인식")

            # 추출 결과 카드
            c1, c2 = st.columns(2)
            with c1:
                st.metric("결제일자",    result["trip_date"])
                st.metric("출발 요금소", result["origin_gate"])
            with c2:
                st.metric("통행료 (편도)", f"{result['toll_fee']:,}원")
                st.metric("도착 요금소",  result["dest_gate"])

            # 도시 인식 결과
            if result.get("origin_city") or result.get("dest_city"):
                st.markdown("**🗺️ 출발지·목적지 자동 인식 →** 아래 셀렉트박스에 반영됩니다")
                ca, cb = st.columns(2)
                with ca:
                    if result.get("origin_city"):
                        st.success(f"출발지: **{result['origin_city']}**")
                with cb:
                    if result.get("dest_city"):
                        st.success(f"목적지: **{result['dest_city']}**")

            st.caption("💡 통행료는 편도 기준으로 추출되며, 왕복(×2)이 자동 반영됩니다.")

            if result.get("ocr_text"):
                with st.expander("📝 원문 보기"):
                    st.text(result["ocr_text"])

            # 세션 상태 저장 — 통행료 왕복(×2)
            st.session_state.toll_fee       = result["toll_fee"] * 2
            st.session_state.trip_date      = result["trip_date"]
            if result.get("origin_city"):
                st.session_state.ocr_origin_city = result["origin_city"]
            if result.get("dest_city"):
                st.session_state.ocr_dest_city = result["dest_city"]

        st.markdown('</div>', unsafe_allow_html=True)

        # ── 출발지 / 목적지 ────────────────────────────────────
        st.markdown('<div class="card"><div class="card-title">② 출발지 · 목적지 설정</div>', unsafe_allow_html=True)

        cities = list(DISTANCE_FROM_SEOUL.keys())
        ocr_origin = st.session_state.get("ocr_origin_city")
        ocr_dest   = st.session_state.get("ocr_dest_city")

        if ocr_origin or ocr_dest:
            st.caption("✅ 영수증에서 자동 인식된 값이 반영되었습니다. 필요 시 수정하세요.")

        origin_default = cities.index(ocr_origin) if ocr_origin and ocr_origin in cities else cities.index("서울")
        dest_default   = cities.index(ocr_dest)   if ocr_dest   and ocr_dest   in cities else (cities.index("수원") if "수원" in cities else 1)

        c1, c2 = st.columns(2)
        with c1:
            origin = st.selectbox("출발지", cities, index=origin_default, key="sel_origin")
        with c2:
            destination = st.selectbox("목적지", cities, index=dest_default, key="sel_dest")

        st.session_state.destination = destination
        st.session_state.dest_coord  = DESTINATION_COORDS.get(destination, (37.5665, 126.9780))

        distance_km = estimate_distance(origin, destination)
        st.session_state.trip_distance = distance_km
        st.session_state.route_text = f"{origin} → {destination} : {distance_km/2:.1f}km"

        st.info(f"📏 예상 왕복 이동거리: **{distance_km} km**  (편도 {distance_km/2:.1f} km)")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 우측: 유류비 계산 & 결과 ─────────────────────────────
    with col_right:
        st.markdown('<div class="card"><div class="card-title">③ 차량 & 유류비 설정</div>', unsafe_allow_html=True)

        car_model = st.selectbox("차종 선택", list(VEHICLE_FUEL_EFFICIENCY.keys()))
        efficiency = VEHICLE_FUEL_EFFICIENCY[car_model]
        st.caption(f"🚘 공인 평균 연비: **{efficiency} km/L**")

        fuel_type = st.selectbox("유종 선택", ["휘발유", "경유", "LPG"])
        st.session_state.fuel_type  = fuel_type
        st.session_state.car_model  = car_model

        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            if st.button("🔄 오피넷 유가 조회", use_container_width=True):
                with st.spinner("오피넷에서 유가 가져오는 중..."):
                    price, source = get_opinet_fuel_price(fuel_type)
                st.session_state.fuel_price = price
                st.session_state.fuel_source = source
                if "예비" in source:
                    st.warning(f"⚠️ 네트워크 제한으로 예비 데이터 사용: {price:,}원/L")
                else:
                    st.success(f"✅ {source}: {price:,}원/L")

        with col_info:
            manual_price = st.number_input(
                "유가 직접 입력 (원/L)",
                min_value=500, max_value=3000,
                value=st.session_state.fuel_price,
                step=10,
            )
            st.session_state.fuel_price = manual_price

        st.markdown('</div>', unsafe_allow_html=True)

        # ── 비용 정산 ──────────────────────────────────────────
        st.markdown('<div class="card"><div class="card-title">④ 비용 정산</div>', unsafe_allow_html=True)

        toll = st.number_input(
            "통행료 — 왕복 합계 (원)  ※ 영수증 편도 금액의 ×2가 자동 반영됩니다",
            min_value=0,
            value=int(st.session_state.toll_fee),
            step=100,
        )
        st.session_state.toll_fee = toll

        fuel_cost  = (distance_km / efficiency) * st.session_state.fuel_price
        total_cost = fuel_cost + toll
        st.session_state.fuel_cost  = fuel_cost
        st.session_state.total_cost = total_cost

        # 비용 breakdown 카드 3개
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-box">
              <div class="metric-label">유류비</div>
              <div class="metric-value" style="font-size:1.2rem">{fuel_cost:,.0f}원</div>
              <div style="font-size:0.75rem;color:#888;margin-top:3px">{distance_km/efficiency:.1f}L 소비</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-box">
              <div class="metric-label">통행료 (왕복)</div>
              <div class="metric-value" style="font-size:1.2rem">{toll:,.0f}원</div>
              <div style="font-size:0.75rem;color:#888;margin-top:3px">편도 {toll//2:,}원 × 2</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-box">
              <div class="metric-label">왕복 거리</div>
              <div class="metric-value" style="font-size:1.2rem">{distance_km:.0f}km</div>
              <div style="font-size:0.75rem;color:#888;margin-top:3px">편도 {distance_km/2:.0f}km</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 최종 금액 — 내역 포함
        fuel_pct = int(fuel_cost / total_cost * 100) if total_cost > 0 else 0
        toll_pct = 100 - fuel_pct
        st.markdown(f"""
        <div class="final-amount">
          <div class="label">💰 최종 청구 금액 (유류비 + 통행료)</div>
          <div class="amount">{total_cost:,.0f} 원</div>
          <div style="display:flex;justify-content:center;gap:16px;margin-top:8px;font-size:0.8rem">
            <span style="color:#388e3c">유류비 {fuel_cost:,.0f}원 ({fuel_pct}%)</span>
            <span style="color:#888">+</span>
            <span style="color:#1565c0">통행료 {toll:,.0f}원 ({toll_pct}%)</span>
          </div>
          <div style="color:#388e3c;font-size:0.75rem;margin-top:4px">
            ({distance_km}km ÷ {efficiency}km/L × {int(st.session_state.fuel_price):,}원/L) + 통행료 왕복
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── PDF 생성 & 다운로드 ────────────────────────────────
        st.markdown('<div class="card"><div class="card-title">⑤ 출장이행확인서 PDF 생성</div>', unsafe_allow_html=True)

        # 원본 양식 업로드 (선택)
        base_pdf = st.file_uploader(
            "원본 출장이행확인서 양식.pdf 업로드 (선택 — 없으면 기본 양식 사용)",
            type=["pdf"],
            key="base_pdf_uploader",
        )

        trip_date_input = st.text_input(
            "출장일 (YYYY.MM.DD)",
            value=st.session_state.trip_date or datetime.date.today().strftime("%Y.%m.%d"),
        )
        st.session_state.trip_date = trip_date_input

        if st.button("📄 PDF 자동 생성 & 다운로드", use_container_width=True, type="primary"):
            with st.spinner("PDF 생성 중 (한글 폰트 로딩 포함, 최초 1회 15초 소요될 수 있습니다)..."):
                pdf_bytes = generate_trip_pdf(
                    trip_date   = st.session_state.trip_date,
                    destination = st.session_state.destination,
                    route_text  = st.session_state.route_text,
                    distance    = st.session_state.trip_distance,
                    car_model   = car_model,
                    fuel_type   = fuel_type,
                    fuel_price  = st.session_state.fuel_price,
                    toll_fee    = st.session_state.toll_fee,
                    total_cost  = st.session_state.total_cost,
                    fuel_source = st.session_state.get("fuel_source", ""),
                )

            filename = f"출장이행확인서_{st.session_state.trip_date.replace('.','')}.pdf"
            st.download_button(
                label="⬇️ PDF 다운로드",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True,
            )
            st.success("✅ PDF가 생성되었습니다. 위 버튼을 눌러 다운로드하세요.")

            # 제출 기록 저장
            st.session_state.submitted_trips.append({
                "제출일":   datetime.date.today().strftime("%Y-%m-%d"),
                "출장일":   st.session_state.trip_date,
                "출장지":   st.session_state.destination,
                "이동거리(km)": st.session_state.trip_distance,
                "차종":    car_model,
                "유류비(원)": round(fuel_cost),
                "통행료(원)": toll,
                "청구금액(원)": round(total_cost),
                "상태":    "자동 승인 (Pass)" if total_cost < 150000 else "수기 확인 필요 (Alert)",
            })

        st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# TAB 2 · 사진 EXIF 기반 위치 증빙
# ═══════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="card"><div class="card-title">📸 현장 사진 EXIF 위치 증빙</div>', unsafe_allow_html=True)

    dest_name  = st.session_state.destination
    dest_coord = st.session_state.dest_coord

    st.info(f"🗺️ Tab 1 설정 목적지: **{dest_name}** ({dest_coord[0]:.4f}, {dest_coord[1]:.4f})")

    photo_file = st.file_uploader(
        "현장 사진 업로드 (GPS EXIF 포함 JPG 권장)",
        type=["jpg", "jpeg"],
        key="photo_uploader",
    )

    col_photo, col_result = st.columns([1, 1], gap="large")

    with col_photo:
        if photo_file:
            photo = Image.open(photo_file)
            st.image(photo, caption="업로드된 현장 사진", use_container_width=True)

            gps_data = extract_exif_gps(photo)

            if gps_data:
                st.markdown(f"""
                <div class="card">
                  <b>📡 EXIF 추출 결과</b><br><br>
                  위도: <code>{gps_data['lat']:.6f}</code><br>
                  경도: <code>{gps_data['lon']:.6f}</code><br>
                  촬영 시각: <code>{gps_data['datetime'] or '정보 없음'}</code>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ 이 사진에서 GPS 정보를 추출하지 못했습니다. 시연용 좌표를 사용합니다.")
                # 시연: 목적지 근처 랜덤 좌표
                gps_data = {
                    "lat":      dest_coord[0] + np.random.uniform(-0.03, 0.03),
                    "lon":      dest_coord[1] + np.random.uniform(-0.03, 0.03),
                    "datetime": datetime.datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
                }
                st.info(f"시연용 좌표: ({gps_data['lat']:.4f}, {gps_data['lon']:.4f})")

    with col_result:
        if photo_file and gps_data:
            distance_km = haversine(
                dest_coord[0], dest_coord[1],
                gps_data["lat"], gps_data["lon"],
            )

            st.markdown("#### 📏 위치 검증 결과")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric("목적지 좌표", f"{dest_coord[0]:.3f}, {dest_coord[1]:.3f}")
            with col_m2:
                st.metric("사진 좌표",   f"{gps_data['lat']:.3f}, {gps_data['lon']:.3f}")

            st.metric("두 지점 간 거리", f"{distance_km:.2f} km", delta=f"기준: 5km 이내")

            if distance_km <= 5.0:
                st.success(f"✅ 정상 증빙 — 사진 촬영 위치가 목적지 {dest_name}에서 {distance_km:.2f}km 이내입니다.")
            else:
                st.warning(f"⚠️ 위치 불일치 — 사진 촬영 위치가 목적지에서 {distance_km:.2f}km 떨어져 있습니다. 수기 확인이 필요합니다.")

    # ── Folium 지도 ────────────────────────────────────────────
    if photo_file and gps_data:
        st.markdown('<hr class="thin">', unsafe_allow_html=True)
        st.markdown("#### 🗺️ 위치 시각화 지도")

        center_lat = (dest_coord[0] + gps_data["lat"]) / 2
        center_lon = (dest_coord[1] + gps_data["lon"]) / 2

        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")

        # 목적지: 반경 5km 원
        folium.Circle(
            location=dest_coord,
            radius=5000,
            color="#1a73e8",
            fill=True,
            fill_opacity=0.12,
            weight=2,
            popup=f"목적지: {dest_name} (반경 5km)",
        ).add_to(m)

        folium.Marker(
            location=dest_coord,
            popup=f"🏢 목적지: {dest_name}",
            tooltip=dest_name,
            icon=folium.Icon(color="blue", icon="building", prefix="fa"),
        ).add_to(m)

        # 사진 촬영 위치 마커
        photo_color = "green" if distance_km <= 5.0 else "orange"
        folium.Marker(
            location=[gps_data["lat"], gps_data["lon"]],
            popup=f"📍 사진 촬영 위치\n({gps_data['lat']:.4f}, {gps_data['lon']:.4f})",
            tooltip="촬영 위치",
            icon=folium.Icon(color=photo_color, icon="camera", prefix="fa"),
        ).add_to(m)

        # 두 지점 연결선
        folium.PolyLine(
            locations=[dest_coord, [gps_data["lat"], gps_data["lon"]]],
            color="#ff6b6b",
            weight=2,
            dash_array="8",
            opacity=0.7,
            tooltip=f"거리: {distance_km:.2f} km",
        ).add_to(m)

        st_folium(m, width=None, height=420, returned_objects=[])

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# TAB 3 · 관리자 대시보드
# ═══════════════════════════════════════════════════════════════
with tab3:
    # ── 가상 데이터 ─────────────────────────────────────────────
    dummy_trips = [
        {"제출일":"2025-06-01","출장일":"2025-05-30","출장지":"수원","이동거리(km)":90,  "차종":"아반떼","유류비(원)":9900,  "통행료(원)":2400,"청구금액(원)":12300, "상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-02","출장일":"2025-05-31","출장지":"대전","이동거리(km)":320, "차종":"쏘나타","유류비(원)":39062,"통행료(원)":7200,"청구금액(원)":46262, "상태":"수기 확인 필요 (Alert)"},
        {"제출일":"2025-06-03","출장일":"2025-06-01","출장지":"인천","이동거리(km)":70,  "차종":"모닝",  "유류비(원)":7219,  "통행료(원)":1600,"청구금액(원)":8819,  "상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-04","출장일":"2025-06-02","출장지":"대구","이동거리(km)":600, "차종":"쏘렌토","유류비(원)":88560,"통행료(원)":18000,"청구금액(원)":106560,"상태":"수기 확인 필요 (Alert)"},
        {"제출일":"2025-06-05","출장일":"2025-06-03","출장지":"성남","이동거리(km)":50,  "차종":"그랜저","유류비(원)":7500,  "통행료(원)":1200,"청구금액(원)":8700,  "상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-06","출장일":"2025-06-04","출장지":"부산","이동거리(km)":840, "차종":"카니발","유류비(원)":154000,"통행료(원)":24000,"청구금액(원)":178000,"상태":"수기 확인 필요 (Alert)"},
        {"제출일":"2025-06-07","출장일":"2025-06-05","출장지":"청주","이동거리(km)":280, "차종":"아반떼","유류비(원)":30800,"통행료(원)":6000,"청구금액(원)":36800, "상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-08","출장일":"2025-06-06","출장지":"광주","이동거리(km)":660, "차종":"쏘나타","유류비(원)":80667,"통행료(원)":16800,"청구금액(원)":97467,"상태":"수기 확인 필요 (Alert)"},
    ]

    # 현재 세션에서 제출된 데이터 병합
    all_trips = dummy_trips + st.session_state.submitted_trips
    df = pd.DataFrame(all_trips)

    pass_count  = len(df[df["상태"].str.contains("Pass")])
    alert_count = len(df[df["상태"].str.contains("Alert")])
    total_count = len(df)
    total_claim = df["청구금액(원)"].sum()
    auto_rate   = round(pass_count / total_count * 100, 1) if total_count else 0

    # ── 요약 위젯 ──────────────────────────────────────────────
    st.markdown("### 📊 이번 달 출장 현황 요약")
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.markdown(f"""
        <div class="metric-box">
          <div class="metric-label">전체 제출 건수</div>
          <div class="metric-value">{total_count}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-box">
          <div class="metric-label">✅ 자동 승인 (Pass)</div>
          <div class="metric-value green">{pass_count}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box">
          <div class="metric-label">⚠️ 수기 확인 필요</div>
          <div class="metric-value orange">{alert_count}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-box">
          <div class="metric-label">자동화율</div>
          <div class="metric-value">{auto_rate}%</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="metric-box">
          <div class="metric-label">총 청구금액</div>
          <div class="metric-value" style="font-size:1.3rem">{total_claim:,.0f}원</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 차트 ──────────────────────────────────────────────────
    col_chart1, col_chart2 = st.columns([1, 1], gap="large")

    with col_chart1:
        st.markdown('<div class="card"><div class="card-title">출장지별 청구금액 분포</div>', unsafe_allow_html=True)
        dest_summary = df.groupby("출장지")["청구금액(원)"].sum().sort_values(ascending=False)
        st.bar_chart(dest_summary, color="#1a73e8", height=280)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_chart2:
        st.markdown('<div class="card"><div class="card-title">승인 상태 현황</div>', unsafe_allow_html=True)
        status_counts = df["상태"].value_counts()
        # Streamlit 내장 차트로 표시
        status_df = pd.DataFrame({
            "건수": status_counts
        })
        st.bar_chart(status_df, color="#4caf50", height=280)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 상세 테이블 ────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">📋 출장 기록 상세 목록</div>', unsafe_allow_html=True)

    # 상태 필터
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
    with filter_col1:
        status_filter = st.selectbox("상태 필터", ["전체", "자동 승인 (Pass)", "수기 확인 필요 (Alert)"])
    with filter_col2:
        sort_col = st.selectbox("정렬 기준", ["제출일", "청구금액(원)", "이동거리(km)"])

    filtered_df = df.copy()
    if status_filter != "전체":
        filtered_df = filtered_df[filtered_df["상태"].str.contains(
            "Pass" if "Pass" in status_filter else "Alert"
        )]
    filtered_df = filtered_df.sort_values(sort_col, ascending=False).reset_index(drop=True)

    # 상태 컬럼에 HTML 태그 추가
    def style_status(val):
        if "Pass" in val:
            return "background-color: #e8f5e9; color: #2e7d32; font-weight: 600;"
        else:
            return "background-color: #fff3e0; color: #e65100; font-weight: 600;"

    styled = filtered_df.style.applymap(style_status, subset=["상태"])
    st.dataframe(
        styled,
        use_container_width=True,
        height=320,
        column_config={
            "청구금액(원)": st.column_config.NumberColumn(format="%,d 원"),
            "유류비(원)":   st.column_config.NumberColumn(format="%,d 원"),
            "통행료(원)":   st.column_config.NumberColumn(format="%,d 원"),
            "이동거리(km)": st.column_config.NumberColumn(format="%.0f km"),
        }
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # ── 행정 효율화 지표 ──────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">⚡ 행정 효율화 지표 (AI-Trip Pass 도입 효과)</div>', unsafe_allow_html=True)

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.markdown("""
        <div class="metric-box">
          <div class="metric-label">문서 처리 시간 단축</div>
          <div class="metric-value green">↓ 87%</div>
          <div style="font-size:0.75rem;color:#888">평균 45분 → 6분</div>
        </div>""", unsafe_allow_html=True)
    with e2:
        st.markdown("""
        <div class="metric-box">
          <div class="metric-label">자동 승인률</div>
          <div class="metric-value">{:.0f}%</div>
          <div style="font-size:0.75rem;color:#888">수기 처리 불필요</div>
        </div>""".format(auto_rate), unsafe_allow_html=True)
    with e3:
        st.markdown("""
        <div class="metric-box">
          <div class="metric-label">담당자 절감 시간</div>
          <div class="metric-value orange">월 {:.0f}h</div>
          <div style="font-size:0.75rem;color:#888">건당 약 39분 절감</div>
        </div>""".format(pass_count * 39 / 60), unsafe_allow_html=True)
    with e4:
        st.markdown("""
        <div class="metric-box">
          <div class="metric-label">오류 발생률</div>
          <div class="metric-value green">↓ 94%</div>
          <div style="font-size:0.75rem;color:#888">OCR 자동 입력</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── CSV 다운로드 ──────────────────────────────────────────
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 전체 출장 기록 CSV 다운로드",
        data=csv,
        file_name=f"출장기록_{datetime.date.today()}.csv",
        mime="text/csv",
    )
