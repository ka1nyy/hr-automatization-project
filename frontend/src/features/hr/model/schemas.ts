import { differenceInCalendarDays, parseISO } from 'date-fns';
import { z } from 'zod';

export const leaveRequestSchema = z.object({
  leaveType: z.string().min(1, 'Выберите тип отпуска'),
  startDate: z.string().min(1, 'Укажите дату начала'),
  endDate: z.string().min(1, 'Укажите дату окончания'),
  substitute: z.string().min(2, 'Укажите замещающего сотрудника'),
  comment: z.string().max(500, 'Комментарий слишком длинный')
}).superRefine((value, context) => {
  if (differenceInCalendarDays(parseISO(value.endDate), parseISO(value.startDate)) < 0) {
    context.addIssue({ code: 'custom', path: ['endDate'], message: 'Дата окончания должна быть позже даты начала' });
  }
});

export type LeaveRequestForm = z.infer<typeof leaveRequestSchema>;

export function calculateLeaveDays(startDate: string, endDate: string) {
  return differenceInCalendarDays(parseISO(endDate), parseISO(startDate)) + 1;
}
