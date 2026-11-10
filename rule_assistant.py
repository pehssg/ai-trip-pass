"""
출장 서무비서 — 규정 근거 안내 모듈

- 규정·지침 파일(md, txt, pdf, hwpx)을 조문 단위로 나눠 색인합니다.
- 질문과 가까운 조문을 BM25로 찾고, 업무 절차(procedures.json)를 매칭합니다.
- LLM이 연결되어 있으면 근거 조문만으로 답하게 하고, 인용한 조문이 실제로
  검색된 조문인지 검사합니다. LLM이 없으면 절차와 조문을 그대로 보여 줍니다.
- 원본 파일은 읽기만 하고 수정·이동·삭제하지 않습니다.
"""

import io
import json
import math
import os
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field

ARTICLE_RE = re.compile(r"(?m)^\s*(?:#+\s*)?(제\s*\d+\s*조(?:\s*의\s*\d+)?)\s*(?:\(([^)\n]*)\))?")


@dataclass
class Article:
    doc: str          # 문서 제목
    number: str       # 제4조 / 단락 3
    title: str        # (자가용 운임 산정)
    text: str         # 조문 전체

    @property
    def ref(self) -> str:
        return f"{self.doc} {self.number}"

    @property
    def heading(self) -> str:
        return f"{self.number}({self.title})" if self.title else self.number


@dataclass
class RuleDoc:
    name: str              # 파일명
    title: str             # 문서 제목
    articles: list = field(default_factory=list)
    builtin: bool = True   # 기본 탑재 여부


# ─────────────────────────────────────────────
# 문서 읽기
# ─────────────────────────────────────────────
def _hwpx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml", n))
        out = []
        for n in names:
            xml = z.read(n).decode("utf-8", errors="ignore")
            for p in re.findall(r"<hp:p[ >].*?</hp:p>", xml, re.S):
                t = "".join(re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", p, re.S))
                t = re.sub(r"<[^>]+>", "", t)
                t = (t.replace("&lt;", "<").replace("&gt;", ">")
                      .replace("&amp;", "&").strip())
                if t:
                    out.append(t)
        return "\n".join(out)


def read_text(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".md", ".txt"):
        for enc in ("utf-8", "cp949"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="ignore")
    if ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    if ext == ".hwpx":
        return _hwpx_text(data)
    raise ValueError(f"지원하지 않는 형식입니다: {ext} (md, txt, pdf, hwpx 지원)")


def split_articles(doc_title: str, text: str) -> list:
    """'제N조(제목)' 단위로 나눕니다. 조문 표기가 없으면 단락 단위로 나눕니다."""
    marks = list(ARTICLE_RE.finditer(text))
    arts = []
    if marks:
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[m.start():end].strip()
            num = re.sub(r"\s+", "", m.group(1))
            arts.append(Article(doc_title, num, (m.group(2) or "").strip(), body))
        return arts
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    buf, n = "", 0
    for p in paras:
        buf = f"{buf}\n{p}".strip()
        if len(buf) > 400:
            n += 1
            arts.append(Article(doc_title, f"단락{n}", "", buf))
            buf = ""
    if buf:
        n += 1
        arts.append(Article(doc_title, f"단락{n}", "", buf))
    return arts


def load_doc(filename: str, data: bytes, builtin: bool = True) -> RuleDoc:
    text = read_text(filename, data)
    title = _nfc(os.path.splitext(os.path.basename(filename))[0])
    m = re.search(r"(?m)^#\s+(.+)$", text)
    if m:
        title = m.group(1).strip()
    return RuleDoc(filename, title, split_articles(title, text), builtin)


def load_folder(folder: str) -> list:
    docs = []
    if not os.path.isdir(folder):
        return docs
    for fn in sorted(os.listdir(folder)):
        if os.path.splitext(fn)[1].lower() in (".md", ".txt", ".pdf", ".hwpx"):
            with open(os.path.join(folder, fn), "rb") as f:   # 읽기 전용
                docs.append(load_doc(fn, f.read(), builtin=True))
    return docs


def load_procedures(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("procedures", [])
    except (OSError, ValueError):
        return []


# ─────────────────────────────────────────────
# 검색 (BM25, 한글 2음절 단위)
# ─────────────────────────────────────────────
def tokenize(text: str) -> list:
    words = re.findall(r"[0-9A-Za-z가-힣]+", text.lower())
    toks = []
    for w in words:
        if len(w) <= 2:
            toks.append(w)
        else:
            toks.extend(w[i:i + 2] for i in range(len(w) - 1))
    return toks


class RuleIndex:
    def __init__(self, articles: list, k1: float = 1.4, b: float = 0.75):
        self.articles = articles
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(f"{a.title} {a.title} {a.text}")) for a in articles]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 1
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 4, min_score: float = 0.5) -> list:
        q = tokenize(query)
        scored = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in d:
                    tf = d[t]
                    s += self.idf.get(t, 0) * tf * (self.k1 + 1) / (
                        tf + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg))
            if s >= min_score:
                scored.append((self.articles[i], round(s, 2)))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]


