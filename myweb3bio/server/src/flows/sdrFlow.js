// server/src/flows/sdrFlow.js
// AI SDR (Sales Development Representative) — outbound sales script

const sdrFlow = {
  id: 'sdr',
  name: 'AI SDR — Продажи',
  steps: [
    {
      id: 'greeting',
      prompt: 'Добрый день! Меня зовут Алекс, я представляю компанию. Могу я узнать, с кем разговариваю?',
      field: 'name',
      validate: v => v.trim().length >= 2,
      reprompt: 'Простите, не расслышал. Как вас зовут?',
    },
    {
      id: 'company',
      prompt: (d) => `${d.name}, скажите, в какой компании вы работаете?`,
      field: 'company',
      validate: v => v.trim().length >= 2,
      reprompt: 'Уточните, пожалуйста, название компании.',
    },
    {
      id: 'role',
      prompt: (d) => `Отлично! А какова ваша должность в ${d.company}?`,
      field: 'role',
      validate: v => v.trim().length >= 2,
      reprompt: 'Пожалуйста, уточните вашу роль.',
    },
    {
      id: 'pain_point',
      prompt: 'С какими основными задачами или сложностями вы сейчас сталкиваетесь в работе?',
      field: 'painPoint',
      validate: v => v.trim().length >= 5,
      reprompt: 'Расскажите подробнее — что именно вас беспокоит?',
    },
    {
      id: 'interest',
      prompt: 'Понимаю вас. Было бы вам интересно узнать, как наше решение помогло похожим компаниям справиться с этим? (да / нет)',
      field: 'interested',
      validate: v => /да|нет|yes|no/i.test(v.trim()),
      reprompt: 'Пожалуйста, ответьте "да" или "нет".',
      transform: v => /да|yes/i.test(v.trim()) ? 'yes' : 'no',
    },
    {
      id: 'contact',
      prompt: (d) =>
        d.interested === 'yes'
          ? 'Отлично! Оставьте, пожалуйста, ваш email — мы пришлём материалы и предложим удобное время для демо.'
          : 'Понимаю! Если в будущем появится интерес — мы всегда рады помочь. Оставьте email, и мы не побеспокоим без причины.',
      field: 'email',
      validate: v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()),
      reprompt: 'Пожалуйста, введите корректный email-адрес.',
      transform: v => v.trim().toLowerCase(),
    },
    {
      id: 'done',
      terminal: true,
      prompt: (d) =>
        `Спасибо, ${d.name}! Мы отправим информацию на ${d.email}. Хорошего дня!`,
    },
  ],
};

module.exports = sdrFlow;
