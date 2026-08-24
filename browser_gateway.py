"""
browser_gateway.py — Máy chủ REST API thông minh xử lý Toàn bộ Tạo ảnh, Sửa ảnh & Media
─────────────────────────────────────────────────────────────────────────────
Chạy trên cổng 8085:
- POST /v1/images/generations  ➔ Hỗ trợ cả 2 chế độ:
                                   • Chỉ có Text Prompt  ➔ Tự động vẽ ảnh mới từ chữ (Text-to-Image)
                                   • Có kèm File/URL ảnh ➔ Tự động Redesign biến đổi ảnh (Image-to-Image)
- POST /v1/images/edits        ➔ Sửa ảnh / Redesign ảnh chuẩn OpenAI
- GET  /v1/media/images/{id}   ➔ Phục vụ ảnh trực tiếp (Static Media Serving)
- GET  /v1/media/videos/{id}   ➔ Phục vụ video trực tiếp
- POST /v1/videos/generations  ➔ Tạo Video
- GET  /v1/videos/{id}         ➔ Truy vấn Video
"""
import os
import time
import uuid
import threading
import base64
import requests
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Request, Response, BackgroundTasks, Form, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import browser_worker

app = FastAPI(title="Grok Smart Gateway", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS_STORE: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
GO_BACKEND_URL = "http://127.0.0.1:8080"


def verify_auth(authorization: Optional[str] = Header(None)):
    if not authorization:
        return "anonymous"
    return authorization.replace("Bearer ", "").strip()


@app.on_event("startup")
def startup_event():
    """Khởi động sẵn Chrome chạy ngầm khi bật server."""
    def prewarm():
        try:
            print("[Gateway] 🚀 Đang khởi động sẵn Chrome chạy ngầm...")
            browser_worker.BROWSER_MANAGER.get_or_create_page()
            print("[Gateway] ✅ Chrome chạy ngầm đã sẵn sàng tiếp nhận request!")
        except Exception as e:
            print(f"[Gateway] ⚠️ Lỗi khởi động Chrome ngầm: {e}")
    threading.Thread(target=prewarm, daemon=True).start()


@app.get("/healthz")
def health_check():
    return {
        "status": "ok",
        "service": "Grok Smart Gateway",
        "timestamp": int(time.time()),
        "active_jobs": len([j for j in JOBS_STORE.values() if j.get("status") == "in_progress"])
    }


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "grok-chat-fast", "object": "model", "owned_by": "xai"},
            {"id": "grok-4.5", "object": "model", "owned_by": "xai"},
            {"id": "grok-imagine-image", "object": "model", "owned_by": "xai"},
            {"id": "grok-imagine-image-edit", "object": "model", "owned_by": "xai"},
            {"id": "grok-imagine-video", "object": "model", "owned_by": "xai"}
        ]
    }


# ==============================================================================
# 0. ENDPOINT CHAT & CODE COMPLETIONS (/v1/chat/completions)
# ==============================================================================
class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "grok-chat-fast"
    messages: List[ChatMessage]
    stream: Optional[bool] = False


@app.post("/v1/chat/completions")
async def handle_chat_completion(
    req: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
    verify_auth(authorization)
    
    # Extract last user message
    user_prompt = ""
    for m in reversed(req.messages):
        if m.role == "user":
            if isinstance(m.content, str):
                user_prompt = m.content
            elif isinstance(m.content, list):
                for part in m.content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        user_prompt += part.get("text", "")
            break
            
    if not user_prompt:
        user_prompt = "Hello"
        
    print(f"[Gateway] 💬 Nhận request chat: \"{user_prompt[:80]}...\" (stream={req.stream})")
    
    import anyio
    try:
        reply_text = await anyio.to_thread.run_sync(browser_worker.execute_chat, user_prompt)
    except Exception as e:
        print(f"[Gateway] ❌ Lỗi chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())
    
    if req.stream:
        def stream_generator():
            chunk_size = 15
            for i in range(0, len(reply_text), chunk_size):
                part = reply_text[i:i+chunk_size]
                chunk_data = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": req.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": part},
                            "finish_reason": None
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                time.sleep(0.03)
                
            done_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            }
            yield f"data: {json.dumps(done_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        import json
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
        
    return {
        "id": req_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply_text
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(user_prompt) // 4,
            "completion_tokens": len(reply_text) // 4,
            "total_tokens": (len(user_prompt) + len(reply_text)) // 4
        }
    }



