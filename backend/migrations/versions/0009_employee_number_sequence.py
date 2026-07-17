"""add a permanent sequence for six-digit employee numbers

Revision ID: 0009_employee_number_sequence
Revises: 0008_merge_module4_hiring_auto
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_employee_number_sequence"
down_revision: str | None = "0008_merge_module4_hiring_auto"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE SEQUENCE employee_number_seq AS BIGINT "
        "MINVALUE 1 MAXVALUE 999999 START WITH 1 INCREMENT BY 1 NO CYCLE"
    )
    op.execute(
        """
        DO $$
        DECLARE
            current_max BIGINT;
        BEGIN
            SELECT COALESCE(MAX(identifier), 0)
            INTO current_max
            FROM (
                SELECT employee_number::BIGINT AS identifier
                FROM employees
                WHERE employee_number ~ '^[0-9]{6}$'

                UNION ALL

                SELECT substring(
                    corporate_email FROM '^ertis([0-9]{6})@ertis[.]kz$'
                )::BIGINT AS identifier
                FROM employees
                WHERE corporate_email ~ '^ertis[0-9]{6}@ertis[.]kz$'
            ) AS existing_identifiers;

            IF current_max = 0 THEN
                PERFORM setval('employee_number_seq', 1, FALSE);
            ELSE
                PERFORM setval('employee_number_seq', current_max, TRUE);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE employee_number_seq")
