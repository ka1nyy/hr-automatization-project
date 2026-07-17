"""store hiring position, department, employment type and manager on employees

Revision ID: 0011_employee_hiring_profile
Revises: 0010_employee_probation_end
"""

# ruff: noqa: RUF001

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_employee_hiring_profile"
down_revision: str | None = "0010_employee_probation_end"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("position_title", sa.String(255), nullable=True))
    op.add_column("employees", sa.Column("department_name", sa.String(255), nullable=True))
    op.add_column("employees", sa.Column("manager_name", sa.String(500), nullable=True))
    op.add_column(
        "employees", sa.Column("employment_type_label", sa.String(128), nullable=True)
    )
    op.execute(
        """
        UPDATE employees AS employee
        SET position_title = NULLIF(request.employment_data ->> 'position', ''),
            department_name = NULLIF(request.employment_data ->> 'department', ''),
            employment_type_label = NULLIF(request.employment_data ->> 'employmentType', ''),
            manager_name = CASE request.employment_data ->> 'department'
                WHEN 'Департамент управления персоналом' THEN 'Сауле Бекенова'
                WHEN 'Департамент документооборота и управления персоналом' THEN 'Сауле Бекенова'
                WHEN 'Департамент цифровой трансформации' THEN 'Мирас Абдрахманов'
                WHEN 'Строительный департамент' THEN 'Нуржан Тлеубаев'
                WHEN 'Юридический департамент' THEN 'Елена Ким'
                WHEN 'Департамент экономического планирования' THEN 'Руслан Ибраев'
                ELSE NULLIF(NULLIF(request.employment_data ->> 'manager', ''), 'Не указан')
            END
        FROM new_employee_hiring_requests AS request
        WHERE request.hired_employee_id = employee.id
        """
    )


def downgrade() -> None:
    op.drop_column("employees", "employment_type_label")
    op.drop_column("employees", "manager_name")
    op.drop_column("employees", "department_name")
    op.drop_column("employees", "position_title")
