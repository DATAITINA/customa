from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from msflib.seed.cli import run_seed_cli

from app.core.config import settings


def _import_models() -> None:
    from app import models  # noqa: F401


def main(argv: Sequence[str] | None = None) -> None:
    seed_dir = Path(__file__).resolve().parent
    run_seed_cli(
        argv=argv,
        description="Run testsite seeders using msflib core seeding infrastructure.",
        default_seeders_yml=str(seed_dir / "seeders.yml"),
        default_data_paths=[str(seed_dir / "data")],
        core_settings=settings.scope("CORE"),
        import_models=_import_models,
    )


if __name__ == "__main__":
    main()
