import sys
import json
import os
import requests
import threading

API_BASE = "http://127.0.0.1:8085/v1"
API_KEY = "g2a_03d12f690dbf_FMCDddgQLRf-3Y1TnmmBM9anlwoWBHqf"

cancel_flag = False
current_workspace_cwd = os.getcwd()

def send_message(msg):
    raw = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(raw + "\n")
    sys.stdout.flush()

def get_workspace_context(cwd, max_files=15):
    """Quét và tóm tắt cấu trúc thư mục repo đang mở trong IDE."""
    if not cwd or not os.path.exists(cwd):
        return ""
    
    ignore_dirs = {".git", ".venv", "node_modules", "__pycache__", "build", "dist", "temp_chrome", ".system_generated"}
    file_list = []
    file_snippets = []
    
    try:
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            rel_root = os.path.relpath(root, cwd)
            for f in files:
                if f.endswith((".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".go", ".html", ".css")):
                    rel_path = f if rel_root == "." else os.path.join(rel_root, f)
                    file_list.append(rel_path)
                    
        # Collect preview of top key files
        for rel_path in file_list[:max_files]:
            full_path = os.path.join(cwd, rel_path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read(1500)
                    file_snippets.append(f"--- File: {rel_path} ---\n{content}\n")
            except Exception:
                pass
    except Exception:
        pass

    summary = f"\n[WORKSPACE REPO CONTEXT]\nDirectory: {cwd}\nFiles found: {', '.join(file_list[:30])}\n\nKey Files Preview:\n" + "\n".join(file_snippets)
    return summary

def handle_prompt_stream(msg_id, session_id, prompt_text, model="grok-4.5", cwd=""):
    global cancel_flag
    cancel_flag = False
    
    ws_context = get_workspace_context(cwd or current_workspace_cwd)
    
    system_prompt = (
        "You are Grok, a world-class AI coding assistant and agent inside Grok Build IDE. "
        "You have full awareness of the user's active codebase, workspace files, and tools. "
        "When the user asks to read, analyze, write, or fix code in their repository, directly inspect "
        "their files from the workspace context provided below, explain your technical solution clearly, "
        "and provide complete, production-ready code implementations."
    )
    
    full_user_content = prompt_text
    if ws_context and any(kw in prompt_text.lower() for kw in ["repo", "code", "đọc", "file", "xem", "dự án", "project", "lỗi", "sửa", "hàm", "class"]):
        full_user_content = f"{prompt_text}\n\n{ws_context}"
    
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model or "grok-4.5",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_user_content}
        ],
        "stream": True
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
        if r.status_code == 200:
            for line in r.iter_lines(decode_unicode=True):
                if cancel_flag:
                    break
                if not line:
                    continue
                if line.startswith("data: "):
                    line = line[6:].strip()
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        # Send ACP agent_message_chunk notification
                        send_message({
                            "jsonrpc": "2.0",
                            "method": "session/update",
                            "params": {
                                "sessionId": session_id,
                                "update": {
                                    "sessionUpdate": "agent_message_chunk",
                                    "content": {
                                        "type": "text",
                                        "text": content
                                    }
                                }
                            }
                        })
                except Exception:
                    pass
        else:
            send_message({
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {
                            "type": "text",
                            "text": f"\n[Grok API Error {r.status_code}]: {r.text[:200]}"
                        }
                    }
                }
            })
    except Exception as e:
        send_message({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {
                        "type": "text",
                        "text": f"\n[Lỗi kết nối]: {str(e)}"
                    }
                }
            }
        })

    # Finished turn
    send_message({
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "stopReason": "end_turn"
        }
    })

def run_acp_server(default_model="grok-4.5"):
    global cancel_flag, current_workspace_cwd
    current_model = default_model
    
    # Configure UTF-8 I/O
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            send_message({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": 1,
                    "serverInfo": {
                        "name": "Grok CLI",
                        "version": "1.0.5"
                    },
                    "capabilities": {
                        "session": True,
                        "tools": True
                    }
                }
            })

        elif method in ["session/new", "session/load"]:
            sess_id = params.get("sessionId", "session-grok-main")
            if "cwd" in params:
                current_workspace_cwd = params["cwd"]
            elif "rootUri" in params:
                current_workspace_cwd = params["rootUri"].replace("file:///", "").replace("/", "\\")
                
            send_message({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "sessionId": sess_id,
                    "configOptions": [],
                    "modes": {
                        "currentModeId": "default",
                        "availableModes": [
                            {
                                "id": "default",
                                "name": "Default",
                                "description": "Standard coding mode"
                            }
                        ]
                    }
                }
            })

        elif method == "session/list":
            send_message({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "sessions": []
                }
            })

        elif method == "session/set_mode" or method == "session/set_model":
            if "model" in params:
                current_model = params["model"]
            if req_id is not None:
                send_message({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                })

        elif method == "session/prompt":
            sess_id = params.get("sessionId", "session-grok-main")
            prompt_data = params.get("prompt", [])
            prompt_text = ""
            if isinstance(prompt_data, list):
                for p in prompt_data:
                    if isinstance(p, dict) and p.get("type") == "text":
                        prompt_text += p.get("text", "")
                    elif isinstance(p, str):
                        prompt_text += p
            elif isinstance(prompt_data, str):
                prompt_text = prompt_data
            
            # Start streaming response with full workspace context in background thread
            t = threading.Thread(target=handle_prompt_stream, args=(req_id, sess_id, prompt_text, current_model, current_workspace_cwd))
            t.daemon = True
            t.start()

        elif method == "session/cancel":
            cancel_flag = True
            if req_id is not None:
                send_message({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                })

        elif method in ["logout", "session/close"]:
            if req_id is not None:
                send_message({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                })
        else:
            if req_id is not None:
                send_message({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                })

if __name__ == "__main__":
    run_acp_server()
