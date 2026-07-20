from __future__ import annotations

from dataclasses import dataclass

from .enums import StageCode


@dataclass(frozen=True, slots=True)
class StagePolicy:
    sequence: int
    code: StageCode
    name: str
    owner_role_code: str
    sla_min_days: int | None
    sla_max_days: int | None
    working_days: bool = True


STAGE_POLICIES: tuple[StagePolicy, ...] = (
    StagePolicy(
        0, StageCode.NEED_SIGNAL, "Сигнал о потребности", "hiring-department-director", 1, 1
    ),
    StagePolicy(1, StageCode.UNIT_CHECK, "Проверка штатной единицы", "hiring-hr-inspector", 1, 1),
    StagePolicy(2, StageCode.REQUEST_FORMATION, "Формирование заявки", "hiring-hr-recruiter", 2, 2),
    StagePolicy(
        3, StageCode.NEED_APPROVAL, "Согласование потребности", "hiring-curating-deputy", 2, 2
    ),
    StagePolicy(4, StageCode.BUDGET_CHECK, "Бюджетная проверка", "hiring-economic-reviewer", 2, 2),
    StagePolicy(5, StageCode.LEGAL_CHECK, "Правовая проверка", "hiring-legal-reviewer", 2, 2),
    StagePolicy(
        6,
        StageCode.SELECTION_AUTHORIZATION,
        "Разрешение на подбор",
        "hiring-authorized-signatory",
        1,
        1,
    ),
    StagePolicy(
        7, StageCode.VACANCY_PUBLICATION, "Публикация вакансии", "hiring-hr-recruiter", None, 5
    ),
    StagePolicy(
        8, StageCode.APPLICATION_INTAKE, "Прием откликов и согласия", "hiring-hr-recruiter", 5, 10
    ),
    StagePolicy(9, StageCode.FORMAL_SCREENING, "Формальный скрининг", "hiring-hr-recruiter", 2, 2),
    StagePolicy(10, StageCode.PHONE_SCREENING, "Телефонный скрининг", "hiring-hr-recruiter", 1, 2),
    StagePolicy(
        11,
        StageCode.PROFESSIONAL_ASSESSMENT,
        "Профессиональное задание или тест",
        "hiring-department-director",
        None,
        3,
    ),
    StagePolicy(
        12,
        StageCode.STRUCTURED_INTERVIEW,
        "Структурированное интервью",
        "hiring-commission-member",
        1,
        1,
    ),
    StagePolicy(
        13, StageCode.FINALIST_CHECKS, "Проверки финалиста", "hiring-compliance-officer", 2, 5
    ),
    StagePolicy(
        14, StageCode.COMMISSION_RESULT, "Итог конкурсной комиссии", "hiring-commission-chair", 1, 1
    ),
    StagePolicy(
        15, StageCode.FINAL_DECISION, "Финальное решение", "hiring-authorized-signatory", 1, 1
    ),
    StagePolicy(16, StageCode.OFFER, "Оффер", "hiring-hr-recruiter", 2, 2),
    StagePolicy(
        17, StageCode.DOCUMENT_COLLECTION, "Сбор документов", "hiring-hr-inspector", None, 3
    ),
    StagePolicy(
        18, StageCode.EMPLOYMENT_CONTRACT, "Трудовой договор", "hiring-hr-inspector", None, None
    ),
    StagePolicy(19, StageCode.HIRING_ORDER, "Приказ о приеме", "hiring-hr-inspector", None, None),
    StagePolicy(
        20,
        StageCode.ESUTD_AND_PERSONNEL_FILE,
        "ЕСУТД и личное дело",
        "hiring-hr-inspector",
        None,
        5,
    ),
    StagePolicy(
        21,
        StageCode.ACCESS_AND_FIRST_DAY,
        "Доступы и первый день",
        "hiring-it-executor",
        None,
        None,
    ),
    StagePolicy(
        22, StageCode.PROBATION, "Испытательный срок", "hiring-department-director", None, None
    ),
)


@dataclass(frozen=True, slots=True)
class FormPolicy:
    sequence: int
    code: str
    name: str
    owner_role_code: str
    signer_role_codes: tuple[str, ...]


