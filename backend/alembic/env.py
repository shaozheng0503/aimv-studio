from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from DATABASE_URL env var (works in Docker and CI)
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url:
    # Alembic uses sync drivers; replace asyncpg with psycopg2
    _db_url = _db_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    config.set_main_option("sqlalchemy.url", _db_url)

# Import all models so Alembic can detect them
from app.models.base import Base
from app.models.user import User  # noqa
from app.models.project import Project, Task, Media  # noqa

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
