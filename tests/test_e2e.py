import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from locust.env import Environment

from locust_sse.user import SSEUser


@pytest.fixture(scope="module")
def sse_server():
    """Starts the SSE server in headless mode."""
    # Build the binary first (assumes 'make build-sse-server' was run or binary exists)
    # But for safety in test, we'll assume the binary is at bin/sse-server
    
    server_bin = Path("bin/sse-server").resolve()
    if not server_bin.exists():
        pytest.fail("SSE server binary not found. Run 'make build-sse-server' first.")

    # Create a temp events file
    events_file = Path("tests/events_e2e.json").resolve()
    events_data = [
        {"type": "append", "text": "Hello"},
        {"type": "append", "text": " E2E"},
        {"type": "close"}
    ]
    events_file.write_text(json.dumps(events_data))

    port = 8888
    endpoint = "/sse-e2e"

    cmd = [
        str(server_bin),
        "--headless",
        "--file", str(events_file),
        "--port", str(port),
        "--endpoint", endpoint,
        "--interval", "50ms"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for server to start
    url = f"http://localhost:{port}{endpoint}"
    max_retries = 20
    for _ in range(max_retries):
        try:
            # Just check if port is open / server is responsive
            # Since it's a stream endpoint, a GET might hang if we read body, 
            # but we can check connection.
            # However, simpler to just wait a bit or check stdout if we were capturing it live.
            # We'll try a HEAD request or just a quick connect.
            requests.get(f"http://localhost:{port}", timeout=0.1)
            # If we get here (even if 404), server is up.
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
    else:
        process.kill()
        pytest.fail("SSE Server failed to start")

    yield f"http://localhost:{port}{endpoint}"

    process.terminate()
    process.wait()
    if events_file.exists():
        events_file.unlink()


def test_e2e_sse_streaming(sse_server):
    """
    Test the full SSE flow against the Go server.
    """
    env = MagicMock(spec=Environment)
    env.events = MagicMock()
    env.events.request = MagicMock()
    env.events.request.fire = MagicMock()

    # Mock the host just to satisfy HttpUser init if needed, though we pass full URL
    SSEUser.host = "http://localhost:8888"
    user = SSEUser(env)
    
    # We need a real Requests session for the real network call
    user.client = requests.Session()

    prompt = "Test Prompt"
    user.handle_sse_request(sse_server, {}, prompt)

    request_fire = user.environment.events.request.fire
    
    # Filter calls
    calls = request_fire.call_args_list
    
    # Debug info
    print("\nCalls made to request.fire:")
    for c in calls:
        print(c.kwargs)

    # Check we got the "close" or completion
    # We expect:
    # 1. Prompt tokens
    # 2. TTFT (after first "append")
    # 3. Completion tokens (at end)
    # 4. Success request (at end)

    completion_calls = [
        c for c in calls 
        if c.kwargs.get("name") == "sse_request_completion_tokens"
    ]
    assert len(completion_calls) == 1
    # "Hello" + " E2E" = 9 chars. Tokens = len // 4 = 2 tokens (integer division)
    assert completion_calls[0].kwargs["response_length"] == 2

    success_calls = [
        c for c in calls 
        if c.kwargs.get("name") == "sse_request" and not c.kwargs.get("exception")
    ]
    assert len(success_calls) == 1