FORM_POLICIES: tuple[FormPolicy, ...] = (
    FormPolicy(
        1,
        "NAIM-01",
        "Заявка на подбор работника",
        "hiring-department-director",
        ("hiring-department-director", "hiring-process-owner", "hiring-curating-deputy"),
    ),
    FormPolicy(
        2,
        "NAIM-02",
        "Заключение о штатной единице",
        "hiring-hr-inspector",
        ("hiring-hr-inspector", "hiring-process-owner"),
    ),
    FormPolicy(
        3,
        "NAIM-03",
        "Заключение ДЭП о стоимости найма",
        "hiring-economic-reviewer",
        ("hiring-economic-reviewer", "hiring-process-owner"),
    ),
    FormPolicy(
        4,
        "NAIM-04",
        "Профиль должности и критерии отбора",
        "hiring-hr-recruiter",
        ("hiring-department-director", "hiring-hr-recruiter", "hiring-process-owner"),
    ),
    FormPolicy(
        5,
        "NAIM-05",
        "Объявление о вакансии",
        "hiring-hr-recruiter",
        ("hiring-hr-recruiter", "hiring-process-owner"),
    ),
    FormPolicy(
        6,
        "NAIM-06",
        "Согласие кандидата на обработку персональных данных",
        "candidate",
        ("candidate",),
    ),
    FormPolicy(7, "NAIM-07", "Анкета кандидата", "candidate", ("candidate", "hiring-hr-recruiter")),
    FormPolicy(
        8,
        "NAIM-08",
        "Лист формального и телефонного скрининга",
        "hiring-hr-recruiter",
        ("hiring-hr-recruiter",),
    ),
    FormPolicy(
        9,
        "NAIM-09",
        "Профессиональное задание и ключ оценки",
        "hiring-department-director",
        ("hiring-department-director", "hiring-hr-recruiter"),
    ),
    FormPolicy(
        10,
        "NAIM-10",
        "Индивидуальный лист оценки члена комиссии",
        "hiring-commission-member",
        ("hiring-commission-member",),
    ),
    FormPolicy(
        11,
        "NAIM-11",
        "Декларация конфликта интересов кандидата",
        "candidate",
        ("candidate", "hiring-compliance-officer"),
    ),
    FormPolicy(
        12,
        "NAIM-12",
        "Протокол конкурсной комиссии",
        "hiring-commission-chair",
        ("hiring-commission-chair", "hiring-commission-member", "hiring-commission-secretary"),
    ),
    FormPolicy(
        13,
        "NAIM-13",
        "Письменный оффер",
        "hiring-hr-recruiter",
        ("hiring-authorized-signatory", "candidate"),
    ),
    FormPolicy(
        14,
        "NAIM-14",
        "Чек-лист документов финалиста",
        "hiring-hr-inspector",
        ("hiring-hr-inspector", "candidate"),
    ),
    FormPolicy(
        15,
        "NAIM-15",
        "Заявление о приеме на работу",
        "candidate",
        ("candidate", "hiring-authorized-signatory"),
    ),
    FormPolicy(
        16,
        "NAIM-16",
        "Проект трудового договора",
        "hiring-hr-inspector",
        ("hiring-authorized-signatory", "candidate"),
    ),
    FormPolicy(
        17,
        "NAIM-17",
        "Приказ о приеме на работу",
        "hiring-hr-inspector",
        ("hiring-authorized-signatory", "candidate"),
    ),
    FormPolicy(
        18,
        "NAIM-18",
        "Лист ознакомления и инструктажей",
        "hiring-hr-inspector",
        ("candidate", "hiring-hr-inspector"),
    ),
    FormPolicy(
        19,
        "NAIM-19",
        "Заявка на доступы, рабочее место и имущество",
        "hiring-department-director",
        ("hiring-department-director", "hiring-system-owner", "hiring-it-executor"),
    ),
    FormPolicy(
        20,
        "NAIM-20",
        "План испытательного срока 30/60/90",
        "hiring-department-director",
        ("hiring-department-director", "candidate", "hiring-hr-inspector"),
    ),
    FormPolicy(
        21,
        "NAIM-21",
        "Итог испытательного срока",
        "hiring-department-director",
        ("hiring-department-director", "hiring-hr-inspector", "hiring-legal-reviewer", "candidate"),
    ),
)
