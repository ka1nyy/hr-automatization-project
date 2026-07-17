from datetime import date

import pytest
from app.core.errors import ConflictError
from app.modules.hiring_requests.service import (
    calculate_probation_end,
    format_employee_identity,
    resolve_department_director,
)


@pytest.mark.parametrize(
    ("sequence_value", "employee_number", "corporate_email"),
    [
        (1, "000001", "ertis000001@ertis.kz"),
        (42, "000042", "ertis000042@ertis.kz"),
        (999_999, "999999", "ertis999999@ertis.kz"),
    ],
)
def test_format_employee_identity(
    sequence_value: int, employee_number: str, corporate_email: str
) -> None:
    assert format_employee_identity(sequence_value) == (employee_number, corporate_email)


@pytest.mark.parametrize("sequence_value", [0, -1, 1_000_000])
def test_format_employee_identity_rejects_values_outside_six_digits(
    sequence_value: int,
) -> None:
    with pytest.raises(ConflictError):
        format_employee_identity(sequence_value)


@pytest.mark.parametrize("value", [0, None, "", -1, "invalid"])
def test_calculate_probation_end_returns_none_when_probation_is_absent(value: object) -> None:
    assert calculate_probation_end(date(2026, 7, 17), value) is None


@pytest.mark.parametrize(
    ("hire_date", "months", "expected"),
    [
        (date(2026, 7, 17), 3, date(2026, 10, 17)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2027, 11, 30), 3, date(2028, 2, 29)),
    ],
)
def test_calculate_probation_end_uses_contract_months(
    hire_date: date, months: int, expected: date
) -> None:
    assert calculate_probation_end(hire_date, months) == expected


@pytest.mark.parametrize(
    ("department", "expected"),
    [
        ("Департамент управления персоналом", "Сауле Бекенова"),
        ("Департамент цифровой трансформации", "Мирас Абдрахманов"),
        ("Строительный департамент", "Нуржан Тлеубаев"),
        ("Юридический департамент", "Елена Ким"),
        ("Департамент экономического планирования", "Руслан Ибраев"),
    ],
)
def test_resolve_department_director_uses_department_configuration(
    department: str, expected: str
) -> None:
    assert resolve_department_director(department, "Не указан") == expected


def test_resolve_department_director_falls_back_to_requested_manager() -> None:
    assert resolve_department_director("Новый департамент", "Алия Сарсенова") == (
        "Алия Сарсенова"
    )
    assert resolve_department_director("Новый департамент", "Не указан") is None
