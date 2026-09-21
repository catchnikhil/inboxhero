# Roll Number: evernorth-aai-1177619
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.5-flash-lite")

    @staticmethod
    def validate():
        if not Config.GEMINI_API_KEY:
            raise ValueError("Missing GEMINI_API_KEY in environment variables.")
