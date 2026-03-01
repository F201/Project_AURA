import requests
import json

def test_chat_rag():
    print("Testing AURA LLM with RAG Knowledge...")
    url = "http://localhost:8001/api/v1/chat"
    payload = {
        "message": "Summarize the main topics of chapter 1 from the slides.",
        "history": []
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print("\n--- AURA RESPONSE ---")
            print(data.get("text", "No text provided."))
            print("\n--- EMOTION ---")
            print(data.get("emotion", "neutral"))
            print("\n--- TOOLS USED ---")
            print(json.dumps(data.get("tools_used", []), indent=2))
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_chat_rag()
