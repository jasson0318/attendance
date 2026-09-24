"""啟動出勤打卡系統"""
import uvicorn

from backend.app.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=HOST,
        port=PORT,
        reload=False,
    )
