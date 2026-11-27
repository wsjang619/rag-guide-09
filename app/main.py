import logging
import os


from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request
from app.guard import check_input, check_output
from app.rag import PROMPT, answer
from fastapi import Depends, Header
from app import agent
from app.agent import audit, continue_with_result
from app.tools import execute, today_kst



logging.basicConfig(level=logging.INFO)
app = FastAPI(title="rag-guide")
APP_VERSION = os.environ.get("APP_VERSION", "dev")
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1")


@app.middleware("http")
async def version_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-App-Version"] = APP_VERSION
    resp.headers["X-Prompt-Version"] = PROMPT_VERSION
    return resp


class Question(BaseModel):
    q: str = Field(min_length=2, max_length=10000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask_api(body: Question):
    reason = check_input(body.q)
    if reason:
        raise HTTPException(status_code=400, detail=reason)
    res = answer(body.q)
    res["answer"] = check_output(res["answer"], PROMPT)
    return res

class ChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    text: str = Field(default="", max_length=2000)       # 확인 응답(confirm)에는 text 가 없다
    confirm: bool | None = None                           # 확인 질문에 대한 예(True) · 아니요(False)


class User(BaseModel):
    id: str


def current_user(x_user_id: str | None = Header(default=None)) -> User:
    """실습용: 신원은 요청 본문이 아니라 로그인 정보(헤더)에서 앱이 정한다. 헤더가 없으면 e001"""
    return User(id=x_user_id or "e001")


PENDING: dict[str, dict] = {}   # session_id → 확인 대기 중인 도구 요청 (실습용 메모리 저장)
HISTORY: dict[str, list] = {}   # session_id → 대화 메시지


def history(session_id: str) -> list:
    return HISTORY.get(session_id, [])


def user_msg(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


@app.post("/chat")
def chat(body: ChatIn, user: User = Depends(current_user)):
    if body.confirm is not None and body.session_id in PENDING:
        p = PENDING.pop(body.session_id)
        if not body.confirm:
            audit(user.id, p["tool"], confirmed=False, result={"cancelled": True})
            HISTORY.pop(body.session_id, None)
            return {"type": "answer", "text": "신청을 취소했습니다."}
        out = execute(p["tool"]["name"], p["tool"]["input"] | {"idem_key": body.session_id}, user.id)
        audit(user.id, p["tool"], confirmed=True, result=out)
        res = continue_with_result(p, out, user.id)
        HISTORY[body.session_id] = res["messages"]
        return {"type": res["type"], "text": res.get("text", "")}
    reason = check_input(body.text)
    if reason:
        raise HTTPException(status_code=400, detail=reason)
    if PENDING.pop(body.session_id, None):          # 확인에 답하지 않고 다른 말을 하면 대기 중인 요청을 버린다
        HISTORY.pop(body.session_id, None)
    res = agent.run(history(body.session_id) + [user_msg(body.text)], user.id, today_kst())
    HISTORY[body.session_id] = res["messages"]
    if res["type"] == "confirm":
        PENDING[body.session_id] = res
        t = res["tool"]["input"]
        return {"type": "confirm", "text": f"{t['date']} {t['kind']}을(를) 신청할까요?"}
    return {"type": res["type"], "text": res["text"]}