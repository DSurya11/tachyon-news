from openai import OpenAI
from pipeline.config import settings
from pipeline.extract.prompt import SYSTEM_PROMPT, build_user_prompt
from pipeline.db.local import LocalSession
from pipeline.db.models import Article

with LocalSession() as db:
    article = db.query(Article).get(190)

user_msg = build_user_prompt(article.headline, article.body)

client = OpenAI(
    base_url=settings.omniroute_base_url,
    api_key="my-secret-key",
    timeout=60.0,
    max_retries=0,
)

response = client.chat.completions.create(
    model=settings.omniroute_model,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ],
    temperature=0.0,
    max_tokens=4096
)

print(repr(response.choices[0].message.content))
print(response.choices[0].finish_reason)
