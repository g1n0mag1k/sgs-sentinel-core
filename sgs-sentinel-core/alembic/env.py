from sqlalchemy import engine_from_config, pool
from alembic import context
from sgs_sentinel_core.config import DATABASE_URL

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
from logging.config import fileConfig
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from sgs_sentinel_core.models import Base  # Assuming Base is your declarative base
target_metadata = Base.metadata

# other values from the config, defined by the needs of
# your application, can be accessed via config.get_main_option()
def get_url():
    return DATABASE_URL

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()