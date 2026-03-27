from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8888/v1",
    api_key="lm-studio"
)

response = client.chat.completions.create(
    model="gemma-3-12b",
    messages=[{"role": "user", "content": "Sag kurz Hallo auf Deutsch."}],
    max_tokens=50
)

print(response.choices[0].message.content)