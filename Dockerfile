# FastAPI/MCP 로컬 실행용 이미지입니다. React 프론트엔드는 Vercel에서 별도 배포합니다.
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY mcp_server/ ./mcp_server/
COPY skills/ ./skills/
EXPOSE 8000 8001
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
