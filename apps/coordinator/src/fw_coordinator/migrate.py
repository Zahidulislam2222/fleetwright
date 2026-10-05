"""Apply database migrations: `python -m fw_coordinator.migrate` (role fw_owner)."""

from importlib import resources

from alembic import command
from alembic.config import Config

from fw_core.db import make_engine
from fw_core.logs import setup_logging
from fw_core.settings import MigrationSettings, load


def upgrade(revision: str = "head") -> None:
    cfg = load(MigrationSettings)
    setup_logging("migrate", cfg.log_level)
    engine = make_engine(cfg.owner_db.dsn, cfg.owner_db, "fw-migrate")
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(resources.files("fw_coordinator").joinpath("migrations")))
    alembic_cfg.attributes["engine"] = engine
    command.upgrade(alembic_cfg, revision)


if __name__ == "__main__":
    upgrade()
