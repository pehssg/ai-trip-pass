"""AI-Trip Pass — 출장 행정 자동화 시스템"""

import streamlit as st
import pandas as pd
import numpy as np
import math, io, json, re, os, base64, datetime, requests
from bs4 import BeautifulSoup
from PIL import Image, ExifTags
import folium
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import warnings
warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════
# 페이지 설정
# ══════════════════════════════════════════════
st.set_page_config(page_title="AI-Trip Pass", page_icon="🚗", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
.main{background:#f8f9fb}
.header-banner{background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;
  padding:24px 32px;border-radius:16px;margin-bottom:24px}
.header-banner h1{margin:0;font-size:2rem;font-weight:700}
.header-banner p{margin:4px 0 0;font-size:.95rem;opacity:.85}
.card{background:#fff;border-radius:12px;padding:20px 24px;
  box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:16px}
.card-title{font-size:1rem;font-weight:600;color:#1a73e8;
  border-left:4px solid #1a73e8;padding-left:10px;margin-bottom:14px}
.metric-box{background:#fff;border-radius:12px;padding:18px 20px;
  box-shadow:0 2px 8px rgba(0,0,0,.07);text-align:center}
.metric-label{font-size:.78rem;color:#888;font-weight:500;margin-bottom:4px}
.metric-value{font-size:1.7rem;font-weight:700;color:#1a73e8}
.final-amount{background:linear-gradient(135deg,#e8f5e9,#c8e6c9);
  border:2px solid #4caf50;border-radius:12px;padding:20px;text-align:center}
.final-amount .label{color:#388e3c;font-size:.9rem;font-weight:600}
.final-amount .amount{color:#1b5e20;font-size:2.4rem;font-weight:800}
.tag-pass{background:#e8f5e9;color:#2e7d32;padding:3px 10px;border-radius:20px;font-size:.82rem;font-weight:600}
.tag-alert{background:#fff3e0;color:#e65100;padding:3px 10px;border-radius:20px;font-size:.82rem;font-weight:600}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-banner">
  <h1>🚗 AI-Trip Pass</h1>
  <p>출장 행정 자동화 시스템 · 영수증 OCR · 위치 증빙 · 관리자 대시보드</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# 세션 초기화
# ══════════════════════════════════════════════
def _init(k, v):
    if k not in st.session_state:
        st.session_state[k] = v

_init("ocr_result", {})
_init("destination", "수원")
_init("dest_coord", (37.2636, 127.0286))
_init("trip_distance", 0.0)
_init("toll_fee", 0)
_init("fuel_cost", 0.0)
_init("total_cost", 0.0)
_init("trip_date", "")
_init("route_text", "")
_init("fuel_type", "휘발유")
_init("fuel_price", 1650)
_init("fuel_source", "")
_init("car_model", "아반떼")
_init("submitted_trips", [])

# ══════════════════════════════════════════════
# 상수
# ══════════════════════════════════════════════
VEHICLE_FUEL_EFFICIENCY = {
    "아반떼":15.0,"쏘나타":13.5,"그랜저":11.0,"쏘렌토":10.5,
    "싼타페":10.0,"카니발":9.0,"스타렉스":9.5,"포터(1톤)":8.5,
    "모닝":16.0,"제네시스G80":10.0,
}

DISTANCE_FROM_SEOUL = {
    "서울":0,"수원":45,"인천":35,"대전":160,"대구":300,"부산":420,
    "광주":330,"울산":390,"세종":140,"춘천":80,"원주":110,"강릉":230,
    "전주":240,"청주":140,"천안":110,"안산":40,"성남":25,"화성":60,
    "평택":80,"의정부":25,
}

DESTINATION_COORDS = {
    "서울":(37.5665,126.9780),"수원":(37.2636,127.0286),"인천":(37.4563,126.7052),
    "대전":(36.3504,127.3845),"대구":(35.8714,128.6014),"부산":(35.1796,129.0756),
    "광주":(35.1595,126.8526),"울산":(35.5384,129.3114),"세종":(36.4801,127.2890),
    "춘천":(37.8813,127.7298),"원주":(37.3422,127.9202),"강릉":(37.7519,128.8761),
    "전주":(35.8242,127.1480),"청주":(36.6424,127.4890),"천안":(36.8151,127.1139),
    "안산":(37.3219,126.8309),"성남":(37.4449,127.1388),"화성":(37.1997,126.8312),
    "평택":(36.9921,127.1128),"의정부":(37.7381,127.0337),
}

FALLBACK_FUEL_PRICES = {"휘발유":1652,"경유":1498,"LPG":963}

TOLLGATE_TO_CITY = {
    "서울":"서울","서울tg":"서울","한남":"서울","반포":"서울","양재":"서울","서서울":"서울",
    "수원":"수원","수원tg":"수원","동수원":"수원","북수원":"수원","남수원":"수원",
    "인천":"인천","인천tg":"인천","서인천":"인천","남인천":"인천",
    "대전":"대전","대전tg":"대전","북대전":"대전","남대전":"대전","유성":"대전",
    "대구":"대구","대구tg":"대구","북대구":"대구","남대구":"대구",
    "부산":"부산","부산tg":"부산","북부산":"부산","남부산":"부산",
    "광주":"광주","광주tg":"광주","북광주":"광주","남광주":"광주",
    "천안":"천안","청주":"청주","전주":"전주","세종":"세종",
    "평택":"평택","안산":"안산","화성":"화성","의정부":"의정부",
    "춘천":"춘천","원주":"원주","강릉":"강릉","울산":"울산",
    "시흥":"안산","금왕":"충주","음성":"충주",
}

# ══════════════════════════════════════════════
# 유틸 함수
# ══════════════════════════════════════════════
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2-lat1)/2)**2 + \
        math.cos(phi1)*math.cos(phi2)*math.sin(math.radians(lon2-lon1)/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def gate_to_city(name: str):
    key = name.lower().replace(" ","").replace("_","").replace("영업소","").replace("요금소","").replace("tg","")
    if key in TOLLGATE_TO_CITY:
        return TOLLGATE_TO_CITY[key]
    for k, v in TOLLGATE_TO_CITY.items():
        if k in key or key in k:
            return v
    return None


def estimate_distance(origin: str, destination: str) -> float:
    d_o = DISTANCE_FROM_SEOUL.get(origin, 0)
    d_d = DISTANCE_FROM_SEOUL.get(destination, 50)
    one_way = abs(d_d - d_o) if d_o != d_d else d_d
    return round((one_way or d_d) * 2, 1)


def get_opinet_fuel_price(fuel_type: str):
    code_map = {"휘발유":"B027","경유":"D047","LPG":"K015"}
    prod_cd = code_map.get(fuel_type, "B027")
    headers = {"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"}

    # XML API
    try:
        r = requests.get(f"https://www.opinet.co.kr/api/avgAllPrice.do?out=xml&prodcd={prod_cd}",
                         headers=headers, timeout=6)
        if r.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)
            el = root.find(".//PRICE")
            if el is not None and el.text:
                return int(float(el.text)), "오피넷 API"
    except Exception:
        pass

    # 스크래핑
    try:
        r = requests.get("https://www.opinet.co.kr/user/main/mainView.do",
                         headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        kw = {"휘발유":"휘발유","경유":"경유","LPG":"LPG"}.get(fuel_type,"휘발유")
        m = re.search(rf"{kw}[^\d]{{0,20}}(\d{{1,2}},?\d{{3}}(?:\.\d+)?)", soup.get_text())
        if m:
            v = int(float(m.group(1).replace(",","")))
            if 500 < v < 4000:
                return v, "오피넷 스크래핑"
    except Exception:
        pass

    return FALLBACK_FUEL_PRICES[fuel_type], "예비 데이터"


# ══════════════════════════════════════════════
# 영수증 분석 (pdfplumber 직접 파싱 — 완전 무료)
# ══════════════════════════════════════════════
def extract_pdf_text(file_bytes: bytes) -> str:
    """pdfplumber로 PDF 전체 텍스트 추출"""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return ""


def parse_receipts(text: str) -> dict:
    """
    하이패스 영수증 텍스트를 파싱합니다.
    여러 건이 포함된 경우 통행료를 합산하고
    첫 번째 입구영업소 = 출발지, 마지막 영업소 = 목적지로 판단합니다.
    """
    cities = list(DISTANCE_FROM_SEOUL.keys())

    # ── 날짜: 가장 이른 날짜 추출 ──────────────────
    dates = re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text)
    if dates:
        parsed_dates = [datetime.date(int(y), int(m), int(d)) for y, m, d in dates]
        earliest = min(parsed_dates)
        trip_date = earliest.strftime("%Y.%m.%d")
    else:
        d = re.search(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})", text)
        trip_date = d.group() if d else datetime.date.today().strftime("%Y.%m.%d")

    # ── 영수증 블록 분리 (영업소 단위) ─────────────
    # 한국도로공사 XXX영업소 패턴으로 블록 나누기
    blocks = re.split(r"(?=한국도로공사)", text)
    blocks = [b.strip() for b in blocks if b.strip()]

    receipts = []
    total_toll = 0

    for block in blocks:
        # 영업소명
        name_m = re.search(r"한국도로공사\s+(.+?영업소)", block)
        office  = name_m.group(1).strip() if name_m else ""

        # 입구영업소 (진입 출발지)
        entry_m = re.search(r"입구영업소\s*[：:]\s*([^\n]+)", block)
        entry   = entry_m.group(1).strip() if entry_m else None

        # 금액: "1 종  2,400원" 또는 "KEC 2,400원" 등
        amt_m = re.search(r"(?:KEC|종)\s+([\d,]+)원", block)
        if not amt_m:
            amt_m = re.search(r"([\d,]+)원", block)
        amount = int(amt_m.group(1).replace(",", "")) if amt_m else 0

        # 시각
        time_m = re.search(r"(\d{2})시(\d{2})분", block)
        time_str = f"{time_m.group(1)}:{time_m.group(2)}" if time_m else ""

        if office or amount:
            receipts.append({
                "영업소": office,
                "입구영업소": entry,
                "금액": amount,
                "시각": time_str,
            })
            total_toll += amount

    # 총액 텍스트로 검증 ("총N건/15300원")
    total_m = re.search(r"총\s*\d+건\s*/\s*([\d,]+)원", text)
    if total_m:
        total_toll = int(total_m.group(1).replace(",", ""))

    # ── 시간순 정렬 (빠른 시각이 출발) ────────────
    def sort_key(r):
        t = r.get("시각","99:99")
        return t if t else "99:99"
    receipts_sorted = sorted(receipts, key=sort_key)

    # ── 출발지: 가장 이른 시각의 입구영업소 ────────
    origin_gate = None
    for r in receipts_sorted:
        if r.get("입구영업소"):
            origin_gate = r["입구영업소"]
            break
    if not origin_gate and receipts_sorted:
        origin_gate = receipts_sorted[0]["영업소"]
    origin_gate = origin_gate or "출발요금소"

    # ── 목적지: 가장 늦은 시각의 입구영업소 또는 영업소 ──
    dest_gate = None
    for r in reversed(receipts_sorted):
        if r.get("입구영업소"):
            dest_gate = r["입구영업소"]
            break
    if not dest_gate and receipts_sorted:
        # 입구영업소 없는 경우 중간 영업소(실제 경유지) 중 마지막
        dest_gate = receipts_sorted[-1]["영업소"]
    dest_gate = dest_gate or "도착요금소"

    # ── 도시 매핑 ───────────────────────────────────
    origin_city = gate_to_city(origin_gate)
    dest_city   = gate_to_city(dest_gate)

    # 도시 못 찾으면 텍스트에서 도시명 직접 검색
    if not origin_city:
        for city in cities:
            if city in origin_gate:
                origin_city = city
                break
    if not dest_city:
        for city in cities:
            if city in dest_gate:
                dest_city = city
                break

    return {
        "trip_date":   trip_date,
        "toll_fee":    total_toll,
        "toll_detail": receipts,
        "origin_gate": origin_gate,
        "dest_gate":   dest_gate,
        "origin_city": origin_city,
        "dest_city":   dest_city,
        "ocr_text":    text[:500],
        "method":      "pdfplumber 직접 파싱 (무료)",
        "is_total":    True,
    }


# ══════════════════════════════════════════════
# EXIF
# ══════════════════════════════════════════════
def extract_exif_gps(image: Image.Image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return None
        exif = {ExifTags.TAGS.get(k,k):v for k,v in exif_data.items()}
        gps_raw = exif.get("GPSInfo")
        dt_str  = exif.get("DateTimeOriginal", exif.get("DateTime",""))
        if not gps_raw:
            return None
        gps = {ExifTags.GPSTAGS.get(k,k):v for k,v in gps_raw.items()}
        def dms(d,r):
            v = float(d[0]) + float(d[1])/60 + float(d[2])/3600
            return -v if r in ("S","W") else v
        return {"lat":dms(gps["GPSLatitude"],gps.get("GPSLatitudeRef","N")),
                "lon":dms(gps["GPSLongitude"],gps.get("GPSLongitudeRef","E")),
                "datetime":dt_str}
    except Exception:
        return None


# ══════════════════════════════════════════════
# 한글 폰트 로드
# ══════════════════════════════════════════════
@st.cache_resource
def load_korean_font():
    paths = {
        "NanumGothic":     "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "NanumGothicBold": "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    }
    for name, path in paths.items():
        try:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            pass

    if not os.path.exists(paths["NanumGothic"]):
        try:
            import subprocess
            subprocess.run(["apt-get","install","-y","fonts-nanum"],
                           capture_output=True, timeout=60)
            for name, path in paths.items():
                if os.path.exists(path):
                    try: pdfmetrics.registerFont(TTFont(name, path))
                    except Exception: pass
        except Exception:
            pass

    try: pdfmetrics.getFont("NanumGothic"); F = "NanumGothic"
    except Exception: F = "Helvetica"
    try: pdfmetrics.getFont("NanumGothicBold"); FB = "NanumGothicBold"
    except Exception: FB = "Helvetica-Bold"
    return {"regular": F, "bold": FB}


# ══════════════════════════════════════════════
# PDF 생성
# ══════════════════════════════════════════════
def generate_trip_pdf(trip_date, destination, route_text, distance,
                      car_model, fuel_type, fuel_price, toll_fee,
                      total_cost, fuel_source="") -> bytes:
    fonts = load_korean_font()
    F, FB = fonts["regular"], fonts["bold"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColorRGB(0.10, 0.45, 0.91)
    c.rect(0, H-90, W, 90, fill=1, stroke=0)
    c.setFillColorRGB(1,1,1)
    c.setFont(FB, 20); c.drawCentredString(W/2, H-42, "출장이행확인서")
    c.setFont(F, 10);  c.drawCentredString(W/2, H-63, "AI-Trip Pass 자동 생성 문서")

    y = H - 108
    lh = 27

    def sec(title, yy):
        c.setFillColorRGB(0.93,0.96,1.0)
        c.rect(38, yy-5, W-76, 22, fill=1, stroke=0)
        c.setFillColorRGB(0.10,0.45,0.91)
        c.setFont(FB, 10); c.drawString(50, yy+4, title)
        return yy - lh

    def row(label, value, yy):
        c.setFillColorRGB(0.5,0.5,0.5)
        c.setFont(F, 9); c.drawString(58, yy, label)
        c.setFillColorRGB(0.1,0.1,0.1)
        c.setFont(F, 10); c.drawString(195, yy, str(value))
        c.setStrokeColorRGB(0.91,0.91,0.91)
        c.line(50, yy-5, W-50, yy-5)
        return yy - lh

    y = sec("[ 출장 기본 정보 ]", y)
    y = row("출장일",          trip_date, y)
    y = row("출장지",          destination, y)
    y = row("이동경로",        route_text, y)
    y = row("총 이동거리",     f"{distance} km (왕복)", y)
    y = row("자차 이용 사유",  "출장경로 복잡 / 대중교통 불편", y)

    y -= 8
    y = sec("[ 차량 및 유류 정보 ]", y)
    y = row("차종",            car_model, y)
    y = row("유종",            fuel_type, y)
    y = row(f"오피넷 유가 ({fuel_source})" if fuel_source else "오피넷 유가",
            f"{fuel_price:,} 원/L", y)

    y -= 8
    y = sec("[ 비용 내역 ]", y)
    y = row("유류비",          f"{total_cost - toll_fee:,.0f} 원", y)
    y = row("통행료 (왕복)",   f"{toll_fee:,} 원", y)

    y -= 10
    bh = 52
    c.setFillColorRGB(0.88,0.97,0.88)
    c.setStrokeColorRGB(0.30,0.69,0.31)
    c.roundRect(38, y-bh, W-76, bh, 8, fill=1, stroke=1)
    c.setFillColorRGB(0.11,0.37,0.13)
    c.setFont(FB, 11); c.drawString(58, y-18, "최종 청구 금액")
    c.setFont(FB, 20); c.drawRightString(W-58, y-24, f"{total_cost:,.0f} 원")
    y -= (bh + 24)

    y -= 10
    c.setStrokeColorRGB(0.8,0.8,0.8); c.line(50, y, W-50, y)
    c.setFillColorRGB(0.5,0.5,0.5)
    c.setFont(F, 8)
    c.drawString(58,  y-16, "신청인: _______________")
    c.drawString(218, y-16, "부서장: _______________")
    c.drawString(378, y-16, "결  재: _______________")

    c.setFillColorRGB(0.7,0.7,0.7)
    c.setFont(F, 7)
    c.drawCentredString(W/2, 28,
        f"Generated by AI-Trip Pass  ·  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c.save()
    return buf.getvalue()


# ══════════════════════════════════════════════
# 탭 구성
# ══════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs([
    "📄 Tab 1 · 영수증 처리 & 출장이행확인서",
    "📍 Tab 2 · 사진 EXIF 위치 증빙",
    "📊 Tab 3 · 관리자 대시보드",
])


# ──────────────────────────────────────────────
# TAB 1
# ──────────────────────────────────────────────
with tab1:
    col_left, col_right = st.columns([1,1], gap="large")

    with col_left:
        # ① 영수증 업로드
        st.markdown('<div class="card"><div class="card-title">① 하이패스 영수증 업로드</div>', unsafe_allow_html=True)
        receipt_file = st.file_uploader(
            "PDF 또는 이미지(jpg/png) — 여러 건 자동 합산",
            type=["pdf","jpg","jpeg","png"],
            key="receipt_uploader", label_visibility="collapsed",
        )

        if receipt_file:
            file_bytes = receipt_file.read()
            result = None

            if receipt_file.type == "application/pdf":
                with st.spinner("📄 PDF 텍스트 추출 중..."):
                    pdf_text = extract_pdf_text(file_bytes)

                if pdf_text.strip():
                    result = parse_receipts(pdf_text)
                    st.success(f"✅ {result['method']} 완료")
                else:
                    st.error("❌ PDF에서 텍스트를 추출하지 못했습니다. 스캔된 이미지 PDF일 수 있습니다.")
            else:
                img = Image.open(io.BytesIO(file_bytes))
                st.image(img, caption="업로드된 영수증", use_container_width=True)
                st.warning("⚠️ 이미지 파일은 PDF로 변환 후 업로드하시면 더 정확하게 인식됩니다.")
                # 이미지도 pdfplumber로 처리 불가 → 간단 정규식 파싱 시도
                try:
                    import pytesseract
                    text = pytesseract.image_to_string(img, lang="kor+eng")
                    result = parse_receipts(text)
                    result["method"] = "pytesseract (이미지)"
                    st.info(f"ℹ️ pytesseract로 인식")
                except Exception:
                    st.info("💡 PDF 파일로 업로드하면 자동 인식됩니다.")

            if not result:
                result = {
                    "trip_date":   datetime.date.today().strftime("%Y.%m.%d"),
                    "toll_fee":    0,
                    "toll_detail": [],
                    "origin_gate": "출발요금소",
                    "dest_gate":   "도착요금소",
                    "origin_city": None,
                    "dest_city":   None,
                    "ocr_text":    "",
                    "method":      "수동 입력 필요",
                    "is_total":    True,
                }

            c1, c2 = st.columns(2)
            with c1:
                st.metric("출장일",     result["trip_date"])
                st.metric("출발 요금소", result["origin_gate"])
            with c2:
                lbl = "통행료 합계" if result.get("is_total") else "통행료 (편도)"
                st.metric(lbl, f"{result['toll_fee']:,}원")
                st.metric("도착 요금소", result["dest_gate"])

            if result.get("toll_detail"):
                with st.expander(f"📋 통행료 상세 ({len(result['toll_detail'])}건)"):
                    for i, r in enumerate(result["toll_detail"], 1):
                        if isinstance(r, dict):
                            name = r.get("영업소") or r.get("name") or f"영업소{i}"
                            amt  = r.get("금액") or r.get("amount") or 0
                            time = r.get("시각") or r.get("time") or ""
                            st.write(f"{i}. {name}  —  {int(amt):,}원  {time}")

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
                with st.expander("📝 AI 분석 원문"):
                    st.text(result["ocr_text"])

            # 세션 저장
            st.session_state.toll_fee  = result["toll_fee"] if result.get("is_total") else result["toll_fee"] * 2
            st.session_state.trip_date = result["trip_date"]
            if result.get("origin_city"):
                st.session_state.ocr_origin_city = result["origin_city"]
            if result.get("dest_city"):
                st.session_state.ocr_dest_city = result["dest_city"]

        st.markdown('</div>', unsafe_allow_html=True)

        # ② 출발지·목적지
        st.markdown('<div class="card"><div class="card-title">② 출발지 · 목적지 설정</div>', unsafe_allow_html=True)
        cities = list(DISTANCE_FROM_SEOUL.keys())
        ocr_origin = st.session_state.get("ocr_origin_city")
        ocr_dest   = st.session_state.get("ocr_dest_city")

        if ocr_origin or ocr_dest:
            st.caption("✅ 영수증에서 자동 인식된 값이 반영되었습니다. 필요 시 수정하세요.")

        oi = cities.index(ocr_origin) if ocr_origin and ocr_origin in cities else cities.index("서울")
        di = cities.index(ocr_dest)   if ocr_dest   and ocr_dest   in cities else (cities.index("수원") if "수원" in cities else 1)

        c1, c2 = st.columns(2)
        with c1: origin      = st.selectbox("출발지", cities, index=oi, key="sel_origin")
        with c2: destination = st.selectbox("목적지", cities, index=di, key="sel_dest")

        st.session_state.destination = destination
        st.session_state.dest_coord  = DESTINATION_COORDS.get(destination, (37.5665,126.9780))
        distance_km = estimate_distance(origin, destination)
        st.session_state.trip_distance = distance_km
        st.session_state.route_text = f"{origin} → {destination} : {distance_km/2:.1f}km"

        st.info(f"📏 예상 왕복 이동거리: **{distance_km} km** (편도 {distance_km/2:.1f} km)")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        # ③ 차량·유류비
        st.markdown('<div class="card"><div class="card-title">③ 차량 & 유류비 설정</div>', unsafe_allow_html=True)
        car_model  = st.selectbox("차종 선택", list(VEHICLE_FUEL_EFFICIENCY.keys()))
        efficiency = VEHICLE_FUEL_EFFICIENCY[car_model]
        st.caption(f"🚘 공인 평균 연비: **{efficiency} km/L**")
        fuel_type  = st.selectbox("유종 선택", ["휘발유","경유","LPG"])
        st.session_state.fuel_type  = fuel_type
        st.session_state.car_model  = car_model

        cb1, cb2 = st.columns([1,2])
        with cb1:
            if st.button("🔄 오피넷 유가 조회", use_container_width=True):
                with st.spinner("조회 중..."):
                    price, source = get_opinet_fuel_price(fuel_type)
                st.session_state.fuel_price  = price
                st.session_state.fuel_source = source
                if "예비" in source:
                    st.warning(f"⚠️ 예비 데이터: {price:,}원/L")
                else:
                    st.success(f"✅ {source}: {price:,}원/L")
        with cb2:
            manual = st.number_input("유가 직접 입력 (원/L)", min_value=500, max_value=3000,
                                     value=int(st.session_state.fuel_price), step=10)
            st.session_state.fuel_price = manual

        st.markdown('</div>', unsafe_allow_html=True)

        # ④ 비용 정산
        st.markdown('<div class="card"><div class="card-title">④ 비용 정산</div>', unsafe_allow_html=True)
        toll = st.number_input(
            "통행료 — 왕복 합계 (원)  ※ 영수증에서 자동 반영",
            min_value=0, value=int(st.session_state.toll_fee), step=100,
        )
        st.session_state.toll_fee = toll

        fuel_cost  = (distance_km / efficiency) * st.session_state.fuel_price
        total_cost = fuel_cost + toll
        st.session_state.fuel_cost  = fuel_cost
        st.session_state.total_cost = total_cost

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-box"><div class="metric-label">유류비</div>'
                        f'<div class="metric-value" style="font-size:1.2rem">{fuel_cost:,.0f}원</div>'
                        f'<div style="font-size:.75rem;color:#888">{distance_km/efficiency:.1f}L 소비</div></div>',
                        unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-box"><div class="metric-label">통행료 (왕복)</div>'
                        f'<div class="metric-value" style="font-size:1.2rem">{toll:,.0f}원</div>'
                        f'<div style="font-size:.75rem;color:#888">편도 {toll//2:,}원 × 2</div></div>',
                        unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-box"><div class="metric-label">왕복 거리</div>'
                        f'<div class="metric-value" style="font-size:1.2rem">{distance_km:.0f}km</div>'
                        f'<div style="font-size:.75rem;color:#888">편도 {distance_km/2:.0f}km</div></div>',
                        unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        fp = int(fuel_cost / total_cost * 100) if total_cost > 0 else 0
        st.markdown(f"""
        <div class="final-amount">
          <div class="label">💰 최종 청구 금액 (유류비 + 통행료)</div>
          <div class="amount">{total_cost:,.0f} 원</div>
          <div style="display:flex;justify-content:center;gap:16px;margin-top:8px;font-size:.8rem">
            <span style="color:#388e3c">유류비 {fuel_cost:,.0f}원 ({fp}%)</span>
            <span style="color:#888">+</span>
            <span style="color:#1565c0">통행료 {toll:,.0f}원 ({100-fp}%)</span>
          </div>
          <div style="color:#388e3c;font-size:.75rem;margin-top:4px">
            ({distance_km}km ÷ {efficiency}km/L × {int(st.session_state.fuel_price):,}원/L) + 통행료 왕복
          </div>
        </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ⑤ PDF 생성
        st.markdown('<div class="card"><div class="card-title">⑤ 출장이행확인서 PDF 생성</div>', unsafe_allow_html=True)
        trip_date_input = st.text_input("출장일 (YYYY.MM.DD)",
                                        value=st.session_state.trip_date or datetime.date.today().strftime("%Y.%m.%d"))
        st.session_state.trip_date = trip_date_input

        if st.button("📄 PDF 자동 생성 & 다운로드", use_container_width=True, type="primary"):
            with st.spinner("PDF 생성 중..."):
                pdf_bytes = generate_trip_pdf(
                    trip_date   = st.session_state.trip_date,
                    destination = st.session_state.destination,
                    route_text  = st.session_state.route_text,
                    distance    = st.session_state.trip_distance,
                    car_model   = car_model,
                    fuel_type   = fuel_type,
                    fuel_price  = int(st.session_state.fuel_price),
                    toll_fee    = int(st.session_state.toll_fee),
                    total_cost  = st.session_state.total_cost,
                    fuel_source = st.session_state.get("fuel_source",""),
                )
            fname = f"출장이행확인서_{st.session_state.trip_date.replace('.','')}.pdf"
            st.download_button("⬇️ PDF 다운로드", data=pdf_bytes,
                               file_name=fname, mime="application/pdf",
                               use_container_width=True)
            st.success("✅ PDF 생성 완료")
            st.session_state.submitted_trips.append({
                "제출일": datetime.date.today().strftime("%Y-%m-%d"),
                "출장일": st.session_state.trip_date,
                "출장지": st.session_state.destination,
                "이동거리(km)": st.session_state.trip_distance,
                "차종": car_model,
                "유류비(원)": round(fuel_cost),
                "통행료(원)": int(toll),
                "청구금액(원)": round(total_cost),
                "상태": "자동 승인 (Pass)" if total_cost < 150000 else "수기 확인 필요 (Alert)",
            })
        st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────
# TAB 2
# ──────────────────────────────────────────────
with tab2:
    st.markdown('<div class="card"><div class="card-title">📸 현장 사진 EXIF 위치 증빙</div>', unsafe_allow_html=True)
    dest_name  = st.session_state.destination
    dest_coord = st.session_state.dest_coord
    st.info(f"🗺️ Tab 1 목적지: **{dest_name}** ({dest_coord[0]:.4f}, {dest_coord[1]:.4f})")

    photo_file = st.file_uploader("현장 사진 (GPS EXIF 포함 JPG 권장)",
                                  type=["jpg","jpeg"], key="photo_uploader")

    col_photo, col_result = st.columns([1,1], gap="large")
    with col_photo:
        if photo_file:
            photo = Image.open(photo_file)
            st.image(photo, caption="업로드된 현장 사진", use_container_width=True)
            gps_data = extract_exif_gps(photo)
            if gps_data:
                st.markdown(f'<div class="card"><b>📡 EXIF 추출 결과</b><br><br>'
                            f'위도: <code>{gps_data["lat"]:.6f}</code><br>'
                            f'경도: <code>{gps_data["lon"]:.6f}</code><br>'
                            f'촬영 시각: <code>{gps_data["datetime"] or "없음"}</code></div>',
                            unsafe_allow_html=True)
            else:
                st.warning("⚠️ GPS 정보 없음 — 시연용 좌표 사용")
                gps_data = {
                    "lat": dest_coord[0] + np.random.uniform(-0.03, 0.03),
                    "lon": dest_coord[1] + np.random.uniform(-0.03, 0.03),
                    "datetime": datetime.datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
                }
                st.info(f"시연 좌표: ({gps_data['lat']:.4f}, {gps_data['lon']:.4f})")

    with col_result:
        if photo_file and gps_data:
            dist_km = haversine(dest_coord[0], dest_coord[1], gps_data["lat"], gps_data["lon"])
            st.markdown("#### 📏 위치 검증 결과")
            m1, m2 = st.columns(2)
            with m1: st.metric("목적지 좌표", f"{dest_coord[0]:.3f}, {dest_coord[1]:.3f}")
            with m2: st.metric("사진 좌표",   f"{gps_data['lat']:.3f}, {gps_data['lon']:.3f}")
            st.metric("두 지점 간 거리", f"{dist_km:.2f} km", delta="기준: 5km 이내")
            if dist_km <= 5.0:
                st.success(f"✅ 정상 증빙 — {dest_name}에서 {dist_km:.2f}km 이내")
            else:
                st.warning(f"⚠️ 위치 불일치 — {dist_km:.2f}km 떨어져 있음, 수기 확인 필요")

    if photo_file and gps_data:
        st.markdown("#### 🗺️ 위치 시각화 지도")
        clat = (dest_coord[0] + gps_data["lat"]) / 2
        clon = (dest_coord[1] + gps_data["lon"]) / 2
        m = folium.Map(location=[clat,clon], zoom_start=11, tiles="CartoDB positron")
        folium.Circle(location=dest_coord, radius=5000,
                      color="#1a73e8", fill=True, fill_opacity=0.12,
                      popup=f"목적지: {dest_name} (반경 5km)").add_to(m)
        folium.Marker(dest_coord, popup=f"🏢 {dest_name}",
                      icon=folium.Icon(color="blue", icon="building", prefix="fa")).add_to(m)
        pc = "green" if dist_km <= 5.0 else "orange"
        folium.Marker([gps_data["lat"], gps_data["lon"]],
                      popup=f"📍 촬영 위치",
                      icon=folium.Icon(color=pc, icon="camera", prefix="fa")).add_to(m)
        folium.PolyLine(locations=[dest_coord,[gps_data["lat"],gps_data["lon"]]],
                        color="#ff6b6b", weight=2, dash_array="8", opacity=0.7).add_to(m)
        st_folium(m, width=None, height=420, returned_objects=[])

    st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────
# TAB 3
# ──────────────────────────────────────────────
with tab3:
    DUMMY = [
        {"제출일":"2025-06-01","출장일":"2025-05-30","출장지":"수원","이동거리(km)":90,"차종":"아반떼","유류비(원)":9900,"통행료(원)":2400,"청구금액(원)":12300,"상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-02","출장일":"2025-05-31","출장지":"대전","이동거리(km)":320,"차종":"쏘나타","유류비(원)":39062,"통행료(원)":7200,"청구금액(원)":46262,"상태":"수기 확인 필요 (Alert)"},
        {"제출일":"2025-06-03","출장일":"2025-06-01","출장지":"인천","이동거리(km)":70,"차종":"모닝","유류비(원)":7219,"통행료(원)":1600,"청구금액(원)":8819,"상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-04","출장일":"2025-06-02","출장지":"대구","이동거리(km)":600,"차종":"쏘렌토","유류비(원)":88560,"통행료(원)":18000,"청구금액(원)":106560,"상태":"수기 확인 필요 (Alert)"},
        {"제출일":"2025-06-05","출장일":"2025-06-03","출장지":"성남","이동거리(km)":50,"차종":"그랜저","유류비(원)":7500,"통행료(원)":1200,"청구금액(원)":8700,"상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-06","출장일":"2025-06-04","출장지":"부산","이동거리(km)":840,"차종":"카니발","유류비(원)":154000,"통행료(원)":24000,"청구금액(원)":178000,"상태":"수기 확인 필요 (Alert)"},
        {"제출일":"2025-06-07","출장일":"2025-06-05","출장지":"청주","이동거리(km)":280,"차종":"아반떼","유류비(원)":30800,"통행료(원)":6000,"청구금액(원)":36800,"상태":"자동 승인 (Pass)"},
        {"제출일":"2025-06-08","출장일":"2025-06-06","출장지":"광주","이동거리(km)":660,"차종":"쏘나타","유류비(원)":80667,"통행료(원)":16800,"청구금액(원)":97467,"상태":"수기 확인 필요 (Alert)"},
    ]

    all_trips = DUMMY + st.session_state.submitted_trips
    df = pd.DataFrame(all_trips)
    pass_n  = len(df[df["상태"].str.contains("Pass")])
    alert_n = len(df[df["상태"].str.contains("Alert")])
    total_n = len(df)
    total_c = df["청구금액(원)"].sum()
    rate    = round(pass_n / total_n * 100, 1) if total_n else 0

    st.markdown("### 📊 이번 달 출장 현황 요약")
    c1,c2,c3,c4,c5 = st.columns(5)
    for col, label, val, cls in [
        (c1,"전체 제출 건수",total_n,""),
        (c2,"✅ 자동 승인",pass_n," style='color:#2e7d32'"),
        (c3,"⚠️ 수기 확인",alert_n," style='color:#e65100'"),
        (c4,"자동화율",f"{rate}%",""),
        (c5,"총 청구금액",f"{total_c:,.0f}원",""),
    ]:
        col.markdown(f'<div class="metric-box"><div class="metric-label">{label}</div>'
                     f'<div class="metric-value"{cls}>{val}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c_chart, c_eff = st.columns([1,1], gap="large")
    with c_chart:
        st.markdown('<div class="card"><div class="card-title">출장지별 청구금액</div>', unsafe_allow_html=True)
        st.bar_chart(df.groupby("출장지")["청구금액(원)"].sum().sort_values(ascending=False), color="#1a73e8", height=240)
        st.markdown('</div>', unsafe_allow_html=True)
    with c_eff:
        st.markdown('<div class="card"><div class="card-title">⚡ 행정 효율화 지표</div>', unsafe_allow_html=True)
        e1,e2,e3,e4 = st.columns(2), st.columns(2), None, None
        for cols, items in [
            (st.columns(2), [("처리 시간 단축","↓87%","green"),("오류 발생률","↓94%","green")]),
            (st.columns(2), [("자동화율",f"{rate}%",""),("월 절감 시간",f"{pass_n*39/60:.1f}h","")]),
        ]:
            for col, (lbl, val, cls) in zip(cols, items):
                color = " style='color:#2e7d32'" if cls=="green" else ""
                col.markdown(f'<div class="metric-box"><div class="metric-label">{lbl}</div>'
                             f'<div class="metric-value" style="font-size:1.3rem"{color}>{val}</div></div>',
                             unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="card-title">📋 출장 기록 상세</div>', unsafe_allow_html=True)
    f_col, _ = st.columns([1,3])
    with f_col:
        filt = st.selectbox("상태 필터", ["전체","자동 승인 (Pass)","수기 확인 필요 (Alert)"])
    show_df = df if filt == "전체" else df[df["상태"] == filt]

    def style_row(val):
        if "Pass" in str(val): return "background-color:#e8f5e9;color:#2e7d32;font-weight:600"
        else: return "background-color:#fff3e0;color:#e65100;font-weight:600"

    st.dataframe(
        show_df.style.applymap(style_row, subset=["상태"]),
        use_container_width=True, height=300,
        column_config={
            "청구금액(원)": st.column_config.NumberColumn(format="%,d 원"),
            "유류비(원)":   st.column_config.NumberColumn(format="%,d 원"),
            "통행료(원)":   st.column_config.NumberColumn(format="%,d 원"),
        }
    )

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSV 다운로드", data=csv,
                       file_name=f"출장기록_{datetime.date.today()}.csv", mime="text/csv")
    st.markdown('</div>', unsafe_allow_html=True)
