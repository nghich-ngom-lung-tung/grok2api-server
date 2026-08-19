import sys, os, time, json, requests
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "g2a_23add0565c43_0huEvba19LTk2yQbvMQlSchQlVyVzYNr"
BASE_URL = "http://127.0.0.1:8080/v1"

print("="*60)
print("🧪 TEST GỌI API CHAT & TẠO ẢNH TRÊN GROK2API (PORT 8080)")
print("="*60)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Test Chat
print("\n[1] Gửi tin nhắn Chat với Grok...")
chat_payload = {
    "model": "grok-3",
    "messages": [
        {"role": "user", "content": "Xin chào! Bạn là ai?"}
    ]
}

try:
    t0 = time.time()
    res = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=chat_payload, timeout=60)
    print(f"Chat Response [{res.status_code}] ({time.time()-t0:.2f}s):")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print("Chat Error:", e)

# 2. Test Image Generation
print("\n[2] Gửi yêu cầu vẽ ảnh (Imagine FLUX.1)...")
img_payload = {
    "model": "grok-imagine-image",
    "prompt": "Một chú rồng pha lê tuyệt đẹp trên đỉnh núi tuyết, 8k resolution"
}

try:
    t0 = time.time()
    res = requests.post(f"{BASE_URL}/images/generations", headers=headers, json=img_payload, timeout=90)
    print(f"Image Response [{res.status_code}] ({time.time()-t0:.2f}s):")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print("Image Error:", e)
