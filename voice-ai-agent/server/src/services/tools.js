const MENU = [
  {
    id: 1,
    category: 'pizza',
    name: 'Пицца Пепперони',
    aliases: ['пепперони', 'пицца пепперони'],
    price: 890,
    available: true,
    sizes: ['маленькая', 'средняя', 'большая'],
    doughTypes: ['традиционное', 'тонкое'],
    crustTypes: ['классический', 'сырный'],
    description: 'Пепперони, моцарелла, томатный соус',
    weight: '520 г',
    calories: '1280 ккал',
  },
  {
    id: 2,
    category: 'salad',
    name: 'Салат Цезарь',
    aliases: ['цезарь', 'салат цезарь'],
    price: 540,
    available: true,
    portions: ['стандартная'],
    description: 'Курица, салат романо, соус цезарь, сухарики',
    weight: '280 г',
    calories: '540 ккал',
  },
  {
    id: 3,
    category: 'bakery',
    name: 'Хачапури с беконом',
    aliases: ['хачапури', 'хачапури с беконом'],
    price: 670,
    available: false,
    portions: ['стандартная'],
    description: 'Тесто, сыр, бекон, сливочное масло',
    weight: '410 г',
    calories: '930 ккал',
  },
  {
    id: 6,
    category: 'bakery',
    name: 'Хачапури по-аджарски',
    aliases: ['хачапури по-аджарски', 'аджарский хачапури'],
    price: 690,
    available: true,
    portions: ['стандартная'],
    description: 'Тесто, сыр, яйцо, сливочное масло',
    weight: '430 г',
    calories: '960 ккал',
  },
  {
    id: 4,
    category: 'rolls',
    name: 'Ролл Филадельфия',
    aliases: ['ролл филадельфия', 'филадельфия'],
    price: 760,
    available: true,
    portions: ['8 шт'],
    description: 'Лосось, сливочный сыр, рис, нори',
    weight: '240 г',
    calories: '480 ккал',
  },
  {
    id: 5,
    category: 'drink',
    name: 'Морс клюквенный',
    aliases: ['морс', 'морс клюквенный'],
    price: 180,
    available: true,
    volumes: ['0.5 л'],
    description: 'Домашний клюквенный морс',
    volume: '0.5 л',
  },
];

const CLINIC_SPECIALISTS = {
  лечение: 'Иванова Елена Сергеевна',
  чистка: 'Петрова Мария Андреевна',
  удаление: 'Смирнов Дмитрий Олегович',
  имплантация: 'Волков Алексей Игоревич',
  ортодонтия: 'Кузнецова Ольга Викторовна',
  консультация: 'Иванова Елена Сергеевна',
};

const KB = [
  {
    type: 'auth',
    keywords: ['не входит', 'вход', 'логин', 'авториза'],
    steps: [
      'Проверьте, что email введен без лишних пробелов.',
      'Нажмите "Забыли пароль?" и запросите новое письмо.',
      'Если используется SSO, попробуйте вход через корпоративный портал.',
    ],
  },
  {
    type: 'mfa',
    keywords: ['mfa', 'код', 'двухфактор'],
    steps: [
      'Проверьте корректность времени на телефоне.',
      'Сгенерируйте новый код в приложении-аутентификаторе.',
      'Если резервные коды есть, используйте один из них для входа.',
    ],
  },
  {
    type: 'payment',
    keywords: ['оплата', 'платеж', 'карта', 'подписк'],
    steps: [
      'Проверьте, что карта активна и на ней достаточно средств.',
      'Попробуйте повторить оплату из раздела "Биллинг".',
      'Если ошибка сохраняется, пришлите точное время и текст ошибки.',
    ],
  },
  {
    type: 'performance',
    keywords: ['медленно', 'таймаут', 'долго', 'тормозит'],
    steps: [
      'Очистите кэш браузера и обновите страницу.',
      'Проверьте, повторяется ли проблема в режиме инкогнито.',
      'Если проблема только в одном разделе, сообщите его название.',
    ],
  },
];

