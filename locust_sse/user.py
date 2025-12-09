import json
import logging
import time
from typing import Any

from locust import HttpUser
from requests_sse import EventSource

logger = logging.getLogger(__name__)


class SSEUser(HttpUser):
    abstract = True

    def handle_sse_request(
        self,
        url: str,
        params: dict[str, Any],
        prompt: str,
        request_name: str = "sse_request",
    ) -> None:
        """
        Handles an SSE request and tracks LLM metrics.

        Args:
            url: The URL to connect to.
            params: Parameters for the request (headers, etc.).
            prompt: The input prompt (for token counting).
            request_name: Name for Locust metrics.
        """
        start_time = time.perf_counter()
        first_token_received = False
        response_content = ""
        chat_ended_successfully = True
        completion_tokens = 0

        prompt_tokens = self.count_tokens(prompt)
        self.environment.events.request.fire(
            request_type="SSE",
            name=f"{request_name}_prompt_tokens",
            response_time=0,
            response_length=prompt_tokens,
            exception=None,
        )

        try:
            headers = params.get("headers", {})
            if not headers:
                headers = self.client.headers.copy()

            with EventSource(
                url,
                session=self.client,
                headers=headers,
                **{k: v for k, v in params.items() if k != "headers"},
            ) as event_source:
                for event in event_source:
                    if event.type == "error":
                        raise Exception(f"SSE error event: {event.data}")

                    if not event.data or not event.data.strip():
                        continue

                    try:
                        event_data = json.loads(event.data)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode JSON: {event.data}")
                        continue

                    # Track Time To First Token (TTFT)
                    if event_data.get("type", "") == "append" and not first_token_received:
                        now = time.perf_counter()
                        ttft = (now - start_time) * 1000  # ms
                        self.environment.events.request.fire(
                            request_type="SSE",
                            name=f"{request_name}_ttft",
                            response_time=ttft,
                            response_length=0,
                            exception=None,
                        )
                        first_token_received = True

                    if event_data.get("type", "") == "append" and "text" in event_data:
                        response_content += event_data["text"]

                    if event_data.get("type", "") == "close":
                        break

        except Exception as e:
            chat_ended_successfully = False
            logger.error(f"Error occurred while handling SSE: {e}")
            self.environment.events.request.fire(
                request_type="SSE",
                name=request_name,
                response_time=(time.perf_counter() - start_time) * 1000,
                response_length=0,
                exception=e,
            )
            return

        total_time = (time.perf_counter() - start_time) * 1000

        if response_content:
            completion_tokens = self.count_tokens(response_content)
            self.environment.events.request.fire(
                request_type="SSE",
                name=f"{request_name}_completion_tokens",
                response_time=0,
                response_length=completion_tokens,
                exception=None,
            )

        if chat_ended_successfully:
            self.environment.events.request.fire(
                request_type="SSE",
                name=request_name,
                response_time=total_time,
                response_length=len(response_content),
                exception=None,
            )

    def count_tokens(self, text: str) -> int:
        """
        Calculates token count for a given text (simple word-based counting).
        """
        return len(text) // 4  # 4 characters per token
