from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .domain import APPROVAL_STAGES


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
    return "—" if value is None or value == "" else escape(str(value))


def _section(title: str, rows: Iterable[tuple[str, object]], font: str) -> list[Flowable]:
    heading = ParagraphStyle(
        "section",
        fontName=font,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#344054"),
        spaceBefore=8,
        spaceAfter=5,
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
    story: list[Flowable] = [Paragraph("Заявление о найме нового сотрудника", title)]
    story += _section(
        "Метаданные документа",
        [
            ("Номер заявления", request.get("requestNumber")),
            ("Дата создания", request.get("createdAt")),
            ("Инициатор", request.get("initiatorName")),
            ("Статус", request.get("status")),
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
        ],
        font,
    )
    employment = request.get("employmentData", {})
    story += _section(
        "Предлагаемая занятость",
        [
            ("Департамент", employment.get("department")),
            ("Должность", employment.get("position")),
            ("Вид занятости", employment.get("employmentType")),
            ("Формат работы", employment.get("workArrangement")),
            ("Рабочее место", employment.get("workplace")),
            ("Дата выхода", employment.get("startDate")),
            ("Испытательный срок", f"{employment.get('probationMonths', 0)} мес."),
            ("График", employment.get("schedule")),
            ("Основание", employment.get("hiringReason")),
        ],
        font,
    )
    education = request.get("educationData", {})
    story += _section(
        "Образование и опыт",
        [
            ("Уровень образования", education.get("educationLevel")),
            ("Учебное заведение", education.get("institution")),
            ("Специальность", education.get("specialization")),
            ("Опыт работы", education.get("totalExperience")),
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
        summary = " · ".join(
            filter(
                None,
                [
                    str(decision.get("decision") or "Ожидает"),
                    str(decision.get("approverName") or ""),
                    str(decision.get("decidedAt") or ""),
                    str(decision.get("comment") or ""),
                ],
            )
        )
        rows.append((f"{index}. {stage.name}", summary))
    story += _section("Лист согласования", rows, font)
    story.append(
        Paragraph("Документ сформирован информационной системой ERTIS OPERATIONS.", normal)
    )
    document.build(story)
    return output.getvalue()
