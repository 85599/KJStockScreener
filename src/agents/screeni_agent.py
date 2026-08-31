"""
ScreeniAgent - AI-native stock screening agent powered by openai-agents.
Supports OpenAI, Anthropic, and OpenAI-compatible LLM providers.
Integrates Kite MCP for live market data when configured.

Based on upstream Screeni-py (pranjal-joshi/Screeni-py) with small fixes for
newer openai-agents SDK + Groq openai-compatible endpoints.
"""
import asyncio
import logging
import os
import sys

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from agents.llm_config import load_llm_config, ScreeniConfigError

logger = logging.getLogger(__name__)

# ── Load real openai-agents package BEFORE importing our local agents ─────
# Our local src/agents/ package shadows the openai-agents 'agents' namespace,
# so we must grab Agent, Runner, function_tool before Python ever resolves
# 'agents' to our local package.
try:
    import importlib as _il

    def _load_real_agents():
        """Load real openai-agents, bypassing our local src/agents/ shadow."""
        _our_keys = [k for k in list(sys.modules) if k == 'agents' or k.startswith('agents.')]
        _our_snap = {k: sys.modules.pop(k) for k in _our_keys}
        _paths_to_remove = [
            p for p in sys.path
            if os.path.abspath(p) == _src_dir
        ]
        for p in _paths_to_remove:
            sys.path.remove(p)
        try:
            _mod = _il.import_module('agents')
            # Make sure OpenAIChatCompletionsModel is reachable on _mod even if
            # the installed version doesn't re-export it at the top level —
            # import the submodule HERE, inside this same isolated import
            # context, so the class identity always matches _mod.Agent's
            # isinstance checks. Importing it later from a *different* import
            # context (e.g. after our local src/agents/ package has been
            # re-inserted into sys.path) creates a duplicate, distinct class
            # object with the same name, and Agent(model=...) then rejects it
            # with "Agent model must be a string, Model, or None, got
            # OpenAIChatCompletionsModel" — silently falling back to a plain
            # model string, which re-exposes the Groq 404 model_not_found bug.
            if not hasattr(_mod, 'OpenAIChatCompletionsModel'):
                try:
                    _occm_mod = _il.import_module('agents.models.openai_chatcompletions')
                    _mod.OpenAIChatCompletionsModel = _occm_mod.OpenAIChatCompletionsModel
                except Exception:
                    pass
            sys.modules['_KJScreener_openai_agents_real'] = _mod
            # Drop only the top-level 'agents' name so a later `import agents`
            # resolves to our local src/agents/ package again. Deliberately do
            # NOT pop the real package's submodules (agents.models,
            # agents.models.interface, agents.mcp, agents.agent, ...) — our
            # local package has no submodules with those names, so leaving them
            # cached is harmless, and it's required: openai-agents' Agent class
            # does `from .models.interface import Model` lazily inside
            # __post_init__ (i.e. only when Agent(...) is actually
            # instantiated, later, after this shadow-swap). If that submodule
            # cache entry were removed, Python would try to resolve it via
            # sys.modules['agents'].__path__ at that later point — which by
            # then points at our local package — and raise
            # "ModuleNotFoundError: No module named 'agents.models'".
            for k in [k for k in list(sys.modules) if k == 'agents']:
                if k not in _our_snap:
                    sys.modules.pop(k, None)
            return _mod
        finally:
            for p in reversed(_paths_to_remove):
                sys.path.insert(0, p)
            if _our_snap:
                sys.modules.update(_our_snap)
            else:
                sys.modules.pop('agents', None)
                import agents as _local_agents  # noqa: F401

    _REAL_AGENTS = _load_real_agents()
    Agent = _REAL_AGENTS.Agent
    Runner = _REAL_AGENTS.Runner
    _function_tool = _REAL_AGENTS.function_tool
    _AGENTS_AVAILABLE = True
except (ImportError, AttributeError, Exception) as _e:
    _AGENTS_AVAILABLE = False
    Agent = None
    Runner = None
    _function_tool = None
    _REAL_AGENTS = None

# ── Our local tool definitions (import AFTER real agents are cached) ─────
from agents.screener_tools import TOOL_MAP, ALL_TOOLS

