# Escape Ops 운영자 UI 통합

## Why

게임마스터는 여러 세션의 진행 상태, 힌트 판정, 직원 호출을 한 화면에서 확인해야 한다. 현재 `/game-master` 화면은 기능 위치만 설명하는 최소 화면이라 실제 운영 흐름과 프로젝트의 Agent 정책을 시연하기 어렵다.

## Goal

- 제공된 Escape Ops UI를 기존 Vite 프론트엔드의 `/game-master` 경로에서 실행한다.
- 기존 `/customer` 경로와 테스트를 유지한다.
- `npm test -- --run`과 `npm run build`를 통과한다.
- 데모 자격 증명이 실제 키로 오인되거나 Secret Scan을 통과하지 못하는 문자열을 제거한다.

### Out of Scope

- FastAPI 및 MCP 실데이터 연결
- 실제 로그인과 역할별 서버 권한 검증
- 영상 스트리밍 및 장비 제어
- 제공된 정적 JavaScript의 React 컴포넌트 전면 재작성

## What

### Happy Path

1. 사용자가 `/game-master`에 접속한다.
2. Escape Ops 입장 화면이 표시된다.
3. 입장 후 실시간 관제, 테마·퍼즐, 힌트 정책, 판정 로그, 연동 관리 데모를 확인한다.
4. `/customer` 링크로 기존 고객 화면에 이동할 수 있다.

### Edge Case

- 영상 자동 재생이 차단되면 poster 이미지가 표시된다.
- JavaScript가 API에 연결되지 않아도 데모 데이터로 화면을 조작할 수 있다.
- 모바일 화면에서는 제공된 반응형 레이아웃을 사용한다.

## How

- 정적 UI는 `frontend/public/escape-ops/`에 둔다.
- React의 `/game-master` 라우트는 같은 출처의 `/escape-ops/index.html`을 `iframe`으로 표시한다.
- 이미지와 영상은 정적 UI 폴더에서 상대 경로로 불러온다.
- 정답 직접 요구 정책은 프로젝트 규칙에 맞게 차단 상태로 표현한다.
- 연동 자격 증명은 실제 형식의 키 대신 명시적인 데모 문자열만 사용한다.

## AC

- Given 프론트엔드가 실행됐을 때, When `/game-master`에 접속하면, Then 제목이 있는 Escape Ops 프레임이 표시된다.
- Given 기존 고객 경로가 있을 때, When `/customer`에 접속하면, Then 기존 힌트 요청 화면이 표시된다.
- Given 정적 UI가 로드됐을 때, When 상대 경로 자산을 요청하면, Then CSS·JavaScript·이미지·영상 파일을 찾을 수 있다.
- Given 정답 직접 요구 로그를 볼 때, When 판정 상태를 확인하면, Then `BLOCKED`로 표시된다.
- Given 저장소 검증을 실행할 때, When 테스트와 빌드를 수행하면, Then 모두 오류 없이 완료된다.

