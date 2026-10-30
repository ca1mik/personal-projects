const {
  CHECK_SYSTEM_STATUS,
  CREATE_SUPPORT_TICKET,
  ESCALATE_TO_L2,
  SEARCH_KNOWLEDGE_BASE,
  SEARCH_PREVIOUS_INCIDENTS,
} = require('../services/tools');

function normalize(value) {
  return String(value || '').trim().toLowerCase();
}

function detectPriority(description) {
  const lowered = normalize(description);
  if (
    lowered.includes('не работает вообще') ||
    lowered.includes('полностью недоступ') ||
    lowered.includes('сервис лежит')
  ) {
    return 'P1';
  }

  if (
    lowered.includes('не работает оплата') ||
    lowered.includes('не могу войти') ||
    lowered.includes('ключевой')
  ) {
    return 'P2';
  }

  if (lowered.includes('медленно') || lowered.includes('таймаут') || lowered.includes('частично')) {
    return 'P3';
  }

  return 'P4';
}

function detectEscalation(description) {
  const lowered = normalize(description);
  return ['баг', 'ошибка сервера', '500', 'потеря данных', 'api', 'интеграц'].some((token) =>
    lowered.includes(token),
  );
}

module.exports = [
  {
    id: 'greeting',
    prompt: 'Здравствуйте. Опишите, пожалуйста, проблему, с которой вы столкнулись.',
    field: 'issue_description',
    next: 'name',
  },
  {
    id: 'name',
    prompt: 'Как я могу к вам обращаться?',
    field: 'name',
    next: 'email',
  },
  {
    id: 'email',
    prompt: 'Укажите, пожалуйста, email для связи.',
    field: 'email',
    next: 'account',
  },
  {
    id: 'account',
    prompt: 'Какой у вас аккаунт или ID организации?',
    field: 'account',
    next: 'product',
  },
  {
    id: 'product',
    prompt: 'Какой продукт или модуль используете?',
    field: 'product',
    next: 'diagnose',
  },
  {
    id: 'diagnose',
    autoRun: true,
    tool: async (message, data, session) => {
      const kb = await SEARCH_KNOWLEDGE_BASE(data.issue_description);
      const incidents = await SEARCH_PREVIOUS_INCIDENTS(data.issue_description);
      const status = await CHECK_SYSTEM_STATUS();

      session.collected.issue_type = kb.type || 'unknown';
      session.collected.priority = detectPriority(data.issue_description);
      session.collected.system_status = status.status;
      session.collected.previous_incidents = incidents.incidents;
      session.collected.solution_steps = kb.steps || [];
      session.collected.solution_index = 0;
      session.collected.requires_escalation = detectEscalation(data.issue_description);

      if (session.collected.requires_escalation) {
        return { nextStepId: 'collect_logs' };
      }

      if (kb.found && kb.steps.length > 0) {
        return { nextStepId: 'solution_step' };
      }

      return { nextStepId: 'collect_logs' };
    },
    next: null,
  },
  {
    id: 'solution_step',
    prompt: (session) => {
      const steps = session.collected.solution_steps || [];
      const index = session.collected.solution_index || 0;
      const step = steps[index];
      return `Предлагаю проверить шаг ${index + 1}: ${step}\nПолучилось?`;
    },
    field: 'solution_feedback',
    next: 'solution_router',
  },
  {
    id: 'solution_router',
    autoRun: true,
    tool: async (message, data, session) => {
      const feedback = normalize(data.solution_feedback);
      if (feedback.startsWith('да')) {
        return { nextStepId: 'resolved' };
      }

      session.collected.solution_index += 1;
      const steps = session.collected.solution_steps || [];
      if (session.collected.solution_index < steps.length) {
        return { nextStepId: 'solution_step' };
      }

      return { nextStepId: 'collect_logs' };
    },
    next: null,
  },
  {
    id: 'collect_logs',
    prompt: 'Пришлите, пожалуйста, логи или текст ошибки.',
    field: 'logs',
    next: 'collect_screenshots',
  },
  {
    id: 'collect_screenshots',
    prompt: 'Есть ли скриншоты или запись экрана? Если нет, так и напишите.',
    field: 'screenshots',
    next: 'collect_error_time',
  },
  {
    id: 'collect_error_time',
    prompt: 'Уточните, пожалуйста, время возникновения ошибки.',
    field: 'error_time',
    next: 'create_ticket',
  },
  {
    id: 'create_ticket',
    autoRun: true,
    tool: async (message, data, session) => {
      const ticket = await CREATE_SUPPORT_TICKET({
        name: data.name,
        email: data.email,
        account: data.account,
        product: data.product,
        description: data.issue_description,
        logs: data.logs,
        screenshots: data.screenshots,
        errorTime: data.error_time,
        priority: data.priority,
      });

      session.collected.ticket_id = ticket.ticketId;
      return {
        nextStepId: data.requires_escalation ? 'escalate_l2' : 'ticket_done',
      };
    },
    next: null,
  },
  {
    id: 'escalate_l2',
    autoRun: true,
    tool: async (message, data, session) => {
      await ESCALATE_TO_L2({
        ticketId: data.ticket_id,
        account: data.account,
        issueType: data.issue_type,
      });
      return { nextStepId: 'ticket_done' };
    },
    next: null,
  },
  {
    id: 'ticket_done',
    prompt: (session) =>
      `Ваше обращение зарегистрировано под номером ${session.collected.ticket_id}. Специалисты уже получили информацию.`,
    terminal: true,
    next: null,
  },
  {
    id: 'resolved',
    prompt: 'Отлично. Рада, что удалось помочь. Если проблема повторится, напишите нам снова.',
    terminal: true,
    next: null,
  },
];
