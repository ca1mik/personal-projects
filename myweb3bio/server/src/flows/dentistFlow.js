// server/src/flows/dentistFlow.js
// Dental clinic administrator — appointment booking script

const dentistFlow = {
  id: 'dentist',
  name: 'Администратор стоматологии',
  steps: [
    {
      id: 'greeting',
      prompt: 'Добрый день! Стоматология «Улыбка». Чем могу помочь?',
      field: 'request',
      validate: v => v.trim().length >= 2,
      reprompt: 'Уточните, пожалуйста, с чем вы хотите обратиться?',
    },
    {
      id: 'name',
      prompt: 'Назовите, пожалуйста, ваше имя и фамилию.',
      field: 'name',
      validate: v => v.trim().split(/\s+/).length >= 2,
      reprompt: 'Пожалуйста, укажите имя и фамилию.',
    },
    {
      id: 'phone',
      prompt: (d) => `${d.name.split(' ')[0]}, укажите ваш номер телефона для подтверждения.`,
      field: 'phone',
      validate: v => /[\d\s\+\-\(\)]{7,}/.test(v.trim()),
      reprompt: 'Введите корректный номер телефона.',
      transform: v => v.trim(),
    },
    {
      id: 'service',
      prompt: 'Какая услуга вас интересует? Например: консультация, лечение, чистка, протезирование.',
      field: 'service',
      validate: v => v.trim().length >= 3,
      reprompt: 'Уточните, пожалуйста, нужную услугу.',
    },
    {
      id: 'doctor',
      prompt: 'Есть ли предпочтение по врачу или вам подойдёт первый свободный специалист?',
      field: 'doctorPreference',
      validate: v => v.trim().length >= 2,
    },
    {
      id: 'date',
      prompt: 'Какая дата и время вам удобны? (например: завтра в 14:00 или пятница после 16:00)',
      field: 'preferredTime',
      validate: v => v.trim().length >= 3,
      reprompt: 'Укажите предпочтительное время для визита.',
    },
    {
      id: 'done',
      terminal: true,
      prompt: (d) =>
        `Отлично, ${d.name.split(' ')[0]}! Записываю вас на «${d.service}» (${d.preferredTime}). ` +
        `Подтверждение придёт на номер ${d.phone}. Ждём вас!`,
    },
  ],
};

module.exports = dentistFlow;
