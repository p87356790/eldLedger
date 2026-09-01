from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="ok if the process and database are available")
    service: str
    database: str


class HelloResponse(BaseModel):
    message: str
    app: str
