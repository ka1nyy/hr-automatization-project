from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApprovalStage:
    code: str
    name: str
    permission: str
    role_label: str


APPROVAL_STAGES = (
    ApprovalStage(
        "hr_director",
        "Директор департамента документооборота и управления персоналом",
        "hiring.approve.hr_director",
        "Директор департамента документооборота и управления персоналом",
    ),
    ApprovalStage(
        "economic_director",
        "Директор департамента экономического планирования",
        "hiring.approve.economic",
        "Директор департамента экономического планирования",
    ),
    ApprovalStage(
        "competition_commission",
        "Конкурсная комиссия",
        "hiring.approve.commission",
        "Конкурсная комиссия",
    ),
    ApprovalStage(
        "legal_department",
        "Юридический департамент",
        "hiring.approve.legal",
        "Юридический департамент",
    ),
    ApprovalStage(
        "chairman", "Председатель правления", "hiring.approve.chairman", "Председатель правления"
    ),
)

EDITABLE_STATUSES = frozenset({"draft", "returned"})
REQUIRED_ATTACHMENT_CATEGORIES = frozenset({"identity", "diploma"})
