from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.competition import Competition
from app.schemas.competition import CompetitionResponse

router = APIRouter(prefix="/competitions", tags=["Competitions"])


@router.get("", response_model=list[CompetitionResponse])
def list_competitions(db: Session = Depends(get_db)):
    return db.query(Competition).all()
