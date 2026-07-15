# Alembic migrations

This directory is the only production schema creation path. Run `alembic upgrade head`; the web
application does not call SQLAlchemy `create_all`.
