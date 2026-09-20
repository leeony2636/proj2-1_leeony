# AGENTS.md

AI 코딩 에이전트(Claude Code, Codex, Cursor 등)가 이 저장소에서 작업할 때 따르는 공통 지침입니다. 어떤 도구를 쓰든 이 문서를 기준으로 합니다.

## 프로젝트 개요

방탈출 도우미 agent 
방탈출 테마 플레이어의 상황에 맞는 힌트 제공 및 질의응답을 제공
방탈출 테마 마스터의 개입을 최대한 덜어주는 Agent

## 기술 스택
1. 개발 언어: Python / TypeScript / HTML / CSS
2. 백엔드: FastAPI / Pydantic / Uvicorn
3. MCP: FastMCP / Streamable HTTP
4. 데이터 저장: PostgreSQL
5. 프론트엔드: React / TypeScript / Vite
6. 관측·로그: Langfuse
7. 실행·배포: Docker / Docker Compose / Google Cloud Run


## Spec 먼저, 구현은 그다음

기능을 에이전트에게 시키기 전에 `docs/specs/{기능명}.md`에 Spec을 먼저 작성하세요. 형식은 `docs/specs/_example.md` 참고 — 다섯 섹션(Why · Goal · What · How · AC)이 다 있어야 에이전트에게 그대로 넘길 수 있습니다.

- **Why**: 페르소나·상황·문제·측정 지표
- **Goal**: 숫자로 된 성공 기준 + Out of Scope
- **What**: Happy Path + Edge Case
- **How**: API·데이터·제약 (에이전트가 임의 결정할 여지를 없앤다)
- **AC**: Given-When-Then 형식, 테스트 코드로 바로 옮길 수 있어야 함

## Out of Scope 원칙

에이전트는 Spec에 없는 기능을 임의로 추가하지 않습니다. "이왕이면"으로 범위를 넓히지 않습니다.

## 완료 기준

테스트(AC 기준) 통과 없이 "완료"라고 보고하지 않습니다.
