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
    # ── 현대 ─────────────────────────────────────
    "캐스퍼(현대)":       16.0,
    "모닝(기아)":          17.0,
    "아반떼(현대)":        15.0,
    "i30(현대)":          13.5,
    "벨로스터(현대)":      13.0,
    "쏘나타(현대)":        13.5,
    "쏘나타 하이브리드":   20.0,
    "아이오닉6(현대)":     6.3,   # 전비 km/kWh → 유류비 불필요하나 선택용
    "그랜저(현대)":        11.0,
    "넥쏘(현대)":          96.0,  # 수소차(km/kg)
    "코나(현대)":          13.5,
    "투싼(현대)":          12.0,
    "싼타페(현대)":        10.5,
    "팰리세이드(현대)":     9.5,
    "스타리아(현대)":       9.0,
    "포터2(현대)":          9.5,
    "마이티(현대)":         8.0,
    "제네시스G70":         11.5,
    "제네시스G80":         10.0,
    "제네시스G90":          9.0,
    "제네시스GV70":        10.5,
    "제네시스GV80":         9.5,
    # ── 기아 ─────────────────────────────────────
    "레이(기아)":          14.5,
    "K3(기아)":            14.5,
    "K5(기아)":            13.5,
    "K5 하이브리드":       19.5,
    "K8(기아)":            11.5,
    "K8 하이브리드":       17.5,
    "K9(기아)":             9.0,
    "스토닉(기아)":        14.0,
    "셀토스(기아)":        13.0,
    "스포티지(기아)":      12.5,
    "쏘렌토(기아)":        10.5,
    "쏘렌토 하이브리드":   15.5,
    "카니발(기아)":         9.0,
    "EV6(기아)":            5.8,
    "봉고3(기아)":          9.0,
    # ── 쉐보레(GM) ───────────────────────────────
    "스파크(쉐보레)":      15.5,
    "말리부(쉐보레)":      12.5,
    "트레일블레이저(쉐보레)": 13.0,
    "트래버스(쉐보레)":     8.5,
    "콜로라도(쉐보레)":     8.0,
    # ── 르노코리아 ───────────────────────────────
    "QM3(르노)":           16.0,
    "QM6(르노)":           11.5,
    "SM6(르노)":           13.0,
    "XM3(르노)":           15.0,
    # ── KG모빌리티(구 쌍용) ──────────────────────
    "티볼리(KG)":          13.5,
    "코란도(KG)":          12.0,
    "렉스턴(KG)":          10.0,
    "무쏘(KG)":             9.5,
    # ── 수입차 ───────────────────────────────────
    "BMW 3시리즈":         13.0,
    "BMW 5시리즈":         11.5,
    "BMW X5":              9.5,
    "벤츠 C클래스":        13.0,
    "벤츠 E클래스":        11.5,
    "벤츠 GLE":             9.0,
    "아우디 A6":           12.0,
    "폭스바겐 골프":       15.0,
    "폭스바겐 티구안":     13.0,
    "토요타 캠리":         14.0,
    "렉서스 ES":           14.5,
    # ── 상용/특수 ─────────────────────────────────
    "1톤 트럭(포터/봉고)":  9.0,
    "1.4톤 트럭":           8.0,
    "2.5톤 트럭":           6.5,
    "5톤 트럭":             5.0,
    "카고트럭(소형)":       8.5,
}

