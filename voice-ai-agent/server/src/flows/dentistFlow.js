const {
  CHECK_DOCTOR_AVAILABILITY,
  CONFIRM_APPOINTMENT,
  CREATE_APPOINTMENT,
  FIND_SPECIALIST,
  GET_CLINIC_INFO,
  GET_PREPARATION_RULES,
  GET_PRICE_LIST,
  TRANSFER_TO_DOCTOR,
} = require('../services/tools');

function normalize(value) {
  return String(value || '').trim().toLowerCase();
}

function formatSlots(slots) {
  return slots
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
}

module.exports = [
  {
    id: 'greeting',
    prompt: 'Здравствуйте. Вас приветствует стоматологическая клиника. Чем могу помочь?',
    tool: async (message, data, session) => {
      const lowered = normalize(message);
      session.collected.intent = lowered;

      if (
        ['боль', 'болит', 'кровь', 'кровоточит', 'температура', 'опухло'].some((word) =>
          lowered.includes(word),
        )
      ) {
        return { nextStepId: 'transfer_doctor' };
      }

      if (lowered.includes('перенос')) {
        return { nextStepId: 'reschedule_name' };
      }

      if (lowered.includes('отмен')) {
        return { nextStepId: 'cancel_name' };
      }

      if (lowered.includes('стоим') || lowered.includes('стоит') || lowered.includes('цен')) {
        return { nextStepId: 'faq_price' };
      }

      if (lowered.includes('адрес') || lowered.includes('где') || lowered.includes('как вас найти')) {
        return { nextStepId: 'faq_info' };
      }

      if (lowered.includes('подготов')) {
        return { nextStepId: 'faq_preparation_service' };
      }

      return { nextStepId: 'collect_name' };
    },
    next: null,
  },
  {
    id: 'collect_name',
    prompt: 'Подскажите, пожалуйста, как вас зовут?',
    field: 'name',
    next: 'collect_phone',
  },
  {
    id: 'collect_phone',
    prompt: 'Укажите, пожалуйста, номер телефона.',
    field: 'phone',
    next: 'collect_birthdate',
  },
  {
    id: 'collect_birthdate',
    prompt: 'Назовите, пожалуйста, дату рождения.',
    field: 'birthdate',
    next: 'collect_service',
  },
  {
    id: 'collect_service',
    prompt:
      'Подскажите, какая услуга вас интересует: лечение, чистка, удаление, имплантация, ортодонтия или консультация?',
    field: 'service',
    next: 'find_specialist',
  },
  {
    id: 'find_specialist',
    autoRun: true,
    tool: async (message, data, session) => {
      const specialist = await FIND_SPECIALIST(data.service);
      const availability = await CHECK_DOCTOR_AVAILABILITY(specialist.specialist);
      session.collected.specialist = specialist.specialist;
      session.collected.available_slots = availability.slots;
      return { nextStepId: 'offer_slots' };
    },
    next: null,
  },
  {
    id: 'offer_slots',
    prompt: (session) => {
      const slots = session.collected.available_slots || [];
      return `Подобрала врача: ${session.collected.specialist}.\nСвободные слоты:\n${formatSlots(
        slots,
      )}\nВыберите, пожалуйста, номер удобного времени.`;
    },
    field: 'selected_slot',
    next: 'appointment_confirm',
  },
  {
    id: 'appointment_confirm',
    prompt: (session) => {
      const slots = session.collected.available_slots || [];
      const slot = slots[Number.parseInt(session.collected.selected_slot, 10) - 1];
      session.collected.selected_slot_details = slot || null;

      const slotText = slot
        ? new Date(slot.start).toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })
        : 'не выбран';

      return `Проверим запись.\nИмя: ${session.collected.name}.\nВрач: ${session.collected.specialist}.\nДата и время: ${slotText}.\nВсе верно?`;
    },
    field: 'appointment_confirmation',
    next: (message, data) => {
      if (!data.selected_slot_details) {
        return 'offer_slots';
      }

      return normalize(message).startsWith('да') ? 'create_appointment' : 'offer_slots';
    },
  },
  {
    id: 'create_appointment',
    autoRun: true,
    tool: async (message, data) => {
      const appointment = await CREATE_APPOINTMENT({
        patientName: data.name,
        phone: data.phone,
        birthdate: data.birthdate,
        service: data.service,
        specialist: data.specialist,
        slot: data.selected_slot_details,
      });

      const confirmation = await CONFIRM_APPOINTMENT(appointment);
      return {
        nextStepId: 'appointment_done',
        appointmentId: appointment.appointmentId,
        confirmationCode: confirmation.confirmationCode,
      };
    },
    next: null,
  },
  {
    id: 'appointment_done',
    prompt: 'Запись подтверждена. Спасибо, мы будем ждать вас в клинике.',
    terminal: true,
    next: null,
  },
  {
    id: 'reschedule_name',
    prompt: 'Подскажите, пожалуйста, имя пациента.',
    field: 'name',
    next: 'reschedule_phone',
  },
  {
    id: 'reschedule_phone',
    prompt: 'Назовите номер телефона, на который оформлена запись.',
    field: 'phone',
    next: 'reschedule_current_date',
  },
  {
    id: 'reschedule_current_date',
    prompt: 'На какую дату и время у вас сейчас запись?',
    field: 'current_appointment',
    next: 'reschedule_service',
  },
  {
    id: 'reschedule_service',
    prompt: 'Какая услуга была запланирована?',
    field: 'service',
    next: 'reschedule_find_slots',
  },
  {
    id: 'reschedule_find_slots',
    autoRun: true,
    tool: async (message, data, session) => {
      const specialist = await FIND_SPECIALIST(data.service);
      const availability = await CHECK_DOCTOR_AVAILABILITY(specialist.specialist);
      session.collected.specialist = specialist.specialist;
      session.collected.available_slots = availability.slots;
      return { nextStepId: 'reschedule_offer_slots' };
    },
    next: null,
  },
  {
    id: 'reschedule_offer_slots',
    prompt: (session) =>
      `Подобрала новые слоты:\n${formatSlots(
        session.collected.available_slots || [],
      )}\nВыберите номер подходящего времени.`,
    field: 'selected_slot',
    next: 'reschedule_confirm',
  },
  {
    id: 'reschedule_confirm',
    prompt: (session) => {
      const slots = session.collected.available_slots || [];
      const slot = slots[Number.parseInt(session.collected.selected_slot, 10) - 1];
      session.collected.selected_slot_details = slot || null;
      const slotText = slot
        ? new Date(slot.start).toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })
        : 'не выбран';
      return `Переносим запись на ${slotText}. Все верно?`;
    },
    field: 'reschedule_confirmation',
    next: (message, data) => {
      if (!data.selected_slot_details) {
        return 'reschedule_offer_slots';
      }

      return normalize(message).startsWith('да') ? 'reschedule_done' : 'reschedule_offer_slots';
    },
  },
  {
    id: 'reschedule_done',
    prompt: 'Запись перенесена. Подтверждение будет отправлено по указанному номеру телефона.',
    terminal: true,
    next: null,
  },
  {
    id: 'cancel_name',
    prompt: 'Подскажите, пожалуйста, имя пациента.',
    field: 'name',
    next: 'cancel_phone',
  },
  {
    id: 'cancel_phone',
    prompt: 'Назовите номер телефона, на который оформлена запись.',
    field: 'phone',
    next: 'cancel_date',
  },
  {
    id: 'cancel_date',
    prompt: 'Уточните дату и время записи, которую нужно отменить.',
    field: 'current_appointment',
    next: 'cancel_confirm',
  },
  {
    id: 'cancel_confirm',
    prompt: 'Подтверждаете отмену записи?',
    field: 'cancel_confirmation',
    next: (message) => (normalize(message).startsWith('да') ? 'cancel_done' : 'cancel_keep'),
  },
  {
    id: 'cancel_keep',
    prompt: 'Хорошо, запись остается без изменений.',
    terminal: true,
    next: null,
  },
  {
    id: 'cancel_done',
    prompt: 'Запись отменена. Если понадобится, я помогу оформить новую.',
    terminal: true,
    next: null,
  },
  {
    id: 'faq_price',
    autoRun: true,
    tool: async (message, data, session) => {
      const result = await GET_PRICE_LIST();
      session.collected.price_list = result.prices;
      return null;
    },
    prompt: (session) => {
      const prices = session.collected.price_list;
      return `По основным услугам ориентир такой:\nКонсультация — ${prices.консультация}\nЧистка — ${prices.чистка}\nЛечение — ${prices.лечение}\nУдаление — ${prices.удаление}\nИмплантация — ${prices.имплантация}\nОртодонтия — ${prices.ортодонтия}`;
    },
    terminal: true,
    next: null,
  },
  {
    id: 'faq_info',
    autoRun: true,
    tool: async (message, data, session) => {
      session.collected.clinic_info = await GET_CLINIC_INFO();
      return null;
    },
    prompt: (session) => {
      const info = session.collected.clinic_info;
      return `Мы находимся по адресу: ${info.address}. График работы: ${info.workingHours}. Телефон клиники: ${info.phone}.`;
    },
    terminal: true,
    next: null,
  },
  {
    id: 'faq_preparation_service',
    prompt: 'Подскажите, к какой процедуре нужна подготовка?',
    field: 'service',
    next: 'faq_preparation',
  },
  {
    id: 'faq_preparation',
    autoRun: true,
    tool: async (message, data, session) => {
      session.collected.preparation = await GET_PREPARATION_RULES(data.service);
      return null;
    },
    prompt: (session) => session.collected.preparation.rules,
    terminal: true,
    next: null,
  },
  {
    id: 'transfer_doctor',
    autoRun: true,
    tool: async () => TRANSFER_TO_DOCTOR(),
    prompt: 'Чтобы не ошибиться, я переведу ваш вопрос на врача.',
    next: null,
  },
];