function buildSlots(baseDate, hours) {
  return hours.map((hour) => {
    const start = new Date(baseDate);
    start.setHours(hour, 0, 0, 0);
    const end = new Date(start);
    end.setMinutes(30);
    return {
      start: start.toISOString(),
      end: end.toISOString(),
    };
  });
}

async function CHECK_MANAGER_CALENDAR() {
  const base = new Date();
  base.setDate(base.getDate() + 1);
  return {
    slots: buildSlots(base, [11, 14, 16]),
  };
}

async function BOOK_MEETING(payload) {
  return {
    success: true,
    meetingId: `meet_${Date.now()}`,
    slot: payload.slot,
    email: payload.email || null,
  };
}

async function CREATE_LEAD(payload) {
  return {
    success: true,
    leadId: `lead_${Date.now()}`,
    payload,
  };
}

async function UPDATE_CRM(payload) {
  return {
    success: true,
    updatedAt: new Date().toISOString(),
    payload,
  };
}

async function TRANSFER_TO_SALES_MANAGER() {
  return { success: true, queue: 'sales_manager' };
}

async function FIND_SPECIALIST(service) {
  const normalized = String(service || '').trim().toLowerCase();
  return {
    specialist: CLINIC_SPECIALISTS[normalized] || 'Иванова Елена Сергеевна',
  };
}

async function CHECK_DOCTOR_AVAILABILITY() {
  const base = new Date();
  base.setDate(base.getDate() + 2);
  return {
    slots: buildSlots(base, [10, 13, 17]),
  };
}

async function CREATE_APPOINTMENT(payload) {
  return {
    success: true,
    appointmentId: `appt_${Date.now()}`,
    payload,
  };
}

async function CONFIRM_APPOINTMENT(payload) {
  return {
    success: true,
    confirmationCode: `cnf_${Date.now()}`,
    payload,
  };
}

async function GET_PRICE_LIST() {
  return {
    prices: {
      консультация: 'от 1 500 руб.',
      чистка: 'от 3 900 руб.',
      лечение: 'от 4 500 руб.',
      удаление: 'от 5 000 руб.',
      имплантация: 'от 38 000 руб.',
      ортодонтия: 'от 65 000 руб.',
    },
  };
}

async function GET_CLINIC_INFO() {
  return {
    address: 'г. Тула, проспект Ленина, 85',
    workingHours: 'ежедневно с 09:00 до 21:00',
    phone: '+7 (4872) 00-00-00',
  };
}

async function GET_PREPARATION_RULES(service) {
  const normalized = String(service || '').trim().toLowerCase();
  const rules = {
    чистка: 'За 2 часа до приема не употребляйте красящие напитки.',
    удаление: 'Возьмите с собой список принимаемых препаратов.',
    имплантация: 'Накануне не употребляйте алкоголь и плотно поешьте за 2 часа до визита.',
  };
  return {
    rules: rules[normalized] || 'Специальная подготовка не требуется, врач уточнит детали на приеме.',
  };
}

async function TRANSFER_TO_DOCTOR() {
  return { success: true, queue: 'doctor' };
}

async function SEARCH_KNOWLEDGE_BASE(query) {
  const lowered = String(query || '').toLowerCase();
  const article = KB.find((item) => item.keywords.some((keyword) => lowered.includes(keyword)));
  return {
    found: Boolean(article),
    type: article ? article.type : 'unknown',
    steps: article ? article.steps : [],
  };
}

async function SEARCH_PREVIOUS_INCIDENTS(query) {
  const lowered = String(query || '').toLowerCase();
  const match = lowered.includes('таймаут') || lowered.includes('ошибка 500');
  return {
    found: match,
    incidents: match ? ['INC-44021', 'INC-44102'] : [],
  };
}

async function CHECK_SYSTEM_STATUS() {
  return {
    status: 'operational',
    updatedAt: new Date().toISOString(),
  };
}

