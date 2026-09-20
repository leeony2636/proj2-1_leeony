# 로컬 실행 절차
1. `.env.example`을 `.env`로 복사한다.
2. `docker compose up --build`를 실행한다.
3. FastAPI는 http://localhost:8000/docs에서 확인한다.
4. frontend 폴더에서 `npm install` 후 `npm run dev`를 실행한다.
5. 고객 화면은 http://localhost:5173/customer, 게임마스터 화면은 http://localhost:5173/game-master이다.
<!-- 통합 메모: temp-git의 FastAPI 정적 화면 대신 Vite 개발 서버와 Vercel 배포를 기준으로 합니다. -->