# ─────────────────────────────────────────────
# 업무 절차 매칭
# ─────────────────────────────────────────────
def match_procedure(query: str, procedures: list):
    q = query.replace(" ", "")
    best, best_score = None, 0
    for p in procedures:
        score = sum(1 for kw in p.get("keywords", []) if kw.replace(" ", "") in q)
        if score > best_score:
            best, best_score = p, score
    return best


def basis_articles(proc: dict, articles: list) -> list:
    """절차에 적힌 근거('문서제목 제N조')에 해당하는 조문을 찾습니다."""
    found = []
    for step in proc.get("steps", []):
        for ref in step.get("basis", []):
            num = re.search(r"제\s*\d+\s*조(?:\s*의\s*\d+)?", ref)
            if not num:
                continue
            num = re.sub(r"\s+", "", num.group())
            for a in articles:
                if a.number == num and (a.doc in ref or ref.split(" 제")[0] in a.doc):
                    if a not in found:
                        found.append(a)
    return found


# ─────────────────────────────────────────────
# 답변 구성
# ─────────────────────────────────────────────
SYSTEM_PROMPT = (
    "당신은 공공기관 직원의 서무 업무를 돕는 '출장 서무비서'입니다.\n"
    "규칙:\n"
    "1. 반드시 아래 [업무 절차]와 [규정 발췌]에 적힌 내용만 근거로 답합니다.\n"
    "2. 근거가 된 문장 끝에 [근거: 문서제목 제N조] 형식으로 출처를 붙입니다.\n"
    "3. 자료에 없는 내용은 추측하지 말고 '등록된 규정에서 확인되지 않습니다'라고 답합니다.\n"
    "4. 금액 계산은 하지 말고, 계산이 필요하면 '영수증 처리' 탭을 안내합니다.\n"
    "5. 한국어 공문 어투로 간결하게, 할 일은 순서·기한·필요 서류가 보이게 번호 목록으로 씁니다."
)


def build_messages(query: str, proc, hits: list, base_date=None) -> list:
    ctx = []
    if base_date:
        ctx.append(f"[기준일] 출장일(영수증 기준) {base_date.isoformat()}, 오늘 {__import__('datetime').date.today().isoformat()} "
                   "— 기한이 '복귀 후 N일 이내'이면 실제 날짜로 바꿔 알려 줍니다.")
    if proc:
        lines = [f"[업무 절차] {proc['name']}"]
        for s in proc.get("steps", []):
            lines.append(
                f"{s['order']}. {s['title']} — {s.get('detail','')}"
                f" / 기한: {s.get('deadline','-')} / 서류: {', '.join(s.get('documents', [])) or '-'}"
                f" / 서식: {', '.join(s.get('forms', [])) or '-'}"
                f" / 근거: {', '.join(s.get('basis', [])) or '-'}")
        ctx.append("\n".join(lines))
    if hits:
        ctx.append("[규정 발췌]\n" + "\n\n".join(f"<{a.ref}>\n{a.text}" for a, _ in hits))
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(ctx) + f"\n\n[질문]\n{query}"},
    ]


