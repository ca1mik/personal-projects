const {
  CALCULATE_ORDER,
  CHECK_AVAILABILITY,
  CHECK_DELIVERY_ZONE,
  CREATE_ORDER,
  GET_ITEM_DETAILS,
  GET_MENU,
  SEARCH_MENU_ITEM,
  TRANSFER_TO_MANAGER,
} = require('../services/tools');

function normalize(value) {
  return String(value || '').trim().toLowerCase();
}

function getGreetingByTime() {
  const now = new Date();
  const hour = now.getHours();

  if (hour >= 9 && hour <= 11) {
    return 'Служба доставки, доброе утро. Оформляем заказ?';
  }

  if (hour >= 12 && hour <= 18) {
    return 'Служба доставки, добрый день. Оформляем заказ?';
  }

  return 'Служба доставки, добрый вечер. Оформляем заказ?';
}

function formatAddress(data) {
  const apartment = normalize(data.apartment);
  const objectDetails =
    apartment && apartment !== 'нет' ? `${data.object_type} ${data.apartment}` : data.object_type;
  return `улица ${data.street}, дом ${data.house}, ${objectDetails}, подъезд ${data.entrance}, этаж ${data.floor}, домофон ${data.intercom}`;
}

function parseQuantity(text) {
  const match = String(text || '').match(/\d+/);
  return match ? Number.parseInt(match[0], 10) : 1;
}

function buildOrderSummary(items) {
  return items
    .map((item) => `${item.name}, ${item.quantity} шт., ${item.notes}`.trim())
    .join('; ');
}

