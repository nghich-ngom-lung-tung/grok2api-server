"""
grok_cli.py — Công cụ dòng lệnh CLI chuyên nghiệp cho Grok AI
─────────────────────────────────────────────────────────────
Sử dụng trực tiếp qua API https://api.grokapi.cyou/v1 (hoặc local http://127.0.0.1:8080/v1)

Các tính năng:
  • grok "câu hỏi"                   -> Chat streaming với Grok-3 (Siêu nhanh & thông minh)
  • grok -m grok-3-reasoning "..."   -> Chế độ suy luận logic sâu
  • grok -m grok-3-deepsearch "..."  -> Tìm kiếm web thời gian thực
  • grok --img "prompt vẽ ảnh"       -> Tạo ảnh 4K tự động
  • grok --vision path/to/img "..."  -> Phân tích & đọc ảnh
  • grok -i                          -> Chế độ Chat tương tác liên tục (Interactive Shell)
"""

import os
import sys
import argparse
import json
import base64
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_BASE = os.getenv("GROK_API_BASE", "https://api.grokapi.cyou/v1")
API_KEY = os.getenv("GROK_API_KEY", "g2a_03d12f690dbf_FMCDddgQLRf-3Y1TnmmBM9anlwoWBHqf")

# ANSI Color codes for beautiful terminal UI
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def chat_stream(prompt, model="grok-chat-fast", system_prompt=None, history=None):
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": True
    }

    try:
        r = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
        if r.status_code != 200:
            print(f"\n{YELLOW}[Lỗi API {r.status_code}]: {r.text}{RESET}")
            return ""

        print(f"\n{CYAN}{BOLD}🤖 Grok ({model}):{RESET} ", end="", flush=True)
        full_content = ""
        for line in r.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            print(delta, end="", flush=True)
                            full_content += delta
                    except Exception:
                        pass
        print("\n")
        return full_content
    except Exception as e:
        print(f"\n{YELLOW}[Lỗi kết nối]: {e}{RESET}")
        return ""


def generate_image(prompt):
    url = f"{API_BASE}/images/generations"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "grok-imagine-image",
        "prompt": prompt
    }
    print(f"\n{MAGENTA}🎨 Đang gửi prompt sang Grok Imagine Studio...{RESET}")
    print(f"{DIM}Prompt: \"{prompt}\"{RESET}")
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        if r.status_code == 200:
            data = r.json()
            img_url = data["data"][0]["url"]
            print(f"\n{GREEN}{BOLD}✨ Tạo ảnh thành công!{RESET}")
            print(f"🔗 Link ảnh 4K: {CYAN}{img_url}{RESET}\n")
        else:
            print(f"{YELLOW}[Lỗi {r.status_code}]: {r.text}{RESET}")
    except Exception as e:
        print(f"{YELLOW}[Lỗi kết nối]: {e}{RESET}")


def analyze_vision(img_path, prompt, model="grok-3"):
    if not os.path.exists(img_path):
        print(f"{YELLOW}[!] File ảnh không tồn tại: {img_path}{RESET}")
        return

    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    ext = os.path.splitext(img_path)[1].lower().replace(".", "")
    mime = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
    data_uri = f"data:{mime};base64,{b64}"

    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or "Hãy miêu tả chi tiết bức ảnh này."},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]
            }
        ],
        "stream": True
    }

    print(f"\n{CYAN}{BOLD}👁️ Đang phân tích ảnh với {model}...{RESET}")
    try:
        r = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
        if r.status_code != 200:
            print(f"{YELLOW}[Lỗi {r.status_code}]: {r.text}{RESET}")
            return

        print(f"\n{CYAN}{BOLD}🤖 Grok Vision:{RESET} ", end="", flush=True)
        for line in r.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            print(delta, end="", flush=True)
                    except Exception:
                        pass
        print("\n")
    except Exception as e:
        print(f"{YELLOW}[Lỗi kết nối]: {e}{RESET}")


def interactive_mode(model="grok-3"):
    print(f"{GREEN}{BOLD}══════════════════════════════════════════════════════{RESET}")
    print(f"{GREEN}{BOLD}       🚀 GROK CLI INTERACTIVE CHAT ({model})         {RESET}")
    print(f"{DIM}    Gõ câu hỏi để trò chuyện. Gõ 'exit' hoặc 'quit' để thoát. {RESET}")
    print(f"{GREEN}{BOLD}══════════════════════════════════════════════════════{RESET}\n")

    history = []
    while True:
        try:
            user_input = input(f"{BOLD}User > {RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print(f"{DIM}Tạm biệt! 👋{RESET}")
                break
            if user_input.lower() == "clear":
                history = []
                print(f"{DIM}Đã xóa lịch sử hội thoại.{RESET}\n")
                continue

            response = chat_stream(user_input, model=model, history=history)
            if response:
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": response})
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Tạm biệt! 👋{RESET}")
            break


def main():
    parser = argparse.ArgumentParser(description="Grok AI CLI Client")
    parser.add_argument("prompt", nargs="*", help="Nội dung câu hỏi cần hỏi Grok")
    parser.add_argument("-m", "--model", default="grok-chat-fast", help="Model: grok-chat-fast (mặc định), grok-4.5, grok-4.6, grok-composer-2.5-fast")

    parser.add_argument("-i", "--interactive", action="store_true", help="Bật chế độ chat tương tác liên tục")
    parser.add_argument("--img", "--image", type=str, help="Tạo ảnh với prompt chỉ định")
    parser.add_argument("--vision", type=str, help="Đường dẫn file ảnh cần đọc / phân tích")

    args = parser.parse_args()

    if args.img:
        generate_image(args.img)
        return

    if args.vision:
        prompt_text = " ".join(args.prompt) if args.prompt else "Hãy miêu tả chi tiết hình ảnh này."
        analyze_vision(args.vision, prompt_text, model=args.model)
        return

    if args.interactive or not args.prompt:
        interactive_mode(model=args.model)
        return

    prompt_text = " ".join(args.prompt)
    chat_stream(prompt_text, model=args.model)


if __name__ == "__main__":
    main()