# 전국 시·군 (서울 기준 직선거리 km) — 250개 지역
DISTANCE_FROM_SEOUL = {
    # 서울특별시
    "서울":0,
    # 인천광역시
    "인천":35,"강화":60,"옹진":80,
    # 경기도
    "수원":45,"성남":25,"의정부":25,"안양":25,"부천":28,"광명":22,
    "평택":80,"동두천":50,"안산":40,"고양":28,"과천":20,"구리":20,
    "남양주":35,"오산":60,"시흥":30,"군포":32,"의왕":28,"하남":22,
    "용인":50,"파주":45,"이천":80,"안성":90,"김포":35,"화성":60,
    "광주":55,"양주":45,"포천":75,"여주":100,"연천":85,"가평":75,
    "양평":70,
    # 강원도
    "춘천":80,"원주":110,"강릉":230,"동해":250,"태백":240,"속초":220,
    "삼척":270,"홍천":110,"횡성":120,"영월":175,"평창":170,"정선":200,
    "철원":90,"화천":100,"양구":120,"인제":130,"고성(강원)":240,"양양":210,
    # 충청북도
    "청주":140,"충주":145,"제천":170,"보은":165,"옥천":170,"영동":200,
    "진천":125,"괴산":160,"음성":130,"단양":195,"증평":130,
    # 충청남도
    "천안":110,"공주":145,"보령":185,"아산":115,"서산":170,"논산":170,
    "계룡":150,"당진":155,"금산":185,"부여":185,"서천":210,"청양":170,
    "홍성":175,"예산":145,"태안":195,
    # 세종특별자치시
    "세종":140,
    # 대전광역시
    "대전":160,
    # 전라북도
    "전주":240,"군산":230,"익산":225,"정읍":255,"남원":280,"김제":245,
    "완주":245,"진안":265,"무주":265,"장수":285,"임실":270,"순창":270,
    "고창":275,"부안":255,
    # 전라남도
    "목포":330,"여수":365,"순천":360,"나주":330,"광양":370,"담양":310,
    "곡성":330,"구례":350,"고흥":385,"보성":360,"화순":325,"장흥":360,
    "강진":360,"해남":380,"영암":345,"무안":330,"함평":320,"영광":305,
    "장성":315,"완도":390,"진도":395,"신안":340,
    # 광주광역시
    "광주":330,
    # 경상북도
    "포항":330,"경주":335,"김천":265,"안동":260,"구미":270,"영주":245,
    "영천":310,"상주":245,"문경":215,"경산":305,"군위":285,"의성":270,
    "청송":295,"영양":290,"영덕":315,"청도":315,"고령":295,"성주":285,
    "칠곡":280,"예천":240,"봉화":265,"울진":310,"울릉":460,
    # 대구광역시
    "대구":300,
    # 경상남도
    "창원":385,"진주":370,"통영":415,"사천":395,"김해":395,"밀양":340,
    "거제":435,"양산":375,"의령":370,"함안":385,"창녕":345,"고성(경남)":405,
    "남해":415,"하동":395,"산청":365,"함양":350,"거창":330,"합천":345,
    # 부산광역시
    "부산":420,
    # 울산광역시
    "울산":390,
    # 제주특별자치도
    "제주":460,"서귀포":480,
}

