"""Source protocol. Every data source implements fetch + load + refresh."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb


@dataclass
class RefreshResult:
    source: str
    rows_loaded: int
    status: str
    error: str | None = None


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self, raw_dir: Path) -> Path:
        """Download to raw_dir; return path to the file written."""

    @abstractmethod
    def load(self, con: duckdb.DuckDBPyConnection, raw_path: Path) -> int:
        """Parse the raw file and load into the warehouse. Return rows loaded."""

    def refresh(
        self,
        con: duckdb.DuckDBPyConnection,
        raw_dir: Path,
        from_fixture: Path | None = None,
    ) -> RefreshResult:
        started = datetime.utcnow()
        rows = 0
        status = "ok"
        error: str | None = None
        try:
            raw_path = from_fixture if from_fixture is not None else self.fetch(raw_dir)
            rows = self.load(con, raw_path)
        except Exception as exc:
            status = "error"
            error = str(exc)
        finally:
            con.execute(
                "INSERT INTO refresh_log VALUES (?, ?, ?, ?, ?, ?)",
                [self.name, started, datetime.utcnow(), rows, status, error],
            )
            # Persist a manifest entry so freshness can be queried without
            # opening DuckDB. Best-effort: never let manifest IO mask the
            # actual refresh result.
            try:
                from rental.manifest import update_manifest

                update_manifest(
                    source=self.name,
                    rows_loaded=rows,
                    status=status,
                    error=error,
                    when=datetime.now(UTC),
                )
            except Exception:
                pass
        return RefreshResult(self.name, rows, status, error)
