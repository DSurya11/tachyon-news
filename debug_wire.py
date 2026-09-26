import logging
import httpx
from openai import OpenAI
from pipeline.config import settings
from pipeline.extract.prompt import SYSTEM_PROMPT, build_user_prompt
from pipeline.db.local import LocalSession
from pipeline.db.models import Article

logging.basicConfig(level=logging.DEBUG)

client = OpenAI(
    base_url=settings.omniroute_base_url,
    api_key="my-secret-key",
    timeout=60.0,
    max_retries=0,
    http_client=httpx.Client(event_hooks={'request': [lambda r: print(r.read().decode())]})
)
user_msg = build_user_prompt("Berkshire Hathaway Buys More Lennar Stock; Now Owns 11% of Big Homebuilder", None)
response = client.chat.completions.create(
    model=settings.omniroute_model,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ],
    temperature=0.0,
    max_tokens=4096
)
print("Finish reason:", response.choices[0].finish_reason)
