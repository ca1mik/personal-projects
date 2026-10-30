// server/src/flows/deliveryFlow.js
// Voice delivery operator — order status & re-delivery booking script

const deliveryFlow = {
  id: 'delivery',
  name: 'Голосовой оператор доставки',
  steps: [
    {
      id: 'greeting',
      prompt: 'Добрый день! Служба доставки. Чем могу помочь? Уточните ваш запрос: статус заказа, переназначить доставку или другое.',
      field: 'requestType',
      validate: v => v.trim().length >= 2,
      reprompt: 'Уточните, пожалуйста, ваш вопрос.',
    },
    {
      id: 'order_number',
      prompt: 'Назовите номер вашего заказа.',
      field: 'orderNumber',
      validate: v => /[\w\d\-]{3,}/.test(v.trim()),
      reprompt: 'Укажите корректный номер заказа (он указан в SMS или email-подтверждении).',
      transform: v => v.trim().toUpperCase(),
    },
    {
      id: 'phone',
      prompt: 'Подтвердите номер телефона, указанный при оформлении заказа.',
      field: 'phone',
      validate: v => /[\d\s\+\-\(\)]{7,}/.test(v.trim()),
      reprompt: 'Введите номер телефона в формате +7 (XXX) XXX-XX-XX.',
      transform: v => v.trim(),
    },
    {
      id: 'action',
      prompt: (d) =>
        `Заказ ${d.orderNumber} найден. Что вы хотите сделать?\n` +
        '1 — Узнать статус\n' +
        '2 — Перенести дату доставки\n' +
        '3 — Изменить адрес',
      field: 'action',
      validate: v => /^[123]$/.test(v.trim()),
      reprompt: 'Введите цифру: 1, 2 или 3.',
    },
    {
      id: 'details',
      prompt: (d) => {
        if (d.action === '1') return 'Статус вашего заказа уточняется. Есть ли ещё вопросы? (да / нет)';
        if (d.action === '2') return 'Укажите удобную дату и временной интервал для новой доставки.';
        return 'Укажите новый адрес доставки.';
      },
      field: 'details',
      validate: v => v.trim().length >= 2,
    },
    {
      id: 'done',
      terminal: true,
      prompt: (d) => {
        if (d.action === '1') return `Заказ ${d.orderNumber}: в пути, ожидаемая доставка — сегодня до 21:00. Спасибо, что обратились!`;
        if (d.action === '2') return `Отлично! Доставка заказа ${d.orderNumber} перенесена. Новое время: ${d.details}. Уведомление придёт на ${d.phone}.`;
        return `Адрес для заказа ${d.orderNumber} изменён на: "${d.details}". Курьер будет уведомлён. До свидания!`;
      },
    },
  ],
};

module.exports = deliveryFlow;
