import { zodResolver } from '@hookform/resolvers/zod';
import { Download, Eye, FileText, Paperclip, RotateCcw, Save, X } from 'lucide-react';
import { useEffect, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { useForm, type FieldErrors, type UseFormRegister } from 'react-hook-form';
import { PageHeader, Section } from '../../../shared/components';
import { usePermission } from '../../../shared/permissions';
import { Link } from 'react-router-dom';
import { createAddEmployeeDocx, downloadBlob } from '../add-employee/docx';
import { ADD_EMPLOYEE_DRAFT_KEY, addEmployeeSchema, type AddEmployeeFormValues } from '../add-employee/schema';
import { HrSubnav } from '../components/HrSubnav';

const defaults: AddEmployeeFormValues = {
  recipient: 'Председателю Правления', recipientPosition: 'Председатель Правления', recipientDepartment: 'Исполнительное руководство', recipientType: 'Руководитель', requestDate: new Date().toISOString().slice(0, 10),
  initiatorName: 'Зарина Ахметова', initiatorPosition: 'HR специалист', initiatorDepartment: 'Департамент управления персоналом', initiatorEmail: 'z.akhmetova@ertis.kz', initiatorPhone: '+7 7182 55 10 10',
  lastName: '', firstName: '', middleName: '', iin: '', birthDate: '', citizenship: 'Республика Казахстан', personalPhone: '', personalEmail: '', address: '', identityDocument: '',
  department: '', team: '', position: '', manager: '', employmentType: 'Полная занятость', workArrangement: 'Офис', workplace: 'Павлодар', startDate: '', probationMonths: 3, schedule: '5/2, 09:00–18:00', fte: 1, salary: '', currency: 'KZT',
  hiringReason: 'Замещение штатной позиции', responsibilities: '', justification: '', educationLevel: 'Высшее', institution: '', specialization: '', graduationYear: '', qualification: '', totalExperience: '', relevantExperience: '', skills: '', languages: '', certifications: '',
  requestText: 'Прошу рассмотреть возможность приёма указанного сотрудника на предложенную должность согласно штатному расписанию.'
};

function Field({ name, label, register, errors, required, ...props }: InputHTMLAttributes<HTMLInputElement> & { name: keyof AddEmployeeFormValues; label: string; register: UseFormRegister<AddEmployeeFormValues>; errors: FieldErrors<AddEmployeeFormValues>; required?: boolean }) {
  const numericValue = name === 'probationMonths' || name === 'fte';
  return <label>{label}{required && <em>*</em>}<input {...register(name, numericValue ? { valueAsNumber: true } : undefined)} {...props} />{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}

function TextArea({ name, label, register, errors, required, rows = 3 }: { name: keyof AddEmployeeFormValues; label: string; register: UseFormRegister<AddEmployeeFormValues>; errors: FieldErrors<AddEmployeeFormValues>; required?: boolean; rows?: number }) {
  return <label className="span-two">{label}{required && <em>*</em>}<textarea rows={rows} {...register(name)} />{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}

export default function HrAddEmployeePage() {
  const canOpen = usePermission('hr.employees.read');
  const form = useForm<AddEmployeeFormValues>({ resolver: zodResolver(addEmployeeSchema), mode: 'onBlur', defaultValues: defaults });
  const [attachments, setAttachments] = useState<File[]>([]);
  const [preview, setPreview] = useState<AddEmployeeFormValues | null>(null);
  const [notice, setNotice] = useState('');
  const { register, formState: { errors }, getValues, reset, handleSubmit } = form;

  useEffect(() => {
    const stored = localStorage.getItem(ADD_EMPLOYEE_DRAFT_KEY);
    if (!stored) return;
    try { reset({ ...defaults, ...(JSON.parse(stored) as Partial<AddEmployeeFormValues>) }); setNotice('Локальный черновик восстановлен'); } catch { localStorage.removeItem(ADD_EMPLOYEE_DRAFT_KEY); }
  }, [reset]);

  if (!canOpen) return <div className="hr-access-denied"><span>HR</span><h1>Доступ ограничен</h1><p>Локальная форма добавления сотрудника доступна только HR-роли.</p><Link className="secondary-button" to="/">На главную</Link></div>;

  const saveDraft = () => { localStorage.setItem(ADD_EMPLOYEE_DRAFT_KEY, JSON.stringify(getValues())); setNotice('Черновик сохранён только в этом браузере. Файлы не сохраняются.'); };
  const clearForm = () => { localStorage.removeItem(ADD_EMPLOYEE_DRAFT_KEY); reset(defaults); setAttachments([]); setNotice('Форма очищена'); };
  const openPreview = handleSubmit((values) => setPreview(values));
  const generate = handleSubmit(async (values) => {
    const blob = await createAddEmployeeDocx(values, attachments);
    const safeName = `${values.lastName}_${values.firstName}`.replace(/[^\p{L}\p{N}_-]+/gu, '_');
    downloadBlob(blob, `Employee_Hiring_Request_${safeName}_${values.requestDate}.docx`);
    setNotice('DOCX сформирован локально. Данные на сервер не отправлялись.');
  });
  const section = (title: string, content: ReactNode) => <Section title={title}><div className="field-grid hr-add-employee-fields">{content}</div></Section>;

  return <>
    <HrSubnav />
    <PageHeader eyebrow="HR · Добавить сотрудника" title="Служебная записка на приём" description="Форма работает полностью в браузере: серверные заявки, загрузка файлов и Hiring API не используются." />
    <div className="hr-local-only-banner"><FileText size={18} /><span><strong>Локальный режим</strong><small>Черновик хранится на устройстве, DOCX создаётся в браузере. Отправка на согласование появится отдельной интеграцией.</small></span></div>
    {notice && <div className="hr-form-notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Закрыть"><X size={14} /></button></div>}
    <form className="hr-add-employee-form" onSubmit={(event) => event.preventDefault()}>
      {section('1. Получатель обращения', <><Field name="recipient" label="Получатель" register={register} errors={errors} required /><Field name="recipientPosition" label="Должность" register={register} errors={errors} required /><Field name="recipientDepartment" label="Подразделение" register={register} errors={errors} required /><label>Тип получателя<select {...register('recipientType')}><option>Руководитель</option><option>Коллегиальный орган</option></select></label><Field name="requestDate" label="Дата обращения" type="date" register={register} errors={errors} required /></>)}
      {section('2. Инициатор', <><Field name="initiatorName" label="ФИО" register={register} errors={errors} required /><Field name="initiatorPosition" label="Должность" register={register} errors={errors} required /><Field name="initiatorDepartment" label="Подразделение" register={register} errors={errors} required /><Field name="initiatorEmail" label="Рабочий e-mail" type="email" register={register} errors={errors} required /><Field name="initiatorPhone" label="Рабочий телефон" register={register} errors={errors} required /></>)}
      {section('3. Персональные данные', <><Field name="lastName" label="Фамилия" register={register} errors={errors} required /><Field name="firstName" label="Имя" register={register} errors={errors} required /><Field name="middleName" label="Отчество" register={register} errors={errors} /><Field name="iin" label="ИИН" inputMode="numeric" maxLength={12} register={register} errors={errors} required /><Field name="birthDate" label="Дата рождения" type="date" register={register} errors={errors} required /><Field name="citizenship" label="Гражданство" register={register} errors={errors} required /><Field name="personalPhone" label="Личный телефон" register={register} errors={errors} required /><Field name="personalEmail" label="Личный e-mail" type="email" register={register} errors={errors} required /><Field name="address" label="Адрес проживания" register={register} errors={errors} required /><Field name="identityDocument" label="Удостоверение личности" register={register} errors={errors} required /></>)}
      {section('4. Предлагаемая занятость', <><Field name="department" label="Подразделение" register={register} errors={errors} required /><Field name="team" label="Команда / отдел" register={register} errors={errors} /><Field name="position" label="Должность" register={register} errors={errors} required /><Field name="manager" label="Непосредственный руководитель" register={register} errors={errors} required /><Field name="employmentType" label="Вид занятости" register={register} errors={errors} required /><Field name="workArrangement" label="Формат работы" register={register} errors={errors} required /><Field name="workplace" label="Рабочее место" register={register} errors={errors} required /><Field name="startDate" label="Предлагаемая дата выхода" type="date" register={register} errors={errors} required /><Field name="probationMonths" label="Испытательный срок, мес." type="number" min={0} max={6} register={register} errors={errors} /><Field name="schedule" label="График" register={register} errors={errors} required /><Field name="fte" label="FTE" type="number" min="0.1" max="1" step="0.1" register={register} errors={errors} required /><Field name="salary" label="Оклад (при наличии доступа)" type="number" register={register} errors={errors} /><Field name="hiringReason" label="Основание" register={register} errors={errors} required /><TextArea name="responsibilities" label="Основные обязанности" register={register} errors={errors} required /><TextArea name="justification" label="Деловое обоснование" register={register} errors={errors} required /></>)}
      {section('5. Образование и квалификация', <><Field name="educationLevel" label="Уровень образования" register={register} errors={errors} required /><Field name="institution" label="Учебное заведение" register={register} errors={errors} required /><Field name="specialization" label="Специальность" register={register} errors={errors} required /><Field name="graduationYear" label="Год окончания" type="number" register={register} errors={errors} /><Field name="qualification" label="Квалификация" register={register} errors={errors} /><Field name="totalExperience" label="Общий опыт" register={register} errors={errors} /><Field name="relevantExperience" label="Релевантный опыт" register={register} errors={errors} /><Field name="languages" label="Языки" register={register} errors={errors} /><TextArea name="skills" label="Навыки" register={register} errors={errors} /><TextArea name="certifications" label="Сертификаты" register={register} errors={errors} /></>)}
      <Section title="6. Вложения" meta="Файлы не покидают браузер"><div className="hr-attachment-zone"><Paperclip size={20} /><label><strong>Выберите документы</strong><small>Удостоверение, диплом, резюме, сертификаты и другие файлы</small><input type="file" multiple onChange={(event) => setAttachments(Array.from(event.target.files ?? []))} /></label>{attachments.length > 0 && <ul>{attachments.map((file) => <li key={`${file.name}-${file.size}`}>{file.name}<span>{Math.ceil(file.size / 1024)} КБ</span></li>)}</ul>}</div></Section>
      {section('7. Текст обращения', <TextArea name="requestText" label="Официальный текст служебной записки" rows={6} register={register} errors={errors} required />)}
      <div className="hr-add-employee-actions"><span>Backend-запросы отсутствуют</span><button type="button" className="secondary-button" onClick={clearForm}><RotateCcw size={16} /> Очистить</button><button type="button" className="secondary-button" onClick={saveDraft}><Save size={16} /> Сохранить черновик</button><button type="button" className="secondary-button" onClick={openPreview}><Eye size={16} /> Предпросмотр</button><button type="button" className="primary-button" onClick={generate}><Download size={16} /> Создать DOCX</button></div>
    </form>
    {preview && <div className="dialog-backdrop" onMouseDown={() => setPreview(null)}><section className="dialog hr-memorandum-preview" role="dialog" aria-modal="true" aria-label="Предпросмотр служебной записки" onMouseDown={(event) => event.stopPropagation()}><header><span>Предпросмотр документа</span><button className="icon-button" onClick={() => setPreview(null)} aria-label="Закрыть"><X size={18} /></button></header><article><p className="memo-recipient">{preview.recipient}<br />{preview.recipientPosition}</p><h2>СЛУЖЕБНАЯ ЗАПИСКА</h2><h3>О рассмотрении вопроса о приёме сотрудника</h3><p>{preview.requestText}</p><dl><dt>Кандидат</dt><dd>{preview.lastName} {preview.firstName} {preview.middleName}</dd><dt>Должность</dt><dd>{preview.position}</dd><dt>Подразделение</dt><dd>{preview.department}</dd><dt>Дата выхода</dt><dd>{preview.startDate}</dd></dl><p><strong>Обоснование:</strong> {preview.justification}</p><footer>Инициатор: {preview.initiatorName} ____________________</footer></article></section></div>}
  </>;
}