# 전국 시·군 좌표 (위도, 경도)
DESTINATION_COORDS = {
    "서울":(37.5665,126.9780),"인천":(37.4563,126.7052),"강화":(37.7473,126.4877),
    "옹진":(37.4463,126.1640),
    # 경기
    "수원":(37.2636,127.0286),"성남":(37.4449,127.1388),"의정부":(37.7381,127.0337),
    "안양":(37.3943,126.9568),"부천":(37.5035,126.7660),"광명":(37.4784,126.8649),
    "평택":(36.9921,127.1128),"동두천":(37.9036,127.0606),"안산":(37.3219,126.8309),
    "고양":(37.6584,126.8320),"과천":(37.4292,126.9874),"구리":(37.5943,127.1296),
    "남양주":(37.6367,127.2165),"오산":(37.1498,127.0773),"시흥":(37.3800,126.8031),
    "군포":(37.3614,126.9352),"의왕":(37.3449,126.9686),"하남":(37.5397,127.2148),
    "용인":(37.2411,127.1776),"파주":(37.7601,126.7798),"이천":(37.2723,127.4349),
    "안성":(37.0078,127.2698),"김포":(37.6153,126.7156),"화성":(37.1997,126.8312),
    "광주":(37.4294,127.2550),"양주":(37.7855,127.0457),"포천":(37.8948,127.2003),
    "여주":(37.2982,127.6374),"연천":(38.0961,127.0745),"가평":(37.8314,127.5097),
    "양평":(37.4916,127.4875),
    # 강원
    "춘천":(37.8813,127.7298),"원주":(37.3422,127.9202),"강릉":(37.7519,128.8761),
    "동해":(37.5245,129.1143),"태백":(37.1641,128.9856),"속초":(38.2070,128.5918),
    "삼척":(37.4497,129.1658),"홍천":(37.6970,127.8882),"횡성":(37.4918,127.9841),
    "영월":(37.1838,128.4616),"평창":(37.3706,128.3896),"정선":(37.3801,128.6601),
    "철원":(38.1467,127.3137),"화천":(38.1061,127.7081),"양구":(38.1097,127.9895),
    "인제":(38.0694,128.1702),"고성(강원)":(38.3805,128.4677),"양양":(38.0754,128.6180),
    # 충북
    "청주":(36.6424,127.4890),"충주":(36.9910,127.9259),"제천":(37.1326,128.1905),
    "보은":(36.4896,127.7295),"옥천":(36.3063,127.5711),"영동":(36.1750,127.7783),
    "진천":(36.8554,127.4356),"괴산":(36.8153,127.7874),"음성":(36.9398,127.6902),
    "단양":(36.9848,128.3649),"증평":(36.7855,127.5814),
    # 충남
    "천안":(36.8151,127.1139),"공주":(36.4465,127.1189),"보령":(36.3330,126.6129),
    "아산":(36.7898,127.0020),"서산":(36.7848,126.4503),"논산":(36.1873,127.0988),
    "계룡":(36.2742,127.2489),"당진":(36.8895,126.6298),"금산":(36.1088,127.4882),
    "부여":(36.2757,126.9096),"서천":(36.0798,126.6911),"청양":(36.4593,126.8022),
    "홍성":(36.6014,126.6607),"예산":(36.6826,126.8452),"태안":(36.7455,126.2981),
    "세종":(36.4801,127.2890),
    # 대전
    "대전":(36.3504,127.3845),
    # 전북
    "전주":(35.8242,127.1480),"군산":(35.9678,126.7368),"익산":(35.9483,126.9577),
    "정읍":(35.5699,126.8563),"남원":(35.4164,127.3897),"김제":(35.8033,126.8803),
    "완주":(35.9055,127.1632),"진안":(35.7923,127.4248),"무주":(35.9065,127.6607),
    "장수":(35.6474,127.5213),"임실":(35.6175,127.2891),"순창":(35.3745,127.1376),
    "고창":(35.4357,126.7022),"부안":(35.7319,126.7329),
    # 전남
    "목포":(34.8118,126.3922),"여수":(34.7604,127.6622),"순천":(34.9507,127.4872),
    "나주":(35.0160,126.7107),"광양":(34.9407,127.6958),"담양":(35.3215,126.9881),
    "곡성":(35.2822,127.2919),"구례":(35.2025,127.4626),"고흥":(34.6111,127.2763),
    "보성":(34.7716,127.0801),"화순":(35.0643,126.9866),"장흥":(34.6818,126.9073),
    "강진":(34.6420,126.7679),"해남":(34.5730,126.5990),"영암":(34.8003,126.6962),
    "무안":(34.9899,126.4819),"함평":(35.0651,126.5179),"영광":(35.2771,126.5121),
    "장성":(35.3025,126.7898),"완도":(34.3140,126.7553),"진도":(34.4868,126.2636),
    "신안":(34.8300,126.1080),
    # 광주
    "광주":(35.1595,126.8526),
    # 경북
    "포항":(36.0190,129.3435),"경주":(35.8562,129.2247),"김천":(36.1398,128.1136),
    "안동":(36.5684,128.7294),"구미":(36.1195,128.3444),"영주":(36.8057,128.6235),
    "영천":(35.9734,128.9383),"상주":(36.4106,128.1592),"문경":(36.5869,128.1867),
    "경산":(35.8248,128.7417),"군위":(36.2394,128.5724),"의성":(36.3527,128.6970),
    "청송":(36.4358,129.0568),"영양":(36.6668,129.1122),"영덕":(36.4152,129.3652),
    "청도":(35.6478,128.7355),"고령":(35.7264,128.2634),"성주":(35.9196,128.2831),
    "칠곡":(35.9955,128.4013),"예천":(36.6579,128.4516),"봉화":(36.8935,128.9327),
    "울진":(36.9930,129.4006),"울릉":(37.4845,130.9057),
    # 대구
    "대구":(35.8714,128.6014),
    # 경남
    "창원":(35.2279,128.6811),"진주":(35.1800,128.1076),"통영":(34.8544,128.4330),
    "사천":(35.0036,128.0644),"김해":(35.2342,128.8811),"밀양":(35.5038,128.7463),
    "거제":(34.8800,128.6211),"양산":(35.3350,129.0337),"의령":(35.3222,128.2616),
    "함안":(35.2728,128.4068),"창녕":(35.5444,128.4921),"고성(경남)":(34.9731,128.3228),
    "남해":(34.8378,127.8923),"하동":(35.0674,127.7514),"산청":(35.4153,127.8741),
    "함양":(35.5207,127.7249),"거창":(35.6869,127.9097),"합천":(35.5665,128.1656),
    # 부산
    "부산":(35.1796,129.0756),
    # 울산
    "울산":(35.5384,129.3114),
    # 제주
    "제주":(33.4996,126.5312),"서귀포":(33.2541,126.5601),
}

