import { z } from 'zod';

const required = (message: string) => z.string().trim().min(1, message);

export const addEmployeeSchema = z.object({
  recipient: required('Укажите получателя'), recipientPosition: required('Укажите должность получателя'),
  recipientDepartment: required('Укажите подразделение получателя'), recipientType: z.enum(['Руководитель', 'Коллегиальный орган']), requestDate: required('Укажите дату обращения'),
  initiatorName: required('Укажите инициатора'), initiatorPosition: required('Укажите должность инициатора'), initiatorDepartment: required('Укажите подразделение инициатора'),
  initiatorEmail: z.string().email('Некорректный рабочий e-mail'), initiatorPhone: required('Укажите рабочий телефон'),
  lastName: required('Укажите фамилию'), firstName: required('Укажите имя'), middleName: z.string(), iin: z.string().regex(/^\d{12}$/, 'ИИН должен содержать 12 цифр'),
  birthDate: required('Укажите дату рождения'), citizenship: required('Укажите гражданство'), personalPhone: required('Укажите личный телефон'), personalEmail: z.string().email('Некорректный личный e-mail'),
  address: required('Укажите адрес проживания'), identityDocument: required('Укажите данные удостоверения личности'),
  department: required('Выберите подразделение'), team: z.string(), position: required('Укажите предлагаемую должность'), manager: required('Укажите непосредственного руководителя'),
  employmentType: required('Выберите вид занятости'), workArrangement: required('Выберите формат работы'), workplace: required('Укажите место работы'), startDate: required('Укажите дату выхода'),
  probationMonths: z.number().min(0).max(6), schedule: required('Укажите график'), fte: z.number().min(0.1).max(1), salary: z.string(), currency: z.literal('KZT'),
  hiringReason: required('Укажите основание'), responsibilities: required('Опишите обязанности'), justification: required('Добавьте деловое обоснование'),
  educationLevel: required('Укажите уровень образования'), institution: required('Укажите учебное заведение'), specialization: required('Укажите специальность'), graduationYear: z.string(),
  qualification: z.string(), totalExperience: z.string(), relevantExperience: z.string(), skills: z.string(), languages: z.string(), certifications: z.string(),
  requestText: required('Введите текст служебной записки')
});

export type AddEmployeeFormValues = z.infer<typeof addEmployeeSchema>;
export const ADD_EMPLOYEE_DRAFT_KEY = 'ertis.hr.add-employee.draft.v1';
