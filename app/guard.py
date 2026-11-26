import re

MAX_LEN = 500
BLOCK = [r"(이전|위의?)\s*(지시|명령).{0,10}(무시|잊어)", r"시스템\s*프롬프트",
         r"ignore (all|previous) instructions", r"</?(발췌|질문|schema)"]
ALLOWED_LINK = ("https://intranet.example.com",)
PII = [r"\d{6}-[1-4]\d{6}", r"01[016789]-?\d{3,4}-?\d{4}"]


def check_input(q: str) -> str | None:
    """문제가 있으면 거절 사유, 없으면 None"""
    if len(q) > MAX_LEN:
        return "질문이 너무 깁니다"
    if any(re.search(p, q, re.I) for p in BLOCK):
        return "처리할 수 없는 요청입니다"
    return None


def check_output(answer: str, system_prompt: str) -> str:
    # 1) 시스템 프롬프트 유출: 프롬프트의 긴 문장이 답에 그대로 나오면 차단
    for line in system_prompt.splitlines():
        if len(line) > 20 and line.strip() in answer:
            return "답변을 제공할 수 없습니다."
    # 2) 개인정보 마스킹
    for p in PII:
        answer = re.sub(p, "[개인정보 가림]", answer)
    # 3) 허용되지 않은 링크 제거
    for url in re.findall(r"https?://\S+", answer):
        if not url.startswith(ALLOWED_LINK):
            answer = answer.replace(url, "[링크 제거]")
    return answer