def check_citations(answer: str, hits: list) -> list:
    """답변이 인용한 조문 중 검색 결과에 없는 것을 돌려줍니다(신뢰성 점검)."""
    cited = {re.sub(r"\s+", "", c) for c in re.findall(r"제\s*\d+\s*조(?:\s*의\s*\d+)?", answer)}
    known = {a.number for a, _ in hits}
    return sorted(cited - known)


def fallback_answer(query: str, proc, hits: list, base_date=None) -> str:
    """LLM 없이 만드는 답변: 절차 + 기한 날짜 + 서식 + 근거 조문 안내."""
    out = []
    if proc:
        out.append(f"**{proc['name']}** 절차로 안내합니다.")
        for s in proc.get("steps", []):
            meta = []
            if s.get("deadline"):
                dd = deadline_date(s["deadline"], base_date)
                meta.append(f"기한 {s['deadline']}" + (f"({format_due(dd)})" if dd else ""))
            if s.get("forms"):
                meta.append("서식 " + ", ".join(s["forms"]))
            if s.get("documents"):
                meta.append("서류 " + ", ".join(s["documents"]))
            if s.get("basis"):
                meta.append("근거 " + ", ".join(s["basis"]))
            tail = f" ({' · '.join(meta)})" if meta else ""
            out.append(f"{s['order']}. {s['title']} — {s.get('detail','')}{tail}")
    if hits:
        out.append("\n관련 조문을 아래 '근거 조문'에 표시했습니다.")
    if not proc and not hits:
        out.append("등록된 규정에서 관련 내용을 찾지 못했습니다. "
                   "'기관 설정' 탭에서 해당 업무의 규정 파일을 추가해 주세요.")
    return "\n".join(out)


# ─────────────────────────────────────────────
# 기한 날짜 계산
# ─────────────────────────────────────────────
import datetime as _dt

WEEKDAY = "월화수목금토일"


def deadline_date(text: str, base_date):
    """'복귀 후 7일 이내' 같은 기한을 실제 날짜로 바꿉니다(기준일 없으면 None)."""
    if not base_date or not text:
        return None
    m = re.search(r"(\d+)\s*일\s*(?:이내|안|까지)", text)
    if m and re.search(r"복귀|출장|후|부터", text):
        return base_date + _dt.timedelta(days=int(m.group(1)))
    return None


def format_due(d) -> str:
    left = (d - _dt.date.today()).days
    tag = f"D-{left}" if left > 0 else ("오늘 마감" if left == 0 else f"{-left}일 지남")
    return f"{d.month}.{d.day}({WEEKDAY[d.weekday()]})까지 · {tag}"


# ─────────────────────────────────────────────
# 서식 관리
# ─────────────────────────────────────────────
FORM_EXT = (".hwpx", ".hwp", ".docx", ".xlsx", ".pdf", ".md", ".txt")


def _nfc(text: str) -> str:
    """한글 파일명 정규화(macOS 등에서 올린 자모 분리형 이름도 같은 글자로 인식)."""
    import unicodedata
    return unicodedata.normalize("NFC", text or "")


def form_title(filename: str) -> str:
    stem = _nfc(os.path.splitext(os.path.basename(filename))[0])
    return re.sub(r"^\[[^\]]*\]\s*", "", stem)          # '[모의]출장명령서' → '출장명령서'


def load_form_folder(folder: str) -> list:
    out = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith(FORM_EXT):
                out.append({"file": _nfc(fn), "title": form_title(fn), "path": os.path.join(folder, fn), "builtin": True})
    return out


def match_forms(names: list, forms: list) -> list:
    """절차에 적힌 서식 이름과 등록된 서식 파일을 이름 일부로 연결합니다."""
    found = []
    for n in names:
        key = _nfc(n).replace(" ", "")
        for f in forms:
            title = _nfc(f["title"]).replace(" ", "")
            if key and (key in title or title in key):
                if f not in found:
                    found.append(f)
    return found