module.exports = [
  {
    id: 'greeting',
    prompt: getGreetingByTime,
    tool: async (message, data, session) => {
      const lowered = normalize(message);
      session.collected.initial_intent = lowered;

      if (
        [
          'жалоб',
          'изменить заказ',
          'отмен',
          'возврат',
          'забронировать',
          'банкет',
          'корпоратив',
          'сотрудник',
          'менеджер',
        ].some((token) => lowered.includes(token))
      ) {
        return { nextStepId: 'transfer_manager' };
      }

      if (lowered.includes('меню')) {
        return { nextStepId: 'menu_overview' };
      }

      if (
        lowered.includes('есть ') ||
        lowered.includes('наличие') ||
        lowered.includes('доступно') ||
        lowered.includes('состав')
      ) {
        session.collected.menu_question = message;
        return { nextStepId: 'menu_question' };
      }

      return { nextStepId: 'phone' };
    },
    next: null,
  },
  {
    id: 'menu_overview',
    autoRun: true,
    tool: async (message, data, session) => {
      session.collected.menu = await GET_MENU();
      return { nextStepId: 'phone' };
    },
    prompt: (session) => {
      const lines = session.collected.menu.map((item) => `${item.name} — ${item.price} руб.`);
      return `По меню сейчас доступны: ${lines.join('; ')}.`;
    },
    next: null,
  },
  {
    id: 'menu_question',
    autoRun: true,
    tool: async (message, data, session) => {
      const search = await SEARCH_MENU_ITEM(session.collected.menu_question);
      session.collected.menu_question_result = search;

      if (!search.found) {
        session.collected.menu_question_answer =
          'Не нашла такую позицию в меню. Давайте подберем похожее блюдо при оформлении заказа.';
        return { nextStepId: 'phone' };
      }

      if (normalize(session.collected.menu_question).includes('состав')) {
        const details = await GET_ITEM_DETAILS(search.item.id);
        const info = details.details;
        session.collected.menu_question_answer = `В ${search.item.name}: ${info.composition}. Вес: ${
          info.weight || info.volume || 'не указан'
        }.`;
        return { nextStepId: 'phone' };
      }

      const availability = await CHECK_AVAILABILITY(search.item.id);
      session.collected.menu_question_answer = availability.available
        ? `${search.item.name} сейчас доступно.`
        : `${search.item.name} сейчас недоступно.`;
      return { nextStepId: 'phone' };
    },
    prompt: (session) => session.collected.menu_question_answer,
    next: null,
  },
  {
    id: 'phone',
    prompt: 'Назовите, пожалуйста, номер телефона для заказа.',
    field: 'customer_phone',
    next: 'street',
  },
  {
    id: 'street',
    prompt: 'Назовите улицу доставки.',
    field: 'street',
    next: 'house',
  },
  {
    id: 'house',
    prompt: 'Укажите номер дома.',
    field: 'house',
    next: 'apartment',
  },
  {
    id: 'apartment',
    prompt: 'Укажите квартиру или офис. Если не нужно, скажите "нет".',
    field: 'apartment',
    next: 'entrance',
  },
  {
    id: 'entrance',
    prompt: 'Подъезд?',
    field: 'entrance',
    next: 'floor',
  },
  {
    id: 'floor',
    prompt: 'Этаж?',
    field: 'floor',
    next: 'intercom',
  },
  {
    id: 'intercom',
    prompt: 'Код домофона? Если его нет, скажите "нет".',
    field: 'intercom',
    next: 'object_type',
  },
  {
    id: 'object_type',
    prompt: 'Это квартира, частный дом или офис?',
    field: 'object_type',
    next: 'check_zone',
  },
  {
    id: 'check_zone',
    autoRun: true,
    tool: async (message, data, session) => {
      const address = formatAddress(data);
      session.collected.full_address = address;
      const zone = await CHECK_DELIVERY_ZONE(address);
      session.collected.delivery_available = zone.available;
      session.collected.delivery_eta = zone.etaMinutes;
      return { nextStepId: zone.available ? 'confirm_address' : 'pickup_offer' };
    },
    next: null,
  },
  {
    id: 'pickup_offer',
    prompt:
      'К сожалению, доставка по этому адресу сейчас недоступна. Могу предложить самовывоз. Подойдет?',
    field: 'pickup_decision',
    next: (message) => (normalize(message).startsWith('да') ? 'pickup_finish' : 'decline_finish'),
  },
  {
    id: 'pickup_finish',
    autoRun: true,
    prompt: 'Хорошо. Для оформления самовывоза вас свяжу с менеджером.',
    tool: async () => null,
    next: 'transfer_manager',
  },
  {
    id: 'decline_finish',
    prompt: 'Поняла. Спасибо за звонок. Всего доброго.',
    terminal: true,
    next: null,
  },
  {
    id: 'confirm_address',
    prompt: (session) => `Подтвердите адрес: ${session.collected.full_address}. Всё верно?`,
    field: 'address_confirmation',
    next: (message) => (normalize(message).startsWith('да') ? 'order_item_name' : 'street'),
  },
  {
    id: 'order_item_name',
    prompt: 'Что добавляем в заказ?',
    field: 'item_name',
    next: 'check_item',
  },
  {
    id: 'check_item',
    autoRun: true,
    tool: async (message, data, session) => {
      const search = await SEARCH_MENU_ITEM(data.item_name);
      session.collected.item_search = search;

      if (!search.found) {
        return { nextStepId: 'item_retry' };
      }

      const availability = await CHECK_AVAILABILITY(search.item.id);
      if (!availability.available) {
        const menu = await GET_MENU();
        const alternative = menu.find(
          (item) => item.category === search.item.category && item.id !== search.item.id && item.available,
        );

        session.collected.alternative_item = alternative || null;
        return { nextStepId: 'item_unavailable' };
      }

      session.collected.current_item = search.item;
      return { nextStepId: 'item_details' };
    },
    next: null,
  },
  {
    id: 'item_retry',
    prompt: 'Не нашла такую позицию. Повторите, пожалуйста, название блюда.',
    field: 'item_name',
    next: 'check_item',
  },
  {
    id: 'item_unavailable',
    prompt: (session) => {
      const item = session.collected.item_search.item;
      const alternative = session.collected.alternative_item;
      if (alternative) {
        return `К сожалению, ${item.name} сейчас недоступно. Могу предложить ${alternative.name}. Добавляем?`;
      }

      return `К сожалению, ${item.name} сейчас недоступно. Давайте выберем другое блюдо.`;
    },
    field: 'alternative_confirmation',
    next: 'alternative_router',
  },
  {
    id: 'alternative_router',
    autoRun: true,
    tool: async (message, data, session) => {
      if (normalize(data.alternative_confirmation).startsWith('да') && session.collected.alternative_item) {
        session.collected.current_item = session.collected.alternative_item;
        return { nextStepId: 'item_details' };
      }

      return { nextStepId: 'order_item_name' };
    },
    next: null,
  },
  {
    id: 'item_details',
    prompt: (session) => {
      const item = session.collected.current_item;
      if (item.category === 'pizza') {
        return `По ${item.name} уточните количество, размер, тип теста и борт одним сообщением.`;
      }

      return `По ${item.name} уточните количество и при необходимости порцию, соус, добавки, напитки или приборы одним сообщением.`;
    },
    field: 'item_details_text',
    next: 'add_item',
  },
  {
    id: 'add_item',
    autoRun: true,
    tool: async (message, data, session) => {
      const item = session.collected.current_item;
      const quantity = parseQuantity(data.item_details_text);
      const orderItem = {
        id: item.id,
        name: item.name,
        price: item.price,
        quantity,
        notes: data.item_details_text,
      };

      if (!Array.isArray(session.collected.items)) {
        session.collected.items = [];
      }

      session.collected.items.push(orderItem);
      session.collected.last_added_item = orderItem.name;
      return { nextStepId: 'add_more' };
    },
    next: null,
  },
  {
    id: 'add_more',
    prompt: (session) => `${session.collected.last_added_item} добавила. Что-нибудь ещё?`,
    field: 'add_more_items',
    next: (message) => (normalize(message).startsWith('да') ? 'order_item_name' : 'payment_method'),
  },
  {
    id: 'payment_method',
    prompt: 'Какой способ оплаты: наличными курьеру, картой курьеру, онлайн или через СБП?',
    field: 'payment_method',
    next: 'calculate_order',
  },
  {
    id: 'calculate_order',
    autoRun: true,
    tool: async (message, data, session) => {
      const calculation = await CALCULATE_ORDER({
        items: session.collected.items || [],
      });

      session.collected.calculation = calculation;
      session.collected.order_total = calculation.total;
      return { nextStepId: 'final_confirm' };
    },
    next: null,
  },
  {
    id: 'final_confirm',
    prompt: (session) => {
      const calc = session.collected.calculation;
      return `Проверим заказ.\nДоставка на ${session.collected.full_address}.\n${buildOrderSummary(
        session.collected.items || [],
      )}.\nОплата: ${session.collected.payment_method}.\nИтоговая сумма ${calc.total} рублей.\nОриентировочное время доставки ${calc.etaMinutes} минут.\nВсё верно, оформляем?`;
    },
    field: 'final_confirmation',
    next: (message) => (normalize(message).startsWith('да') ? 'create_order' : 'order_item_name'),
  },
  {
    id: 'create_order',
    autoRun: true,
    tool: async (message, data, session) => {
      const result = await CREATE_ORDER({
        phone: data.customer_phone,
        address: data.full_address,
        items: data.items,
        paymentMethod: data.payment_method,
        total: data.order_total,
      });

      session.collected.order_result = result;
      return { nextStepId: result.success ? 'order_success' : 'order_error' };
    },
    next: null,
  },
  {
    id: 'order_success',
    prompt: 'Ваш заказ успешно оформлен. Ожидайте доставку. Спасибо за заказ.',
    terminal: true,
    next: null,
  },
  {
    id: 'order_error',
    autoRun: true,
    prompt: 'Для завершения оформления заказа мне нужно привлечь специалиста.',
    tool: async () => null,
    next: 'transfer_manager',
  },
  {
    id: 'transfer_manager',
    autoRun: true,
    tool: async () => TRANSFER_TO_MANAGER(),
    prompt: 'Секунду, перенаправляю ваш звонок на менеджера.',
    next: null,
  },
];
