import pytest
from app.core.errors import ConflictError
from app.modules.hiring_requests.service import format_employee_identity


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
