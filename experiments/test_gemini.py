import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

response = client.models.generate_content(
    model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
    contents="Explain how AI works in a few words",
)
print(response.text)