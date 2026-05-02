from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="User message to send to the chat service.")
    session_id: str | None = Field(
        default=None,
        description="Optional conversation session ID. A new session is created when omitted.",
    )
    tables: list[str] = Field(
        default_factory=list,
        description="Optional database tables the chat request is allowed to reference.",
    )


class ChatResponse(BaseModel):
    session_id: str
    message: str
    response: str
    response_time: float
    tool_calls: list[str]
    provider: str
    model: str
    allowed_tables: list[str]
    requested_tables: list[str]
    llm_configured: bool
