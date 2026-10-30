const assert = require('assert');
const app = require('./src/index');

const PORT = 4010;
const BASE_URL = `http://127.0.0.1:${PORT}/api`;

if (typeof fetch !== 'function') {
  throw new Error('For test.js требуется Node.js с глобальным fetch.');
}

async function post(path, body) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });

  const json = await response.json();
  if (!response.ok) {
    throw new Error(`${path}: ${response.status} ${JSON.stringify(json)}`);
  }

  return json;
}

async function postExpectStatus(path, body, expectedStatus) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });

  const json = await response.json();
  assert.strictEqual(response.status, expectedStatus, `${path} should return ${expectedStatus}`);
  return json;
}

function printTurn(label, payload) {
  const parts = [];
  if (payload.systemMessages && payload.systemMessages.length > 0) {
    parts.push(`system=${payload.systemMessages.join(' | ')}`);
  }
  if (payload.prompt) {
    parts.push(`prompt=${payload.prompt}`);
  }
  if (payload.completed) {
    parts.push('completed=true');
  }
  console.log(`${label}: ${parts.join(' || ')}`);
}

async function runScenario(name, startPath, messages, finalCheck) {
  console.log(`\n=== ${name} ===`);
  const started = await post(`/${startPath}/start`, {});
  assert.ok(started.sessionId, 'sessionId is required');
  assert.ok(typeof started.prompt === 'string' || Array.isArray(started.systemMessages));
  printTurn('start', started);

  let state = started;
  for (const message of messages) {
    state = await post(`/${startPath}/message`, {
      sessionId: started.sessionId,
      message,
    });
    console.log(`user: ${message}`);
    printTurn('bot', state);
    if (state.completed) {
      break;
    }
  }

  assert.ok(state.completed, `${name} should complete`);
  await finalCheck(state);
}

