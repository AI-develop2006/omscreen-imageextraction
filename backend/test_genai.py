import os
import traceback
from dotenv import load_dotenv
from google import genai

load_dotenv()

key = os.environ.get("GEMINI_API_KEY")
print(f"Key preview: {key[:5]}...{key[-5:]}" if key else "No key")

client = genai.Client(api_key=key)

try:
    print("Attempting to generate content...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Say hello world",
    )
    print("Response:", response.text)
except Exception as e:
    print("FAILED with Exception:")
    traceback.print_exc()
