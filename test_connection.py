from openai import OpenAI

client = OpenAI(api_key="REDACTED-ROTATED-KEY")

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("✅ SUCCESS! Key ekdum sahi chal rahi hai!")
except Exception as e:
    print(f"❌ ERROR: {e}")