# ==============================================================================
# 1. ENDPOINT TẠO ẢNH & REDESIGN ĐA NĂNG (/v1/images/generations & /v1/images/edits)
# ==============================================================================
@app.post("/v1/images/generations")
@app.post("/v1/images/edits")
async def handle_images_request(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    verify_auth(authorization)
    content_type = request.headers.get("content-type", "")

    prompt = ""
    image_input = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        prompt = form.get("prompt", "")
        file_obj = form.get("image") or form.get("file")
        if file_obj and hasattr(file_obj, "read"):
            content = await file_obj.read()
            b64 = base64.b64encode(content).decode("utf-8")
            image_input = f"data:image/jpeg;base64,{b64}"
        elif form.get("image_url"):
            image_input = str(form.get("image_url"))
    else:
        try:
            body_data = await request.json()
            prompt = body_data.get("prompt", "")
            img_val = body_data.get("image") or body_data.get("images") or body_data.get("image_url")
            if isinstance(img_val, dict):
                image_input = img_val.get("url") or img_val.get("b64_json")
            elif isinstance(img_val, list) and img_val:
                first = img_val[0]
                image_input = first.get("url") if isinstance(first, dict) else str(first)
            elif isinstance(img_val, str):
                image_input = img_val
        except Exception:
            raise HTTPException(status_code=400, detail="JSON không hợp lệ")

    if not prompt:
        raise HTTPException(status_code=400, detail="Trường 'prompt' là bắt buộc")

    action_name = "Redesign ảnh (Image-to-Image)" if image_input else "Tạo ảnh mới (Text-to-Image)"
    print(f"[Gateway] 🎨 Nhận request {action_name}: \"{prompt}\"")

    try:
        import anyio
        result = await anyio.to_thread.run_sync(browser_worker.execute_image_edit, prompt, image_input)
        return {
            "created": int(time.time()),
            "data": [
                {
                    "url": result["url"]
                }
            ]
        }
    except Exception as e:
        print(f"[Gateway] ❌ Lỗi xử lý ảnh: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 2. ENDPOINTS: PHỤC VỤ STATIC MEDIA (IMAGES & VIDEOS)
# ==============================================================================
@app.get("/v1/media/images/{asset_id}")
def serve_image_file(asset_id: str):
    """Phục vụ file ảnh tĩnh cho trình duyệt và client."""
    # Tìm kiếm file trong thư mục media cục bộ
    for ext in ["", ".jpg", ".jpeg", ".png", ".webp"]:
        cand = os.path.join(browser_worker.MEDIA_IMAGES_DIR, asset_id + ext)
        if os.path.exists(cand) and os.path.isfile(cand):
            return FileResponse(cand, media_type="image/jpeg")

    # Nếu không tìm thấy cục bộ, thử chuyển tiếp sang Go Backend (Port 8080)
    try:
        r = requests.get(f"{GO_BACKEND_URL}/v1/media/images/{asset_id}", timeout=10)
        if r.status_code == 200:
            return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Không tìm thấy file ảnh")


@app.get("/v1/media/videos/{filename}")
def serve_video_file(filename: str):
    file_path = os.path.join(browser_worker.VIDEOS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file video")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)


# ==============================================================================
# 3. ENDPOINTS: TẠO VÀ TRUY VẤN VIDEO (VIDEO GENERATION & POLLING)
# ==============================================================================
class VideoGenRequest(BaseModel):
    model: Optional[str] = "grok-imagine-video"
    prompt: str
    duration: Optional[int] = 5
    aspect_ratio: Optional[str] = "16:9"
    image_url: Optional[str] = None


def background_video_worker(job_id: str, prompt: str, duration: int, aspect_ratio: str, image_url: Optional[str]):
    with JOBS_LOCK:
        JOBS_STORE[job_id]["status"] = "in_progress"
        JOBS_STORE[job_id]["progress"] = 10

    def on_progress(p, msg):
        with JOBS_LOCK:
            if job_id in JOBS_STORE:
                JOBS_STORE[job_id]["progress"] = p
                JOBS_STORE[job_id]["message"] = msg

    try:
        res = browser_worker.execute_image_edit(prompt, image_url, progress_callback=on_progress)
        with JOBS_LOCK:
            JOBS_STORE[job_id]["status"] = "completed"
            JOBS_STORE[job_id]["progress"] = 100
            JOBS_STORE[job_id]["url"] = res["url"]
            JOBS_STORE[job_id]["completed_at"] = int(time.time())
    except Exception as e:
        with JOBS_LOCK:
            JOBS_STORE[job_id]["status"] = "failed"
            JOBS_STORE[job_id]["error"] = str(e)


@app.post("/v1/videos/generations")
def create_video_job(
    req: VideoGenRequest,
    authorization: Optional[str] = Header(None)
):
    verify_auth(authorization)
    if not req.prompt:
        raise HTTPException(status_code=400, detail="Trường 'prompt' là bắt buộc")

    job_id = f"video_{uuid.uuid4().hex[:16]}"
    now = int(time.time())

    with JOBS_LOCK:
        JOBS_STORE[job_id] = {
            "id": job_id,
            "prompt": req.prompt,
            "status": "in_progress",
            "progress": 5,
            "message": "Đang chuẩn bị phiên duyệt...",
            "created_at": now,
            "url": None,
            "error": None
        }

    t = threading.Thread(
        target=background_video_worker,
        args=(job_id, req.prompt, req.duration, req.aspect_ratio, req.image_url),
        daemon=True
    )
    t.start()

    return {
        "request_id": job_id,
        "status": "in_progress",
        "created_at": now
    }


@app.get("/v1/videos/{request_id}")
def get_video_job(
    request_id: str,
    authorization: Optional[str] = Header(None)
):
    verify_auth(authorization)
    with JOBS_LOCK:
        job = JOBS_STORE.get(request_id)
        if not job:
            raise HTTPException(status_code=404, detail="Không tìm thấy Video Job với request_id này")
        return job


def run():
    print("=" * 65)
    print("🚀 GROK SMART API GATEWAY ĐANG CHẠY TRÊN CỔNG 8085")
    print("📡 Endpoints hỗ trợ:")
    print("   • POST /v1/images/generations (Text-to-Image & Image Redesign)")
    print("   • POST /v1/images/edits")
    print("   • GET  /v1/media/images/{asset_id}")
    print("   • POST /v1/videos/generations")
    print("=================================================================")
    uvicorn.run(app, host="127.0.0.1", port=8085, log_level="info")


if __name__ == "__main__":
    run()
