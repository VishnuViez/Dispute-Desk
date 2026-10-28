"""
models.py – Shared Pydantic response models.

Field descriptions are written for a non-expert reader because
IBM watsonx Orchestrate uses them to understand what each field means.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Always 'ok' when the API is running.")
    database: str = Field(
        description="'connected' if the database file is present, 'missing' if not."
    )
