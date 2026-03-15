from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class LinkCreateRequest(BaseModel):
    original_url: AnyHttpUrl
    custom_alias: str | None = Field(default=None, min_length=3, max_length=32)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_minute_precision(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.second != 0 or value.microsecond != 0:
            raise ValueError("expires_at must have minute precision")
        return value


class LinkUpdateRequest(BaseModel):
    original_url: AnyHttpUrl


class LinkResponse(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None
    owner_id: int | None


class LinkStatsResponse(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime
    click_count: int
    last_accessed_at: datetime | None
    expires_at: datetime | None
