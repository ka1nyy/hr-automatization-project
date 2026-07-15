import { zodResolver } from '@hookform/resolvers/zod';
import { Download, Eye, FileText, LoaderCircle, Paperclip, RotateCcw, Save, Send, Trash2, X } from 'lucide-react';
import { useEffect, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { useForm, type FieldErrors, type UseFormRegister } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { PageHeader, Section } from '../../../shared/components';
import { usePermission } from '../../../shared/permissions';
import { hrRepository } from '../api';
import { clearEmployeeDraft, restoreEmployeeDraft, saveEmployeeDraft } from '../add-employee/draft';
import { addEmployeeDefaults } from '../add-employee/defaults';
import { createAddEmployeeDocx, downloadBlob } from '../add-employee/docx';
import { attachmentCategories, currencies, departments, educationLevels, employmentTypes, executives, hiringReasons, managers, positions, teams, workArrangements, workSchedules, type AttachmentCategory } from '../add-employee/referenceData';
import { addEmployeeSchema, type AddEmployeeFormValues } from '../add-employee/schema';
import { buildEmployeeFullName, buildRequestText, createEmployeeRequestFilename, validateAttachment, type EmployeeAttachment } from '../add-employee/utils';

type CommonFieldProps = { name: keyof AddEmployeeFormValues; label: string; register: UseFormRegister<AddEmployeeFormValues>; errors: FieldErrors<AddEmployeeFormValues>; required?: boolean };
function Field({ name, label, register, errors, required, ...props }: InputHTMLAttributes<HTMLInputElement> & CommonFieldProps) {
  const numericValue = name === 'probationMonths' || name === 'fte';
  return <label>{label}{required && <em>*</em>}<input {...register(name, numericValue ? { valueAsNumber: true } : undefined)} {...props} />{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}
function SelectField({ name, label, options, register, errors, required }: CommonFieldProps & { options: readonly string[] }) {
  return <label>{label}{required && <em>*</em>}<select {...register(name)}><option value="">Выберите</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select>{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}
function TextArea({ name, label, register, errors, required, rows = 3, onChange }: CommonFieldProps & { rows?: number; onChange?: () => void }) {
  const registration = register(name);
  return <label className="span-two">{label}{required && <em>*</em>}<textarea rows={rows} {...registration} onChange={(event) => { registration.onChange(event); onChange?.(); }} />{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}

export default function HrAddEmployeePage() {
  const canOpen = usePermission('hr.employees.read');
  const canReadSalary = usePermission('hr.sensitive.read');
  const form = useForm<AddEmployeeFormValues>({ resolver: zodResolver(addEmployeeSchema), mode: 'onBlur', defaultValues: addEmployeeDefaults });
  const [attachments, setAttachments] = useState<EmployeeAttachment[]>([]);
  const [attachmentCategory, setAttachmentCategory] = useState<AttachmentCategory>(attachmentCategories[0]);
  const [preview, setPreview] = useState<AddEmployeeFormValues | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [notice, setNotice] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestTextEdited, setRequestTextEdited] = useState(false);
  const { register, formState: { errors, isDirty }, getValues, reset, handleSubmit, setValue, watch } = form;

  useEffect(() => {
    const draft = restoreEmployeeDraft(localStorage);
    if (draft) { reset({ ...addEmployeeDefaults, ...draft.values }); setRequestTextEdited(true); setNotice(`Локальный черновик восстановлен${draft.savedAt.startsWith('1970-') ? '' : ` · ${new Date(draft.savedAt).toLocaleString('ru-RU')}`}`); }
  }, [reset]);

  useEffect(() => {
    const subscription = watch((values, { name }) => {
      if (!requestTextEdited && ['lastName', 'firstName', 'middleName', 'position', 'department', 'startDate', 'hiringReason'].includes(name ?? '')) setValue('requestText', buildRequestText({ ...addEmployeeDefaults, ...values } as AddEmployeeFormValues), { shouldDirty: false });
      if (name === 'recipient') {
        const executive = executives.find((item) => item.name === values.recipient);
        if (executive) { setValue('recipientPosition', executive.position); setValue('recipientDepartment', executive.department); setValue('recipientType', executive.type); }
      }
    });
    return () => subscription.unsubscribe();
  }, [requestTextEdited, setValue, watch]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (isDirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [isDirty]);

  if (!canOpen) return <div className="hr-access-denied"><span>HR</span><h1>Доступ ограничен</h1><p>Локальная форма добавления сотрудника доступна только HR-роли.</p><Link className="secondary-button" to="/">На главную</Link></div>;

  const saveDraft = () => { const values = getValues(); const draft = saveEmployeeDraft(localStorage, values); reset(values); setNotice(`Черновик сохранён локально · ${new Date(draft.savedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}. Файлы не сохраняются.`); };
  const clearForm = () => { clearEmployeeDraft(localStorage); reset(addEmployeeDefaults); setAttachments([]); setRequestTextEdited(false); setConfirmClear(false); setNotice('Форма и локальный черновик очищены'); };
  const openPreview = handleSubmit((values) => setPreview(values));
  const generate = handleSubmit(async (values) => {
    setGenerationError(''); setIsGenerating(true);
    try { const blob = await createAddEmployeeDocx(values, attachments); downloadBlob(blob, createEmployeeRequestFilename(values)); setNotice('DOCX сформирован локально. Данные на сервер не отправлялись.'); }
    catch { setGenerationError('Не удалось создать DOCX. Проверьте данные и повторите попытку.'); }
    finally { setIsGenerating(false); }
  });
  const submit = handleSubmit(async (values) => {
    setGenerationError(''); setIsSubmitting(true);
    try {
      const result = await hrRepository.submitHiringRequest(values, attachments.map((item) => ({ name: item.file.name, size: item.file.size, category: item.category })));
      clearEmployeeDraft(localStorage);
      reset(values);
      setNotice(`Заявка ${result.number} направлена в HR. Текущий этап: ${result.currentStep}.`);
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : 'Не удалось направить заявку в HR.');
    } finally { setIsSubmitting(false); }
  });
  const addFiles = (files: File[]) => {
    const accepted: EmployeeAttachment[] = []; const rejected: string[] = [];
    files.forEach((file) => { const error = validateAttachment(file); if (error) rejected.push(`${file.name}: ${error}`); else accepted.push({ id: `${file.name}-${file.size}-${file.lastModified}`, category: attachmentCategory, file }); });
    setAttachments((current) => [...current, ...accepted.filter((next) => !current.some((item) => item.id === next.id))]);
    setGenerationError(rejected.join(' '));
  };
  const section = (title: string, content: ReactNode) => <Section title={title}><div className="field-grid hr-add-employee-fields">{content}</div></Section>;

  return <>
    <PageHeader eyebrow="HR · Добавить сотрудника" title="Служебная записка на приём" />
    <div className="hr-local-only-banner"><FileText size={18} /><span><strong>Backend-процесс найма</strong><small>Черновик остаётся на устройстве, а готовая заявка фиксируется на сервере вместе со снимком версии маршрута.</small></span></div>
    {notice && <div className="hr-form-notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Закрыть уведомление"><X size={14} /></button></div>}
    {generationError && <div className="hr-generation-error" role="alert">{generationError}</div>}
    <form className="hr-add-employee-form" onSubmit={(event) => event.preventDefault()}>
      {section('1. Получатель обращения', <><SelectField name="recipient" label="Получатель" options={executives.map((item) => item.name)} register={register} errors={errors} required /><Field name="recipientPosition" label="Должность" readOnly register={register} errors={errors} required /><Field name="recipientDepartment" label="Подразделение" readOnly register={register} errors={errors} required /><Field name="recipientType" label="Тип получателя" readOnly register={register} errors={errors} required /><Field name="requestDate" label="Дата обращения" type="date" register={register} errors={errors} required /></>)}
      {section('2. Инициатор', <><Field name="initiatorName" label="ФИО" register={register} errors={errors} required /><Field name="initiatorPosition" label="Должность" register={register} errors={errors} required /><Field name="initiatorDepartment" label="Подразделение" register={register} errors={errors} required /><Field name="initiatorEmail" label="Рабочий e-mail" type="email" register={register} errors={errors} required /><Field name="initiatorPhone" label="Рабочий телефон" placeholder="+7 700 000 00 00" register={register} errors={errors} required /></>)}
      {section('3. Персональные данные', <><Field name="lastName" label="Фамилия" register={register} errors={errors} required /><Field name="firstName" label="Имя" register={register} errors={errors} required /><Field name="middleName" label="Отчество" register={register} errors={errors} /><Field name="iin" label="ИИН" inputMode="numeric" maxLength={12} register={register} errors={errors} required /><Field name="birthDate" label="Дата рождения" type="date" register={register} errors={errors} required /><SelectField name="gender" label="Пол" options={['Женский', 'Мужской']} register={register} errors={errors} required /><Field name="citizenship" label="Гражданство" register={register} errors={errors} required /><Field name="personalPhone" label="Личный телефон" placeholder="+7 700 000 00 00" register={register} errors={errors} required /><Field name="personalEmail" label="Личный e-mail" type="email" register={register} errors={errors} required /><Field name="address" label="Адрес проживания" register={register} errors={errors} required /><SelectField name="maritalStatus" label="Семейное положение" options={['Не указано', 'Не состоит в браке', 'Состоит в браке']} register={register} errors={errors} /><Field name="emergencyContact" label="Экстренный контакт" register={register} errors={errors} /><Field name="emergencyPhone" label="Телефон экстренного контакта" register={register} errors={errors} /><SelectField name="identityDocumentType" label="Тип документа" options={['Удостоверение личности', 'Паспорт', 'Вид на жительство']} register={register} errors={errors} /><Field name="identityDocumentNumber" label="Номер документа" register={register} errors={errors} /><Field name="identityIssueDate" label="Дата выдачи" type="date" register={register} errors={errors} /><Field name="identityExpirationDate" label="Срок действия" type="date" register={register} errors={errors} /><Field name="issuingAuthority" label="Кем выдан" register={register} errors={errors} /></>)}
      {section('4. Предлагаемая занятость', <><SelectField name="department" label="Подразделение" options={departments} register={register} errors={errors} required /><SelectField name="team" label="Команда / отдел" options={teams} register={register} errors={errors} /><SelectField name="position" label="Должность" options={positions} register={register} errors={errors} required /><SelectField name="manager" label="Непосредственный руководитель" options={managers} register={register} errors={errors} required /><SelectField name="employmentType" label="Вид занятости" options={employmentTypes} register={register} errors={errors} required /><SelectField name="workArrangement" label="Формат работы" options={workArrangements} register={register} errors={errors} required /><Field name="workplace" label="Рабочее место" register={register} errors={errors} required /><Field name="startDate" label="Предлагаемая дата выхода" type="date" register={register} errors={errors} required /><Field name="probationMonths" label="Испытательный срок, мес." type="number" min={0} max={6} register={register} errors={errors} /><SelectField name="schedule" label="График" options={workSchedules} register={register} errors={errors} required /><Field name="fte" label="FTE" type="number" min="0.1" max="1" step="0.1" register={register} errors={errors} required />{canReadSalary && <><Field name="salary" label="Оклад" type="number" min="0" register={register} errors={errors} /><SelectField name="currency" label="Валюта" options={currencies} register={register} errors={errors} /></>}<SelectField name="hiringReason" label="Основание" options={hiringReasons} register={register} errors={errors} required /><TextArea name="responsibilities" label="Основные обязанности" register={register} errors={errors} required /><TextArea name="justification" label="Деловое обоснование" register={register} errors={errors} required /></>)}
      {section('5. Образование и квалификация', <><SelectField name="educationLevel" label="Уровень образования" options={educationLevels} register={register} errors={errors} required /><Field name="institution" label="Учебное заведение" register={register} errors={errors} required /><Field name="specialization" label="Специальность" register={register} errors={errors} required /><Field name="graduationYear" label="Год окончания" type="number" min="1950" max="2100" register={register} errors={errors} /><Field name="qualification" label="Квалификация" register={register} errors={errors} /><Field name="totalExperience" label="Общий опыт" register={register} errors={errors} /><Field name="relevantExperience" label="Релевантный опыт" register={register} errors={errors} /><Field name="languages" label="Языки" register={register} errors={errors} /><TextArea name="skills" label="Профессиональные навыки" register={register} errors={errors} /><TextArea name="certifications" label="Сертификаты" register={register} errors={errors} /><TextArea name="additionalInfo" label="Дополнительная информация" register={register} errors={errors} /></>)}
      <Section title="6. Вложения" meta="PDF, DOC, DOCX, JPG, PNG · до 10 МБ"><div className="hr-attachment-controls"><select value={attachmentCategory} onChange={(event) => setAttachmentCategory(event.target.value as AttachmentCategory)}>{attachmentCategories.map((category) => <option key={category}>{category}</option>)}</select><label className="secondary-button"><Paperclip size={16} /> Добавить файлы<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" multiple onChange={(event) => { addFiles(Array.from(event.target.files ?? [])); event.currentTarget.value = ''; }} /></label></div>{attachments.length > 0 ? <ul className="hr-attachment-list">{attachments.map((item) => <li key={item.id}><span><strong>{item.file.name}</strong><small>{item.category} · {(item.file.size / 1024).toFixed(1)} КБ</small></span><button type="button" className="icon-button" onClick={() => setAttachments((current) => current.filter((attachment) => attachment.id !== item.id))} aria-label={`Удалить ${item.file.name}`}><Trash2 size={15} /></button></li>)}</ul> : <div className="hr-attachments-empty">Файлы ещё не добавлены. Они не сохраняются в черновике.</div>}</Section>
      {section('7. Текст обращения', <TextArea name="requestText" label="Официальный текст служебной записки" rows={6} register={register} errors={errors} required onChange={() => setRequestTextEdited(true)} />)}
      <div className="hr-add-employee-actions"><span>{isDirty ? 'Есть несохранённые изменения' : 'Черновик синхронизирован'} · отправка запускает маршрут найма</span><button type="button" className="secondary-button" onClick={() => setConfirmClear(true)}><RotateCcw size={16} /> Очистить</button><button type="button" className="secondary-button" onClick={saveDraft} disabled={isGenerating || isSubmitting}><Save size={16} /> Сохранить черновик</button><button type="button" className="secondary-button" onClick={openPreview} disabled={isGenerating || isSubmitting}><Eye size={16} /> Предпросмотр</button><button type="button" className="secondary-button" onClick={generate} disabled={isGenerating || isSubmitting}>{isGenerating ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />}{isGenerating ? 'Формирование…' : 'Создать DOCX'}</button><button type="button" className="primary-button" onClick={submit} disabled={isGenerating || isSubmitting}>{isSubmitting ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}{isSubmitting ? 'Отправка…' : 'Направить в HR'}</button></div>
    </form>
    {preview && <div className="dialog-backdrop" onMouseDown={() => setPreview(null)}><section className="dialog hr-memorandum-preview" role="dialog" aria-modal="true" aria-label="Предпросмотр служебной записки" onMouseDown={(event) => event.stopPropagation()}><header><span>Предпросмотр документа</span><button className="icon-button" onClick={() => setPreview(null)} aria-label="Закрыть предпросмотр"><X size={18} /></button></header><article><p className="memo-recipient">Кому: {preview.recipient}<br />{preview.recipientPosition}<br /><br />От: {preview.initiatorName}<br />{preview.initiatorPosition}</p><h2>СЛУЖЕБНАЯ ЗАПИСКА</h2><h3>О рассмотрении вопроса о приёме сотрудника</h3><p>{preview.requestText}</p><dl><dt>Будущий сотрудник</dt><dd>{buildEmployeeFullName(preview)}</dd><dt>Должность</dt><dd>{preview.position}</dd><dt>Подразделение</dt><dd>{preview.department}</dd><dt>Дата выхода</dt><dd>{preview.startDate}</dd><dt>Приложения</dt><dd>{attachments.length || 'Нет'}</dd></dl><p><strong>Обоснование:</strong> {preview.justification}</p><footer>Инициатор: {preview.initiatorName} ____________________</footer></article></section></div>}
    {confirmClear && <div className="dialog-backdrop"><section className="dialog hr-confirm-dialog" role="dialog" aria-modal="true" aria-label="Очистить форму"><header><span>Очистить форму?</span><button className="icon-button" onClick={() => setConfirmClear(false)} aria-label="Закрыть подтверждение"><X size={18} /></button></header><p>Все введённые данные и локальный черновик будут удалены. Вложения также будут очищены.</p><footer><button className="secondary-button" onClick={() => setConfirmClear(false)}>Отмена</button><button className="primary-button" onClick={clearForm}>Очистить</button></footer></section></div>}
  </>;
}
