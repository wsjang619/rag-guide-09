from app.llm import MODEL, client
from app.tools import TOOLS, execute          # 도구 정의와 허용 목록 실행(execute)은 app/tools.py 에 이미 있습니다 (HANDLERS 도 거기)

AGENT_PROMPT = open("prompts/agent.txt", encoding="utf-8").read()
MAX_STEPS = 5
NEEDS_CONFIRM = {"request_leave"}


def text_of(msg: dict) -> str:
    return "".join(b["text"] for b in msg["content"] if "text" in b)


def run(messages: list, user_id: str, today: str) -> dict:
    system = [{"text": AGENT_PROMPT.replace("{today}", today)}]
    for step in range(MAX_STEPS):
        resp = client.converse(modelId=MODEL, system=system, messages=messages,
                               toolConfig=TOOLS, inferenceConfig={"maxTokens": 1024})
        msg = resp["output"]["message"]
        messages.append(msg)
        if resp["stopReason"] != "tool_use":
            return {"type": "answer", "text": text_of(msg), "messages": messages}
        results = []
        for b in msg["content"]:
            if "toolUse" in b:
                tu = b["toolUse"]
                if tu["name"] in NEEDS_CONFIRM:              # 쓰기 작업 → 멈추고 확인 요청
                    return {"type": "confirm", "tool": tu, "messages": messages}
                out = execute(tu["name"], tu["input"], user_id)
                results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"json": out}]}})
        messages.append({"role": "user", "content": results})
    return {"type": "answer", "text": "처리 단계가 너무 많아 중단했습니다.", "messages": messages}

import json, logging, os
from datetime import datetime
from app.tools import today_kst
log = logging.getLogger("agent")


def audit(user_id: str, tool: dict, confirmed: bool, result: dict) -> None:
    """쓰기 작업의 확인 기록. 컨테이너는 파일 시스템이 읽기 전용일 수 있어 stdout 로그가 기본, 파일은 가능할 때만."""
    line = json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "user": user_id, "tool": tool["name"],
                       "input": tool["input"], "confirmed": confirmed, "result": result}, ensure_ascii=False)
    log.info("AUDIT %s", line)
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/agent-audit.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def continue_with_result(p: dict, out: dict, user_id: str) -> dict:
    """확인된 도구의 실행 결과를 모델에게 돌려주고 최종 답을 받는다"""
    messages = p["messages"]
    results = []
    for b in messages[-1]["content"]:                 # 같은 응답의 도구 요청마다 결과가 있어야 한다
        if "toolUse" in b:
            tu = b["toolUse"]
            res = out if tu["toolUseId"] == p["tool"]["toolUseId"] else execute(tu["name"], tu["input"], user_id)
            results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"json": res}]}})
    messages.append({"role": "user", "content": results})
    return run(messages, user_id, today_kst())