# Learnbuddy AI — Web version

Bản web này giữ nguyên luồng nghiệp vụ và bố cục giao diện Learnbuddy AI hiện có, thay Streamlit bằng frontend HTML/CSS/JavaScript + FastAPI.

## Chạy local

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn web_app:app --host 0.0.0.0 --port 8501
```

Mở http://localhost:8501

## Deploy Render

Build: `pip install -r requirements.txt`

Start: `uvicorn web_app:app --host 0.0.0.0 --port $PORT`

Thêm `OPENAI_API_KEY` trong Environment Variables.
