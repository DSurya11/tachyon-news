from openai import OpenAI
from pipeline.config import settings
from pipeline.extract.prompt import SYSTEM_PROMPT, build_user_prompt

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="my-secret-key",
    timeout=60.0,
    max_retries=0,
)

user_msg = build_user_prompt("Berkshire Hathaway Buys More Lennar Stock; Now Owns 11% of Big Homebuilder", None)

response = client.chat.completions.create(
    model="extraction-combo",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ],
    max_tokens=4096
)

print(repr(response.choices[0].message.content))
