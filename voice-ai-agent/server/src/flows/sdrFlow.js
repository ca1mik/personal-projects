const {
  BOOK_MEETING,
  CHECK_MANAGER_CALENDAR,
  CREATE_LEAD,
  TRANSFER_TO_SALES_MANAGER,
  UPDATE_CRM,
} = require('../services/tools');

function normalize(value) {
  return String(value || '').trim().toLowerCase();
}

function isDecisionMaker(value) {
  const lowered = normalize(value);
  return (
    lowered.includes('сам') ||
    lowered.includes('самостоятельно') ||
    lowered.includes('я принимаю') ||
    lowered.includes('лпр')
  );
}

function hasNoInterest(data) {
  const source = `${data.business_need || ''} ${data.problem || ''}`.toLowerCase();
  return ['нет интерес', 'не актуаль', 'просто смотр', 'пока не нужно', 'не требуется'].some((token) =>
    source.includes(token),
  );
}

function classifyLead(data) {
  if (hasNoInterest(data)) {
    return 'Cold Lead';
  }

  const hasNeed = Boolean(data.business_need);
  const hasBudget = ['есть', 'планируется'].includes(normalize(data.budget));
  const isAuthority = isDecisionMaker(data.authority);
  const timeline = normalize(data.timeline);
  const fastTimeline = ['срочно', 'в течение месяца', 'в течение квартала'].includes(timeline);

  if (hasNeed && hasBudget && isAuthority && fastTimeline) {
    return 'Hot Lead';
  }

  if (hasNeed) {
    return 'Warm Lead';
  }

  return 'Cold Lead';
}

module.exports = [
  {
    id: 'greeting',
    prompt:
      'Здравствуйте. Меня зовут Анна, я виртуальный помощник компании. Подскажите, пожалуйста, как я могу к вам обращаться?',
    field: 'customer_name',
    next: 'company',
  },
  {
    id: 'company',
    prompt: 'Спасибо. Подскажите, пожалуйста, как называется ваша компания?',
    field: 'company',
    next: 'job_title',
  },
  {
    id: 'job_title',
    prompt: 'Какая у вас должность?',
    field: 'job_title',
    next: 'industry',
  },
  {
    id: 'industry',
    prompt: 'В какой отрасли работает ваша компания?',
    field: 'industry',
    next: 'company_size',
  },
  {
    id: 'company_size',
    prompt: 'Сколько сотрудников работает в компании?',
    field: 'company_size',
    next: 'need',
  },
  {
    id: 'need',
    prompt: 'Расскажите, пожалуйста, какая задача стоит перед вашей компанией?',
    field: 'business_need',
    next: 'problem',
  },
  {
    id: 'problem',
    prompt: 'Что сейчас вызывает наибольшие сложности?',
    field: 'problem',
    next: 'budget',
  },
  {
    id: 'budget',
    prompt: 'Предусмотрен ли бюджет на решение данной задачи? Ответьте, пожалуйста: есть, планируется или нет.',
    field: 'budget',
    next: 'authority',
  },
  {
    id: 'authority',
    prompt: 'Вы самостоятельно принимаете решение по выбору решения или участвуют другие коллеги?',
    field: 'authority',
    next: 'timeline',
  },
  {
    id: 'timeline',
    prompt: 'Когда вы планируете запуск проекта? Срочно, в течение месяца, в течение квартала или позже?',
    field: 'timeline',
    next: 'email',
  },
  {
    id: 'email',
    prompt: 'Подскажите, пожалуйста, рабочий email для приглашения на встречу.',
    field: 'email',
    next: 'evaluate_lead',
  },
  {
    id: 'evaluate_lead',
    autoRun: true,
    tool: async (message, data, session) => {
      const leadStatus = classifyLead(data);
      session.collected.lead_status = leadStatus;

      await CREATE_LEAD(data);
      await UPDATE_CRM({ ...data, leadStatus });

      if (leadStatus === 'Cold Lead') {
        return { nextStepId: 'cold_finish' };
      }

      const calendar = await CHECK_MANAGER_CALENDAR();
      session.collected.available_slots = calendar.slots;
      return { nextStepId: 'offer_slots' };
    },
    next: null,
  },
  {
    id: 'offer_slots',
    prompt: (session) => {
      const slots = session.collected.available_slots || [];
      const formatted = slots
        .map((slot, index) => {
          const start = new Date(slot.start);
          return `${index + 1}. ${start.toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })}`;
        })
        .join('\n');

      const intro =
        session.collected.lead_status === 'Hot Lead'
          ? 'По вашему запросу вижу, что встречу лучше назначить сразу.'
          : 'Чтобы детальнее обсудить задачу, предлагаю короткую встречу с менеджером.';

      return `${intro}\nСвободные слоты:\n${formatted}\nВыберите, пожалуйста, номер удобного слота.`;
    },
    field: 'selected_slot',
    next: 'book_meeting',
  },
  {
    id: 'book_meeting',
    autoRun: true,
    tool: async (message, data, session) => {
      const slots = session.collected.available_slots || [];
      const index = Number.parseInt(data.selected_slot, 10) - 1;
      const slot = slots[index];

      if (!slot) {
        session.collected.selected_slot = '';
        return { nextStepId: 'offer_slots' };
      }

      const booking = await BOOK_MEETING({
        email: data.email,
        customerName: data.customer_name,
        slot,
      });

      session.collected.meeting_id = booking.meetingId;
      session.collected.booked_slot = slot;
      await UPDATE_CRM({
        customerName: data.customer_name,
        leadStatus: data.lead_status,
        meetingId: booking.meetingId,
        slot,
      });
      return { nextStepId: 'meeting_confirmed' };
    },
    next: null,
  },
  {
    id: 'meeting_confirmed',
    prompt:
      'Встреча успешно назначена. На вашу почту будет отправлено приглашение. Спасибо за уделенное время.',
    terminal: true,
    next: null,
  },
  {
    id: 'cold_finish',
    prompt:
      'Спасибо за информацию. Я зафиксировала ваш запрос в CRM. Если захотите вернуться к обсуждению, менеджер сможет связаться с вами позже.',
    terminal: true,
    next: null,
  },
  {
    id: 'transfer_sales',
    autoRun: true,
    tool: async () => TRANSFER_TO_SALES_MANAGER(),
    prompt: 'Секунду, переключаю вас на менеджера по продажам.',
    next: null,
  },
];
