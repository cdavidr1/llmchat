from pydantic import BaseModel, Field


class ConfigSourceResponse(BaseModel):
    source: str
    config_dir: str
    loaded_files: list[str] = Field(default_factory=list)
    fallback_config_dir: str | None = None
    fallback_loaded_files: list[str] = Field(default_factory=list)
