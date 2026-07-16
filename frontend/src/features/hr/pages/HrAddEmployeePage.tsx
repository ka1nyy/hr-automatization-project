import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, BriefcaseBusiness, CheckCircle2, FileText, GraduationCap, Info, Paperclip, RotateCcw, Save, Trash2, UserRound, X } from 'lucide-react';
import { useEffect, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { useForm, type FieldErrors, type UseFormRegister } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { PageHeader, Section } from '../../../shared/components';
import { usePermission } from '../../../shared/permissions';
import { clearEmployeeDraft, restoreEmployeeDraft, saveEmployeeDraft } from '../add-employee/draft';
import { addEmployeeDefaults } from '../add-employee/defaults';
import {
  departments,
  educationLevels,
  employmentTypes,
  hiringReasons,
  positions,
  workArrangements,
  workSchedules,
  type AttachmentCategory,
} from '../add-employee/referenceData';
import { addEmployeeSchema, type AddEmployeeFormValues } from '../add-employee/schema';
import { validateAttachment, type EmployeeAttachment } from '../add-employee/utils';

const genders = ['Женский', 'Мужской'] as const;
const maritalStatuses = ['Не состоит в браке', 'Состоит в браке', 'Разведён(а)', 'Вдовец / вдова'] as const;
const identityDocumentTypes = ['Удостоверение личности', 'Паспорт', 'Вид на жительство'] as const;
const workplaces = ['Павлодар', 'Астана', 'Алматы', 'Экибастуз', 'Аксу', 'Другой город'] as const;

type CommonFieldProps = {
  name: keyof AddEmployeeFormValues;
  label: string;
  register: UseFormRegister<AddEmployeeFormValues>;
  errors: FieldErrors<AddEmployeeFormValues>;
  required?: boolean;
  hint?: string;
};

function Field({ name, label, register, errors, required, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & CommonFieldProps) {
  const numericValue = name === 'probationMonths';
  return <label>{label}{required && <em>*</em>}<input {...register(name, numericValue ? { valueAsNumber: true } : undefined)} {...props} />{hint && !errors[name] && <small className="hr-field-hint">{hint}</small>}{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}

function SelectField({ name, label, options, register, errors, required }: CommonFieldProps & { options: readonly string[] }) {
  return <label>{label}{required && <em>*</em>}<select {...register(name)}><option value="">Выберите</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select>{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}

function FormSection({ step, title, description, icon, children }: { step: string; title: string; description: string; icon: ReactNode; children: ReactNode }) {
  return <Section title={`${step}. ${title}`} meta={description} className="hr-hiring-section"><div className="hr-section-icon" aria-hidden="true">{icon}</div><div className="field-grid hr-add-employee-fields">{children}</div></Section>;
}

export default function HrAddEmployeePage({ onBack }: { onBack?: () => void }) {
  const canOpen = usePermission('hr.employees.read');
  const form = useForm<AddEmployeeFormValues>({ resolver: zodResolver(addEmployeeSchema), mode: 'onBlur', defaultValues: addEmployeeDefaults });
  const [attachments, setAttachments] = useState<EmployeeAttachment[]>([]);
  const [notice, setNotice] = useState('');
  const [attachmentError, setAttachmentError] = useState('');
  const [confirmClear, setConfirmClear] = useState(false);
  const { register, formState: { errors, isDirty }, getValues, handleSubmit, reset, watch } = form;
  const educationLevel = watch('educationLevel');
  const diplomaRequired = educationLevel !== 'Среднее общее';

  useEffect(() => {
    const draft = restoreEmployeeDraft(localStorage);
    if (draft) {
      reset({ ...addEmployeeDefaults, ...draft.values });
      setNotice(`Черновик восстановлен · ${new Date(draft.savedAt).toLocaleString('ru-RU')}`);
    }
  }, [reset]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (isDirty) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [isDirty]);

  if (!canOpen) return <div className="hr-access-denied"><span>HR</span><h1>Доступ ограничен</h1><p>Форма найма доступна только HR-роли.</p><Link className="secondary-button" to="/">На главную</Link></div>;

  const saveDraft = () => {
    const values = getValues();
    const draft = saveEmployeeDraft(localStorage, values);
    reset(values);
    setNotice(`Черновик сохранён · ${new Date(draft.savedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}. Файлы не сохраняются.`);
  };

  const clearForm = () => {
    clearEmployeeDraft(localStorage);
    reset(addEmployeeDefaults);
    setAttachments([]);
    setAttachmentError('');
    setConfirmClear(false);
    setNotice('Форма и локальный черновик очищены');
  };

  const addFiles = (files: File[], category: AttachmentCategory) => {
    const accepted: EmployeeAttachment[] = [];
    const rejected: string[] = [];
    files.forEach((file) => {
      const error = validateAttachment(file);
      if (error) rejected.push(`${file.name}: ${error}`);
      else accepted.push({ id: `${category}-${file.name}-${file.size}-${file.lastModified}`, category, file });
    });
    setAttachments((current) => [...current, ...accepted.filter((next) => !current.some((item) => item.id === next.id))]);
    setAttachmentError(rejected.join(' '));
  };

  const complete = handleSubmit(() => {
    const hasIdentity = attachments.some((item) => item.category === 'Удостоверение личности');
    const hasDiploma = attachments.some((item) => item.category === 'Диплом');
    if (!hasIdentity || (diplomaRequired && !hasDiploma)) {
      setAttachmentError(!hasIdentity ? 'Прикрепите копию документа, удостоверяющего личность.' : 'Для выбранного уровня образования нужно прикрепить диплом.');
      return;
    }
    setAttachmentError('');
    saveEmployeeDraft(localStorage, getValues());
    setNotice('Данные кандидата заполнены. Автоматическое формирование PDF-заявления будет добавлено на следующем этапе.');
  });

  const documentUpload = (category: AttachmentCategory, title: string, description: string, required: boolean) => {
    const files = attachments.filter((item) => item.category === category);
    return <div className="hr-document-upload">
      <div className="hr-document-upload-copy"><span><FileText size={18} /></span><div><strong>{title}{required && <em>*</em>}</strong><small>{description}</small></div></div>
      <label className="secondary-button"><Paperclip size={15} />{files.length ? 'Добавить ещё' : 'Выбрать файл'}<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" multiple onChange={(event) => { addFiles(Array.from(event.target.files ?? []), category); event.currentTarget.value = ''; }} /></label>
      {files.length > 0 && <ul>{files.map((item) => <li key={item.id}><span><strong>{item.file.name}</strong><small>{(item.file.size / 1024 / 1024).toFixed(2)} МБ</small></span><button type="button" className="icon-button" onClick={() => setAttachments((current) => current.filter((file) => file.id !== item.id))} aria-label={`Удалить ${item.file.name}`}><Trash2 size={15} /></button></li>)}</ul>}
    </div>;
  };

  return <>
    <PageHeader eyebrow="HR · Найм" title="Найм сотрудника" description="Заполните данные кандидата и условия предлагаемой занятости." actions={onBack ? <button type="button" className="secondary-button" onClick={onBack}><ArrowLeft size={16} /> Назад к списку</button> : undefined} />
    <div className="hr-hiring-intro"><Info size={18} /><span><strong>PDF-заявление</strong><small>После заполнения формы здесь будет автоматически создаваться заявление на рассмотрение. На текущем этапе доступен только фронтенд формы.</small></span></div>
    {notice && <div className="hr-form-notice" role="status"><span><CheckCircle2 size={15} />{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Закрыть уведомление"><X size={14} /></button></div>}
    <form className="hr-add-employee-form" onSubmit={complete}>
      <FormSection step="1" title="Персональная информация" description="Личные и контактные данные" icon={<UserRound size={18} />}>
        <Field name="lastName" label="Фамилия" autoComplete="family-name" register={register} errors={errors} required />
        <Field name="firstName" label="Имя" autoComplete="given-name" register={register} errors={errors} required />
        <Field name="middleName" label="Отчество" autoComplete="additional-name" register={register} errors={errors} />
        <Field name="iin" label="ИИН" inputMode="numeric" maxLength={12} placeholder="12 цифр" register={register} errors={errors} required />
        <Field name="birthDate" label="Дата рождения" type="date" register={register} errors={errors} required />
        <SelectField name="gender" label="Пол" options={genders} register={register} errors={errors} required />
        <Field name="citizenship" label="Гражданство" register={register} errors={errors} required />
        <SelectField name="maritalStatus" label="Семейное положение" options={maritalStatuses} register={register} errors={errors} required />
        <Field name="personalPhone" label="Номер телефона" type="tel" autoComplete="tel" placeholder="+7 700 000 00 00" register={register} errors={errors} required />
        <Field name="personalEmail" label="Email" type="email" autoComplete="email" placeholder="name@example.com" register={register} errors={errors} required />
        <Field name="address" label="Адрес проживания" autoComplete="street-address" register={register} errors={errors} required />
        <SelectField name="identityDocumentType" label="Тип документа" options={identityDocumentTypes} register={register} errors={errors} required />
        <Field name="identityDocumentNumber" label="Номер документа" register={register} errors={errors} required />
      </FormSection>

      <FormSection step="2" title="Предлагаемая занятость" description="Должность и условия работы" icon={<BriefcaseBusiness size={18} />}>
        <SelectField name="department" label="Департамент" options={departments} register={register} errors={errors} required />
        <SelectField name="position" label="Должность" options={positions} register={register} errors={errors} required />
        <SelectField name="employmentType" label="Вид занятости" options={employmentTypes} register={register} errors={errors} required />
        <SelectField name="workArrangement" label="Формат работы" options={workArrangements} register={register} errors={errors} required />
        <SelectField name="workplace" label="Рабочее место (город)" options={workplaces} register={register} errors={errors} required />
        <Field name="startDate" label="Дата выхода на работу" type="date" register={register} errors={errors} required />
        <Field name="probationMonths" label="Испытательный срок" type="number" min={0} max={6} hint="В месяцах, по умолчанию — 0" register={register} errors={errors} required />
        <SelectField name="schedule" label="График работы" options={workSchedules} register={register} errors={errors} required />
        <SelectField name="hiringReason" label="Основание" options={hiringReasons} register={register} errors={errors} required />
      </FormSection>

      <FormSection step="3" title="Образование" description="Образование и опыт работы" icon={<GraduationCap size={18} />}>
        <SelectField name="educationLevel" label="Уровень образования" options={educationLevels} register={register} errors={errors} required />
        <Field name="institution" label="Вуз / учебное заведение" register={register} errors={errors} required />
        <Field name="specialization" label="Специальность" register={register} errors={errors} required />
        <Field name="totalExperience" label="Опыт работы" placeholder="Например, 3 года 6 месяцев" register={register} errors={errors} required />
      </FormSection>

      <Section title="4. Вложения" meta="PDF, DOC, DOCX, JPG, PNG · до 10 МБ" className="hr-hiring-section hr-documents-section">
        <div className="hr-section-icon" aria-hidden="true"><Paperclip size={18} /></div>
        <div className="hr-document-grid">
          {documentUpload('Удостоверение личности', 'Документ, удостоверяющий личность', 'Удостоверение, паспорт или вид на жительство', true)}
          {documentUpload('Диплом', 'Диплом об образовании', diplomaRequired ? 'Обязателен для выбранного уровня образования' : 'Не требуется для среднего общего образования', diplomaRequired)}
        </div>
        {attachmentError && <div className="hr-attachment-error" role="alert">{attachmentError}</div>}
      </Section>

      <div className="hr-add-employee-actions"><span>{isDirty ? 'Есть несохранённые изменения' : 'Черновик сохранён'} · PDF пока не формируется</span><button type="button" className="secondary-button" onClick={() => setConfirmClear(true)}><RotateCcw size={16} />Очистить</button><button type="button" className="secondary-button" onClick={saveDraft}><Save size={16} />Сохранить черновик</button><button type="submit" className="primary-button"><CheckCircle2 size={16} />Завершить заполнение</button></div>
    </form>

    {confirmClear && <div className="dialog-backdrop"><section className="dialog hr-confirm-dialog" role="dialog" aria-modal="true" aria-label="Очистить форму"><header><span>Очистить форму?</span><button className="icon-button" onClick={() => setConfirmClear(false)} aria-label="Закрыть"><X size={18} /></button></header><p>Все введённые данные, вложения и локальный черновик будут удалены.</p><footer><button className="secondary-button" onClick={() => setConfirmClear(false)}>Отмена</button><button className="primary-button" onClick={clearForm}>Очистить</button></footer></section></div>}
  </>;
}
