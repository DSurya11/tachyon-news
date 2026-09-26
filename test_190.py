import httpx
import json
from pipeline.extract.prompt import SYSTEM_PROMPT, build_user_prompt

user_msg = build_user_prompt("Berkshire Hathaway Buys More Lennar Stock; Now Owns 11% of Big Homebuilder", None)

payload = {
    "model": "extraction-combo",
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ],
    "max_tokens": 4096
}

r = httpx.post("http://localhost:8000/v1/chat/completions", json=payload, timeout=60.0)
print(json.dumps(r.json(), indent=2))
