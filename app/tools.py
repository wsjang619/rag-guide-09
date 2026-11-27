import os
from datetime import date, datetime, timedelta, timezone

from app import hr_client as hr

KST = timezone(timedelta(hours=9))


def today_kst() -> str:
    return os.environ.get("FAKE_TODAY") or datetime.now(KST).date().isoformat()


def _today() -> date:
    return date.fromisoformat(today_kst())


def _parse(s: str) -> date:
    return date.fromisoformat(s)


TOOLS = {"tools": [
    {"toolSpec": {
        "name": "get_leave_balance",
        "description": "현재 로그인한 직원의 잔여 연차 일수를 조회한다.",
        "inputSchema": {"json": {"type": "object", "properties": {}}}}},
    {"toolSpec": {
        "name": "request_leave",
        "description": "휴가를 신청한다. 반드시 사용자 확인 후 실행된다.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "kind": {"type": "string", "enum": ["연차", "반차(오전)", "반차(오후)"]}},
            "required": ["date", "kind"]}}}},
]}


def get_leave_balance(user_id: str) -> dict:
    return hr.balance(user_id)


def request_leave(user_id: str, date: str, kind: str, idem_key: str = "") -> dict:
    d = _parse(date)                                 # 형식 오류 → ValueError
    if d < _today() or d > _today() + timedelta(days=90):
        raise ValueError("신청 가능 기간이 아닙니다")
    if d.weekday() >= 5 or hr.is_holiday(d):
        raise ValueError("휴일에는 신청할 수 없습니다")
    days = 1.0 if kind == "연차" else 0.5
    if hr.balance(user_id)["remaining"] < days:
        raise ValueError("잔여 연차가 부족합니다")
    return hr.create_request(user_id, d, kind, days, idem_key)   # 같은 키 → 같은 결과


HANDLERS = {"get_leave_balance": get_leave_balance, "request_leave": request_leave}


def execute(name: str, args: dict, user_id: str) -> dict:
    if name not in HANDLERS:                       # 허용 목록 밖 도구 → 거절
        return {"error": f"unknown tool {name}"}
    try:
        return HANDLERS[name](user_id=user_id, **args)
    except (TypeError, ValueError) as e:            # 잘못된 인자 → 모델에게 오류로 알림
        return {"error": str(e)[:200]}
