import json
import time
import uuid
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.core.cache import get_cache
from app.core.logging import log_simulation
from app.core.metrics import record_simulation_duration
from app.domain.entities import SimulationConfig, TeamEntity
from app.engine.igf import IGFEngine
from app.engine.monte_carlo import MonteCarloEngine
from app.models.elo_rating import EloRating
from app.models.fifa_ranking import FifaRanking
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.models.simulation import Simulation, SimulationResult
from app.models.team import Team
from app.models.xg_metrics import XGMetrics
from app.schemas.simulation import SimulationCreate


class SimulationService:
    def __init__(self, db: Session):
        self.db = db
        self.engine = MonteCarloEngine()
        self.igf_engine = IGFEngine()

    def get_all(self, skip: int = 0, limit: int = 20) -> list[Simulation]:
        cache_key = f"simulations:list:skip={skip}:limit={limit}"
        cache = get_cache()
        cached = cache.get_sync(cache_key)
        if cached is not None:
            return cached
        result = (
            self.db.query(Simulation)
            .order_by(Simulation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        cache.set_sync(cache_key, result)
        return result

    def get_by_id(self, sim_id: uuid.UUID) -> Simulation | None:
        cache_key = f"simulations:detail:{sim_id}"
        cache = get_cache()
        cached = cache.get_sync(cache_key)
        if cached is not None:
            return cached
        result = (
            self.db.query(Simulation)
            .options(joinedload(Simulation.results).joinedload(SimulationResult.team))
            .filter(Simulation.id == sim_id)
            .first()
        )
        if result:
            cache.set_sync(cache_key, result)
        return result

    def create(self, data: SimulationCreate) -> Simulation:
        sim = Simulation(
            competition_id=data.competition_id,
            name=data.name or f"Simulation_{datetime.utcnow().isoformat()}",
            num_simulations=data.num_simulations,
            config=json.dumps(data.config) if data.config else None,
        )
        self.db.add(sim)
        self.db.commit()
        self.db.refresh(sim)
        cache = get_cache()
        cache.invalidate("simulations:list:*")
        return sim

    def _load_team_entities(self) -> tuple[list[TeamEntity], dict[uuid.UUID, str]]:
        """Load all teams with full IGF scores and real group mappings."""
        teams = self.db.query(Team).all()
        group_standings = self.db.query(GroupStanding).options(
            joinedload(GroupStanding.group), joinedload(GroupStanding.team)
        ).all()

        team_to_group = {}
        for gs in group_standings:
            if gs.team_id not in team_to_group:
                team_to_group[gs.team_id] = gs.group.name

        # Build DataFrame for full IGF computation
        rows = []
        for team in teams:
            latest_elo = (
                self.db.query(EloRating)
                .filter(EloRating.team_id == team.id)
                .order_by(EloRating.rating_date.desc())
                .first()
            )
            latest_fifa = (
                self.db.query(FifaRanking)
                .filter(FifaRanking.team_id == team.id)
                .order_by(FifaRanking.ranking_date.desc())
                .first()
            )
            latest_xg = (
                self.db.query(XGMetrics)
                .filter(XGMetrics.team_id == team.id)
                .order_by(XGMetrics.metric_date.desc())
                .first()
            )
            rows.append({
                "team_name": team.name,
                "elo_score": latest_elo.elo_score if latest_elo else 1500,
                "fifa_rank": latest_fifa.rank if latest_fifa else 100,
                "xg_for": latest_xg.xg_for if latest_xg else 1.0,
                "xg_against": latest_xg.xg_against if latest_xg else 1.0,
            })

        df = pd.DataFrame(rows)
        all_igf = self.igf_engine.compute_team_scores(df)

        # Index row data by team name for fast lookup
        team_data_map = {r["team_name"]: r for r in rows}

        team_entities = []
        group_mapping = {}

        for team in teams:
            igf_info = all_igf.get(team.name, {"igf_score": 50.0})
            data_row = team_data_map.get(team.name, {})

            entity = TeamEntity(
                id=team.id,
                name=team.name,
                fifa_code=team.fifa_code,
                continent=team.continent,
                elo_score=data_row.get("elo_score", 1500),
                fifa_rank=data_row.get("fifa_rank", 100),
                igf_score=igf_info.get("igf_score", 50.0),
            )
            team_entities.append(entity)
            group_mapping[team.id] = team_to_group.get(team.id, "A")

        return team_entities, group_mapping

    def run_simulation(self, sim_id: uuid.UUID) -> Simulation | None:
        sim = self.get_by_id(sim_id)
        if not sim:
            return None

        sim.status = "running"
        self.db.commit()

        start = time.time()
        team_entities, group_mapping = self._load_team_entities()

        config = SimulationConfig(
            num_simulations=sim.num_simulations,
        )
        self.engine.config = config
        results = self.engine.run(team_entities, group_mapping)

        for r in results:
            sr = SimulationResult(
                simulation_id=sim_id,
                team_id=r.team_id,
                group_name=r.group_name,
                group_position=r.group_position,
                reached_round_of_32=r.round_of_32_count,
                reached_round_of_16=r.round_of_16_count,
                reached_quarter_final=r.quarter_final_count,
                reached_semi_final=r.semi_final_count,
                reached_final=r.final_count,
                won_tournament=r.won_count,
                points=r.total_points,
            )
            self.db.add(sr)

        sim.status = "completed"
        sim.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sim)

        duration = time.time() - start
        record_simulation_duration(duration * 1000)
        log_simulation(
            simulation_id=str(sim_id),
            teams=len(team_entities),
            iterations=sim.num_simulations,
            duration=duration,
            success=True,
        )

        cache = get_cache()
        cache.invalidate("simulations:list:*")
        cache.invalidate(f"simulations:detail:{sim_id}")
        cache.invalidate("dashboard:*")
        cache.invalidate("rankings:*")

        return sim