FALLBACK_FUEL_PRICES = {"휘발유":1652,"경유":1498,"LPG":963}

# 전국 요금소 → 시·군 매핑 (하이패스 영수증 표기 기준)
TOLLGATE_TO_CITY = {
    # 서울
    "서울":"서울","서서울":"서울","동서울":"서울","남서울":"서울","북서울":"서울",
    "한남":"서울","반포":"서울","양재":"서울","잠원":"서울","성산":"서울",
    "공항":"김포","인천공항":"인천",
    # 경기
    "수원":"수원","동수원":"수원","북수원":"수원","남수원":"수원","서수원":"수원",
    "성남":"성남","판교":"성남","분당":"성남",
    "의정부":"의정부","고양":"고양","일산":"고양","덕은":"고양",
    "안양":"안양","군포":"군포","과천":"과천","의왕":"의왕",
    "부천":"부천","광명":"광명","시흥":"시흥","안산":"안산",
    "평택":"평택","안성":"안성","오산":"오산","화성":"화성","향남":"화성",
    "용인":"용인","기흥":"용인","수지":"용인","동탄":"화성",
    "광주":"광주","하남":"하남","남양주":"남양주","구리":"구리",
    "파주":"파주","문산":"파주","김포":"김포","통진":"김포",
    "포천":"포천","동두천":"동두천","양주":"양주","의정부북":"의정부",
    "가평":"가평","춘천ic":"춘천","청평":"가평",
    "이천":"이천","여주":"여주","양평":"양평",
    # 인천
    "인천":"인천","서인천":"인천","남인천":"인천","북인천":"인천",
    "강화":"강화",
    # 강원
    "춘천":"춘천","동춘천":"춘천","남춘천":"춘천",
    "원주":"원주","만종":"원주","문막":"원주",
    "횡성":"횡성","홍천":"홍천",
    "강릉":"강릉","동강릉":"강릉","강릉jc":"강릉",
    "속초":"속초","양양":"양양","고성":"고성(강원)",
    "동해":"동해","삼척":"삼척",
    "영월":"영월","평창":"평창","정선":"정선","태백":"태백",
    "철원":"철원","화천":"화천","인제":"인제","양구":"양구",
    # 충북
    "청주":"청주","북청주":"청주","남청주":"청주","오창":"청주",
    "충주":"충주","금왕":"음성","음성":"음성","증평":"증평",
    "진천":"진천","괴산":"괴산","보은":"보은","옥천":"옥천","영동":"영동",
    "제천":"제천","단양":"단양",
    # 충남
    "천안":"천안","북천안":"천안","남천안":"천안","천안jc":"천안",
    "아산":"아산","탕정":"아산",
    "공주":"공주","논산":"논산","계룡":"계룡",
    "서산":"서산","당진":"당진","홍성":"홍성","예산":"예산",
    "보령":"보령","서천":"서천","청양":"청양","부여":"부여",
    "태안":"태안","금산":"금산",
    # 세종
    "세종":"세종","전의":"세종",
    # 대전
    "대전":"대전","북대전":"대전","남대전":"대전","동대전":"대전","서대전":"대전",
    "유성":"대전","회덕":"대전",
    # 전북
    "전주":"전주","북전주":"전주","남전주":"전주","완주":"완주",
    "익산":"익산","군산":"군산","김제":"김제","정읍":"정읍",
    "남원":"남원","순창":"순창","임실":"임실","장수":"장수",
    "무주":"무주","진안":"진안","고창":"고창","부안":"부안",
    # 전남
    "광양":"광양","순천":"순천","여수":"여수",
    "나주":"나주","목포":"목포","무안":"무안","함평":"함평","영광":"영광",
    "담양":"담양","곡성":"곡성","구례":"구례","화순":"화순",
    "보성":"보성","고흥":"고흥","장흥":"장흥","강진":"강진",
    "해남":"해남","영암":"영암","장성":"장성","완도":"완도",
    "진도":"진도","신안":"신안",
    # 광주
    "광주(광역)":"광주","북광주":"광주","남광주":"광주","동광주":"광주","서광주":"광주",
    # 경북
    "포항":"포항","북포항":"포항","남포항":"포항",
    "경주":"경주","북경주":"경주","남경주":"경주",
    "구미":"구미","북구미":"구미","남구미":"구미","김천":"김천",
    "안동":"안동","영주":"영주","봉화":"봉화","울진":"울진",
    "상주":"상주","문경":"문경","예천":"예천","의성":"의성",
    "군위":"군위","청송":"청송","영양":"영양","영덕":"영덕",
    "영천":"영천","청도":"청도","고령":"고령","성주":"성주","칠곡":"칠곡",
    # 대구
    "대구":"대구","북대구":"대구","남대구":"대구","동대구":"대구","서대구":"대구",
    "다사":"대구","왜관":"칠곡",
    # 경남
    "창원":"창원","북창원":"창원","남창원":"창원","마산":"창원","진해":"창원",
    "진주":"진주","사천":"사천","통영":"통영","고성":"고성(경남)",
    "김해":"김해","장유":"김해","밀양":"밀양",
    "거제":"거제","양산":"양산","물금":"양산",
    "함안":"함안","의령":"의령","창녕":"창녕",
    "남해":"남해","하동":"하동","산청":"산청","함양":"함양",
    "거창":"거창","합천":"합천",
    # 부산
    "부산":"부산","북부산":"부산","남부산":"부산","동부산":"부산","서부산":"부산",
    "기장":"부산","장안":"부산","금정":"부산",
    # 울산
    "울산":"울산","북울산":"울산","남울산":"울산","언양":"울산",
    # 제주
    "제주":"제주","서귀포":"서귀포",
    # 꽃동네(충북 음성군 소재 특수 요금소)
    "꽃동네":"음성",
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
    """
    유가를 가져옵니다.
    1순위: GitHub 저장소 fuel_prices.json (raw.githubusercontent.com)
    2순위: 로컬 fuel_prices.json
    3순위: 예비 데이터
    """
    today = datetime.date.today().strftime("%Y-%m-%d")

    # ── 1순위: GitHub raw로 최신 유가 읽기 ───────
    try:
        raw_url = (
            "https://raw.githubusercontent.com/"
            "pehssg/ai-trip-pass/main/fuel_prices.json"
        )
        r = requests.get(raw_url, timeout=6)
        if r.status_code == 200:
            data    = r.json()
            price   = data.get(fuel_type)
            updated = data.get("updated", "")
            source  = data.get("source", "GitHub")
            if price and 400 < int(price) < 4000:
                freshness = "오늘" if updated == today else f"{updated} 기준"
                return int(price), f"{freshness} · {source}"
    except Exception:
        pass

    # ── 2순위: 로컬 파일 ─────────────────────────
    try:
        json_path = os.path.join(os.path.dirname(__file__), "fuel_prices.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        price   = data.get(fuel_type)
        updated = data.get("updated", "")
        source  = data.get("source", "로컬")
        if price and 400 < int(price) < 4000:
            freshness = "오늘" if updated == today else f"{updated} 기준"
            return int(price), f"{freshness} · {source}"
    except Exception:
        pass

    # ── 3순위: 예비 데이터 ───────────────────────
    return FALLBACK_FUEL_PRICES[fuel_type], "예비 데이터"


# ══════════════════════════════════════════════
# 영수증 분석 (pdfplumber 직접 파싱 — 완전 무료)
# ══════════════════════════════════════════════
def extract_pdf_receipts(file_bytes: bytes) -> list[str]:
    """
    pdfplumber로 PDF를 컬럼별로 분리해 각 영수증 텍스트 리스트를 반환합니다.
    하이패스 영수증은 3단 컬럼 레이아웃이므로 x 좌표로 컬럼을 나눕니다.
    """
    try:
        import pdfplumber
        receipt_texts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue
                W = page.width
                col_w = W / 3

                # x 좌표 기준으로 3컬럼 분리
                cols = {0: [], 1: [], 2: []}
                for w in words:
                    c = min(int(w['x0'] // col_w), 2)
                    cols[c].append(w)

                # 컬럼별 → y 순서로 텍스트 재조합
                for c in [0, 1, 2]:
                    lines = {}
                    for w in cols[c]:
                        y = round(w['top'] / 4) * 4  # 4px 단위 그룹핑
                        lines.setdefault(y, []).append(w)
                    col_text = "\n".join(
                        " ".join(w['text'] for w in sorted(lines[y], key=lambda x: x['x0']))
                        for y in sorted(lines)
                    )
                    # 영수증이 포함된 컬럼만 추가 (KEC 또는 영업소 포함 여부로 판단)
                    if re.search(r"영업소|KEC|통행료|\d종\s*\d", col_text):
                        # 컬럼 안에 여러 영수증이 있을 수 있으므로 블록 분리
                        blocks = re.split(r"(?=하이패스는|영수증\n한국도로공사)", col_text)
                        for block in blocks:
                            if re.search(r"KEC|종\s*[\d,]+\s*원|영업소", block):
                                receipt_texts.append(block.strip())
        return receipt_texts
    except Exception:
        return []


def parse_single_receipt(block: str) -> dict | None:
    """단일 영수증 블록에서 정보를 파싱합니다."""
    # 영업소명
    name_m = re.search(r"한국도로공사\s+(\S+영업소)", block)
    if not name_m:
        name_m = re.search(r"(\S+영업소)", block)
    office = name_m.group(1).strip() if name_m else ""

    # 날짜·시각
    dt_m = re.search(r"(\d{4})년(\d{2})월(\d{2})일\s*(\d{2})시(\d{2})분", block)
    if dt_m:
        y, mo, d, h, mi = dt_m.groups()
        date_str = f"{y}.{mo}.{d}"
        time_str = f"{h}:{mi}"
        dt_obj   = datetime.datetime(int(y), int(mo), int(d), int(h), int(mi))
    else:
        date_str = datetime.date.today().strftime("%Y.%m.%d")
        time_str = ""
        dt_obj   = None

    # 입구영업소
    entry_m = re.search(r"입구영업소\s*:\s*(\S+)", block)
    entry   = entry_m.group(1).strip() if entry_m else None

    # 금액 (KEC 우선)
    amt_m = re.search(r"KEC\s*([\d,]+)\s*원", block)
    if not amt_m:
        amt_m = re.search(r"\d\s*종\s*([\d,]+)\s*원", block)
    if not amt_m:
        amt_m = re.search(r"공급가액\s*:\s*([\d,]+)\s*원", block)
    amount = int(amt_m.group(1).replace(",", "")) if amt_m else 0

    if not office and amount == 0:
        return None

    return {
        "영업소":    office,
        "입구영업소": entry,
        "금액":      amount,
        "날짜":      date_str,
        "시각":      time_str,
        "datetime":  dt_obj,
    }


def parse_receipts(text: str = "", file_bytes: bytes = None) -> dict:
    """
    하이패스 PDF 영수증 전체 파싱.
    - file_bytes가 있으면 컬럼 분리 방식으로 정확하게 파싱
    - text만 있으면 총액 텍스트 기반 파싱으로 폴백
    """
    cities = list(DISTANCE_FROM_SEOUL.keys())
    receipts = []

    # ── 컬럼 분리 방식 (정확) ────────────────────
    if file_bytes:
        blocks = extract_pdf_receipts(file_bytes)
        for block in blocks:
            r = parse_single_receipt(block)
            if r:
                receipts.append(r)

    # ── 폴백: 텍스트 전체 파싱 ──────────────────
    if not receipts and text:
        offices  = re.findall(r"한국도로공사\s+(\S+영업소)", text)
        times_raw = re.findall(r"(\d{4})년(\d{2})월(\d{2})일\s*(\d{2})시(\d{2})분", text)
        entries  = re.findall(r"입구영업소\s*:\s*(\S+)", text)
        kec_amts = re.findall(r"KEC\s*([\d,]+)\s*원", text)
        amounts  = [int(a.replace(",", "")) for a in kec_amts]
        for i, office in enumerate(offices):
            t = times_raw[i] if i < len(times_raw) else None
            receipts.append({
                "영업소":    office,
                "입구영업소": entries[i] if i < len(entries) else None,
                "금액":      amounts[i] if i < len(amounts) else 0,
                "날짜":      f"{t[0]}.{t[1]}.{t[2]}" if t else "",
                "시각":      f"{t[3]}:{t[4]}" if t else "",
                "datetime":  datetime.datetime(int(t[0]),int(t[1]),int(t[2]),int(t[3]),int(t[4])) if t else None,
            })

    # ── 시간순 정렬 ──────────────────────────────
    receipts.sort(key=lambda r: r["datetime"] or datetime.datetime.max)

    # ── 통행료 합계 ──────────────────────────────
    total_toll = sum(r["금액"] for r in receipts)
    # 총액 텍스트로 검증
    total_m = re.search(r"총\s*\d+\s*건\s*/\s*([\d,]+)\s*원", text)
    if total_m:
        total_toll = int(total_m.group(1).replace(",", ""))

    # ── 출장일: 가장 이른 날짜 ─────────────────
    first = receipts[0] if receipts else {}
    trip_date = first.get("날짜") or datetime.date.today().strftime("%Y.%m.%d")

    # ── 출발 요금소: 가장 이른 시각의 입구영업소 ─
    # 입구영업소 = 그 톨게이트에 진입한 출발지
    origin_gate = first.get("입구영업소") or first.get("영업소") or "출발요금소"

    # ── 목적지 판단 로직 ──────────────────────────
    # 입구영업소가 있는 영수증 = 고속도로 진입점 (출발지 정보 포함)
    # 입구영업소가 없는 영수증 = 일반 통과 요금소 (경유지/목적지)
    # 목적지 = 입구영업소 없는 영수증 중 가장 많이 등장하는 영업소
    middle_receipts = [r for r in receipts if not r.get("입구영업소")]

    if middle_receipts:
        # 목적지 판단: 전체 이동 시간의 중간점에 가장 가까운 영수증 영업소
        # (왕복 출장에서 중간점 = 실제 목적지에서 머문 시간대)
        has_dt = [r for r in middle_receipts if r.get("datetime")]
        if has_dt and first.get("datetime") and receipts[-1].get("datetime"):
            start_dt = first["datetime"]
            end_dt   = receipts[-1]["datetime"]
            mid_dt   = start_dt + (end_dt - start_dt) / 2
            closest  = min(has_dt,
                           key=lambda r: abs((r["datetime"] - mid_dt).total_seconds()))
            dest_gate = closest.get("영업소") or "도착요금소"
        else:
            # datetime 없으면 빈도 기준
            from collections import Counter
            names = [r["영업소"].replace("영업소","").strip() for r in middle_receipts]
            dest_gate = Counter(names).most_common(1)[0][0] + "영업소"
    else:
        dest_gate = receipts[-1].get("영업소") or "도착요금소"

    # ── 도시 매핑 ────────────────────────────────
    def find_city(gate):
        # 1. 전체 이름으로 매핑
        city = gate_to_city(gate)
        if city:
            return city
        # 2. 영업소명 내 도시명 직접 검색
        gate_clean = gate.replace("영업소","").replace("한국도로공사","").strip()
        city = gate_to_city(gate_clean)
        if city:
            return city
        # 3. DISTANCE_FROM_SEOUL 키로 직접 매핑
        for c in cities:
            if c in gate:
                return c
        return None

    origin_city = find_city(origin_gate)
    dest_city   = find_city(dest_gate)

    last = receipts[-1] if receipts else {}

    return {
        "trip_date":   trip_date,
        "toll_fee":    total_toll,
        "toll_detail": receipts,
        "origin_gate": origin_gate,
        "dest_gate":   dest_gate,
        "origin_city": origin_city,
        "dest_city":   dest_city,
        "ocr_text":    f"영수증 {len(receipts)}건 인식 | 출발: {origin_gate}({first.get('시각','')}) → 도착: {dest_gate}({last.get('시각','')})",
        "method":      f"pdfplumber 컬럼 분리 파싱 (무료) — {len(receipts)}건",
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
                with st.spinner("📄 PDF 분석 중 (컬럼 분리 파싱)..."):
                    pdf_text = ""
                    try:
                        import pdfplumber
                        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                            pdf_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                    except Exception:
                        pass
                    result = parse_receipts(text=pdf_text, file_bytes=file_bytes)

                if result and result.get("toll_fee", 0) > 0:
                    st.success(f"✅ {result['method']} 완료")
                else:
                    st.warning("⚠️ 일부 항목을 인식하지 못했습니다. 아래에서 직접 수정하세요.")
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

            # ── 세션 저장: selectbox key에 직접 반영 ──
            st.session_state.toll_fee  = result["toll_fee"] if result.get("is_total") else result["toll_fee"] * 2
            st.session_state.trip_date = result["trip_date"]
            cities_tmp = list(DISTANCE_FROM_SEOUL.keys())
            if result.get("origin_city") and result["origin_city"] in cities_tmp:
                st.session_state["sel_origin"] = result["origin_city"]
                st.session_state["ocr_origin_city"] = result["origin_city"]
            if result.get("dest_city") and result["dest_city"] in cities_tmp:
                st.session_state["sel_dest"] = result["dest_city"]
                st.session_state["ocr_dest_city"] = result["dest_city"]

        st.markdown('</div>', unsafe_allow_html=True)

        # ② 출발지·목적지
        st.markdown('<div class="card"><div class="card-title">② 출발지 · 목적지 설정</div>', unsafe_allow_html=True)
        cities = list(DISTANCE_FROM_SEOUL.keys())

        # OCR 인식값 읽기
        ocr_origin = st.session_state.get("ocr_origin_city")
        ocr_dest   = st.session_state.get("ocr_dest_city")

        if ocr_origin or ocr_dest:
            st.caption("✅ 영수증에서 자동 인식 — 필요 시 수정 가능합니다.")

        # index 직접 계산 (key 방식 사용 안 함 → Streamlit rerun 없이도 반영)
        origin_default = cities.index(ocr_origin) if ocr_origin and ocr_origin in cities else 0
        dest_default   = cities.index(ocr_dest)   if ocr_dest   and ocr_dest   in cities else 1

        c1, c2 = st.columns(2)
        with c1:
            origin = st.selectbox("출발지", cities, index=origin_default)
        with c2:
            destination = st.selectbox("목적지", cities, index=dest_default)

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
        car_model  = st.selectbox(
            "차종 선택",
            list(VEHICLE_FUEL_EFFICIENCY.keys()),
            help="브랜드별로 정렬되어 있습니다. 해당 차량이 없으면 유사 차종을 선택하세요.",
        )
        efficiency = VEHICLE_FUEL_EFFICIENCY[car_model]
        st.caption(f"🚘 공인 평균 연비: **{efficiency} km/L**  |  총 {len(VEHICLE_FUEL_EFFICIENCY)}개 차종 등록")
        fuel_type  = st.selectbox("유종 선택", ["휘발유","경유","LPG"])
        st.session_state.fuel_type  = fuel_type
        st.session_state.car_model  = car_model

        # 자동으로 fuel_prices.json에서 현재 유가 로드
        _auto_price, _auto_source = get_opinet_fuel_price(fuel_type)
        if st.session_state.fuel_price == 1650:   # 초기값이면 자동 반영
            st.session_state.fuel_price  = _auto_price
            st.session_state.fuel_source = _auto_source

        cb1, cb2 = st.columns([1,2])
        with cb1:
            if st.button("🔄 유가 새로고침", use_container_width=True):
                price, source = get_opinet_fuel_price(fuel_type)
                st.session_state.fuel_price  = price
                st.session_state.fuel_source = source
                if "예비" in source:
                    st.warning(f"⚠️ {source}: {price:,}원/L")
                else:
                    st.success(f"✅ {source}: {price:,}원/L")
        with cb2:
            manual = st.number_input("유가 직접 입력 (원/L)", min_value=500, max_value=3000,
                                     value=int(st.session_state.fuel_price), step=10)
            st.session_state.fuel_price = manual

        # 현재 유가 출처 표시
        _src = st.session_state.get("fuel_source", "")
        if _src:
            if "예비" in _src:
                st.caption(f"⚠️ {_src} — GitHub Actions 설정 후 자동 업데이트됩니다")
            else:
                st.caption(f"✅ {_src}")

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
            radius  = get_verify_radius(dest_name)

            st.markdown("#### 📏 위치 검증 결과")
            m1, m2 = st.columns(2)
            with m1: st.metric("목적지 좌표", f"{dest_coord[0]:.3f}, {dest_coord[1]:.3f}")
            with m2: st.metric("사진 좌표",   f"{gps_data['lat']:.3f}, {gps_data['lon']:.3f}")
            st.metric("두 지점 간 거리", f"{dist_km:.2f} km",
                      delta=f"허용 반경: {radius:.0f}km ({dest_name} 기준)")
            if dist_km <= radius:
                st.success(
                    f"✅ 정상 증빙 — {dest_name} 내 {dist_km:.2f}km 지점 "
                    f"(허용 반경 {radius:.0f}km 이내)"
                )
            else:
                st.warning(
                    f"⚠️ 위치 불일치 — {dest_name} 중심에서 {dist_km:.2f}km "
                    f"(허용 반경 {radius:.0f}km 초과) · 수기 확인 필요"
                )

    if photo_file and gps_data:
        st.markdown("#### 🗺️ 위치 시각화 지도")
        clat = (dest_coord[0] + gps_data["lat"]) / 2
        clon = (dest_coord[1] + gps_data["lon"]) / 2
        m = folium.Map(location=[clat,clon], zoom_start=11, tiles="CartoDB positron")
        folium.Circle(location=dest_coord, radius=int(radius*1000),
                      color="#1a73e8", fill=True, fill_opacity=0.10,
                      popup=f"목적지: {dest_name} (허용 반경 {radius:.0f}km)").add_to(m)
        folium.Marker(dest_coord, popup=f"🏢 {dest_name}",
                      icon=folium.Icon(color="blue", icon="building", prefix="fa")).add_to(m)
        pc = "green" if dist_km <= radius else "orange"
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
        show_df.style.map(style_row, subset=["상태"]),
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
