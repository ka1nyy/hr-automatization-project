import { zodResolver } from '@hookform/resolvers/zod';
import {
  ArrowLeft,
  ArrowRight,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  ChevronLeft,
  FileText,
  GraduationCap,
  Loader2,
  Paperclip,
  Send,
  Trash2,
  UserRound,
  X
} from 'lucide-react';
import { useEffect, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { useForm, type FieldErrors, type UseFormRegister } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { PageHeader } from '../../../shared/components';
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
  type AttachmentCategory
} from '../add-employee/referenceData';
import { addEmployeeSchema, type AddEmployeeFormValues } from '../add-employee/schema';
import { validateAttachment, type EmployeeAttachment } from '../add-employee/utils';
import { hiringRequestsApi } from '../api/hiringRequests';

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

type RegistrationStep = {
  title: string;
  shortTitle: string;
  description: string;
  icon: ReactNode;
  fields: Array<keyof AddEmployeeFormValues>;
};

const registrationSteps: RegistrationStep[] = [
  {
    title: 'Персональная информация',
    shortTitle: 'Личные данные',
    description: 'Основные сведения, контакты и документ кандидата',
    icon: <UserRound size={20} />,
    fields: ['lastName', 'firstName', 'middleName', 'iin', 'birthDate', 'gender', 'citizenship', 'maritalStatus', 'personalPhone', 'personalEmail', 'address', 'identityDocumentType', 'identityDocumentNumber']
  },
  {
    title: 'Предлагаемая занятость',
    shortTitle: 'Занятость',
    description: 'Должность, подразделение и условия выхода на работу',
    icon: <BriefcaseBusiness size={20} />,
    fields: ['department', 'position', 'employmentType', 'workArrangement', 'workplace', 'startDate', 'probationMonths', 'schedule', 'hiringReason']
  },
  {
    title: 'Образование и опыт',
    shortTitle: 'Образование',
    description: 'Квалификация кандидата и релевантный опыт работы',
    icon: <GraduationCap size={20} />,
    fields: ['educationLevel', 'institution', 'specialization', 'totalExperience']
  },
  {
    title: 'Документы и проверка',
    shortTitle: 'Документы',
    description: 'Вложения и итоговая проверка данных перед завершением',
    icon: <Paperclip size={20} />,
    fields: []
  }
];

