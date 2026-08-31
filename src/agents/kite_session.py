"""
KiteMCPSession — persistent Kite MCP session manager.

The Kite MCP login flow requires the MCP session to stay open between:
  1. Calling the `login` tool (which returns a browser URL)
  2. The user completing browser auth
  3. Subsequent tool calls (get_ltp, get_quotes, etc.)

This module manages a background thread + event loop that keeps the MCP
server connected across multiple agent invocations, so the session_id
in the login URL remains valid until the user completes auth.
"""
import asyncio
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_SESSION_LOCK = threading.Lock()
_SESSION: Optional["KiteMCPSession"] = None


class KiteMCPSession:
    """
    Persistent holder for a connected MCPServerStreamableHttp instance.
    Runs its own daemon thread + event loop so the session stays alive
    across multiple synchronous call sites (e.g., Streamlit reruns).
    """

    def __init__(self, url: str):
        self.url = url
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None          # MCPServerStreamableHttp instance
        self._connected = False
        self._login_url: Optional[str] = None
        self._ready_event = threading.Event()
        self._error: Optional[Exception] = None

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        """Spin up the background event loop and connect to MCP."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="kite-mcp-loop")
        self._thread.start()
        # Wait up to 15 s for the connect to complete
        if not self._ready_event.wait(timeout=15):
            raise TimeoutError("Kite MCP connect timed out")
        if self._error:
            raise self._error

    def stop(self):
        """Disconnect and shut down the background loop."""
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._cleanup(), self._loop).result(timeout=10)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
            # Keep the loop running (servicing keep-alive pings etc.)
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _connect(self):
        try:
            # Import lazily — avoids breaking if openai-agents absent.
            # Prefer the real agents reference cached by screeni_agent.py;
            # fall back to sys.path surgery (no fragile site.getsitepackages).
            import sys as _sys, importlib as _il, os as _os
            _real = _sys.modules.get('_KJScreener_openai_agents_real')
            if _real is not None and hasattr(_real, 'mcp'):
                _mcp_mod = _real.mcp
            else:
                _src_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
                _our = _sys.modules.pop('agents', None)
                _our_mcp = _sys.modules.pop('agents.mcp', None)
                _paths_to_remove = [
                    p for p in _sys.path
                    if _os.path.abspath(p) == _src_dir
                ]
                for p in _paths_to_remove:
                    _sys.path.remove(p)
                try:
                    _il.import_module('agents')
                    _mcp_mod = _il.import_module('agents.mcp')
                finally:
                    for p in reversed(_paths_to_remove):
                        _sys.path.insert(0, p)
                    if _our is not None:
                        _sys.modules['agents'] = _our
                    else:
                        _sys.modules.pop('agents', None)
                    if _our_mcp is not None:
                        _sys.modules['agents.mcp'] = _our_mcp
            MCPServerStreamableHttp = _mcp_mod.MCPServerStreamableHttp
            MCPServerStreamableHttpParams = _mcp_mod.MCPServerStreamableHttpParams

            self._server = MCPServerStreamableHttp(
                MCPServerStreamableHttpParams({'url': self.url})
            )
            await self._server.connect()
            self._connected = True
            logger.info(f"Kite MCP session connected: {self.url}")
        except Exception as e:
            self._error = e
            logger.error(f"Kite MCP connect failed: {e}")
        finally:
            self._ready_event.set()

    async def _cleanup(self):
        if self._server:
            try:
                await self._server.cleanup()
            except Exception:
                pass
        self._connected = False
        if self._loop and self._loop.is_running():
            self._loop.stop()

    # ── public API ─────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def server(self):
        """The live MCPServerStreamableHttp instance (for passing to Agent)."""
        return self._server

    def get_login_url(self) -> Optional[str]:
        """
        Call the Kite `login` MCP tool synchronously and return the URL.
        The session stays open so the session_id in the URL remains valid.
        """
        if not self._connected or not self._loop:
            raise RuntimeError("Session not connected. Call start() first.")
        future = asyncio.run_coroutine_threadsafe(self._call_login(), self._loop)
        return future.result(timeout=30)

    async def _call_login(self) -> str:
        """Invoke the MCP login tool and extract the URL from the response."""
        try:
            result = await self._server.call_tool("login", {})
            # CallToolResult has a .content list of TextContent items
            if result.content:
                return result.content[0].text
            return str(result)
        except Exception as e:
            logger.error(f"Kite login tool call failed: {e}")
            raise

    def run_agent_query(self, screeni_agent, query: str, sql_session=None) -> str:
        """
        Run a ScreeniAgent query inside this session's event loop so it shares
        the already-authenticated MCP server connection.
        Pass a SQLiteSession for multi-turn conversation history.

        `screeni_agent` is the ScreeniAgent wrapper (not the raw Agent object).
        For openai-compatible providers (Groq etc.) this routes through the
        wrapper's direct AsyncOpenAI tool-loop instead of Runner.run() — Runner
        goes through openai-agents' MultiProvider, which strips the provider
        prefix off model ids like "openai/gpt-oss-120b" and sends the bare
        "gpt-oss-120b" to Groq, causing a 404 model_not_found error. The direct
        loop keeps the exact model id intact and still gets full Kite MCP tool
        access via the mcp_server argument.
        """
        if not self._connected or not self._loop:
            raise RuntimeError("Session not connected.")
        future = asyncio.run_coroutine_threadsafe(
            self._run_agent(screeni_agent, query, sql_session=sql_session), self._loop
        )
        return future.result(timeout=300)

    async def _run_agent(self, screeni_agent, query: str, sql_session=None) -> str:
        try:
            provider = ''
            compat_client = None
            try:
                provider = (getattr(screeni_agent, 'llm_config', {}) or {}).get('provider', '')
                compat_client = getattr(screeni_agent, '_compat_client', None)
            except Exception:
                pass

            if provider == 'openai-compatible' and compat_client is not None:
                return await screeni_agent._run_compatible_direct(
                    query, mcp_server=self._server
                )

            # openai / anthropic providers: MultiProvider resolves model ids fine
            # for these, so the normal Runner.run() path is safe to use.
            agent = getattr(screeni_agent, '_agent', screeni_agent)
            agent.mcp_servers = [self._server]

            import sys as _sys, importlib as _il, os as _os
            # Prefer cached real openai-agents module; fall back to path surgery
            _real = _sys.modules.get('_KJScreener_openai_agents_real')
            if _real is not None and hasattr(_real, 'Runner'):
                Runner = _real.Runner
            else:
                _src_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
                _our = _sys.modules.pop('agents', None)
                _paths_to_remove = [
                    p for p in _sys.path
                    if _os.path.abspath(p) == _src_dir
                ]
                for p in _paths_to_remove:
                    _sys.path.remove(p)
                try:
                    _agents = _il.import_module('agents')
                    Runner = _agents.Runner
                finally:
                    for p in reversed(_paths_to_remove):
                        _sys.path.insert(0, p)
                    if _our is not None:
                        _sys.modules['agents'] = _our
                    else:
                        _sys.modules.pop('agents', None)

            run_kwargs = {}
            if sql_session is not None:
                run_kwargs['session'] = sql_session
            result = await Runner.run(agent, query, **run_kwargs)
            return result.final_output
        except Exception as e:
            logger.error(f"Agent run in Kite session failed: {e}")
            return f"Error: {e}"


# ── module-level singleton helpers ─────────────────────────────────────────────

def get_or_create_session(url: str = "https://mcp.kite.trade/mcp") -> "KiteMCPSession":
    """Return the existing live session or create a new one."""
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is None or not _SESSION.is_connected:
            if _SESSION is not None:
                try:
                    _SESSION.stop()
                except Exception:
                    pass
            _SESSION = KiteMCPSession(url)
            _SESSION.start()
        return _SESSION


def clear_session():
    """Tear down the singleton session (e.g., on logout)."""
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is not None:
            try:
                _SESSION.stop()
            except Exception:
                pass
            _SESSION = None
