from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .domain import APPROVAL_STAGES

STATUS_LABELS = {
    "draft": "Черновик",
    "pdf_generated": "PDF сформирован",
    "under_review": "На согласовании",
    "returned": "Возвращено",
    "rejected": "Отклонено",
    "final_approved": "Финально согласовано",
    "dispatched": "Отправлено в подразделения",
    "partially_acknowledged": "Получено частично",
    "completed": "Завершено",
}

DECISION_LABELS = {"approve": "Согласовано", "return": "Возвращено", "reject": "Отклонено"}


def _font_file() -> Path:
    root = files("rinoh_typeface_dejavusansmono")
    stack = [root]
    while stack:
        item = stack.pop()
        if item.name.casefold() == "dejavusansmono.ttf":
            return Path(str(item))
        if item.is_dir():
            stack.extend(item.iterdir())
    raise RuntimeError("Bundled DejaVu Sans Mono font is missing")


def _font() -> str:
    name = "HiringDejaVu"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(_font_file())))
    return name


def _value(value: object) -> str:
    return "-" if value is None or value == "" else escape(str(value))


def _section(title: str, rows: Iterable[tuple[str, object]], font: str) -> list[Flowable]:
    heading = ParagraphStyle(
        "section",
        fontName=font,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#344054"),
        spaceBefore=8,
        spaceAfter=5,
        keepWithNext=True,
    )
    body = ParagraphStyle("body", fontName=font, fontSize=8.5, leading=11)
    table = Table(
        [[Paragraph(escape(label), body), Paragraph(_value(value), body)] for label, value in rows],
        colWidths=[62 * mm, 112 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F4F7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [Paragraph(escape(title), heading), table, Spacer(1, 4 * mm)]


def render_hiring_request_pdf(
    request: Mapping[str, Any],
    personal: Mapping[str, Any],
    decisions: list[Mapping[str, Any]],
    attachments: list[Mapping[str, Any]],
) -> bytes:
    font = _font()
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Заявление о найме нового сотрудника",
    )
    title = ParagraphStyle(
        "title",
        fontName=font,
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#101828"),
        spaceAfter=8 * mm,
    )
    normal = ParagraphStyle("normal", fontName=font, fontSize=8.5, leading=11)
    right = ParagraphStyle(
        "recipient", fontName=font, fontSize=9, leading=12, alignment=TA_RIGHT, spaceAfter=7 * mm
    )
    request_number = str(request.get("requestNumber") or "-")
    employment = request.get("employmentData", {})
    education = request.get("educationData", {})
    story: list[Flowable] = [
        Paragraph(
            "<b>Кому:</b> "
            f"{_value(employment.get('recipientPosition'))}<br/>"
            f"{_value(employment.get('recipient'))}<br/>"
            f"{_value(employment.get('recipientDepartment'))}",
            right,
        ),
        Paragraph("ЗАЯВЛЕНИЕ О НАЙМЕ НОВОГО СОТРУДНИКА", title),
        Paragraph(
            f"<b>№ {_value(request_number)}</b> &nbsp;&nbsp; от "
            f"{_value(employment.get('requestDate') or request.get('createdAt'))}",
            ParagraphStyle(
                "document-number", parent=normal, alignment=TA_CENTER, spaceAfter=6 * mm
            ),
        ),
        Paragraph(
            _value(employment.get("requestText")),
            ParagraphStyle(
                "request-text", parent=normal, fontSize=9.5, leading=14, spaceAfter=5 * mm
            ),
        ),
    ]
    story += _section(
        "Инициатор и реквизиты",
        [
            ("Инициатор", employment.get("initiatorName") or request.get("initiatorName")),
            ("Должность инициатора", employment.get("initiatorPosition")),
            ("Подразделение инициатора", employment.get("initiatorDepartment")),
            ("Рабочий e-mail", employment.get("initiatorEmail")),
            ("Рабочий телефон", employment.get("initiatorPhone")),
            ("Тип адресата", employment.get("recipientType")),
            (
                "Статус",
                STATUS_LABELS.get(str(request.get("status")), request.get("status")),
            ),
        ],
        font,
    )
    story += _section(
        "Персональная информация",
        [
            (
                "ФИО",
                " ".join(
                    filter(
                        None,
                        [
                            personal.get("lastName"),
                            personal.get("firstName"),
                            personal.get("middleName"),
                        ],
                    )
                ),
            ),
            ("ИИН", personal.get("iin")),
            ("Дата рождения", personal.get("birthDate")),
            ("Пол", personal.get("gender")),
            ("Гражданство", personal.get("citizenship")),
            ("Семейное положение", personal.get("maritalStatus")),
            ("Телефон", personal.get("personalPhone")),
            ("Email", personal.get("personalEmail")),
            ("Адрес", personal.get("address")),
            ("Тип документа", personal.get("identityDocumentType")),
            ("Номер документа", personal.get("identityDocumentNumber")),
            ("Дата выдачи", personal.get("identityIssueDate")),
            ("Срок действия", personal.get("identityExpirationDate")),
            ("Кем выдан", personal.get("issuingAuthority")),
            ("Контакт в экстренном случае", personal.get("emergencyContact")),
            ("Телефон экстренного контакта", personal.get("emergencyPhone")),
        ],
        font,
    )
    story += _section(
        "Предлагаемая занятость",
        [
            ("Департамент", employment.get("department")),
            ("Команда / отдел", employment.get("team")),
            ("Должность", employment.get("position")),
            ("Непосредственный руководитель", employment.get("manager")),
            ("Вид занятости", employment.get("employmentType")),
            ("Формат работы", employment.get("workArrangement")),
            ("Рабочее место", employment.get("workplace")),
            ("Дата выхода", employment.get("startDate")),
            ("Испытательный срок", f"{employment.get('probationMonths', 0)} мес."),
            ("График", employment.get("schedule")),
            ("Ставка", f"{employment.get('fte', 1)} FTE"),
            (
                "Заработная плата",
                " ".join(
                    filter(
                        None,
                        [
                            str(employment.get("salary") or ""),
                            str(employment.get("currency") or ""),
                        ],
                    )
                ),
            ),
            ("Основание", employment.get("hiringReason")),
            ("Обязанности", employment.get("responsibilities")),
            ("Деловое обоснование", employment.get("justification")),
        ],
        font,
    )
    story += _section(
        "Образование и опыт",
        [
            ("Уровень образования", education.get("educationLevel")),
            ("Учебное заведение", education.get("institution")),
            ("Специальность", education.get("specialization")),
            ("Год окончания", education.get("graduationYear")),
            ("Квалификация", education.get("qualification")),
            ("Опыт работы", education.get("totalExperience")),
            ("Релевантный опыт", education.get("relevantExperience")),
            ("Навыки", education.get("skills")),
            ("Языки", education.get("languages")),
            ("Сертификаты", education.get("certifications")),
            ("Дополнительная информация", education.get("additionalInfo")),
        ],
        font,
    )
    story += _section(
        "Вложения", [("Файл", item.get("originalFilename")) for item in attachments], font
    )
    by_stage = {int(item["stageNumber"]): item for item in decisions}
    rows = []
    for index, stage in enumerate(APPROVAL_STAGES, 1):
        decision = by_stage.get(index, {})
        summary = " | ".join(
            filter(
                None,
                [
                    DECISION_LABELS.get(
                        str(decision.get("decision")),
                        str(decision.get("decision") or "Ожидает"),
                    ),
                    str(decision.get("approverName") or ""),
                    str(decision.get("decidedAt") or ""),
                    str(decision.get("comment") or ""),
                ],
            )
        )
        rows.append((f"{index}. {stage.name}", summary))
    story += _section("Лист согласования", rows, font)
    story.append(
        Paragraph(
            "Документ сформирован информационной системой ERTIS OPERATIONS. "
            "Персональные данные. Доступ ограничен.",
            normal,
        )
    )

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(18 * mm, 9 * mm, f"Заявление {request_number}")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Страница {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
