from tradingagents.llm_clients import create_llm_client
from tradingagents.llm_clients.validators import (
    get_provider_config,
    validate_model,
)


def test_aliyun_coding_plan_config_and_aliases():
    config = get_provider_config("aliyun_coding_plan")
    alias_config = get_provider_config("coding_plan")

    assert config["default_base_url"] == "https://coding.dashscope.aliyuncs.com/v1"
    assert alias_config == config
    assert validate_model("coding_plan", "kimi-k2.5")


def test_aliyun_coding_plan_client_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("ALIYUN_CODING_PLAN_API_KEY", "test-coding-plan-key")

    llm = create_llm_client("coding_plan", "kimi-k2.5").get_llm()

    assert llm.model_name == "kimi-k2.5"
    assert str(llm.openai_api_base) == "https://coding.dashscope.aliyuncs.com/v1"
    assert llm.openai_api_key.get_secret_value() == "test-coding-plan-key"
