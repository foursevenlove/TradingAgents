#!/usr/bin/env python
"""Test script to verify LLM configuration from llm_models.json."""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from tradingagents.llm_clients.validators import get_default_settings, get_provider_config, reload_config
from tradingagents.llm_clients import create_llm_client


def test_llm_config():
    """Test LLM configuration and connectivity."""
    print("=" * 60)
    print("LLM Configuration Test")
    print("=" * 60)

    # Reload config to get latest settings
    reload_config()

    # 1. Show config
    settings = get_default_settings()
    print("\n[1] Configuration from llm_models.json:")
    print(f"    Provider: {settings.get('provider')}")
    print(f"    Deep Think LLM: {settings.get('deep_think_llm')}")
    print(f"    Quick Think LLM: {settings.get('quick_think_llm')}")
    print(f"    Temperature: {settings.get('temperature')}")
    print(f"    Enable Thinking: {settings.get('enable_thinking')}")

    # 2. Show provider config
    provider_config = get_provider_config(settings.get('provider'))
    print(f"\n[2] Provider Config ({settings.get('provider')}):")
    print(f"    API Key Env: {provider_config.get('api_key_env')}")
    print(f"    Base URL: {provider_config.get('default_base_url')}")

    # 3. Check API Key
    api_key_env = provider_config.get('api_key_env')
    if api_key_env:
        api_key = os.environ.get(api_key_env)
        if api_key:
            print(f"    API Key: {api_key[:20]}...{api_key[-10:]}")
        else:
            print(f"    API Key: ❌ NOT SET (env: {api_key_env})")
            return False
    else:
        print("    API Key: Not required (local provider)")

    # 4. Create LLM clients
    print("\n[3] Creating LLM Clients...")

    # Build kwargs based on config
    kwargs = {"temperature": settings.get("temperature", 0.1)}

    # Add enable_thinking for Alibaba
    if settings.get("provider") in ("alibaba", "bailian", "dashscope"):
        if settings.get("enable_thinking"):
            kwargs["enable_thinking"] = True

    try:
        deep_client = create_llm_client(
            provider=settings.get("provider"),
            model=settings.get("deep_think_llm"),
            **kwargs,
        )
        deep_llm = deep_client.get_llm()
        print(f"    Deep LLM: ✓ Created")
        print(f"      Model: {deep_llm.model_name}")
        print(f"      Base URL: {deep_llm.openai_api_base}")
        print(f"      Model kwargs: {deep_llm.model_kwargs}")

        quick_client = create_llm_client(
            provider=settings.get("provider"),
            model=settings.get("quick_think_llm"),
            **kwargs,
        )
        quick_llm = quick_client.get_llm()
        print(f"    Quick LLM: ✓ Created")
        print(f"      Model: {quick_llm.model_name}")

    except Exception as e:
        print(f"    ❌ Failed to create LLM: {e}")
        return False

    # 5. Test API call
    print("\n[4] Testing API Call (Quick LLM)...")
    test_prompt = "请用一句话回答：你是谁？"

    try:
        response = quick_llm.invoke(test_prompt)
        print(f"    ✓ API Call Successful!")
        print(f"    Response: {response.content[:200]}...")
    except Exception as e:
        print(f"    ❌ API Call Failed: {e}")
        return False

    # 6. Test Deep Thinking (if enabled)
    if settings.get("enable_thinking"):
        print("\n[5] Testing Deep Thinking (Deep LLM)...")
        test_prompt = "思考一下：1+1等于几？请简要说明思考过程。"

        try:
            response = deep_llm.invoke(test_prompt)
            print(f"    ✓ Deep Thinking API Call Successful!")

            # Check reasoning_tokens in response_metadata (LangChain stores it here)
            meta = response.response_metadata
            if 'token_usage' in meta:
                details = meta['token_usage'].get('completion_tokens_details', {})
                reasoning_tokens = details.get('reasoning_tokens', 0)
                if reasoning_tokens > 0:
                    print(f"    ✓ Reasoning Tokens: {reasoning_tokens} (深度思考已开启！)")
                else:
                    print(f"    ? Reasoning Tokens: 0")

            print(f"    Response: {response.content[:200]}...")
        except Exception as e:
            print(f"    ❌ Deep Thinking API Call Failed: {e}")
            return False

    print("\n" + "=" * 60)
    print("✓ All tests passed! LLM configuration is working.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_llm_config()
    sys.exit(0 if success else 1)