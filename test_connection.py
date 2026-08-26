import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("❌ OPENAI_API_KEY not set. Add it to your .env file first.")

client = OpenAI(api_key=api_key)

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("✅ SUCCESS! Key ekdum sahi chal rahi hai!")
except Exception as e:
    print(f"❌ ERROR: {e}")