function Field({ name, label, register, errors, required, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & CommonFieldProps) {
  const numericValue = name === 'probationMonths';
  return <label>{label}{required && <em>*</em>}<input {...register(name, numericValue ? { valueAsNumber: true } : undefined)} {...props} />{hint && !errors[name] && <small className="hr-field-hint">{hint}</small>}{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}

function SelectField({ name, label, options, register, errors, required }: CommonFieldProps & { options: readonly string[] }) {
  return <label>{label}{required && <em>*</em>}<select {...register(name)}><option value="">Выберите</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select>{errors[name] && <small className="hr-field-error">{String(errors[name]?.message)}</small>}</label>;
}

function scrollToWizard() {
  const wizard = document.getElementById('employee-registration-wizard');
  if (wizard && 'scrollIntoView' in wizard) wizard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export default function HrAddEmployeePage({ onBack }: { onBack?: () => void }) {
  const canOpen = usePermission('hr.employees.read');
  const form = useForm<AddEmployeeFormValues>({ resolver: zodResolver(addEmployeeSchema), mode: 'onBlur', defaultValues: addEmployeeDefaults });
  const [activeStep, setActiveStep] = useState(0);
  const [highestStep, setHighestStep] = useState(0);
  const [attachments, setAttachments] = useState<EmployeeAttachment[]>([]);
  const [notice, setNotice] = useState('');
  const [attachmentError, setAttachmentError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [requestId, setRequestId] = useState<string | null>(null);
  const [requestRevision, setRequestRevision] = useState(1);
  const [pdfVersionId, setPdfVersionId] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const { register, formState: { errors, isDirty }, getValues, handleSubmit, reset, trigger, watch } = form;
  const values = watch();
  const educationLevel = values.educationLevel;
  const diplomaRequired = educationLevel !== 'Среднее общее';
  const currentStep = registrationSteps[activeStep];
  const candidateName = [values.lastName, values.firstName, values.middleName].filter(Boolean).join(' ') || 'Новый сотрудник';

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

  const saveDraft = async (manageBusy = true) => {
    const draftValues = getValues();
    const draft = saveEmployeeDraft(localStorage, draftValues);
    setNotice(`Локальный черновик сохранён · ${new Date(draft.savedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}. Файлы не сохраняются локально.`);
    if (manageBusy) setBusy(true);
    try {
      const saved = requestId ? await hiringRequestsApi.update(requestId, requestRevision, draftValues) : await hiringRequestsApi.create(draftValues);
      setRequestId(saved.id); setRequestRevision(saved.revision); reset(draftValues);
      setNotice(`Черновик ${saved.requestNumber} сохранён на сервере · ${new Date(draft.savedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`);
      return saved;
    } catch (error) {
      setNotice(`Не удалось сохранить черновик: ${error instanceof Error ? error.message : 'ошибка API'}`);
      return undefined;
    } finally { if (manageBusy) setBusy(false); }
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

  const goToStep = (step: number) => {
    if (step > highestStep) return;
    setActiveStep(step);
    scrollToWizard();
  };

  const goNext = async () => {
    const valid = await trigger(currentStep.fields, { shouldFocus: true });
    if (!valid) return;
    const nextStep = Math.min(activeStep + 1, registrationSteps.length - 1);
    setActiveStep(nextStep);
    setHighestStep((current) => Math.max(current, nextStep));
    scrollToWizard();
  };

  const complete = handleSubmit(async () => {
    const hasIdentity = attachments.some((item) => item.category === 'Удостоверение личности');
    const hasDiploma = attachments.some((item) => item.category === 'Диплом');
    if (!hasIdentity || (diplomaRequired && !hasDiploma)) {
      setAttachmentError(!hasIdentity ? 'Прикрепите копию документа, удостоверяющего личность.' : 'Для выбранного уровня образования нужно прикрепить диплом.');
      setActiveStep(3);
      setHighestStep(3);
      return;
    }
    setAttachmentError(''); setSubmitError(''); setBusy(true);
    try {
      if (requestId && pdfVersionId) {
        const sent = await hiringRequestsApi.submit(requestId, requestRevision);
        setRequestRevision(sent.revision);
        setSubmitted(true);
        clearEmployeeDraft(localStorage);
        reset(getValues());
        setNotice(`Заявление ${sent.requestNumber} отправлено на рассмотрение.`);
        return;
      }
      const saved = await saveDraft(false);
      if (!saved) return;
      for (const attachment of attachments) {
        await hiringRequestsApi.upload(saved.id, attachment.category === 'Удостоверение личности' ? 'identity' : 'diploma', attachment.file);
      }
      const withFiles = await hiringRequestsApi.get(saved.id);
      await hiringRequestsApi.generatePdf(saved.id, withFiles.revision);
      const generated = await hiringRequestsApi.get(saved.id);
      setRequestRevision(generated.revision); setPdfVersionId(generated.pdfVersionId ?? null);
      const sent = await hiringRequestsApi.submit(saved.id, generated.revision);
      setRequestRevision(sent.revision);
      setSubmitted(true);
      clearEmployeeDraft(localStorage);
      reset(getValues());
      setNotice(`Заявление ${sent.requestNumber} сформировано в PDF и отправлено на рассмотрение.`);
    } catch (error) {
      const message = `Не удалось отправить заявление: ${error instanceof Error ? error.message : 'ошибка API'}`;
      setSubmitError(message);
      setNotice(message);
    } finally { setBusy(false); }
  }, (invalidErrors) => {
    const invalidStep = registrationSteps.findIndex((step) => step.fields.some((field) => invalidErrors[field]));
    setActiveStep(invalidStep >= 0 ? invalidStep : 0);
    setNotice('Проверьте обязательные поля отмеченного этапа.');
    scrollToWizard();
  });

  const documentUpload = (category: AttachmentCategory, title: string, description: string, required: boolean) => {
    const files = attachments.filter((item) => item.category === category);
    return <div className={`hr-document-upload ${files.length ? 'has-files' : ''}`}>
      <div className="hr-document-upload-copy"><span><FileText size={18} /></span><div><strong>{title}{required && <em>*</em>}</strong><small>{description}</small></div></div>
      <label className="secondary-button"><Paperclip size={15} />{files.length ? 'Добавить ещё' : 'Выбрать файл'}<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" multiple onChange={(event) => { addFiles(Array.from(event.target.files ?? []), category); event.currentTarget.value = ''; }} /></label>
      {files.length > 0 && <ul>{files.map((item) => <li key={item.id}><span><strong>{item.file.name}</strong><small>{(item.file.size / 1024 / 1024).toFixed(2)} МБ</small></span><button type="button" className="icon-button" onClick={() => setAttachments((current) => current.filter((file) => file.id !== item.id))} aria-label={`Удалить ${item.file.name}`}><Trash2 size={15} /></button></li>)}</ul>}
    </div>;
  };

  return <>
    <PageHeader
      eyebrow="HR · Регистрация сотрудника"
      title={candidateName === 'Новый сотрудник' ? 'Регистрация сотрудника' : `Регистрация: ${candidateName}`}
      actions={onBack ? <button type="button" className="secondary-button" onClick={onBack}><ArrowLeft size={16} /> Назад к списку</button> : undefined}
    />

    {notice && <div className="hr-form-notice" role="status"><span><CheckCircle2 size={15} />{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Закрыть уведомление"><X size={14} /></button></div>}

    <form id="employee-registration-wizard" className="hr-registration-wizard" onSubmit={complete}>
      <div className="hr-timeline-container">
        <div className="hr-timeline-wrapper">
          <div className="hr-timeline-line-background">
            <div className="hr-timeline-line-filled" style={{ width: `${(activeStep / (registrationSteps.length - 1)) * 100}%` }} />
          </div>
          <ol className="hr-registration-timeline" aria-label="Этапы регистрации сотрудника">
            {registrationSteps.map((step, index) => {
              const state = index < activeStep ? 'done' : index === activeStep ? 'active' : index <= highestStep ? 'available' : 'upcoming';
              return <li className={`hr-timeline-item ${state}`} key={step.shortTitle}>
                <button type="button" onClick={() => goToStep(index)} disabled={index > highestStep} aria-current={index === activeStep ? 'step' : undefined}>
                  <span className="hr-timeline-icon-wrapper">
                    {index < activeStep ? <Check size={18} className="hr-icon-check" /> : step.icon}
                  </span>
                  <div className="hr-timeline-text">
                    <strong>{step.shortTitle}</strong>
                  </div>
                </button>
              </li>;
            })}
          </ol>
        </div>
      </div>

      <section key={activeStep} className="hr-registration-stage" aria-labelledby={`registration-step-${activeStep}`}>
        <header>
          <span className="hr-registration-stage-icon">{currentStep.icon}</span>
          <div><small>ЭТАП {activeStep + 1} ИЗ 4</small><h2 id={`registration-step-${activeStep}`}>{currentStep.title}</h2><p>{currentStep.description}</p></div>
          <b>{String(activeStep + 1).padStart(2, '0')}</b>
        </header>

        <div className="hr-registration-stage-body">
          {activeStep === 0 && <div className="field-grid hr-add-employee-fields">
            <div className="hr-name-row">
              <Field name="lastName" label="Фамилия" autoComplete="family-name" register={register} errors={errors} required />
              <Field name="firstName" label="Имя" autoComplete="given-name" register={register} errors={errors} required />
              <Field name="middleName" label="Отчество" autoComplete="additional-name" register={register} errors={errors} />
            </div>
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
          </div>}

          {activeStep === 1 && <div className="field-grid hr-add-employee-fields">
            <SelectField name="department" label="Департамент" options={departments} register={register} errors={errors} required />
            <SelectField name="position" label="Должность" options={positions} register={register} errors={errors} required />
            <SelectField name="employmentType" label="Вид занятости" options={employmentTypes} register={register} errors={errors} required />
            <SelectField name="workArrangement" label="Формат работы" options={workArrangements} register={register} errors={errors} required />
            <SelectField name="workplace" label="Рабочее место (город)" options={workplaces} register={register} errors={errors} required />
            <Field name="startDate" label="Дата выхода на работу" type="date" register={register} errors={errors} required />
            <Field name="probationMonths" label="Испытательный срок" type="number" min={0} max={6} hint="В месяцах, по умолчанию — 0" register={register} errors={errors} required />
            <SelectField name="schedule" label="График работы" options={workSchedules} register={register} errors={errors} required />
            <SelectField name="hiringReason" label="Основание" options={hiringReasons} register={register} errors={errors} required />
          </div>}

          {activeStep === 2 && <div className="field-grid hr-add-employee-fields hr-education-fields">
            <SelectField name="educationLevel" label="Уровень образования" options={educationLevels} register={register} errors={errors} required />
            <Field name="institution" label="Вуз / учебное заведение" register={register} errors={errors} required />
            <Field name="specialization" label="Специальность" register={register} errors={errors} required />
            <Field name="totalExperience" label="Опыт работы" placeholder="Например, 3 года 6 месяцев" register={register} errors={errors} required />
          </div>}

          {activeStep === 3 && <div className="hr-registration-final-step">
            <div className="hr-document-grid">
              {documentUpload('Удостоверение личности', 'Документ, удостоверяющий личность', 'Удостоверение, паспорт или вид на жительство', true)}
              {documentUpload('Диплом', 'Диплом об образовании', diplomaRequired ? 'Обязателен для выбранного уровня образования' : 'Не требуется для среднего общего образования', diplomaRequired)}
            </div>
            {attachmentError && <div className="hr-attachment-error" role="alert">{attachmentError}</div>}
            {submitError && <div className="hr-attachment-error" role="alert">{submitError}</div>}
          </div>}
        </div>

        <footer className="hr-registration-actions">
          <div className="hr-registration-navigation">
            {activeStep > 0 && <button type="button" className="secondary-button" onClick={() => { setActiveStep((step) => step - 1); scrollToWizard(); }}><ChevronLeft size={17} />Назад</button>}
            {activeStep < 3 ? <button type="button" className="primary-button" onClick={goNext}>Продолжить<ArrowRight size={17} /></button> : <button type="submit" className="primary-button" disabled={busy || submitted}>{busy ? <Loader2 className="spin" size={17} /> : <Send size={17} />}{submitted ? 'Заявление отправлено' : 'Отправить заявление'}</button>}
          </div>
        </footer>
      </section>
    </form>

  </>;
}
