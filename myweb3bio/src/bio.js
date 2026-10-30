const BIO = {
  name: 'Калдин Лев',
  fullName: 'Калдин Лев Владимирович',
  tagline: 'Python / AI Automation Engineer',
  age: 22,
  birthday: '5 апреля 2004',
  location: 'Казань, Россия',
  relocate: 'Зеленодольск, Москва · Готов к командировкам',
  salary: '60 000 ₽ на руки',
  experience: '2 года 9 месяцев',

  description:
    'Python Automation Engineer. Автоматизирую бизнес-процессы, обрабатываю данные и большие ' +
    'табличные выгрузки, разрабатываю Telegram-ботов, AI-агентов и внутренние инструменты. ' +
    'Работаю с Excel, Google Sheets, 1С, pandas, интерактивными картами и AI-automation. ' +
    'Практический опыт разработки решений для бизнеса на стыке Python, автоматизации, аналитики и бизнес-процессов.',

  education: {
    degree: 'Бакалавр',
    year: 2025,
    university: 'КНИТУ-КАИ им. А.Н. Туполева',
    faculty: 'ФМФ, Наноинженерия',
    city: 'Казань',
  },

  contacts: {
    phone: '+7 (965) 6066455',
    email: 'koalla.335@mail.ru',
    telegram: '@qwesade',
    telegramLink: 'https://t.me/qwesade',
  },

  links: {
    telegram: 'https://t.me/qwesade',
    email: 'mailto:koalla.335@mail.ru',
  },

  wallet: {
    address: '',
    label: 'EVM',
  },

  skills: [
    'Python', 'FastAPI', 'Telegram Bot API', 'AI Automation',
    'pandas', 'Google API', 'Excel', 'Google Sheets', '1С',
    'Ollama', 'LLM', 'HuggingFace', 'Folium', 'Geocoder',
    'JSON', 'CSV', 'Pytest', 'Backend', 'Data Processing',
  ],

  languages: [
    { lang: 'Русский', level: 'Родной' },
    { lang: 'Английский', level: 'B1 — Средний' },
  ],

  workExperience: [
    {
      period: 'Май 2025 — настоящее время',
      duration: '1 год 2 месяца',
      company: 'Фриланс',
      industry: 'Проекты',
      position: 'Python / AI Automation Engineer',
      description:
        'Разработка AI-агентов, Telegram/web-сервисов, backend automation решений и внутренних платформ для бизнеса.',
      tasks: [
        'Автоматизация бизнес-процессов',
        'Обработка больших табличных выгрузок',
        'Интеграции с Telegram, Google Sheets, Gmail, Google Calendar и 1С',
        'Разработка AI-agent систем',
        'Automation и internal tools',
        'Геосервисы и geolocation решения',
      ],
    },
    {
      period: 'Август 2024 — Май 2025',
      duration: '10 месяцев',
      company: 'АО "ЗВКС"',
      industry: 'ЖКХ · Водоснабжение и канализация',
      position: 'Диспетчер',
      description: 'Приём и обработка обращений, организация рабочих коммуникаций, ведение заявок.',
      tasks: [
        'Разработал Telegram-бота для приёма обращений с фото и геолокацией',
        'Организовал 5 рабочих чатов и систему статусов с автоответом',
        'Построил интерактивную тепловую карту обращений на Python + Folium',
        'Автоматизировал отчётность: с 10–12 часов до 10–15 минут',
        'Работал при нагрузке до 100 звонков/день',
      ],
    },
    {
      period: 'Август 2023 — Май 2024',
      duration: '10 месяцев',
      company: 'МЦ «Мир здоровья»',
      industry: 'Медицина',
      position: 'Помощник бухгалтера',
      description:
        'Анализ данных для расчёта зарплаты (3 филиала), работа с 1С, контроль первичных документов.',
      tasks: [],
    },
  ],

  projects: [
    {
      name: 'TMC Planner',
      description: 'Система выравнивания планов поставок. Обработка 65 000 строк, 6 700 контрагентов, 50+ SKU. Перерасчёт базы за ~1 минуту.',
      tags: ['Python', 'pandas', 'Excel', 'Google Sheets', '1С'],
    },
    {
      name: 'Open Claw Agent',
      description: 'AI-agent платформа для remote управления Windows через Telegram и web. Multimodal UI-анализ, интеграции с Gmail, Calendar, Sheets.',
      tags: ['Python', 'Telegram Bot API', 'Ollama', 'Mistral 7B', 'Google APIs'],
    },
    {
      name: 'Logistics',
      description: 'Telegram-first marketplace для перевозчиков. Geocoding, подписки, платежи, админ-панель, верификация.',
      tags: ['Python', 'Telegram Bot API', 'Geolocation', 'Backend'],
    },
    {
      name: 'Telegram-боты и automation',
      description: 'Боты для бизнеса, экскурсий, внутренних процессов. Сбор контактов, заявок, фото, геолокации. Автоматизация workflow.',
      tags: ['Python', 'Telegram Bot API', 'Automation'],
    },
  ],
};

export default BIO;
