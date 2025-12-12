import json
from unittest.mock import MagicMock

import pytest
from locust.env import Environment

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

    # Mock response.iter_lines()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_lines.return_value = [
        'data: {"type": "append", "text": "Hello"}',
        "",
        'data: {"type": "append", "text": " world"}',
        "",
        'data: {"type": "close"}',
        "",
    ]
    
    sse_user.client.request.return_value.__enter__.return_value = mock_response
    sse_user.handle_sse_request(url, params, prompt)

    # Verify metrics were fired
    request_fire = sse_user.environment.events.request.fire
    
    request_fire.assert_any_call(
        request_type="SSE",
        name="sse_request_prompt_tokens",
        response_time=0,
        response_length=2,
        exception=None,
    )

    ttft_calls = [
        c for c in request_fire.call_args_list 
        if c.kwargs.get("name") == "sse_request_ttft"
    ]
    assert len(ttft_calls) == 1

    request_fire.assert_any_call(
        request_type="SSE",
        name="sse_request_completion_tokens",
        response_time=0,
        response_length=2,
        exception=None,
    )

    success_calls = [
        c for c in request_fire.call_args_list 
        if c.kwargs.get("name") == "sse_request" and not c.kwargs.get("exception")
    ]
    assert len(success_calls) == 1


def test_handle_sse_request_error(sse_user):
    prompt = "test"
    url = "http://example.com/sse"
    
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_lines.return_value = [
        "event: error",
        "data: Something went wrong",
        "",
    ]

    sse_user.client.request.return_value.__enter__.return_value = mock_response

    sse_user.handle_sse_request(url, {}, prompt)

    request_fire = sse_user.environment.events.request.fire
    
    failure_calls = [
        c for c in request_fire.call_args_list 
        if c.kwargs.get("name") == "sse_request" and c.kwargs.get("exception")
    ]
    assert len(failure_calls) == 1
    assert "SSE error event: Something went wrong" in str(failure_calls[0].kwargs["exception"])


def test_no_reconnection_on_disconnect(sse_user):
    """
    Test that the client does NOT reconnect when the server closes the connection
    unexpectedly or the stream ends. This ensures exactly 1 HTTP request per call.
    """
    prompt = "test"
    url = "http://example.com/sse"
    
    # Mock response.iter_lines() to simulate a stream that ends (StopIteration)
    # without sending a "close" event.
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    
    # Simulate data followed by end of stream
    mock_response.iter_lines.return_value = [
        'data: {"type": "append", "text": "Some text"}',
        "",
        # Stream ends here
    ]

    sse_user.client.request.return_value.__enter__.return_value = mock_response

    sse_user.handle_sse_request(url, {}, prompt)

    # 1. Verify that client.request was called exactly ONCE
    assert sse_user.client.request.call_count == 1

    # 2. Verify that the task completed (metrics fired) despite no explicit "close" event
    request_fire = sse_user.environment.events.request.fire
    
    success_calls = [
        c for c in request_fire.call_args_list 
        if c.kwargs.get("name") == "sse_request" and not c.kwargs.get("exception")
    ]
    # It should still be considered a successful request/chat termination 
    # (or at least the function returns without error/looping)
    assert len(success_calls) == 1
