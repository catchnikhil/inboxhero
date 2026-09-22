# probe_genai.py
import inspect, json, os
import google.generativeai as genai
from config import Config

def list_attrs(obj):
    return sorted([n for n in dir(obj) if not n.startswith("_")])

print("genai top-level attrs:")
print(", ".join(list_attrs(genai)))

for name in ("chat","models","generate_text","generate","chat_response","TextGenerationClient"):
    if hasattr(genai, name):
        print(f"FOUND: genai.{name}")

if hasattr(genai, "chat"):
    print("\ngenai.chat attrs:", ", ".join(list_attrs(genai.chat)))
    if hasattr(genai.chat, "create"):
        print("genai.chat.create signature:", inspect.signature(genai.chat.create))

if hasattr(genai, "models"):
    print("\ngenai.models attrs:", ", ".join(list_attrs(genai.models)))
    if hasattr(genai.models, "generate"):
        print("genai.models.generate signature:", inspect.signature(genai.models.generate))

if hasattr(genai, "generate_text"):
    print("genai.generate_text signature:", inspect.signature(genai.generate_text))

print("\nENV:")
print("GEMINI_API_KEY set:", bool(os.getenv("GEMINI_API_KEY")))
try:
    Config.validate()
except Exception as e:
    print("Config.validate() warning:", e)
