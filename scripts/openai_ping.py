from pathlib import Path
import os
from dotenv import load_dotenv
from openai import OpenAI

def main():
    # Load .env explicitly
    env_path = Path.cwd() / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    key = os.getenv("OPENAI_API_KEY")
    print("CWD:", Path.cwd())
    print(".env:", env_path, "exists:", env_path.exists())
    print("OPENAI_API_KEY loaded:", bool(key))
    if key:
        print("Key prefix:", key[:8] + "...")

    client = OpenAI(api_key=key)

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input="Reply with exactly: OK"
    )

    # Print model output (this is what you were missing)
    print("MODEL OUTPUT:", resp.output_text)

if __name__ == "__main__":
    main()