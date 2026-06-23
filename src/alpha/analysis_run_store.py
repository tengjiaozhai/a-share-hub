import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.core.tenant import TenantContext
from src.storage.models import AlphaAnalysisRunEventRow, AlphaAnalysisRunRow


class AnalysisRunStore:
    def __init__(self, engine: Engine, tenant: TenantContext) -> None:
        self._engine = engine
        self._tenant = tenant

    def create_run(self, *, symbol: str, model_name: str) -> str:
        now = datetime.utcnow()
        run_id = f"alpha-ar-{int(now.timestamp() * 1000)}"
        with Session(self._engine) as session:
            row = AlphaAnalysisRunRow(
                run_id=run_id,
                user_id=self._tenant.user_id,
                symbol=symbol,
                status="accepted",
                current_stage="accepted",
                started_at=now,
                updated_at=now,
                model_name=model_name,
            )
            session.add(row)
            session.commit()
        return run_id

    def update_run(self, run_id: str, **fields: Any) -> None:
        field_map = {
            "snapshot": "snapshot_json",
            "research": "research_json",
            "trader": "trader_json",
            "risk": "risk_json",
            "backtest": "backtest_json",
        }
        for src, dst in field_map.items():
            if src in fields:
                fields[dst] = json.dumps(fields.pop(src), ensure_ascii=False, sort_keys=True)
        fields["updated_at"] = datetime.utcnow()
        with Session(self._engine) as session:
            session.execute(
                update(AlphaAnalysisRunRow)
                .where(AlphaAnalysisRunRow.run_id == run_id)
                .where(AlphaAnalysisRunRow.user_id == self._tenant.user_id)
                .values(**fields)
            )
            session.commit()

    def append_event(
        self,
        *,
        run_id: str,
        stage: str,
        status: str,
        payload: dict | None = None,
        event_type: str = "stage",
    ) -> int:
        with Session(self._engine) as session:
            existing_max = session.execute(
                select(AlphaAnalysisRunEventRow.seq)
                .where(AlphaAnalysisRunEventRow.run_id == run_id)
                .where(AlphaAnalysisRunEventRow.user_id == self._tenant.user_id)
                .order_by(AlphaAnalysisRunEventRow.seq.desc())
                .limit(1)
            ).scalar_one_or_none()
            next_seq = (existing_max or 0) + 1
            event = AlphaAnalysisRunEventRow(
                user_id=self._tenant.user_id,
                run_id=run_id,
                seq=next_seq,
                event_type=event_type,
                stage=stage,
                status=status,
                payload_json=json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
            )
            session.add(event)
            session.commit()
            return next_seq

    def list_events(self, run_id: str, after_seq: int = 0) -> list[dict]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(AlphaAnalysisRunEventRow)
                .where(AlphaAnalysisRunEventRow.run_id == run_id)
                .where(AlphaAnalysisRunEventRow.user_id == self._tenant.user_id)
                .where(AlphaAnalysisRunEventRow.seq > after_seq)
                .order_by(AlphaAnalysisRunEventRow.seq.asc())
            ).scalars().all()
            return [self._event_to_dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict | None:
        with Session(self._engine) as session:
            row = session.execute(
                select(AlphaAnalysisRunRow)
                .where(AlphaAnalysisRunRow.run_id == run_id)
                .where(AlphaAnalysisRunRow.user_id == self._tenant.user_id)
            ).scalar_one_or_none()
            return self._run_to_dict(row) if row else None

    def get_run_detail(self, run_id: str) -> dict | None:
        with Session(self._engine) as session:
            row = session.execute(
                select(AlphaAnalysisRunRow)
                .where(AlphaAnalysisRunRow.run_id == run_id)
                .where(AlphaAnalysisRunRow.user_id == self._tenant.user_id)
            ).scalar_one_or_none()
            if not row:
                return None
            return self._run_to_detail_dict(row, session)

    def list_runs(
        self,
        *,
        market: str | None = None,
        status_filter: str | None = None,
        limit: int = 20,
        cursor_run_id: str | None = None,
    ) -> dict:
        limit = max(1, min(limit, 100))
        with Session(self._engine) as session:
            stmt = select(AlphaAnalysisRunRow).where(AlphaAnalysisRunRow.user_id == self._tenant.user_id)
            if market == "us":
                stmt = stmt.where(AlphaAnalysisRunRow.symbol.like("%.US"))
            elif market == "a":
                stmt = stmt.where(~AlphaAnalysisRunRow.symbol.like("%.US"))
            if status_filter and status_filter != "all":
                stmt = stmt.where(AlphaAnalysisRunRow.status == status_filter)
            if cursor_run_id:
                cursor_row = session.execute(
                    select(AlphaAnalysisRunRow.created_at, AlphaAnalysisRunRow.run_id)
                    .where(AlphaAnalysisRunRow.run_id == cursor_run_id)
                    .where(AlphaAnalysisRunRow.user_id == self._tenant.user_id)
                ).first()
                if cursor_row:
                    stmt = stmt.where(
                        (AlphaAnalysisRunRow.created_at < cursor_row[0])
                        | (
                            (AlphaAnalysisRunRow.created_at == cursor_row[0])
                            & (AlphaAnalysisRunRow.run_id < cursor_row[1])
                        )
                    )
            stmt = stmt.order_by(
                AlphaAnalysisRunRow.created_at.desc(),
                AlphaAnalysisRunRow.run_id.desc(),
            ).limit(limit + 1)
            rows = session.execute(stmt).scalars().all()
            has_more = len(rows) > limit
            rows = rows[:limit]
            items = [self._run_to_summary_dict(row, session) for row in rows]
            next_cursor = rows[-1].run_id if has_more and rows else None
            return {"items": items, "next_cursor": next_cursor}

    def find_active_run(self, *, symbol: str | None = None) -> dict | None:
        with Session(self._engine) as session:
            stmt = (
                select(AlphaAnalysisRunRow)
                .where(AlphaAnalysisRunRow.user_id == self._tenant.user_id)
                .where(AlphaAnalysisRunRow.status.in_(["accepted", "running"]))
            )
            if symbol:
                stmt = stmt.where(AlphaAnalysisRunRow.symbol == symbol)
            stmt = stmt.order_by(AlphaAnalysisRunRow.created_at.desc()).limit(1)
            row = session.execute(stmt).scalar_one_or_none()
            return self._run_to_dict(row) if row else None

    def find_any_active_run(self) -> dict | None:
        return self.find_active_run()

    @staticmethod
    def _run_to_dict(row: AlphaAnalysisRunRow) -> dict:
        return {
            "run_id": row.run_id,
            "user_id": row.user_id,
            "symbol": row.symbol,
            "status": row.status,
            "current_stage": row.current_stage,
            "model_name": row.model_name,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "error": row.error,
            "error_stage": row.error_stage,
        }

    def _run_to_summary_dict(self, row: AlphaAnalysisRunRow, session: Session) -> dict:
        risk = json.loads(row.risk_json) if row.risk_json else None
        research = json.loads(row.research_json) if row.research_json else None
        snapshot = json.loads(row.snapshot_json) if row.snapshot_json else None
        return {
            "run_id": row.run_id,
            "symbol": row.symbol,
            "market": "us" if row.symbol.endswith(".US") else "a",
            "status": row.status,
            "current_stage": row.current_stage,
            "risk_action": risk.get("action") if isinstance(risk, dict) else None,
            "research_rating": research.get("rating") if isinstance(research, dict) else None,
            "research_confidence": research.get("confidence") if isinstance(research, dict) else None,
            "close_date": snapshot.get("as_of") if isinstance(snapshot, dict) else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }

    def _run_to_detail_dict(self, row: AlphaAnalysisRunRow, session: Session) -> dict:
        snapshot = json.loads(row.snapshot_json) if row.snapshot_json else None
        research = json.loads(row.research_json) if row.research_json else None
        trader = json.loads(row.trader_json) if row.trader_json else None
        risk = json.loads(row.risk_json) if row.risk_json else None
        backtest = json.loads(row.backtest_json) if row.backtest_json else None
        events = session.execute(
            select(AlphaAnalysisRunEventRow)
            .where(AlphaAnalysisRunEventRow.run_id == row.run_id)
            .where(AlphaAnalysisRunEventRow.user_id == self._tenant.user_id)
            .order_by(AlphaAnalysisRunEventRow.seq.asc())
        ).scalars().all()
        return {
            "run_id": row.run_id,
            "symbol": row.symbol,
            "market": "us" if row.symbol.endswith(".US") else "a",
            "status": row.status,
            "current_stage": row.current_stage,
            "model_name": row.model_name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "snapshot": snapshot,
            "research": research,
            "trader": trader,
            "risk": risk,
            "backtest": backtest,
            "error": row.error,
            "error_stage": row.error_stage,
            "events": [self._event_to_dict(e) for e in events],
        }

    @staticmethod
    def _event_to_dict(row: AlphaAnalysisRunEventRow) -> dict:
        return {
            "event_id": row.event_id,
            "user_id": row.user_id,
            "seq": row.seq,
            "stage": row.stage,
            "status": row.status,
            "event_type": row.event_type,
            "payload": json.loads(row.payload_json) if row.payload_json else {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
