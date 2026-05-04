from pydantic import BaseModel


class Prediction(BaseModel):
    label: str
    score: float


class AudioResult(BaseModel):
    result_id: int
    user_email: str
    filename: str
    size_bytes: int
    storage: str
    location: str
    model_name: str
    predictions: list[Prediction]
    created_at: str


class AudioResultsResponse(BaseModel):
    items: list[AudioResult]
    limit: int
    offset: int