# ─────────────────────────────────────────────
# 규정에서 절차 초안 만들기
# ─────────────────────────────────────────────
DEADLINE_RE = re.compile(r"(?:출발|복귀|출장|납품|검수|신청)?\s*(?:전|후|시)?\s*\d+\s*일\s*(?:이내|안|까지)|출발\s*전|납품\s*시|검수\s*후|당일")
DOC_RE = re.compile(r"[가-힣]{0,10}(?:요청서|명령서|신청서|확인서|조서|명세서|영수증|견적서|사유서|계획서|보고서|현장사진|증빙서류)")
STOP = {"목적", "정의", "적용범위", "시행일", "부칙"}


def draft_procedure_rule_based(doc: RuleDoc) -> dict:
    """LLM 없이 조문 순서대로 절차 초안을 만듭니다(담당자가 확인·수정하는 전제)."""
    steps = []
    for a in doc.articles:
        if a.title in STOP or not a.title:
            continue
        body = re.sub(r"^제\s*\d+\s*조(?:\s*의\s*\d+)?\s*(?:\([^)]*\))?", "", a.text).strip()
        first = re.split(r"(?<=다)\.\s|\n", body)[0].strip()
        dl = DEADLINE_RE.search(body)
        docs = sorted({d for d in DOC_RE.findall(body) if len(d) >= 3})[:4]
        steps.append({"order": len(steps) + 1, "title": a.title, "detail": first[:120],
                      "deadline": dl.group().strip() if dl else "", "documents": docs, "forms": [],
                      "basis": [f"{doc.title} {a.number}"]})
    kw = set()
    for w in re.findall(r"[가-힣]{2,}", doc.title):
        if any(x in w for x in ("모의", "업무", "처리", "지침", "규정")):
            continue
        kw.update({w, w[:2], w[-2:]})
    kw = sorted(kw)
    return {"id": f"draft_{abs(hash(doc.title)) % 10**6}", "name": re.sub(r"^\[[^\]]*\]\s*", "", doc.title).replace("업무처리 지침", "").strip() or doc.title,
            "keywords": kw, "steps": steps, "draft_by": "규칙 기반 초안"}


PROC_PROMPT = (
    "아래 규정 조문만 근거로, 담당자가 실제로 따라 할 업무 절차를 JSON 하나로만 답하세요. 설명·코드블록 표시 없이 JSON만 씁니다.\n"
    '형식: {"name": "업무 이름", "keywords": ["사용자가 말할 법한 단어"], "steps": [{"order": 1, "title": "할 일", '
    '"detail": "한 문장 설명", "deadline": "기한(없으면 빈 문자열)", "documents": ["필요 서류"], "forms": ["서식 이름"], '
    '"basis": ["문서제목 제N조"]}]}\n'
    "규칙: 조문에 없는 내용은 만들지 않습니다. basis에는 실제 조문 번호만 씁니다. 단계는 시간 순서로 3~8개입니다."
)


def build_procedure_messages(doc: RuleDoc) -> list:
    body = "\n\n".join(f"<{a.ref}>\n{a.text}" for a in doc.articles)[:9000]
    return [{"role": "system", "content": PROC_PROMPT},
            {"role": "user", "content": f"[문서제목] {doc.title}\n\n{body}"}]


def parse_procedure_json(text: str, doc: RuleDoc) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("LLM 응답에서 JSON을 찾지 못했습니다.")
    proc = json.loads(m.group())
    known = {a.number for a in doc.articles}
    for i, st_ in enumerate(proc.get("steps", []), 1):
        st_["order"] = i
        for k in ("documents", "forms", "basis"):
            st_[k] = [x for x in (st_.get(k) or []) if isinstance(x, str)]
        # 실제로 없는 조문을 근거로 든 경우 표시
        bad = [b for b in st_["basis"] if (re.search(r"제\s*\d+\s*조(?:\s*의\s*\d+)?", b) or [None])[0] is not None
               and re.sub(r"\s+", "", re.search(r"제\s*\d+\s*조(?:\s*의\s*\d+)?", b).group()) not in known]
        if bad:
            st_["detail"] = (st_.get("detail", "") + f" [근거 확인 필요: {', '.join(bad)}]").strip()
    proc.setdefault("keywords", [])
    proc["id"] = f"draft_{abs(hash(doc.title)) % 10**6}"
    proc["draft_by"] = "LLM 초안"
    return proc
