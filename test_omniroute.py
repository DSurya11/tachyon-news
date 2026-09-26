import httpx
import json

payload = {
    "model": "extraction-combo",
    "messages": [
        {"role": "user", "content": "Extract the tickers from this headline: Apple and Microsoft soar."}
    ],
    "max_tokens": 512
}
r = httpx.post("http://localhost:8000/v1/chat/completions", json=payload)
print(r.status_code)
print(r.text)