async function CREATE_SUPPORT_TICKET(payload) {
  return {
    success: true,
    ticketId: `548${String(Date.now()).slice(-2)}`,
    payload,
  };
}

async function ESCALATE_TO_L2(payload) {
  return {
    success: true,
    escalationId: `l2_${Date.now()}`,
    payload,
  };
}

async function GET_MENU() {
  return MENU;
}

async function SEARCH_MENU_ITEM(query) {
  const lowered = String(query || '').toLowerCase();
  const item = MENU.find(
    (menuItem) =>
      menuItem.name.toLowerCase().includes(lowered) ||
      lowered.includes(menuItem.name.toLowerCase()) ||
      menuItem.aliases.some((alias) => alias.includes(lowered) || lowered.includes(alias)),
  );

  return {
    found: Boolean(item),
    item: item || null,
  };
}

async function CHECK_AVAILABILITY(itemId) {
  const item = MENU.find((menuItem) => menuItem.id === Number(itemId));
  return {
    available: Boolean(item && item.available),
    item: item || null,
  };
}

async function CHECK_DELIVERY_ZONE(address) {
  const lowered = String(address || '').toLowerCase();
  const allowed = ['тула', 'ленина', 'советская', 'пролетарская', 'октябрьская'];
  const available = allowed.some((token) => lowered.includes(token));
  return {
    available,
    etaMinutes: available ? 55 : null,
  };
}

async function GET_ITEM_DETAILS(itemId) {
  const item = MENU.find((menuItem) => menuItem.id === Number(itemId));
  return item
    ? {
        found: true,
        details: {
          composition: item.description,
          weight: item.weight || null,
          volume: item.volume || null,
          calories: item.calories || null,
        },
      }
    : {
        found: false,
        details: null,
      };
}

async function CALCULATE_ORDER(order) {
  const items = Array.isArray(order.items) ? order.items : [];
  const itemsTotal = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const delivery = itemsTotal >= 1500 ? 0 : 250;
  const discount = itemsTotal >= 2000 ? 200 : 0;
  return {
    itemsTotal,
    delivery,
    discount,
    promotions: discount ? ['Скидка 200 руб. на заказ от 2000 руб.'] : [],
    total: itemsTotal + delivery - discount,
    etaMinutes: 55,
  };
}

async function CREATE_ORDER(payload) {
  if (!payload || !payload.items || payload.items.length === 0) {
    return { success: false, error: 'EMPTY_ORDER' };
  }

  return {
    success: true,
    orderId: `ord_${Date.now()}`,
    payload,
  };
}

async function TRANSFER_TO_MANAGER() {
  return { success: true, queue: 'manager' };
}

async function CREATE_CALLBACK(payload) {
  return {
    success: true,
    callbackId: `cb_${Date.now()}`,
    payload,
  };
}

module.exports = {
  BOOK_MEETING,
  CALCULATE_ORDER,
  CHECK_AVAILABILITY,
  CHECK_DELIVERY_ZONE,
  CHECK_DOCTOR_AVAILABILITY,
  CHECK_MANAGER_CALENDAR,
  CHECK_SYSTEM_STATUS,
  CONFIRM_APPOINTMENT,
  CREATE_APPOINTMENT,
  CREATE_CALLBACK,
  CREATE_LEAD,
  CREATE_ORDER,
  CREATE_SUPPORT_TICKET,
  ESCALATE_TO_L2,
  FIND_SPECIALIST,
  GET_CLINIC_INFO,
  GET_ITEM_DETAILS,
  GET_MENU,
  GET_PREPARATION_RULES,
  GET_PRICE_LIST,
  SEARCH_KNOWLEDGE_BASE,
  SEARCH_MENU_ITEM,
  SEARCH_PREVIOUS_INCIDENTS,
  TRANSFER_TO_DOCTOR,
  TRANSFER_TO_MANAGER,
  TRANSFER_TO_SALES_MANAGER,
  UPDATE_CRM,
};
