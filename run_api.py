"""
run_api.py — Launch the FastAPI dashboard backend.

Run: python run_api.py
API available at: http://localhost:8000
Docs at:         http://localhost:8000/docs
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
