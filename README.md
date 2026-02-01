# P

## Overview
This repository documents a minimal setup for using the OpenAI Python client with the Perplexity API endpoint, plus the command to install the Codex CLI globally.

## Install Codex CLI
```sh
npm install -g @openai/codex@0.91.0
```

## Example: OpenAI client configured for Perplexity
```python
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_PERPLEXITY_API_KEY",
    base_url="https://api.perplexity.ai/v2",
)
```