# Appended to every persona's instructions, on both the Runner path and the
# direct compat-loop path — stops the model from inventing plausible-looking
# numbers (e.g. NIFTY index level) when no tool actually returned that data.
_ANTI_HALLUCINATION_GUARDRAIL = (
    "\n\nIMPORTANT: Never invent, estimate, or guess numeric market data "
    "(index levels, prices, RSI, moving averages, volumes, support/resistance) "
    "that wasn't returned by an actual tool call in this conversation. If a "
    "user asks about something you have no tool result for (e.g. the NIFTY "
    "index level, when only stock-level screener tools are available), say "
    "plainly that you don't have that live data rather than making up a "
    "number that looks plausible.\n\n"
    "TABLE FORMATTING: When you put tool results into a markdown table, every "
    "column in every row must come directly from that tool's output — never "
    "leave a Symbol/Price/Volume/etc. cell blank while writing a fluent "
    "description in another cell (e.g. a 'Comment' column) that implies you "
    "know the value. If a specific field wasn't in the tool output, either "
    "omit that column entirely or write 'N/A' in the cell — do not leave "
    "cells visually empty next to narrative text that reads as if they were "
    "filled in."
)


def _build_openai_model(llm_cfg: dict):
    return llm_cfg['model']


def _build_anthropic_model(llm_cfg: dict):
    model = llm_cfg['model']
    if not model.startswith('anthropic/'):
        model = f"anthropic/{model}"
    return model


def _build_openai_compatible_model(llm_cfg: dict):
    return llm_cfg['model']


def _strip_unsupported_openai_params():
    """Groq (and many proxies) reject OpenAI-only body fields like verbosity."""
    try:
        from openai.resources.chat import completions as _completions_mod
    except Exception:
        return

    _unsupported = {
        'verbosity', 'reasoning_effort', 'reasoning', 'text',
        'prompt_cache_retention', 'service_tier',
    }

    def _wrap(fn):
        if getattr(fn, '_kjscreener_stripped', False):
            return fn

        def _filtered(*args, **kwargs):
            for k in list(kwargs.keys()):
                if k in _unsupported:
                    kwargs.pop(k, None)
            extra = kwargs.get('extra_body')
            if isinstance(extra, dict):
                for k in list(extra.keys()):
                    if k in _unsupported:
                        extra.pop(k, None)
            return fn(*args, **kwargs)

        _filtered._kjscreener_stripped = True
        return _filtered

    try:
        Completions = _completions_mod.Completions
        if hasattr(Completions, 'create'):
            Completions.create = _wrap(Completions.create)
    except Exception:
        pass
    try:
        AsyncCompletions = _completions_mod.AsyncCompletions
        if hasattr(AsyncCompletions, 'create'):
            AsyncCompletions.create = _wrap(AsyncCompletions.create)
    except Exception:
        pass


