import httpx
import json
from pipeline.extract.prompt import SYSTEM_PROMPT

payload = {
    "model": "extraction-combo",
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "HEADLINE: Apple and Microsoft soar. BODY: Apple and Microsoft shares went up today after strong earnings. Both companies beat estimates easily."}
    ],
    "max_tokens": 512
}
r = httpx.post("http://localhost:8000/v1/chat/completions", json=payload, timeout=60.0)
print(r.json())
