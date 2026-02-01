"""Example of adding a security validator to a ChatGPT wrapper."""


def check_security(response: str) -> bool:
    dangerous = ["rm -rf", "DROP TABLE", "eval("]
    return not any(d in response for d in dangerous)


# Replace ChatGPTWrapper with the actual wrapper import in your codebase.
wrapper = ChatGPTWrapper(
    api_key="...",
    custom_validators=[check_security],
)
