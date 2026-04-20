
import requests
import json

try:
    r = requests.get('http://127.0.0.1:8000/api/admin/store/data', timeout=5)
    data = r.json()
    with open('api_check_result.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("API Check Successful! Saved to api_check_result.json")
except Exception as e:
    print(f"API Check Failed: {e}")
