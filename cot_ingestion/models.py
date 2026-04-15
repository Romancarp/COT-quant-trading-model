from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CanonicalPosition(Base):
    __tablename__ = "cot_positions_canonical"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    report_format: Mapped[str] = mapped_column(String(64), nullable=False)
    futures_only_or_combined: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cftc_contract_market_code: Mapped[str] = mapped_column(String(32), nullable=False)
    market_name: Mapped[str] = mapped_column(Text, nullable=False)
    trader_category: Mapped[str] = mapped_column(String(32), nullable=False)
    long_pos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    short_pos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    open_interest: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "report_date",
            "report_format",
            "cftc_contract_market_code",
            "trader_category",
            name="uq_cot_canonical_week_contract_cat",
        ),
        Index("ix_cot_canonical_report_date", "report_date"),
        Index("ix_cot_canonical_contract", "cftc_contract_market_code"),
    )


class DerivedPosition(Base):
    __tablename__ = "cot_positions"

    asset: Mapped[str] = mapped_column(String(32), primary_key=True)
    trader_group: Mapped[str] = mapped_column(String(32), primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, primary_key=True)
    long_pos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    short_pos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    open_interest: Mapped[int] = mapped_column(BigInteger, nullable=False)


class WeeklyPrice(Base):
    __tablename__ = "weekly_prices"

    asset: Mapped[str] = mapped_column(String(32), primary_key=True)
    price_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        Index("ix_weekly_prices_asset_date", "asset", "price_date"),
    )


class IngestionRun(Base):
    __tablename__ = "cot_ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    new_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details_json: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)


class IngestionState(Base):
    __tablename__ = "cot_ingestion_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class IngestionError(Base):
    __tablename__ = "cot_ingestion_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cot_ingestion_runs.id"), nullable=False)
    report_format: Mapped[str] = mapped_column(String(64), nullable=False)
    report_date_or_release_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
