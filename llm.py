from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def test_gemini():
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Who is Messi?"
    )
    print(response.text)

test_gemini()