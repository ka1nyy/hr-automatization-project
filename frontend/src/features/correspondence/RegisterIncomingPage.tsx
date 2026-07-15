import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { AlertTriangle, ArrowLeft, CheckCircle2, FileCheck2, Paperclip, Save, ScanLine } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { repositories } from '../../repositories';
import { PageHeader, Section } from '../../shared/components';
import type { IncomingLetterInput } from '../../shared/types';

const schema = z.object({
  sender: z.string().min(3, 'Укажите организацию-отправителя'), senderType: z.string().min(1), senderNumber: z.string().min(2, 'Укажите исходящий номер'), senderDate: z.string().min(1), channel: z.string().min(1), documentType: z.string().min(1), subject: z.string().min(8, 'Тема должна содержать не менее 8 символов'), summary: z.string().min(10, 'Добавьте краткое содержание'), language: z.string(), pageCount: z.number().min(1), confidentiality: z.enum(['public', 'internal', 'restricted']), priority: z.enum(['normal', 'high', 'urgent']), responseRequired: z.boolean(), dueDate: z.string(), department: z.string(), executive: z.string(), notes: z.string()
});

export default function RegisterIncomingPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const { register, handleSubmit, watch, getValues, formState: { errors, isValid, isDirty } } = useForm<IncomingLetterInput>({ resolver: zodResolver(schema), mode: 'onChange', defaultValues: { sender: '', senderType: 'organization', senderNumber: '', senderDate: '2026-07-14', channel: 'Email', documentType: 'Официальное письмо', subject: '', summary: '', language: 'ru', pageCount: 1, confidentiality: 'internal', priority: 'normal', responseRequired: true, dueDate: '2026-07-21', department: '', executive: 'А. С. Нурланов', notes: '' } });
  const mutation = useMutation({ mutationFn: (input: IncomingLetterInput) => repositories.correspondence.registerIncoming(input), onSuccess: async (item) => { await queryClient.invalidateQueries({ queryKey: ['incoming'] }); await queryClient.invalidateQueries({ queryKey: ['dashboard'] }); navigate(`/correspondence/incoming/${item.id}?registered=1`); } });
  const checkDuplicate = async () => { const values = getValues(); const found = await repositories.correspondence.checkDuplicate(values.sender, values.senderNumber); setDuplicate(found ? found.number : 'clear'); };

  return <form onSubmit={handleSubmit((data) => mutation.mutate(data))}>
    <PageHeader eyebrow="Секретариат · Новая запись" title="Регистрация входящего письма" actions={<><Link className="secondary-button" to="/correspondence/incoming"><ArrowLeft size={16} /> К реестру</Link><button type="button" className="secondary-button"><Save size={16} /> Черновик</button><button className="primary-button" disabled={!isValid || mutation.isPending}><FileCheck2 size={16} /> {mutation.isPending ? 'Регистрация…' : 'Зарегистрировать'}</button></>} />
    <div className="form-progress"><span className="active"><i>1</i>Регистрационные данные</span><b /><span><i>2</i>Документы</span><b /><span><i>3</i>Проверка</span></div>
    <div className="form-layout">
      <div className="form-main">
        <Section title="Отправитель и реквизиты" meta="Обязательные поля отмечены *"><div className="field-grid">
          <label className="span-two">Организация-отправитель *<input {...register('sender')} placeholder="Полное наименование организации" />{errors.sender && <em>{errors.sender.message}</em>}</label>
          <label>Тип отправителя<select {...register('senderType')}><option value="organization">Организация</option><option value="government">Государственный орган</option><option value="person">Физическое лицо</option></select></label>
          <label>Исходящий номер *<div className="inline-field"><input {...register('senderNumber')} placeholder="Например, 12-4/1842" /><button type="button" onClick={checkDuplicate}>Проверить</button></div>{errors.senderNumber && <em>{errors.senderNumber.message}</em>}</label>
          <label>Дата документа *<input type="date" {...register('senderDate')} /></label>
          <label>Канал получения<select {...register('channel')}><option>Email</option><option>Бумажный оригинал</option><option>Государственный портал</option><option>ЭДО</option><option>Курьер</option><option>Корпоративный портал</option></select></label>
          {duplicate && <div className={`validation-banner span-two ${duplicate === 'clear' ? 'success' : 'warning'}`}>{duplicate === 'clear' ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}<span><strong>{duplicate === 'clear' ? 'Совпадений не найдено' : 'Возможный дубликат'}</strong>{duplicate === 'clear' ? 'Номер свободен для регистрации.' : `В реестре уже есть документ ${duplicate}.`}</span></div>}
        </div></Section>
        <Section title="Содержание документа"><div className="field-grid">
          <label>Тип документа<select {...register('documentType')}><option>Официальное письмо</option><option>Официальный запрос</option><option>Поручение</option><option>Договорная переписка</option><option>Информационное письмо</option></select></label>
          <label>Язык<select {...register('language')}><option value="ru">Русский</option><option value="kk">Казахский</option><option value="en">Английский</option></select></label>
          <label className="span-two">Тема *<input {...register('subject')} placeholder="Краткая и точная тема документа" />{errors.subject && <em>{errors.subject.message}</em>}</label>
          <label className="span-two">Краткое содержание *<textarea {...register('summary')} rows={4} placeholder="Ключевая суть, ожидаемое действие и важные обстоятельства" />{errors.summary && <em>{errors.summary.message}</em>}</label>
          <label>Количество страниц<input type="number" min="1" {...register('pageCount', { valueAsNumber: true })} /></label>
          <label>Конфиденциальность<select {...register('confidentiality')}><option value="public">Открытый</option><option value="internal">Для внутреннего использования</option><option value="restricted">Ограниченный доступ</option></select></label>
        </div></Section>
        <Section title="Маршрутизация и контроль"><div className="field-grid">
          <label>Предварительное подразделение<select {...register('department')}><option value="">Определит руководитель</option><option>Департамент документооборота и управления персоналом</option><option>Департамент инвестиций</option><option>Департамент кредитования</option><option>Департамент активов</option><option>Департамент строительства</option><option>Департамент стабильности фонда</option><option>Департамент экономического планирования</option><option>Юридический департамент</option><option>Бухгалтерия</option></select></label>
          <label>Получатель резолюции<select {...register('executive')}><option>А. С. Нурланов</option><option>Д. Р. Исмаилов</option><option>Л. К. Абдрахманова</option></select></label>
          <label>Срочность<select {...register('priority')}><option value="normal">Обычная</option><option value="high">Высокая</option><option value="urgent">Срочная</option></select></label>
          <label>Требуемая дата ответа<input type="date" {...register('dueDate')} /></label>
          <label className="checkbox-field span-two"><input type="checkbox" {...register('responseRequired')} /><span><strong>Требуется официальный ответ</strong><small>После исполнения будет создан проект исходящего письма.</small></span></label>
          <label className="span-two">Примечание секретариата<textarea {...register('notes')} rows={3} placeholder="Служебная аннотация для руководителя" /></label>
        </div></Section>
      </div>
      <aside className="form-aside">
        <Section title="Скан документа"><button type="button" className="upload-zone"><ScanLine size={28} /><strong>Загрузить скан</strong><span>PDF, JPG или PNG · до 50 МБ</span></button></Section>
        <Section title="Вложения" meta="0 файлов"><button type="button" className="upload-compact"><Paperclip size={17} /> Добавить вложения</button><p className="helper-text">Файлы появятся в карточке дела и будут доступны участникам процесса.</p></Section>
        <Section title="Готовность"><ul className="check-list"><li className={watch('sender') ? 'done' : ''}><CheckCircle2 size={15} /> Отправитель</li><li className={watch('subject') ? 'done' : ''}><CheckCircle2 size={15} /> Содержание</li><li className={isValid ? 'done' : ''}><CheckCircle2 size={15} /> Обязательные поля</li><li><ScanLine size={15} /> Скан документа</li></ul></Section>
        {mutation.error && <div className="mutation-error"><AlertTriangle size={18} /><span><strong>Регистрация не выполнена</strong>{mutation.error.message}</span></div>}
        <div className="autosave-note"><i className={isDirty ? 'saving' : ''} />{isDirty ? 'Изменения сохраняются локально' : 'Все изменения сохранены'}</div>
      </aside>
    </div>
  </form>;
}
