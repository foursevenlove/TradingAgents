"""Model name validators for each provider.

Loads model lists from llm_models.json configuration file.
Only validates model names - does NOT enforce limits.
Let LLM providers use their own defaults for unspecified params.
"""
import json
from pathlib import Path

# Path to the LLM models configuration file
_CONFIG_PATH = Path(__file__).parent.parent / "llm_models.json"

# Cached config (loaded once)
_LOADED_CONFIG: dict = None
_PROVIDER_ALIASES: dict = None


def _load_config():
    """Load model configuration from JSON file."""
    global _LOADED_CONFIG, _PROVIDER_ALIASES

    if _LOADED_CONFIG is None:
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                _LOADED_CONFIG = json.load(f)

            # Build alias lookup
            _PROVIDER_ALIASES = {}
            for provider, data in _LOADED_CONFIG.get("providers", {}).items():
                for alias in data.get("aliases", []):
                    _PROVIDER_ALIASES[alias] = provider

        except Exception as e:
            print(f"Warning: Failed to load llm_models.json: {e}")
            _LOADED_CONFIG = {"providers": {}}
            _PROVIDER_ALIASES = {}

    return _LOADED_CONFIG, _PROVIDER_ALIASES


def get_default_settings() -> dict:
    """Get default LLM settings from config file.

    Returns:
        dict with keys: provider, deep_think_llm, quick_think_llm, temperature
    """
    config, _ = _load_config()
    return config.get("default_settings", {
        "provider": "minimax",
        "deep_think_llm": "MiniMax-M2.7",
        "quick_think_llm": "MiniMax-M2.5",
        "temperature": 0.1
    })


def get_valid_models(provider: str) -> list:
    """Get list of valid model names for a provider."""
    config, aliases = _load_config()
    provider_lower = aliases.get(provider.lower(), provider.lower())

    provider_data = config.get("providers", {}).get(provider_lower, {})
    return [m["name"] for m in provider_data.get("models", [])]


def get_provider_config(provider: str) -> dict:
    """Get full provider configuration (api_key_env, default_base_url, models, etc.)."""
    config, aliases = _load_config()
    provider_lower = aliases.get(provider.lower(), provider.lower())
    return config.get("providers", {}).get(provider_lower, {})


def validate_model(provider: str, model: str) -> bool:
    """Check if model name is valid for the given provider.

    For ollama, openrouter - any model is accepted (no validation).
    """
    config, aliases = _load_config()
    provider_lower = aliases.get(provider.lower(), provider.lower())

    # Ollama and OpenRouter accept any model name
    if provider_lower in ("ollama", "openrouter"):
        return True

    valid_models = get_valid_models(provider_lower)
    if not valid_models:
        return True  # Provider not in config, accept any

    return model in valid_models


def list_all_providers() -> list:
    """List all configured provider names (including aliases)."""
    config, aliases = _load_config()
    providers = list(config.get("providers", {}).keys())
    providers.extend(aliases.keys())
    return sorted(providers)


def reload_config():
    """Force reload of configuration (useful after editing config file)."""
    global _LOADED_CONFIG, _PROVIDER_ALIASES
    _LOADED_CONFIG = None
    _PROVIDER_ALIASES = None
    _load_config()