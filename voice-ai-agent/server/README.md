# Voice AI Operator Backend

Backend с четырьмя сценариями voice-агентов:

- `AI SDR` для B2B-квалификации и назначения встреч
- `Dental Admin` для записи в стоматологию
- `SaaS Support L1` для первой линии техподдержки
- `Delivery Operator` для доставки ресторана

## Запуск

```bash
npm install
npm run dev
```

Сервер поднимается на `http://localhost:4000`.

## API

- `POST /api/sdr/start`
- `POST /api/sdr/message`
- `POST /api/dentist/start`
- `POST /api/dentist/message`
- `POST /api/support/start`
- `POST /api/support/message`
- `POST /api/delivery/start`
- `POST /api/delivery/message`

Формат сообщения:

```json
{
  "sessionId": "sdr_...",
  "message": "Текст пользователя"
}
```

## Что внутри

- `src/flows/` — сценарии диалогов
- `src/services/tools.js` — мок-инструменты внешних систем
- `src/utils/conversationEngine.js` — асинхронный движок состояний
- `src/prompts/systemPrompts.js` — production-ориентированные системные промпты

## Тесты

```bash
node test.js
```

Тест поднимает HTTP-сервер и проходит несколько end-to-end сценариев, включая:

- hot lead для SDR
- запись и FAQ для стоматологии
- resolved и escalated кейсы для поддержки
- успешный заказ и перевод на менеджера для доставки
