from chatgpt_wrapper import ChatGPTWrapper, GuardRail, ResponseType

# تنظیم guardrails
guardrails = GuardRail(
    max_tokens=1500,
    temperature=0.5,
    forbidden_patterns=["نمی‌دانم", "مطمئن نیستم"],
    required_patterns=["بر اساس"],  # اختیاری
    timeout_seconds=30,
    max_retries=3,
)

# ایجاد wrapper
wrapper = ChatGPTWrapper(
    api_key="your-openai-api-key",
    guardrails=guardrails,
)

# استفاده
result = wrapper.chat(
    prompt="کد Python برای API call بنویس",
    expected_type=ResponseType.CODE,
    system_prompt="کد تمیز و documented بنویس",
)

print(f"Confidence: {result.confidence}")
print(result.content)
