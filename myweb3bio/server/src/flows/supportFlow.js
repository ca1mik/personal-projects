// server/src/flows/supportFlow.js
// SaaS Tech Support L1 — first-line technical support script

const supportFlow = {
  id: 'support',
  name: 'SaaS Техподдержка L1',
  steps: [
    {
      id: 'greeting',
      prompt: 'Здравствуйте! Техническая поддержка на связи. Опишите, пожалуйста, с чем вы столкнулись.',
      field: 'issue',
      validate: v => v.trim().length >= 5,
      reprompt: 'Пожалуйста, подробнее опишите проблему.',
    },
    {
      id: 'account',
      prompt: 'Укажите ваш email или логин от аккаунта.',
      field: 'account',
      validate: v => v.trim().length >= 3,
      reprompt: 'Введите email или логин для идентификации.',
      transform: v => v.trim().toLowerCase(),
    },
    {
      id: 'since_when',
      prompt: 'Когда именно возникла проблема? (например: сегодня с утра, вчера вечером)',
      field: 'sinceWhen',
      validate: v => v.trim().length >= 2,
    },
    {
      id: 'reproduced',
      prompt: 'Проблема возникает постоянно или периодически? Воспроизводится ли она при повторных попытках?',
      field: 'reproduced',
      validate: v => v.trim().length >= 2,
    },
    {
      id: 'error_msg',
      prompt: 'Есть ли какое-либо сообщение об ошибке или код ошибки? Если нет — напишите "нет".',
      field: 'errorMessage',
      validate: v => v.trim().length >= 1,
    },
    {
      id: 'steps_tried',
      prompt: 'Что уже пробовали сделать для решения? (перезагрузка, сброс пароля и т.д.)',
      field: 'stepsTried',
      validate: v => v.trim().length >= 2,
    },
    {
      id: 'done',
      terminal: true,
      prompt: (d) =>
        `Спасибо! Я зафиксировал обращение по аккаунту ${d.account}.\n` +
        `Тикет передан специалисту — ответ придёт в течение 15 минут. ` +
        `Номер обращения: TKT-${Date.now().toString().slice(-6)}. До свидания!`,
    },
  ],
};

module.exports = supportFlow;
