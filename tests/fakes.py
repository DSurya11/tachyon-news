"""Stand-ins for external services."""
from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import httpx
from openai import APIConnectionError


class FakeLLM:
    """Mimics `OpenAI().chat.completions.create` with scripted replies.

    `replies` items are strings (message content), exceptions (raised), or
    callables taking the request kwargs and returning either.
    """

    def __init__(self, replies: list | Callable[[dict], object]):
        self.replies = replies
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies(kwargs) if callable(self.replies) else self.replies.pop(0)
        if callable(reply):
            reply = reply(kwargs)
        if isinstance(reply, BaseException):
            raise reply
        message = SimpleNamespace(content=reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], model="fake-model")


def connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "http://localhost:8000/v1/chat/completions"))