class ScreeniAgent:
    """
    AI-native stock screener agent.
    Wraps openai-agents Agent + Runner with KJScreener tools and optional Kite MCP.
    """

    def __init__(self, persona_config: dict, llm_config: dict = None):
        if not _AGENTS_AVAILABLE:
            raise ImportError(
                "openai-agents package is required. Install with: pip install openai-agents"
            )

        if llm_config is None:
            llm_config = load_llm_config()

        self.persona_config = persona_config
        self.llm_config = llm_config
        self._agent = None
        self._compat_client = None
        self._compat_model_id = None
        self._setup_agent()

    def _setup_agent(self):
        """Build the underlying Agent instance (upstream Screeni-py logic + Groq fixes)."""
        provider = (self.llm_config.get('provider') or 'openai').strip()
        api_key = self.llm_config.get('api_key') or ''
        model_name = (self.llm_config.get('model') or '').strip() or 'openai/gpt-oss-120b'
        base_url = (self.llm_config.get('base_url') or '').strip() or None

        if provider == 'openai':
            os.environ['OPENAI_API_KEY'] = api_key
            model = _build_openai_model(self.llm_config)

        elif provider == 'anthropic':
            os.environ['ANTHROPIC_API_KEY'] = api_key
            model = _build_anthropic_model(self.llm_config)

        elif provider == 'openai-compatible':
            # CRITICAL: model ids like "openai/gpt-oss-120b" must be sent to Groq EXACTLY.
            # If we pass a plain string to Agent(model=...), MultiProvider strips the
            # "openai/" prefix and Groq gets "gpt-oss-120b" → 404 model_not_found.
            # Fix: OpenAIChatCompletionsModel keeps the full model id + custom client.
            model_id = _build_openai_compatible_model(self.llm_config)
            os.environ['OPENAI_API_KEY'] = api_key or 'none'
            os.environ['OPENAI_DEFAULT_MODEL'] = model_id
            if base_url:
                os.environ['OPENAI_BASE_URL'] = base_url
            model = model_id  # fallback string
            self._compat_client = None
            self._compat_model_id = model_id
            try:
                from openai import AsyncOpenAI
                _custom_client = AsyncOpenAI(api_key=api_key or 'none', base_url=base_url)
                self._compat_client = _custom_client
                set_default_openai_client = getattr(_REAL_AGENTS, 'set_default_openai_client', None)
                if set_default_openai_client:
                    set_default_openai_client(_custom_client)
                set_default_openai_api = getattr(_REAL_AGENTS, 'set_default_openai_api', None)
                if set_default_openai_api:
                    set_default_openai_api('chat_completions')

                # OpenAIChatCompletionsModel is cached on _REAL_AGENTS at module
                # load time (see _load_real_agents above) — always use THAT
                # exact reference. Re-importing it here from a different sys.path
                # context creates a second, distinct class object with the same
                # name, which Agent()'s isinstance check then rejects (falls
                # back to a plain model string, which re-exposes the Groq 404
                # model_not_found bug). Do NOT add a fallback re-import here.
                OpenAIChatCompletionsModel = getattr(_REAL_AGENTS, 'OpenAIChatCompletionsModel', None)

                if OpenAIChatCompletionsModel is not None:
                    try:
                        model = OpenAIChatCompletionsModel(
                            model=model_id,
                            openai_client=_custom_client,
                        )
                        logger.info("Using OpenAIChatCompletionsModel model=%r", model_id)
                    except Exception as _occ_e:
                        logger.warning(f"OCCM construct failed: {_occ_e}; using string model")
                        model = model_id
                else:
                    logger.warning("OpenAIChatCompletionsModel not available; string model may strip openai/ prefix")
                    model = model_id
            except Exception as _e:
                logger.warning(f"Could not set custom OpenAI client: {_e}")
                model = model_id
            try:
                _disable_tracing = getattr(_REAL_AGENTS, 'set_tracing_disabled', None)
                if _disable_tracing:
                    _disable_tracing(True)
                else:
                    os.environ['OPENAI_AGENTS_DISABLE_TRACING'] = '1'
            except Exception:
                os.environ['OPENAI_AGENTS_DISABLE_TRACING'] = '1'
            try:
                _strip_unsupported_openai_params()
            except Exception:
                pass
        else:
            os.environ['OPENAI_API_KEY'] = api_key
            model = model_name

        # Filter tools based on persona config
        persona_tools_list = self.persona_config.get('tools', [])
        if persona_tools_list:
            selected_tools = [
                TOOL_MAP[name] for name in persona_tools_list
                if name in TOOL_MAP
            ]
        else:
            selected_tools = ALL_TOOLS

        if _function_tool is not None:
            selected_tools = [_function_tool(fn) for fn in selected_tools]

        instructions = self.persona_config.get('instructions', '')
        persona_index = self.persona_config.get('index', 'Nifty 500')
        if persona_index and 'index' not in instructions.lower():
            instructions = f"{instructions}\n\nDefault index: {persona_index}"
        instructions = f"{instructions}{_ANTI_HALLUCINATION_GUARDRAIL}"

        kwargs = {
            'name': self.persona_config.get('name', 'ScreeniAgent'),
            'instructions': instructions,
            'tools': selected_tools,
        }

        # Newer SDK injects GPT-5 ModelSettings (verbosity etc.) — use plain settings
        # for non-OpenAI providers so Groq does not 400.
        if provider in ('openai-compatible', 'anthropic') and _REAL_AGENTS is not None:
            ModelSettings = getattr(_REAL_AGENTS, 'ModelSettings', None)
            if ModelSettings is not None:
                try:
                    kwargs['model_settings'] = ModelSettings()
                except Exception:
                    pass

        # Prefer model object (OCCM) so full ids like openai/gpt-oss-120b are preserved.
        # If Agent rejects the object type, fall back to string + env defaults.
        try:
            self._agent = Agent(model=model, **kwargs)
        except TypeError as te:
            logger.warning(f"Agent(model=object) rejected ({te}); retrying with string model_id")
            model_str = model_id if provider == 'openai-compatible' else (
                model if isinstance(model, str) else model_name
            )
            try:
                self._agent = Agent(model=model_str, **kwargs)
            except TypeError:
                self._agent = Agent(
                    name=kwargs['name'],
                    instructions=kwargs['instructions'],
                    tools=kwargs.get('tools') or [],
                    model=model_str,
                )
        logger.info(
            "ScreeniAgent ready provider=%s model=%r base_url=%r",
            provider, model if isinstance(model, str) else getattr(model, 'model', model), base_url,
        )

    async def run(self, query: str, session=None) -> str:
        provider = (self.llm_config.get('provider') or '').strip()
        # For openai-compatible (Groq etc.) prefer direct client loop so the full
        # model id (e.g. openai/gpt-oss-120b) is never stripped by MultiProvider.
        if provider == 'openai-compatible' and self._compat_client is not None:
            try:
                return await self._run_compatible_direct(query)
            except Exception as e:
                logger.error(f"Direct compatible run failed: {e}")
                return f"Error: {e}"
        try:
            mcp_servers = getattr(self._agent, 'mcp_servers', []) or []
            connected_servers = []
            if mcp_servers:
                for srv in mcp_servers:
                    try:
                        await srv.connect()
                        connected_servers.append(srv)
                    except Exception as e:
                        logger.warning(f"MCP connect failed, skipping: {e}")
                try:
                    self._agent.mcp_servers = connected_servers
                except Exception:
                    pass
            try:
                run_kwargs = {}
                if session is not None:
                    run_kwargs['session'] = session
                result = await Runner.run(self._agent, query, **run_kwargs)
                return result.final_output
            finally:
                for srv in connected_servers:
                    try:
                        await srv.cleanup()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            return f"Error: {e}"

    async def _run_compatible_direct(self, query: str, mcp_server=None) -> str:
        """Tool-calling loop via AsyncOpenAI — exact model id, no agents MultiProvider.

        This is the ONLY reliable path for openai-compatible providers (Groq etc.):
        it never touches openai-agents' Runner/MultiProvider, which strips the
        provider prefix off model ids like "openai/gpt-oss-120b" and sends the
        bare "gpt-oss-120b" to Groq, causing a 404 model_not_found error.

        Pass an optional connected MCP server (e.g. Kite MCP) to expose its tools
        alongside the local screener tools — this lets Kite MCP work through the
        same crash-proof path instead of falling back to Runner.run().
        """
        import json
        import inspect

        model_id = self._compat_model_id or self.llm_config.get('model')
        client = self._compat_client
        instructions = self.persona_config.get('instructions', '') or ''
        persona_index = self.persona_config.get('index', 'Nifty 500')
        if persona_index and 'index' not in instructions.lower():
            instructions = f"{instructions}\n\nDefault index: {persona_index}"
        instructions = f"{instructions}{_ANTI_HALLUCINATION_GUARDRAIL}"

        persona_tools_list = self.persona_config.get('tools', []) or []
        if persona_tools_list:
            fns = [TOOL_MAP[n] for n in persona_tools_list if n in TOOL_MAP]
        else:
            fns = list(ALL_TOOLS)

        tools_schema = []
        fn_by_name = {}
        for fn in fns:
            name = fn.__name__
            fn_by_name[name] = fn
            sig = inspect.signature(fn)
            props = {}
            required = []
            for pname, param in sig.parameters.items():
                ann = param.annotation
                if ann is int:
                    ptype = 'integer'
                elif ann is float:
                    ptype = 'number'
                elif ann is bool:
                    ptype = 'boolean'
                else:
                    ptype = 'string'
                props[pname] = {'type': ptype}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)
                else:
                    # still include; model can omit
                    pass
            tools_schema.append({
                'type': 'function',
                'function': {
                    'name': name,
                    'description': (fn.__doc__ or name).strip().split('\n')[0][:200],
                    'parameters': {
                        'type': 'object',
                        'properties': props,
                        'required': required,
                    },
                },
            })

        # ── Merge in MCP server tools (e.g. Kite: get_ltp, get_quotes, place_order) ──
        mcp_tool_names = set()
        if mcp_server is not None:
            try:
                mcp_tools = await mcp_server.list_tools()
                for t in mcp_tools:
                    t_name = getattr(t, 'name', None)
                    if not t_name:
                        continue
                    mcp_tool_names.add(t_name)
                    t_schema = getattr(t, 'inputSchema', None) or {
                        'type': 'object', 'properties': {}, 'required': [],
                    }
                    tools_schema.append({
                        'type': 'function',
                        'function': {
                            'name': t_name,
                            'description': (getattr(t, 'description', '') or t_name)[:200],
                            'parameters': t_schema,
                        },
                    })
            except Exception as e:
                logger.warning(f"Kite MCP list_tools failed, continuing without them: {e}")

        messages = [
            {'role': 'system', 'content': instructions},
            {'role': 'user', 'content': query},
        ]

        for _step in range(8):
            kwargs = dict(
                model=model_id,
                messages=messages,
            )
            if tools_schema:
                kwargs['tools'] = tools_schema
                kwargs['tool_choice'] = 'auto'
            resp = await client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            msg = choice.message
            tool_calls = getattr(msg, 'tool_calls', None) or []
            if not tool_calls:
                return (msg.content or '').strip() or '(empty response)'

            messages.append({
                'role': 'assistant',
                'content': msg.content,
                'tool_calls': [
                    {
                        'id': tc.id,
                        'type': 'function',
                        'function': {
                            'name': tc.function.name,
                            'arguments': tc.function.arguments or '{}',
                        },
                    }
                    for tc in tool_calls
                ],
            })
            for tc in tool_calls:
                fname = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or '{}')
                except Exception:
                    args = {}

                if fname in mcp_tool_names and mcp_server is not None:
                    try:
                        mcp_result = await mcp_server.call_tool(fname, args)
                        parts = getattr(mcp_result, 'content', None) or []
                        result = '\n'.join(
                            getattr(p, 'text', '') for p in parts if getattr(p, 'text', '')
                        ) or str(mcp_result)
                    except Exception as e:
                        result = f"Kite tool error: {e}"
                    messages.append({
                        'role': 'tool',
                        'tool_call_id': tc.id,
                        'content': str(result)[:12000],
                    })
                    continue

                fn = fn_by_name.get(fname)
                if fn is None:
                    result = f"Unknown tool: {fname}"
                else:
                    try:
                        result = fn(**args)
                    except TypeError:
                        # drop unexpected kwargs
                        sig = inspect.signature(fn)
                        filtered = {k: v for k, v in args.items() if k in sig.parameters}
                        try:
                            result = fn(**filtered)
                        except Exception as e2:
                            result = f"Tool error: {e2}"
                    except Exception as e:
                        result = f"Tool error: {e}"
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc.id,
                    'content': str(result)[:12000],
                })
        return "Error: tool loop limit reached"

    def run_sync(self, query: str, session=None) -> str:
        import concurrent.futures

        result_holder = {}

        def _run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_holder['result'] = loop.run_until_complete(
                    self.run(query, session=session)
                )
            except Exception as e:
                logger.error(f"Agent run_sync thread failed: {e}")
                result_holder['result'] = f"Error: {e}"
            finally:
                loop.close()

        t = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = t.submit(_run_in_thread)
        future.result()
        t.shutdown(wait=False)
        return result_holder.get('result', 'Error: no result returned')
