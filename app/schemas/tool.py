from pydantic import BaseModel, Field


class ToolDefinitionResponse(BaseModel):
    name: str
    description: str
    input_schema: dict[str, object] = Field(default_factory=dict)


class AllowedTablesResponse(BaseModel):
    tables: list[str]


class TableColumnResponse(BaseModel):
    name: str
    data_type: str
    nullable: bool


class DescribeTableResponse(BaseModel):
    table_name: str
    columns: list[TableColumnResponse]


class QueryTableRequest(BaseModel):
    table_name: str = Field(min_length=1)
    columns: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)


class QueryTableResponse(BaseModel):
    table_name: str
    columns: list[str]
    row_count: int
    rows: list[dict[str, object]]
