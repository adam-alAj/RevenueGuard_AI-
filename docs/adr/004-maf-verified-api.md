# ADR-004: Verified Microsoft Agent Framework + Gemini API Surface

## Status

Accepted

## Date

2026-08-19

## Context

The `agent-framework` package ecosystem has changed shape multiple times in 2026. Before writing any agent code, we inspected the actually-installed packages to confirm current class names, import paths, and method signatures. This ADR documents the verified surface so every later phase (Phase 8+) can rely on accurate import paths without re-inspecting.

## Verified Package Versions

| Package | Version | Import Path |
|---|---|---|
| `agent-framework` | 1.14.0 | `agent_framework` |
| `agent-framework-core` | 1.14.0 | (bundled in `agent_framework`) |
| `agent-framework-gemini` | 1.0.0b260813 | `agent_framework_gemini` |
| `agent-framework-tools` | 1.0.0b260730 | `agent_framework_tools` |

## Core Classes (agent_framework)

### Agent

```python
from agent_framework import Agent

agent = Agent(
    client=gemini_client,           # BaseChatClient (required)
    instructions="system prompt",    # str | None
    id="agent-id",                  # str | None
    name="agent-name",              # str | None
    description="what agent does",  # str | None
    tools=[tool1, tool2],           # ToolTypes | Callable | None
    default_options=ChatOptions(),  # OptionsCoT | None
    middleware=None,                # MiddlewareTypes | None
)
```

**Key methods:**
- `agent.run(messages, *, stream, session, tools, options)` → `Awaitable[AgentResponse]`
- `agent.create_session()` → `AgentSession`
- `agent.as_tool()` — converts agent into a callable tool for delegation

### FunctionTool (via @tool decorator)

```python
from agent_framework import tool

@tool
def my_tool(arg1: str, arg2: int) -> str:
    '''Description visible to the LLM.'''
    return f"Result: {arg1}"
```

The `@tool` decorator creates a `FunctionTool` with:
- `name` derived from function name
- `description` from docstring
- `input_model` auto-generated from type hints (Pydantic model)

### Message and Content

```python
from agent_framework import Message, Content, Role

msg = Message(
    role=Role("user"),       # "user" | "assistant" | "system"
    contents=[Content(type="text", text="Hello")],
)
```

### AgentResponse

```python
response = await agent.run("Hello!")
response.text          # str - concatenated text from all text contents
response.messages      # list[Message]
response.value         # structured output value (if configured)
response.finish_reason # FinishReason
response.usage_details # UsageDetails
```

## Gemini Client (agent_framework_gemini)

### GeminiChatClient

```python
from agent_framework_gemini import GeminiChatClient, GeminiChatOptions

client = GeminiChatClient(
    api_key="GEMINI_API_KEY",     # str | None (falls back to GEMINI_API_KEY env)
    model="gemini-2.0-flash",     # str | None
    vertexai=False,               # bool | None
    project=None,                 # str | None (GCP project for Vertex AI)
    location=None,                # str | None (GCP region for Vertex AI)
    client=None,                  # pre-configured genai.Client | None
    middleware=None,              # ChatAndFunctionMiddlewareTypes | None
)
```

### GeminiChatOptions

```python
options = GeminiChatOptions(
    temperature=0.7,
    model="gemini-2.0-flash",
    max_output_tokens=8192,
)
```

Note: `GeminiChatOptions` is a plain dict subclass (not a Pydantic model). Keys map directly to Gemini API parameters.

## ContentType Values

```
text, text_reasoning, data, uri, error, function_call, function_result,
usage, hosted_file, hosted_vector_store, code_interpreter_tool_call,
code_interpreter_tool_result, image_generation_tool_call,
image_generation_tool_result, mcp_server_tool_call, mcp_server_tool_result,
search_tool_call, search_tool_result, shell_tool_call, shell_tool_result,
shell_command_output, function_approval_request, function_approval_response,
oauth_consent_request
```

## Architectural Implications for RevenueGuard AI

1. **Tool injection**: The `tools` parameter on `Agent.__init__` and `Agent.run` accepts `FunctionTool` objects. Our tool scaffold wraps functions to add tenant-scope injection.

2. **No workflow graph needed for Phase 7**: A single `Agent.run()` suffices for the smoke test. Phase 8 will use `Workflow` and `Edge` for multi-agent orchestration.

3. **Model parameter**: Passed via `GeminiChatOptions` dict, not on the client. The client's `model` parameter is the default; options can override per-call.

4. **Async-first**: `Agent.run()` returns an `Awaitable[AgentResponse]`. Must be `await`ed in async context.

## Alternatives Considered

- **LangChain / LangGraph**: Explicitly rejected by ADR-002. Not considered here.
- **Direct google-genai SDK**: Would bypass the framework's tool/middleware abstraction. Rejected per ADR-002.
- **Semantic Kernel**: Explicitly rejected by ADR-002.

## Consequences

- All Phase 8+ agent code must import from `agent_framework` and `agent_framework_gemini` only.
- Tool implementations must follow the scaffold pattern in `app/agents/tools/base.py`.
- The verified versions in this ADR are pinned in `pyproject.toml`.
