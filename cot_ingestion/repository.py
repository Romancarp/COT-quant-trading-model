from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker

from config import DB_URL
from cot_ingestion.mapping import DerivedPositionRecord
from cot_ingestion.models import Base, CanonicalPosition, DerivedPosition, IngestionError, IngestionRun, IngestionState
from cot_ingestion.normalizer import CanonicalPositionRecord


class COTRepository:
    def __init__(self, db_url: str = DB_URL):
        self.engine = create_engine(db_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, future=True)

    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def create_run(self) -> int:
        with self.SessionLocal() as s:
            run = IngestionRun(status="running")
            s.add(run)
            s.commit()
            s.refresh(run)
            return run.id

    def finish_run(self, run_id: int, status: str, new_rows: int, updated_rows: int, skipped_rows: int, error_count: int, details: dict | None = None) -> None:
        with self.SessionLocal() as s:
            run = s.get(IngestionRun, run_id)
            if not run:
                return
            run.finished_at = datetime.now()
            run.status = status
            run.new_rows = new_rows
            run.updated_rows = updated_rows
            run.skipped_rows = skipped_rows
            run.error_count = error_count
            run.details_json = details
            s.commit()

    def log_error(self, run_id: int, report_format: str, rid: str | None, error_type: str, message: str, payload_excerpt: str | None = None) -> None:
        with self.SessionLocal() as s:
            s.add(
                IngestionError(
                    run_id=run_id,
                    report_format=report_format,
                    report_date_or_release_id=rid,
                    error_type=error_type,
                    message=message,
                    payload_excerpt=payload_excerpt,
                )
            )
            s.commit()

    def get_state(self, key: str) -> str | None:
        with self.SessionLocal() as s:
            state = s.get(IngestionState, key)
            return state.value if state else None

    def set_state(self, key: str, value: str) -> None:
        with self.SessionLocal() as s:
            state = s.get(IngestionState, key)
            if state:
                state.value = value
                state.updated_at = datetime.now()
            else:
                s.add(IngestionState(key=key, value=value))
            s.commit()

    def _insert_stmt(self, table):
        if self.engine.dialect.name == "postgresql":
            return pg_insert(table)
        return sqlite_insert(table)

    def _batch_size(self) -> int:
        return 250 if self.engine.dialect.name == "sqlite" else 2000

    def upsert_canonical(self, records: list[CanonicalPositionRecord]) -> tuple[int, int]:
        if not records:
            return 0, 0

        rows = [r.__dict__ for r in records]
        batch_size = self._batch_size()
        with self.SessionLocal() as s:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                stmt = self._insert_stmt(CanonicalPosition).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["report_date", "report_format", "cftc_contract_market_code", "trader_category"],
                    set_={
                        "as_of_date": stmt.excluded.as_of_date,
                        "futures_only_or_combined": stmt.excluded.futures_only_or_combined,
                        "market_name": stmt.excluded.market_name,
                        "long_pos": stmt.excluded.long_pos,
                        "short_pos": stmt.excluded.short_pos,
                        "open_interest": stmt.excluded.open_interest,
                        "source_file": stmt.excluded.source_file,
                        "source_hash": stmt.excluded.source_hash,
                        "updated_at": datetime.now(),
                    },
                )
                s.execute(stmt)
            s.commit()
        return len(rows), 0

    def upsert_derived(self, rows_in: list[DerivedPositionRecord]) -> tuple[int, int]:
        if not rows_in:
            return 0, 0
        rows = [r.__dict__ for r in rows_in]
        batch_size = self._batch_size()
        with self.SessionLocal() as s:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                stmt = self._insert_stmt(DerivedPosition).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["asset", "trader_group", "report_date"],
                    set_={
                        "long_pos": stmt.excluded.long_pos,
                        "short_pos": stmt.excluded.short_pos,
                        "open_interest": stmt.excluded.open_interest,
                    },
                )
                s.execute(stmt)
            s.commit()
        return len(rows), 0

    def fetch_derived_rows(self, asset: str, trader_group: str) -> list[tuple]:
        with self.SessionLocal() as s:
            stmt = (
                select(DerivedPosition.report_date, DerivedPosition.long_pos, DerivedPosition.short_pos, DerivedPosition.open_interest)
                .where(DerivedPosition.asset == asset, DerivedPosition.trader_group == trader_group)
                .order_by(DerivedPosition.report_date)
            )
            return list(s.execute(stmt).all())

    def has_derived_data(self, asset: str, trader_group: str) -> bool:
        with self.SessionLocal() as s:
            stmt = select(DerivedPosition.asset).where(DerivedPosition.asset == asset, DerivedPosition.trader_group == trader_group).limit(1)
            return s.execute(stmt).first() is not None
