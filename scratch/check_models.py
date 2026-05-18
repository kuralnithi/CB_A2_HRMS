import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"Testing with API Key: {api_key[:10]}...")

genai.configure(api_key=api_key)

print("\nAvailable models:")
try:
    for m in genai.list_models():
        if 'embedContent' in m.supported_generation_methods:
            print(f"- {m.name} (Supports Embedding)")
        else:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
