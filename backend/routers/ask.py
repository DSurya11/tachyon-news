"""
POST /ask: a question about the news, answered by the agent in backend/ask.py.

The dashboard is reachable from the internet, and every question costs model calls on free
tiers, so: signed-in users only (main.py), 300 characters, ASK_PER_USER_HOUR questions per
account an hour, ASK_DAILY_TOTAL for everyone together a day, and a repeated question within
10 minutes gets the stored answer. Limits live in this process's memory (one API process).
"""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import ask
from backend.auth import CurrentUser, current_user
from backend.db import get_db
from backend.routers.news import get_news
from pipeline.config import settings

router = APIRouter(tags=["ask"])

_lock = threading.Lock()
_per_user: dict[int, deque] = defaultdict(deque)
_daily = {"day": None, "count": 0}
_answers: TTLCache = TTLCache(maxsize=256, ttl=600)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=300)


def _key(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()


def _admit(user_id: int) -> None:
    """Count one question against the limits, or refuse it with 429."""
    now = time.monotonic()
    today = datetime.now(UTC).date()
    with _lock:
        recent = _per_user[user_id]
        while recent and now - recent[0] > 3600:
            recent.popleft()
        if len(recent) >= settings.ask_per_user_hour:
            wait = int(3600 - (now - recent[0])) // 60 + 1
            raise HTTPException(status_code=429, detail=f"{settings.ask_per_user_hour} questions an hour; try again in {wait} min")
        if _daily["day"] != today:
            _daily.update(day=today, count=0)
        if _daily["count"] >= settings.ask_daily_total:
            raise HTTPException(status_code=429, detail="Ask has answered its questions for today; it is back tomorrow")
        recent.append(now)
        _daily["count"] += 1


def reset_limits() -> None:
    with _lock:
        _per_user.clear()
        _daily.update(day=None, count=0)
        _answers.clear()


@router.post("/ask")
def post_ask(body: Question, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """The answer, the stories it cites (same shape as /news) and a short trace of the steps."""
    key = _key(body.question)
    if key in _answers:
        return {**_answers[key], "cached": True}
    _admit(user.id)
    result = ask.ask(body.question, db)
    stories = []
    if result.story_ids:
        found = get_news(window=(None, None), sector=None, ticker=None, trading_day=None, q=None, market=None,
                         status="verified,extracted", sentiment=None, event=None, verified_only=False, picks=False,
                         ids=",".join(map(str, result.story_ids)), page=1, limit=len(result.story_ids), db=db)
        by_id = {a["id"]: a for a in found["articles"]}
        stories = [by_id[i] for i in result.story_ids if i in by_id]
    out = {
        "answer": result.answer,
        "stories": stories,
        "stopped": result.stopped,
        "total_matching": result.total_matching,
        "unchecked": result.unchecked,
        "steps": [{k: s[k] for k in ("kind", "tool", "arguments", "failed", "model") if k in s} for s in result.steps],
        "tokens": result.tokens_in + result.tokens_out,
        "seconds": result.seconds,
    }
    if result.stopped == "answered":
        _answers[key] = out
    return {**out, "cached": False}
