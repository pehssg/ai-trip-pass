"""
LLM 연결 모듈 — 모델 비종속 구조

OpenAI 호환 Chat Completions 규격(/v1/chat/completions) 하나만 사용합니다.
주소·모델명·키만 바꾸면 Gemma, EXAONE, Solar, HyperCLOVA X 등
OpenAI 호환 API를 제공하는 어떤 모델로도 교체할 수 있습니다.
(Ollama, vLLM, 행정안전부 AI 공통기반 등 OpenAI 호환 엔드포인트)
"""

import re
import requests

# 화면에서 고르는 사전 설정. 주소·모델명은 설정 화면에서 자유롭게 바꿀 수 있습니다.
PRESETS = {
    "사용 안 함 (규정 검색만)": {"base_url": "", "model": "", "needs_key": False},
    "Ollama · Gemma 3 (로컬 PC)": {
        "base_url": "http://localhost:11434/v1", "model": "gemma3:4b", "needs_key": False},
    "Ollama · EXAONE 3.5 (로컬 PC)": {
        "base_url": "http://localhost:11434/v1", "model": "exaone3.5:7.8b", "needs_key": False},
    "OpenAI 호환 API (직접 입력)": {"base_url": "", "model": "", "needs_key": True},
}

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


class LLMError(Exception):
    pass


class LLMClient:
    """OpenAI 호환 엔드포인트용 최소 클라이언트 (외부 SDK 불필요)."""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: int = 90):
        self.base_url = (base_url or "").rstrip("/")
        self.model = model or ""
        self.api_key = api_key or ""
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.model)

    def label(self) -> str:
        return f"{self.model} @ {self.base_url}" if self.enabled else "규정 검색 전용 (LLM 미연결)"

    def _post(self, messages: list, temperature: float, max_tokens: int) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {"model": self.model, "messages": messages, "temperature": temperature,
                "max_tokens": max_tokens, "stream": False}
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMError(f"연결 실패: {e.__class__.__name__} (주소: {self.base_url})") from e
        if r.status_code != 200:
            err = LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
            err.status = r.status_code
            raise err
        try:
            text = r.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise LLMError("응답 형식이 OpenAI 호환 규격과 다릅니다.") from e
        return _THINK.sub("", text).strip()

    @staticmethod
    def _merge_system(messages: list) -> list:
        """system 역할을 지원하지 않는 모델(예: 일부 Gemma)용: 지시문을 첫 사용자 메시지 앞에 붙임."""
        sys_txt = "\n".join(m["content"] for m in messages if m.get("role") == "system")
        rest = [dict(m) for m in messages if m.get("role") != "system"]
        if sys_txt and rest:
            rest[0]["content"] = f"[지시사항]\n{sys_txt}\n\n{rest[0]['content']}"
        return rest or messages

    def chat(self, messages: list, temperature: float = 0.2, max_tokens: int = 900) -> str:
        """오류 시 한 번 더 시도: system 지시문을 합친 호환 형식 → 잠시 후 재시도."""
        if not self.enabled:
            raise LLMError("LLM이 연결되지 않았습니다.")
        try:
            return self._post(messages, temperature, max_tokens)
        except LLMError as e:
            status = getattr(e, "status", 0)
            if status not in (400, 429, 500, 502, 503, 504):
                raise
            first = e
        import time
        if any(m.get("role") == "system" for m in messages):
            try:
                return self._post(self._merge_system(messages), temperature, max_tokens)
            except LLMError as e2:
                first = e2
        if getattr(first, "status", 0) in (429, 500, 502, 503, 504):
            time.sleep(2)
            return self._post(self._merge_system(messages), temperature, max_tokens)
        raise first

    def list_models(self) -> list:
        """OpenAI 호환 /models 목록(Ollama·Google AI Studio·vLLM 등 지원). 실패 시 LLMError."""
        if not self.base_url:
            raise LLMError("API 주소가 비어 있습니다.")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            r = requests.get(f"{self.base_url}/models", headers=headers, timeout=20)
        except requests.RequestException as e:
            raise LLMError(f"연결 실패: {e.__class__.__name__} (주소: {self.base_url})") from e
        if r.status_code != 200:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
        try:
            data = r.json().get("data", [])
        except ValueError as e:
            raise LLMError("모델 목록 형식이 OpenAI 호환 규격과 다릅니다.") from e
        ids = [str(m.get("id", "")).replace("models/", "", 1) for m in data if m.get("id")]
        # 임베딩·이미지·음성·실시간 전용 모델은 문장 답변에 쓸 수 없으므로 목록에서 뺌
        skip = ("embed", "imagen", "veo", "tts", "aqa", "audio", "image", "live", "speech",
                "transcribe", "computer-use", "robotics", "lyria")
        text_ids = sorted(x for x in ids if not any(k in x.lower() for k in skip))
        return text_ids or sorted(ids)

    def ping(self) -> tuple:
        """연결 테스트: (성공여부, 메시지)"""
        try:
            out = self.chat([{"role": "user", "content": "한 단어로 '정상'이라고만 답하세요."}],
                            max_tokens=20)
            return True, f"응답 확인: {out[:30]}"
        except LLMError as e:
            return False, str(e)
