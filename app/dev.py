"""실습 콘솔용 개발 API (내 PC 전용). 기존 함수 · 명령을 그대로 부르기만 합니다."""
import json, os, re, subprocess, sys, time, urllib.error, urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/dev")
SAFE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,200}$")     # 명령 인자 · 버전 이름에 허용하는 글자


@router.get("/ping")
def ping():
    return {"profile": os.environ.get("AWS_PROFILE"), "region": os.environ.get("AWS_REGION")}


# ---- Lab 2: LLM 호출 ----
class LlmIn(BaseModel):
    system: str = "한 문장으로 답하라"
    user: str
    max_tokens: int = 1024


@router.post("/llm")
def llm(body: LlmIn):
    from app.llm import ask
    r = ask(body.system, body.user, body.max_tokens)
    u = r["usage"]
    r["usd"] = round(u["inputTokens"] * 2 / 1e6 + u["outputTokens"] * 10 / 1e6, 6)
    return r


# ---- Lab 2: 대상 API(로컬 uvicorn · docker · ALB) 호출 중계. Lab 5 부터 사용 ----
class RemoteIn(BaseModel):
    base_url: str
    path: str
    body: dict | None = None
    canary: bool = False


@router.post("/remote")
def remote(r: RemoteIn):
    if r.path not in {"/health", "/ask", "/chat"} or not re.match(r"^https?://[A-Za-z0-9.\-]+(:\d+)?/?$", r.base_url):
        raise HTTPException(400, "허용되지 않은 주소입니다")
    data = None if r.body is None else json.dumps(r.body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(r.base_url.rstrip("/") + r.path, data=data, method="GET" if data is None else "POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if r.canary:
        req.add_header("X-Canary", "1")
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        status, raw, hdr = resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:                   # 400 · 500 도 그대로 화면에 보여 줍니다
        status, raw, hdr = e.code, e.read(), e.headers
    except (urllib.error.URLError, TimeoutError) as e:
        raise HTTPException(502, f"대상 API 에 연결할 수 없습니다: {getattr(e, 'reason', e)}")
    text = raw.decode("utf-8", "replace")
    try:
        payload = json.loads(text)
    except ValueError:
        payload = text
    return {"status": status, "ms": int((time.time() - t0) * 1000), "body": payload,
            "app_version": hdr.get("X-App-Version"), "prompt_version": hdr.get("X-Prompt-Version")}


# ---- Lab 3: 민원 분류 ----
class TextIn(BaseModel):
    text: str


@router.post("/classify")
def classify(body: TextIn):
    from app.classify import classify as run
    return run(body.text)


# ---- Lab 3: 실습 명령 실행 (터미널과 같은 명령을 그대로 실행) ----
RUNNABLE = {
    "run_classify": ["-m", "eval.run_classify"],                         # Lab 3
    "compare_chunks": ["-m", "eval.compare_chunks"],                     # Lab 4
    "run_eval": ["-m", "eval.run_eval"],                                 # Lab 6 · 7 · 12
    "compare": ["-m", "eval.compare"],                                   # Lab 6 (추가, 인자: v1 v2)
}


def _py(args: list[str], env: dict | None = None) -> dict:
    t0 = time.time()
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env={**os.environ, "PYTHONUTF8": "1", **(env or {})}, timeout=1200)
    return {"cmd": "python " + " ".join(args), "code": p.returncode,
            "out": p.stdout + p.stderr, "sec": round(time.time() - t0)}


class RunIn(BaseModel):
    name: str
    args: list[str] = []
    prompt_version: str | None = None


@router.post("/run")
def run_cmd(r: RunIn):
    if r.name not in RUNNABLE or not all(SAFE.match(a) for a in r.args):
        raise HTTPException(400, "허용되지 않은 명령입니다")
    env = {}
    if r.prompt_version:
        if not SAFE.match(r.prompt_version):
            raise HTTPException(400, "잘못된 버전 이름입니다")
        env["PROMPT_VERSION"] = r.prompt_version
    return _py([*RUNNABLE[r.name], *r.args], env)


# ---- Lab 4: 검색 점수 · 답변 ----
class SearchIn(BaseModel):
    q: str
    index: str = "index"
    k: int = 6


@router.post("/search")
def search(body: SearchIn):
    if body.index not in {"index", "index_200", "index_500", "index_1000"}:
        raise HTTPException(400, "허용되지 않은 색인입니다")
    import numpy as np
    from app.index import embed
    vecs = np.load(f"{body.index}/vectors.npy")
    chunks = json.load(open(f"{body.index}/chunks.json", encoding="utf-8"))
    s = vecs @ np.array(embed(body.q), dtype=np.float32)
    top = np.argsort(-s)[: body.k]
    return [{"id": chunks[i]["id"], "score": round(float(s[i]), 3), "text": chunks[i]["text"][:120]} for i in top]


@router.post("/answer")
def answer(body: TextIn):
    from app.rag import answer as run
    return run(body.text)


# ---- Lab 6: 평가 결과 파일 보기 ----
@router.get("/results/{ver}")
def results(ver: str):
    if not re.match(r"^[A-Za-z0-9_]{1,30}$", ver):
        raise HTTPException(400, "잘못된 버전 이름입니다")
    path = f"eval/results/{ver}.json"
    if not os.path.exists(path):
        raise HTTPException(404, "결과 파일이 없습니다. 먼저 평가를 실행하세요")
    return json.load(open(path, encoding="utf-8"))


# ---- Lab 7: 공격 문항 목록 ----
@router.get("/attacks")
def attacks():
    return [json.loads(line) for line in open("eval/attacks.jsonl", encoding="utf-8") if line.strip()]
