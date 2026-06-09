from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.cache_decorator import cached
from app.core.dependencies import PaginationParams, get_db
from app.schemas.ranking import EloRatingResponse, FifaRankingResponse, IGFScoreResponse
from app.services.ranking_service import RankingService

router = APIRouter(prefix="/rankings", tags=["Rankings"])


@router.get("/elo", response_model=list[dict])
@cached("rankings:elo")
def get_elo_rankings(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    service = RankingService(db)
    return service.get_latest_elo(limit=pagination.limit)


@router.get("/fifa", response_model=list[dict])
@cached("rankings:fifa")
def get_fifa_rankings(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    service = RankingService(db)
    return service.get_latest_fifa(limit=pagination.limit)


@router.get("/igf", response_model=list[IGFScoreResponse])
@cached("rankings:igf")
def get_igf_rankings(db: Session = Depends(get_db)):
    service = RankingService(db)
    return service.compute_igf()
