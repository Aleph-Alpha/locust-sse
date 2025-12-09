# Locust SSE User

A Locust plugin for testing Server-Sent Events (SSE) endpoints, specifically designed for LLM streaming response benchmarking.

## Installation

You can install this package using `uv` (recommended) or `pip`.

### Using uv

```bash
uv add locust-sse
```

### Using pip

```bash
pip install locust-sse
```

## Usage

Inherit from `SSEUser` in your `locustfile.py` and use the `handle_sse_request` method to make SSE requests.

```python
from locust import task
from locust_sse import SSEUser

class MyLLMUser(SSEUser):
    # Set the host for the user
    host = "http://localhost:8080"

    @task
    def chat(self):
        # Example payload for a chat completion endpoint
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Tell me a joke."}
            ],
            "stream": True
        }

        # Make the SSE request
        self.handle_sse_request(
            url="/chat/completions",
            params={"json": payload},
            prompt="Tell me a joke.",
            request_name="chat_completion"
        )
```

## Metrics

This plugin automatically tracks specific metrics relevant to LLM streaming performance and reports them to Locust.

| Metric | Description |
| :--- | :--- |
| **TTFT** | **Time To First Token**. Measures the latency from the start of the request until the first "append" event is received. |
| **Prompt Tokens** | Number of tokens in the input prompt (estimated). |
| **Completion Tokens** | Number of tokens in the generated response (estimated). |
| **Processing Time** | Total time taken for the entire generation process. |

### How Metrics Appear in Locust

These metrics are reported as separate entries in the Locust statistics table:

- `{request_name}_ttft`: Latency statistics for the first token.
- `{request_name}_prompt_tokens`: "Response Length" column shows token count.
- `{request_name}_completion_tokens`: "Response Length" column shows token count.
- `{request_name}`: The main request entry showing total duration.

## Development

This project uses `uv` for dependency management.

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

