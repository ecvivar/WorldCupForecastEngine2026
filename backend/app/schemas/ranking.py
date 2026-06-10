import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class EloRatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    rating_date: date
    elo_score: int
    rank: int | None = None


class FifaRankingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    ranking_date: date
    rank: int
    previous_rank: int | None = None
    total_points: float
    confederation: str | None = None


class IGFScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: uuid.UUID
    team_name: str
    igf_score: float
    components: dict[str, float]
