from pydantic import BaseModel


class DatabaseConnectionResponse(BaseModel):
    status: str
    database_type: str
    config_source: str
