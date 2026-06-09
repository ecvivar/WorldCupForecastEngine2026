import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.cache_decorator import cached
from app.core.dependencies import PaginationParams, get_db
from app.schemas.match import MatchCreate, MatchPrediction, MatchResponse
from app.services.match_service import MatchService

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("", response_model=list[MatchResponse])
@cached("matches:list")
def list_matches(
    pagination: PaginationParams = Depends(),
    stage: str | None = Query(None, description="Filter by stage"),
    db: Session = Depends(get_db),
):
    service = MatchService(db)
    return service.get_all(skip=pagination.offset, limit=pagination.limit, stage=stage)


@router.get("/{match_id}", response_model=MatchResponse)
@cached("matches:detail")
def get_match(match_id: uuid.UUID, db: Session = Depends(get_db)):
    service = MatchService(db)
    match = service.get_by_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.post("", response_model=MatchResponse, status_code=201)
def create_match(data: MatchCreate, db: Session = Depends(get_db)):
    service = MatchService(db)
    return service.create(data)


@router.get("/{match_id}/prediction", response_model=MatchPrediction)
@cached("matches:prediction")
def predict_match(match_id: uuid.UUID, db: Session = Depends(get_db)):
    service = MatchService(db)
    prediction = service.get_predictions(match_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Match not found")
    return prediction
