# P

## Perplexity client example

```python
import os
import httpx
from perplexity import Perplexity, DefaultHttpxClient


def create_client():
    # Base configuration
    timeout = httpx.Timeout(
        connect=float(os.getenv("PERPLEXITY_CONNECT_TIMEOUT", "5.0")),
        read=float(os.getenv("PERPLEXITY_READ_TIMEOUT", "30.0")),
        write=float(os.getenv("PERPLEXITY_WRITE_TIMEOUT", "10.0")),
    )

    max_retries = int(os.getenv("PERPLEXITY_MAX_RETRIES", "3"))

    # Optional proxy configuration
    proxy = os.getenv("PERPLEXITY_PROXY")
    http_client_kwargs = {}
    if proxy:
        http_client_kwargs["proxy"] = proxy

    return Perplexity(
        max_retries=max_retries,
        timeout=timeout,
        http_client=DefaultHttpxClient(**http_client_kwargs),
    )


client = create_client()
```

## Codex CLI installation

```sh
npm install -g @openai/codex@0.91.0
```
