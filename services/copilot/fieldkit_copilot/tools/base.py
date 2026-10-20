"""Base interfaces and execution engine for typed copilot tools."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fieldkit_common.logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger("fieldkit.copilot.tools")


class ToolDefinition(BaseModel):
    """Specification of a typed tool in the copilot action registry."""

    name: str = Field(description="Unique tool identifier")
    description: str = Field(description="Operational summary for the LLM planner")
    args_schema: type[BaseModel] = Field(description="Pydantic model for input arguments")
    result_schema: type[BaseModel] = Field(description="Pydantic model for tool return value")
    side_effect: bool = Field(description="Whether tool executes mutating external side-effects")
    required_role: str = Field(default="support", description="Keycloak role required to execute")
    timeout_seconds: float = Field(default=10.0, description="Max execution timeout in seconds")

    model_config = {"arbitrary_types_allowed": True}


class ToolExecutionError(Exception):
    """Raised when a tool execution fails or exceeds timeout."""

    def __init__(self, tool_name: str, message: str, retriable: bool = False) -> None:
        super().__init__(f"Tool '{tool_name}' execution error: {message}")
        self.tool_name = tool_name
        self.message = message
        self.retriable = retriable


class ToolRegistry:
    """Registry managing tool definitions, schema exports, and safe execution with retries."""

    def __init__(self) -> None:
        self.tools: dict[str, ToolDefinition] = {}
        self.executors: dict[str, Callable[[dict[str, Any], str], Awaitable[Any]]] = {}

    def register(
        self,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        result_schema: type[BaseModel],
        side_effect: bool,
        executor_func: Callable[[dict[str, Any], str], Awaitable[Any]],
        required_role: str = "support",
        timeout_seconds: float = 10.0,
    ) -> None:
        """Register a typed tool with its async execution handler."""
        defn = ToolDefinition(
            name=name,
            description=description,
            args_schema=args_schema,
            result_schema=result_schema,
            side_effect=side_effect,
            required_role=required_role,
            timeout_seconds=timeout_seconds,
        )
        self.tools[name] = defn
        self.executors[name] = executor_func

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self.tools.get(name)

    def export_schemas_for_planner(self) -> list[dict[str, Any]]:
        """Export tool specifications as JSON schemas formatted for the LLM prompt."""
        schemas = []
        for name, tool in self.tools.items():
            schema_dict = tool.args_schema.model_json_schema()
            # Clean unwanted schema metadata
            schema_dict.pop("title", None)
            schemas.append(
                {
                    "name": name,
                    "description": tool.description,
                    "parameters": schema_dict,
                    "side_effect": tool.side_effect,
                    "required_role": tool.required_role,
                }
            )
        return schemas

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        ticket_id: str,
        action_index: int,
        max_retries: int = 3,
    ) -> Any:
        """Execute tool with timeout, idempotency key generation, and transient retries."""
        if tool_name not in self.tools or tool_name not in self.executors:
            raise ToolExecutionError(tool_name, f"Tool '{tool_name}' is not registered.")

        tool = self.tools[tool_name]
        executor = self.executors[tool_name]
        idempotency_key = f"{ticket_id}:{action_index}"

        # 1. Validate args against Pydantic schema
        try:
            validated_args = tool.args_schema.model_validate(args).model_dump()
        except Exception as exc:
            raise ToolExecutionError(tool_name, f"Invalid arguments: {exc}") from exc

        # 2. Execute with timeout and transient retry loop
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    executor(validated_args, idempotency_key),
                    timeout=tool.timeout_seconds,
                )
                # 3. Validate result against return schema
                if isinstance(result, BaseModel):
                    return result
                return tool.result_schema.model_validate(result)

            except TimeoutError as exc:
                logger.warning(
                    "tool_execution_timeout",
                    tool=tool_name,
                    attempt=attempt,
                    timeout=tool.timeout_seconds,
                )
                last_error = exc
                if attempt == max_retries:
                    raise ToolExecutionError(
                        tool_name,
                        f"Execution exceeded timeout of {tool.timeout_seconds}s.",
                        retriable=False,
                    ) from exc

            except Exception as exc:
                err_str = str(exc).lower()
                is_transient = "503" in err_str or "unavailable" in err_str or "timeout" in err_str
                last_error = exc
                if is_transient and attempt < max_retries:
                    backoff = 0.1 * (2 ** (attempt - 1))
                    logger.warning(
                        "tool_transient_error_retrying",
                        tool=tool_name,
                        attempt=attempt,
                        backoff=backoff,
                        error=str(exc),
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise ToolExecutionError(tool_name, str(exc), retriable=is_transient) from exc

        raise ToolExecutionError(tool_name, f"Failed after {max_retries} attempts: {last_error}")
