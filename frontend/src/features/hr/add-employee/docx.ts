import { AlignmentType, Document, HeadingLevel, Packer, Paragraph, TextRun } from 'docx';
import type { AddEmployeeFormValues } from './schema';

const line = (label: string, value: string | number) => new Paragraph({ children: [new TextRun({ text: `${label}: `, bold: true }), new TextRun(String(value || '—'))] });

export async function createAddEmployeeDocx(values: AddEmployeeFormValues, attachments: File[]) {
  const document = new Document({ sections: [{ children: [
    new Paragraph({ text: 'СЛУЖЕБНАЯ ЗАПИСКА', heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER }),
    new Paragraph({ text: 'О рассмотрении вопроса о приёме сотрудника', heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER }),
    line('Получатель', `${values.recipient}, ${values.recipientPosition}`), line('Инициатор', `${values.initiatorName}, ${values.initiatorPosition}`), line('Дата', values.requestDate),
    new Paragraph({ text: values.requestText, spacing: { before: 280, after: 280 } }),
    new Paragraph({ text: 'Сведения о сотруднике', heading: HeadingLevel.HEADING_2 }), line('ФИО', `${values.lastName} ${values.firstName} ${values.middleName}`), line('ИИН', values.iin), line('Дата рождения', values.birthDate), line('Гражданство', values.citizenship),
    new Paragraph({ text: 'Предлагаемые условия', heading: HeadingLevel.HEADING_2 }), line('Подразделение', `${values.department}${values.team ? ` / ${values.team}` : ''}`), line('Должность', values.position), line('Руководитель', values.manager), line('Дата выхода', values.startDate), line('Занятость', `${values.employmentType}, ${values.fte} FTE`), line('Испытательный срок', `${values.probationMonths} мес.`),
    new Paragraph({ text: 'Образование и квалификация', heading: HeadingLevel.HEADING_2 }), line('Образование', `${values.educationLevel}, ${values.institution}`), line('Специальность', values.specialization), line('Опыт', values.totalExperience), line('Навыки', values.skills),
    new Paragraph({ text: 'Деловое обоснование', heading: HeadingLevel.HEADING_2 }), new Paragraph(values.justification),
    new Paragraph({ text: 'Приложения', heading: HeadingLevel.HEADING_2 }), new Paragraph(attachments.length ? attachments.map((file, index) => `${index + 1}. ${file.name}`).join('\n') : 'Приложения отсутствуют'),
    new Paragraph({ text: '\nИнициатор: ____________________ / ____________________' }),
    new Paragraph({ text: '\nРезолюция руководства: ______________________________________________\n____________________________________________________________________' })
  ] }] });
  return Packer.toBlob(document);
}

export function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = fileName; anchor.click();
  URL.revokeObjectURL(url);
}
