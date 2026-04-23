from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="User message to send to the chat service.")
    tables: list[str] = Field(
        default_factory=list,
        description="Optional database tables the chat request is allowed to reference.",
    )


class ChatResponse(BaseModel):
    message: str
    response: str
    provider: str
    model: str
    database_url: str
    allowed_tables: list[str]
    requested_tables: list[str]
    llm_configured: bool
