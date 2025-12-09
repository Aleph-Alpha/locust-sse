import json
from unittest.mock import MagicMock, patch

import pytest
from locust.env import Environment
from requests_sse import MessageEvent

from locust_sse.user import SSEUser


@pytest.fixture
def mock_environment():
    env = MagicMock(spec=Environment)
    env.events = MagicMock()
    env.events.request = MagicMock()
    env.events.request.fire = MagicMock()
    return env


@pytest.fixture
def sse_user(mock_environment):
    # HttpUser requires a host to be set or passed via command line
    # We mock it here to avoid the error
    mock_environment.host = "http://localhost"
    SSEUser.host = "http://localhost"
    user = SSEUser(mock_environment)
    user.client = MagicMock()  # Mock the requests session
    return user


def test_handle_sse_request_success(sse_user):
    prompt = "Hello world"
    url = "http://example.com/sse"
    params = {}

    events_data = [
        MessageEvent(
            type="message",
            data=json.dumps({"type": "append", "text": "Hello"}),
            origin="http://example.com",
            last_event_id="1",
        ),
        MessageEvent(
            type="message",
            data=json.dumps({"type": "append", "text": " world"}),
            origin="http://example.com",
            last_event_id="2",
        ),
        MessageEvent(
            type="message",
            data=json.dumps({"type": "close"}),
            origin="http://example.com",
            last_event_id="3",
        ),
    ]

    with patch("locust_sse.user.EventSource") as MockEventSource:
        mock_source_instance = MockEventSource.return_value
        mock_source_instance.__enter__.return_value = events_data
        
        sse_user.handle_sse_request(url, params, prompt)

        # Verify metrics were fired
        request_fire = sse_user.environment.events.request.fire
        
        # 1. Prompt tokens (2 tokens)
        request_fire.assert_any_call(
            request_type="SSE",
            name="sse_request_prompt_tokens",
            response_time=0,
            response_length=2,
            exception=None,
        )

        # 2. TTFT (called once)
        # We can't easily check the exact response_time, but we can check existence
        ttft_calls = [
            c for c in request_fire.call_args_list 
            if c.kwargs.get("name") == "sse_request_ttft"
        ]
        assert len(ttft_calls) == 1

        # 3. Completion tokens (2 tokens: "Hello", "world")
        request_fire.assert_any_call(
            request_type="SSE",
            name="sse_request_completion_tokens",
            response_time=0,
            response_length=2,
            exception=None,
        )

        # 4. Total request success
        success_calls = [
            c for c in request_fire.call_args_list 
            if c.kwargs.get("name") == "sse_request" and not c.kwargs.get("exception")
        ]
        assert len(success_calls) == 1


def test_handle_sse_request_error(sse_user):
    prompt = "test"
    url = "http://example.com/sse"
    
    # Mock error event
    events_data = [
        MessageEvent(
            type="error",
            data="Something went wrong",
            origin="http://example.com",
            last_event_id="1",
        )
    ]

    with patch("locust_sse.user.EventSource") as MockEventSource:
        mock_source_instance = MockEventSource.return_value
        mock_source_instance.__enter__.return_value = events_data

        sse_user.handle_sse_request(url, {}, prompt)

        request_fire = sse_user.environment.events.request.fire
        
        # Verify failure event
        failure_calls = [
            c for c in request_fire.call_args_list 
            if c.kwargs.get("name") == "sse_request" and c.kwargs.get("exception")
        ]
        assert len(failure_calls) == 1
        assert "SSE error event: Something went wrong" in str(failure_calls[0].kwargs["exception"])

