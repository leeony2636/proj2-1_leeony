from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
import re
from typing import Any, Coroutine, Protocol, TypeVar
from urllib.parse import urlparse

import httpx

from mcp_server.contract_dispatch import ContractDispatcher, dispatch_tool


T = TypeVar("T")


class MCPTransport(Protocol):
    def call_tool(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]: ...


class MCPToolCallError(RuntimeError):
    """허용된 도메인 코드로 분류할 수 없는 안전한 MCP Tool 오류."""


_DOMAIN_ERROR_CODES = {
    "APPROVED_HINT_NOT_FOUND",
    "IDEMPOTENCY_CONFLICT",
    "PUZZLE_NOT_FOUND",
    "PUZZLE_SEQUENCE_MISMATCH",
    "SESSION_CLOSED",
    "SESSION_NOT_FOUND",
    "TEAM_SESSION_MISMATCH",
}


def _run_sync(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _safe_error_text(content: list[Any]) -> str:
    return " ".join(
        block.text
        for block in content
        if getattr(block, "type", None) == "text" and isinstance(block.text, str)
    )


def _raise_mapped_tool_error(message: str) -> None:
    matched = next(
        (
            code
            for code in _DOMAIN_ERROR_CODES
            if re.search(rf"(?:^|[^A-Z0-9_]){re.escape(code)}(?:$|[^A-Z0-9_])", message)
        ),
        None,
    )
    if matched in {"SESSION_NOT_FOUND", "PUZZLE_NOT_FOUND", "APPROVED_HINT_NOT_FOUND"}:
        raise KeyError(matched)
    if matched in {"TEAM_SESSION_MISMATCH", "SESSION_CLOSED", "PUZZLE_SEQUENCE_MISMATCH"}:
        raise PermissionError(matched)
    if matched == "IDEMPOTENCY_CONFLICT":
        raise ValueError(matched)
    raise MCPToolCallError("MCP_TOOL_FAILED")


def _require_structured_output(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise MCPToolCallError("MCP_INVALID_STRUCTURED_OUTPUT")
    return data


class InProcessMCPTransport:
    """개발·테스트용 로컬 경로. FastMCP와 동일 contract dispatcher를 사용한다."""

    def __init__(self, dispatcher: ContractDispatcher | None = None) -> None:
        self.dispatcher = dispatcher

    def call_tool(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        result = self.dispatcher.dispatch(name, input_data) if self.dispatcher else dispatch_tool(name, input_data)
        return _require_structured_output(result)


class StreamableHTTPMCPTransport:
    """MCP Python SDK의 Streamable HTTP client로 원격 FastMCP 서버를 호출한다."""

    def __init__(self, url: str, timeout_seconds: float = 10.0) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MCP_SERVER_URL_INVALID")
        if timeout_seconds <= 0:
            raise ValueError("MCP_TIMEOUT_INVALID")
        self.url = url
        self.timeout_seconds = timeout_seconds

    async def _call_tool(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        # 실제 원격 전송을 선택했을 때만 SDK 의존성을 import한다. 로컬 회귀 테스트는
        # mcp 패키지가 없어도 contract dispatcher로 실행할 수 있다.
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
        except ImportError as exc:
            raise RuntimeError("MCP_SDK_NOT_INSTALLED") from exc

        timeout = httpx.Timeout(self.timeout_seconds)
        async with create_mcp_http_client(timeout=timeout) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        name,
                        {"input": input_data},
                        read_timeout_seconds=timedelta(seconds=self.timeout_seconds),
                    )

        if result.isError:
            _raise_mapped_tool_error(_safe_error_text(result.content))
        return _require_structured_output(result.structuredContent)

    def call_tool(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        try:
            return _run_sync(self._call_tool(name, input_data))
        except (KeyError, PermissionError, ValueError, MCPToolCallError, RuntimeError):
            raise
        except Exception as exc:
            raise ConnectionError("MCP_SERVER_UNAVAILABLE") from exc


def build_mcp_transport() -> MCPTransport:
    kind = os.getenv("MCP_CLIENT_TRANSPORT", "local").strip().lower()
    if kind == "local":
        return InProcessMCPTransport()
    if kind == "streamable-http":
        url = os.getenv("MCP_SERVER_URL", "").strip()
        if not url:
            raise ValueError("MCP_SERVER_URL_REQUIRED")
        timeout = float(os.getenv("MCP_CLIENT_TIMEOUT_SECONDS", "10"))
        return StreamableHTTPMCPTransport(url, timeout)
    raise ValueError(f"MCP_CLIENT_TRANSPORT_UNSUPPORTED:{kind}")
