"""
LLM Configuration for KJScreener Agent Harness.
Reads KJScreener.yaml and returns an openai-agents-compatible model config.
"""
import os
import yaml


class ScreeniConfigError(Exception):
    """Raised when KJScreener agent configuration is invalid or missing."""
    pass


def _find_config_file():
    """Locate KJScreener.yaml in the repo root or src/ directory."""
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', '..', 'KJScreener.yaml'),
        os.path.join(os.path.dirname(__file__), '..', 'KJScreener.yaml'),
        'KJScreener.yaml',
    ]
    for path in candidates:
        path = os.path.abspath(path)
        if os.path.exists(path):
            return path
    return None


def load_llm_config():
    """
    Load LLM configuration from KJScreener.yaml.
    Returns a dict with keys: provider, model, base_url, api_key.
    Raises ScreeniConfigError if configuration is invalid.
    """
    config_path = _find_config_file()
    if config_path is None:
        raise ScreeniConfigError(
            "KJScreener.yaml not found. Please create it in the repo root or src/ directory. "
            "See KJScreener.yaml.example for the format."
        )

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    llm_config = config.get('llm', {})
    provider = llm_config.get('provider', 'openai')
    model = llm_config.get('model', 'openai/gpt-oss-120b')
    base_url = llm_config.get('base_url', None)
    api_key_env = llm_config.get('api_key_env', 'KJScreener_API_KEY')

    api_key = os.environ.get(api_key_env, None)
    # Do not hard-fail here: Streamlit Configuration tab / localStorage may
    # supply the key at runtime. Callers that require a key should check it.
    return {
        'provider': provider,
        'model': model,
        'base_url': base_url,
        'api_key': api_key or '',
        'api_key_env': api_key_env,
    }


def load_kite_config():
    """Load Kite MCP configuration from KJScreener.yaml.

    Resolution order (first match wins), so a Docker/cloud deployment can
    force this on/off without rebuilding the image or touching the yaml:
      1. env var KJSCREENER_KITE_ENABLED ('true'/'false'/'1'/'0')
      2. kite_mcp.enabled in KJScreener.yaml
      3. default False

    Any failure to find/parse the config file is recorded in '_debug' so the
    UI can show *why* Kite is off instead of just disappearing.
    """
    env_override = os.environ.get('KJSCREENER_KITE_ENABLED')
    env_url = os.environ.get('KJSCREENER_KITE_URL')

    config_path = _find_config_file()
    if config_path is None:
        return {
            'enabled': env_override.strip().lower() in ('1', 'true', 'yes') if env_override else False,
            'url': env_url or 'https://mcp.kite.trade/mcp',
            '_debug': 'KJScreener.yaml not found on any candidate path (checked repo root, src/, cwd).',
        }

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        return {
            'enabled': env_override.strip().lower() in ('1', 'true', 'yes') if env_override else False,
            'url': env_url or 'https://mcp.kite.trade/mcp',
            '_debug': f'Found {config_path} but failed to parse it: {e!r}',
        }

    kite_config = config.get('kite_mcp', {}) or {}
    enabled = kite_config.get('enabled', False)
    if env_override is not None:
        enabled = env_override.strip().lower() in ('1', 'true', 'yes')

    return {
        'enabled': enabled,
        'url': env_url or kite_config.get('url', 'https://mcp.kite.trade/mcp'),
        '_debug': f'Loaded from {config_path} (kite_mcp.enabled={kite_config.get("enabled", False)!r}, env override={env_override!r})',
    }


def load_workflow_config():
    """Load workflow configuration from KJScreener.yaml."""
    config_path = _find_config_file()
    if config_path is None:
        return {'default_mode': 'classic', 'schedule': []}

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return {
        'default_mode': config.get('workflow', {}).get('default_mode', 'classic'),
        'schedule': config.get('schedule', []),
    }
