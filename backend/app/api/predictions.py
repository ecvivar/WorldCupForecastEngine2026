from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.cache_decorator import cached
from app.core.dependencies import PaginationParams, get_db
from app.core.rate_limit import limiter
from app.schemas.match import MatchPrediction
from app.schemas.ranking import IGFScoreResponse
from app.services.match_service import MatchService
from app.services.ranking_service import RankingService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("", response_model=list[MatchPrediction])
@cached("predictions:list")
@limiter.limit("10/minute")
def list_predictions(
    request: Request,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    service = MatchService(db)
    matches = service.get_all(skip=pagination.offset, limit=pagination.limit)
    predictions = []
    for match in matches:
        pred = service.get_predictions(match.id)
        if pred:
            predictions.append(pred)
    return predictions


@router.get("/rankings", response_model=list[IGFScoreResponse])
@cached("predictions:rankings")
def get_igf_rankings(db: Session = Depends(get_db)):
    service = RankingService(db)
    return service.compute_igf()
