# OpenRouter behind a swappable LLM interface

We have an OpenRouter key, not a single-vendor SDK in the pipeline. Diagnosis, Decision, and Why call an LLM port. The adapter is OpenRouter. Provider and model come from environment variables. If the key or model is missing, fail closed. Changing model later must not change the pipeline.

**Status:** accepted
