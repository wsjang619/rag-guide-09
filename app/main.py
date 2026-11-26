import logging
import os

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request
from app.guard import check_input, check_output
from app.rag import PROMPT, answer


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
    q: str = Field(min_length=2, max_length=2000)


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