async function main() {
  const server = app.listen(PORT, () => {
    console.log(`Test server started on ${PORT}`);
  });

  try {
    await runScenario(
      'SDR Hot Lead',
      'sdr',
      [
        'Иван',
        'ООО Ромашка',
        'Руководитель отдела продаж',
        'ИТ',
        '50 сотрудников',
        'Автоматизация обработки лидов',
        'Менеджеры долго отвечают на входящие заявки',
        'есть',
        'Да, решение принимаю я',
        'в течение месяца',
        'ivan@romashka.ru',
        '1',
      ],
      async (state) => {
        assert.match(state.prompt, /Встреча успешно назначена/);
      },
    );

    await runScenario(
      'SDR Cold Lead',
      'sdr',
      [
        'Мария',
        'ООО Север',
        'Операционный директор',
        'Логистика',
        '120 сотрудников',
        'Пока не требуется, просто изучаем рынок',
        'Нет интереса к проекту в этом квартале',
        'нет',
        'Решаем вместе с коллегами',
        'позже',
        'maria@sever.ru',
      ],
      async (state) => {
        assert.match(state.prompt, /зафиксировала ваш запрос/i);
      },
    );

    await runScenario(
      'Dentist New Appointment',
      'dentist',
      ['Хочу записаться', 'Анна', '+7 999 111-22-33', '12.03.1993', 'чистка', '1', 'да'],
      async (state) => {
        assert.match(state.prompt, /Запись подтверждена/);
      },
    );

    await runScenario(
      'Dentist FAQ Price',
      'dentist',
      ['Сколько стоит чистка?'],
      async (state) => {
        assert.match(state.prompt, /Чистка/);
      },
    );

    await runScenario(
      'Dentist Reschedule',
      'dentist',
      ['Хочу перенос записи', 'Ирина', '+7 999 000-11-22', '20 июня в 14:00', 'лечение', '2', 'да'],
      async (state) => {
        assert.match(state.prompt, /Запись перенесена/);
      },
    );

    await runScenario(
      'Dentist Cancel',
      'dentist',
      ['Нужно отменить прием', 'Павел', '+7 999 777-88-99', '21 июня в 10:00', 'да'],
      async (state) => {
        assert.match(state.prompt, /Запись отменена/);
      },
    );

    await runScenario(
      'Dentist Transfer To Doctor',
      'dentist',
      ['У меня острая боль и опухла десна'],
      async (state) => {
        assert.match(state.prompt, /переведу ваш вопрос на врача/i);
      },
    );

    await runScenario(
      'Support Resolved',
      'support',
      [
        'Не могу войти в систему, пишет неверный логин',
        'Ольга',
        'olga@example.com',
        'acc-1001',
        'Core CRM',
        'нет',
        'да',
      ],
      async (state) => {
        assert.match(state.prompt, /удалось помочь/);
      },
    );

    await runScenario(
      'Support Escalation',
      'support',
      [
        'У нас ошибка сервера 500 в API интеграции',
        'Сергей',
        'sergey@example.com',
        'acc-2002',
        'Public API',
        'stacktrace line 1',
        'нет',
        '16 июня 2026 10:15',
      ],
      async (state) => {
        assert.match(state.prompt, /Ваше обращение зарегистрировано под номером/);
      },
    );

    await runScenario(
      'Support Ticket Without KB',
      'support',
      [
        'В отчете экспорта ломается CSV форматирование у одного клиента',
        'Никита',
        'nikita@example.com',
        'acc-3003',
        'Exports',
        'CSV contains broken delimiter',
        'есть скриншот',
        '16 июня 2026 14:35',
      ],
      async (state) => {
        assert.match(state.prompt, /Ваше обращение зарегистрировано под номером/);
      },
    );

    await runScenario(
      'Delivery Order',
      'delivery',
      [
        'Хочу оформить доставку',
        '+7 999 123-45-67',
        'Ленина',
        '15',
        '34',
        '2',
        '5',
        '1234',
        'квартира',
        'да',
        'пепперони',
        '2 большие на тонком тесте, сырный борт',
        'нет',
        'картой курьеру',
        'да',
      ],
      async (state) => {
        assert.match(state.prompt, /Ваш заказ успешно оформлен/);
      },
    );

    await runScenario(
      'Delivery Menu Question',
      'delivery',
      ['Какой состав у цезаря?', '+7 999 555-55-55', 'Ленина', '12', 'нет', '1', '3', 'нет', 'офис', 'да', 'цезарь', '1 стандартная без лука', 'нет', 'онлайн', 'да'],
      async (state) => {
        assert.match(state.prompt, /Ваш заказ успешно оформлен/);
      },
    );

    await runScenario(
      'Delivery Unavailable Dish Alternative',
      'delivery',
      [
        'Хочу оформить доставку',
        '+7 999 222-22-22',
        'Советская',
        '7',
        '15',
        '1',
        '2',
        'нет',
        'квартира',
        'да',
        'хачапури с беконом',
        'да',
        '1 стандартная',
        'нет',
        'наличными курьеру',
        'да',
      ],
      async (state) => {
        assert.match(state.prompt, /Ваш заказ успешно оформлен/);
      },
    );

    await runScenario(
      'Delivery Unavailable Zone',
      'delivery',
      ['Хочу оформить доставку', '+7 999 666-66-66', 'Калуга', '3', 'нет', '1', '1', 'нет', 'частный дом', 'нет'],
      async (state) => {
        assert.match(state.prompt, /Спасибо за звонок/);
      },
    );

    await runScenario(
      'Delivery Transfer To Manager',
      'delivery',
      ['Хочу отменить существующий заказ'],
      async (state) => {
        assert.match(state.prompt, /перенаправляю ваш звонок на менеджера/i);
      },
    );

    console.log('\n=== API Validation ===');
    const invalidSession = await postExpectStatus('/sdr/message', {
      sessionId: 'missing',
      message: 'test',
    }, 400);
    console.log(`invalid session: ${JSON.stringify(invalidSession)}`);

    const invalidPayload = await postExpectStatus('/delivery/message', {
      sessionId: '',
    }, 400);
    console.log(`invalid payload: ${JSON.stringify(invalidPayload)}`);

    console.log('\nAll scenarios passed.');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

main().catch((error) => {
  console.error('\nTest failed:', error);
  process.exitCode = 1;
});
