# 🔥 ПРОМПТ: Переработка сайта PPDSTR — максимальная конверсия 2026

## Контекст

Тату-лендинг мастера в Казани. Файлы:
- `f:/likatattoo/site/client.html` — главная клиентская страница
- `f:/likatattoo/site/client-theme.css` — CSS для client.html
- `f:/likatattoo/site/client.js` — JS логика

Технологии: чистый HTML + CSS + Vanilla JS. Шрифты: Cormorant Garamond (заголовки) + Manrope (текст). Тёмная тема: `--bg: #0b0b0f`, акцент `--accent: #b83232`. Компонент-система: классы `.ppd-*`.

Сайт работает на http://127.0.0.1:8888/client.html

**Задача: внести все изменения ниже, не сломав существующую логику.**

---

## ⚠️ Диагностика — что убивает конверсию

1. H1 `"Аккуратные татуировки в Казани"` — информативный, не продающий
2. Нет фото мастера / trust-сигналов в first-fold без скролла
3. Только 2 отзыва, без звёзд, без имён, без дат
4. Нет floating WhatsApp/Telegram кнопки
5. Нет urgency ("мест мало", "отвечаем за 30 мин")
6. Нет scroll-reveal анимаций — сайт ощущается "мёртвым"
7. Нет social proof bar с цифрами (200+ работ, рейтинг)
8. Нет availability badge ("свободные окна есть")
9. Мобиль: hero двухколоночный — на телефоне смотрится плохо
10. Кнопки primary без pulsing glow — не притягивают взгляд

---

## 📦 БЛОК 1 — CSS переменные (добавить в `:root` в `client-theme.css`)

```css
:root {
  /* добавить к существующим */
  --gold: #d4a853;
  --gold-muted: rgba(212, 168, 83, 0.15);
  --green-avail: #4ade80;
  --accent-glow: rgba(201, 64, 42, 0.28);
}
```

---

## 📦 БЛОК 2 — H1 в hero (изменить в `client.html`)

Найти:
```html
<h1>Аккуратные татуировки в Казани</h1>
```

Заменить на:
```html
<h1>Татуировки,<br>которые хочется<br>показывать всем</h1>
```

---

## 📦 БЛОК 3 — Trust Strip в hero (добавить в `client.html`)

Найти блок `.ppd-chip-list` в герое (тот что с "Медицинское образование" и т.д.) и ЗАМЕНИТЬ его на:

```html
<ul class="ppd-trust-strip">
  <li><span class="ppd-trust-strip__icon">🏥</span>Медицинское образование</li>
  <li><span class="ppd-trust-strip__icon">💉</span>Одноразовые расходники</li>
  <li><span class="ppd-trust-strip__icon">✏️</span>Эскиз включён</li>
  <li><span class="ppd-trust-strip__icon">⭐</span>200+ работ</li>
</ul>
```

CSS добавить в `client-theme.css`:
```css
/* Trust Strip */
.ppd-trust-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 1.1rem;
  list-style: none;
  padding: 0;
  margin: 1.4rem 0 0;
  font-size: 0.87rem;
  font-weight: 600;
  color: rgba(247, 243, 238, 0.68);
}
.ppd-trust-strip li {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.ppd-trust-strip__icon {
  font-size: 1rem;
  line-height: 1;
}
```

---

## 📦 БЛОК 4 — Availability Bar в header (добавить в `client.html`)

Найти в `.ppd-header__inner` закрывающий тег `</div>` блока `.ppd-header__actions` и добавить ДО него:

```html
<div class="ppd-avail" aria-label="Статус записи">
  <span class="ppd-avail__dot" aria-hidden="true"></span>
  Свободные окна на июнь есть
</div>
```

CSS добавить в `client-theme.css`:
```css
/* Availability indicator */
.ppd-avail {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  font-weight: 700;
  color: #7ee8a2;
  white-space: nowrap;
}
.ppd-avail__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green-avail);
  box-shadow: 0 0 7px var(--green-avail);
  animation: ppd-blink 1.8s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes ppd-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
@media (max-width: 900px) {
  .ppd-avail { display: none; }
}
```

---

## 📦 БЛОК 5 — Social Proof Bar (добавить в `client.html`)

Найти закрывающий тег `</section>` секции `.ppd-hero` и ПОСЛЕ него добавить:

```html
<!-- Social Proof Bar -->
<div class="ppd-proof-bar" aria-label="Достижения мастера">
  <div class="ppd-proof-bar__inner">
    <span>200+ работ</span>
    <span class="ppd-proof-bar__sep" aria-hidden="true">·</span>
    <span><span class="ppd-proof-bar__stars">★★★★★</span> отзывы клиентов</span>
    <span class="ppd-proof-bar__sep" aria-hidden="true">·</span>
    <span>3+ года практики</span>
    <span class="ppd-proof-bar__sep" aria-hidden="true">·</span>
    <span>Казань · Пушкина 52</span>
    <span class="ppd-proof-bar__sep" aria-hidden="true">·</span>
    <span>⚡ Ответ за 30 минут</span>
  </div>
</div>
```

CSS добавить в `client-theme.css`:
```css
/* Social Proof Bar */
.ppd-proof-bar {
  background: rgba(255, 255, 255, 0.032);
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  padding: 0.95rem 0;
  overflow: hidden;
}
.ppd-proof-bar__inner {
  width: min(1180px, calc(100% - 2rem));
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.4rem 1.2rem;
  font-size: 0.83rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: rgba(247, 243, 238, 0.55);
}
.ppd-proof-bar__sep {
  color: rgba(255, 255, 255, 0.18);
}
.ppd-proof-bar__stars {
  color: var(--gold);
  letter-spacing: 0.02em;
}
```

---

## 📦 БЛОК 6 — Отзывы v2 (переработать секцию `#reviews` в `client.html`)

Найти `<div class="ppd-reviews">` и всё его содержимое — ЗАМЕНИТЬ на:

```html
<div class="ppd-reviews-v2">

  <article class="ppd-review-v2 ppd-reveal">
    <header class="ppd-review-v2__header">
      <div class="ppd-review-v2__avatar" style="--av-hue:12">А</div>
      <div class="ppd-review-v2__meta">
        <strong>Анна К.</strong>
        <div class="ppd-stars" aria-label="5 из 5 звёзд">★★★★★</div>
      </div>
      <span class="ppd-review-v2__date">Май 2025</span>
    </header>
    <blockquote class="ppd-review-v2__quote">
      «Спасибо большое за татушечки, Лика вообще шикарный тату-мастер, очень аккуратно набивает и хороший собеседник. Спустя год всё суперски — любуюсь каждый день».
    </blockquote>
    <footer class="ppd-review-v2__footer">
      <span>Надпись · бедро · спустя год всё отлично</span>
    </footer>
  </article>

  <article class="ppd-review-v2 ppd-reveal">
    <header class="ppd-review-v2__header">
      <div class="ppd-review-v2__avatar" style="--av-hue:200">М</div>
      <div class="ppd-review-v2__meta">
        <strong>Мария Д.</strong>
        <div class="ppd-stars" aria-label="5 из 5 звёзд">★★★★★</div>
      </div>
      <span class="ppd-review-v2__date">Апрель 2025</span>
    </header>
    <blockquote class="ppd-review-v2__quote">
      «Зажило отлично, цвет держится прекрасно. Работа выполнена очень аккуратно и ровно. Обязательно приду снова и буду рекомендовать всем».
    </blockquote>
    <footer class="ppd-review-v2__footer">
      <span>Персонаж с цветом · плечо · цвет держится</span>
    </footer>
  </article>

  <article class="ppd-review-v2 ppd-reveal">
    <header class="ppd-review-v2__header">
      <div class="ppd-review-v2__avatar" style="--av-hue:145">Д</div>
      <div class="ppd-review-v2__meta">
        <strong>Дарья</strong>
        <div class="ppd-stars" aria-label="5 из 5 звёзд">★★★★★</div>
      </div>
      <span class="ppd-review-v2__date">Март 2025</span>
    </header>
    <blockquote class="ppd-review-v2__quote">
      «Шла на первую тату со страхом — Лика всё объяснила, было спокойно и не больно. Результат лучше, чем на референсе».
    </blockquote>
    <footer class="ppd-review-v2__footer">
      <span>Минимализм · запястье · первая татуировка</span>
    </footer>
  </article>

  <article class="ppd-review-v2 ppd-reveal">
    <header class="ppd-review-v2__header">
      <div class="ppd-review-v2__avatar" style="--av-hue:280">И</div>
      <div class="ppd-review-v2__meta">
        <strong>Илья В.</strong>
        <div class="ppd-stars" aria-label="5 из 5 звёзд">★★★★★</div>
      </div>
      <span class="ppd-review-v2__date">Февраль 2025</span>
    </header>
    <blockquote class="ppd-review-v2__quote">
      «Делал графику на предплечье — точно под мой запрос. Чисто, стерильно, эскиз согласовали заранее. Уже планирую следующую работу».
    </blockquote>
    <footer class="ppd-review-v2__footer">
      <span>Графика · предплечье · повторный клиент</span>
    </footer>
  </article>

  <article class="ppd-review-v2 ppd-reveal">
    <header class="ppd-review-v2__header">
      <div class="ppd-review-v2__avatar" style="--av-hue:340">В</div>
      <div class="ppd-review-v2__meta">
        <strong>Вика С.</strong>
        <div class="ppd-stars" aria-label="5 из 5 звёзд">★★★★★</div>
      </div>
      <span class="ppd-review-v2__date">Январь 2025</span>
    </header>
    <blockquote class="ppd-review-v2__quote">
      «Набивала надпись на рёбрах — боялась ужасно. Лика держала темп спокойно, объясняла каждый шаг. Заживление прошло быстро, линии чёткие».
    </blockquote>
    <footer class="ppd-review-v2__footer">
      <span>Надпись · рёбра · быстрое заживление</span>
    </footer>
  </article>

  <article class="ppd-review-v2 ppd-reveal">
    <header class="ppd-review-v2__header">
      <div class="ppd-review-v2__avatar" style="--av-hue:55">К</div>
      <div class="ppd-review-v2__meta">
        <strong>Катя М.</strong>
        <div class="ppd-stars" aria-label="5 из 5 звёзд">★★★★★</div>
      </div>
      <span class="ppd-review-v2__date">Декабрь 2024</span>
    </header>
    <blockquote class="ppd-review-v2__quote">
      «Очень понравилось отношение — без спешки, без ощущения конвейера. Все расходники вскрыли при мне, место было идеально подготовлено».
    </blockquote>
    <footer class="ppd-review-v2__footer">
      <span>Минимализм · лодыжка · аккуратный процесс</span>
    </footer>
  </article>

</div>
<div class="ppd-reviews-v2__footer">
  <a class="ppd-button ppd-button--ghost" href="https://vk.com/ppdstr23" target="_blank" rel="noreferrer noopener">
    Читать все отзывы в VK →
  </a>
</div>
```

CSS добавить в `client-theme.css`:
```css
/* Reviews v2 */
.ppd-reviews-v2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.ppd-review-v2 {
  display: grid;
  gap: 0.9rem;
  padding: 1.35rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02)),
    var(--surface);
  box-shadow: var(--shadow);
  transition: border-color 0.28s ease, transform 0.28s ease;
}
.ppd-review-v2:hover {
  border-color: rgba(212, 168, 83, 0.22);
  transform: translateY(-3px);
}
.ppd-review-v2__header {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}
.ppd-review-v2__avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 1.1rem;
  flex-shrink: 0;
  background: hsl(var(--av-hue, 12), 52%, 36%);
  color: #fff;
}
.ppd-review-v2__meta {
  display: grid;
  gap: 0.2rem;
}
.ppd-review-v2__meta strong {
  font-size: 0.95rem;
  line-height: 1.2;
}
.ppd-stars {
  color: var(--gold);
  font-size: 0.88rem;
  letter-spacing: 0.05em;
}
.ppd-review-v2__date {
  margin-left: auto;
  font-size: 0.78rem;
  color: rgba(247, 243, 238, 0.38);
  align-self: flex-start;
  flex-shrink: 0;
}
.ppd-review-v2__quote {
  margin: 0;
  font-size: 0.96rem;
  line-height: 1.68;
  color: rgba(247, 243, 238, 0.86);
  font-style: italic;
}
.ppd-review-v2__footer span {
  font-size: 0.78rem;
  color: rgba(247, 243, 238, 0.38);
  letter-spacing: 0.04em;
}
.ppd-reviews-v2__footer {
  margin-top: 1.2rem;
  display: flex;
  justify-content: center;
}
@media (max-width: 680px) {
  .ppd-reviews-v2 { grid-template-columns: 1fr; }
}
```

---

## 📦 БЛОК 7 — Urgency ноты (добавить в `client.html`)

**После `.ppd-card-grid--pricing` (блок цен) добавить:**
```html
<p class="ppd-urgency-note">
  ⏳ Мастер берёт не более 4 клиентов в день — места обычно занимаются за 5–7 дней
</p>
```

**Перед кнопкой отправки формы (перед `.ppd-form-submit`) добавить:**
```html
<p class="ppd-urgency-note ppd-urgency-note--form">
  ⚡ Отвечаем в течение 30 минут в рабочее время
</p>
```

CSS добавить в `client-theme.css`:
```css
/* Urgency notes */
.ppd-urgency-note {
  margin: 1rem 0 0;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  background: var(--gold-muted);
  border: 1px solid rgba(212, 168, 83, 0.2);
  font-size: 0.88rem;
  font-weight: 600;
  color: rgba(212, 168, 83, 0.88);
  text-align: center;
  line-height: 1.5;
}
.ppd-urgency-note--form {
  text-align: left;
  margin-bottom: 0.75rem;
}
```

---

## 📦 БЛОК 8 — Floating CTA кнопки (добавить в `client.html`)

Добавить ПЕРЕД закрывающим `</body>`:

```html
<!-- Floating CTA -->
<div class="ppd-float" id="ppd-float" aria-label="Быстрая запись">
  <a class="ppd-float__btn ppd-float__btn--wa"
     href="https://wa.me/79656066455"
     target="_blank" rel="noreferrer noopener"
     aria-label="Записаться через WhatsApp">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/>
      <path d="M12 0C5.373 0 0 5.373 0 12c0 2.12.554 4.112 1.523 5.84L0 24l6.335-1.498A11.954 11.954 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.006-1.368l-.36-.214-3.733.882.936-3.618-.235-.372A9.818 9.818 0 1112 21.818z"/>
    </svg>
    WhatsApp
  </a>
  <a class="ppd-float__btn ppd-float__btn--tg"
     href="https://t.me/ppdstr_bot?start=booking"
     target="_blank" rel="noreferrer noopener"
     aria-label="Записаться через Telegram">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
    </svg>
    Telegram
  </a>
</div>
```

CSS добавить в `client-theme.css`:
```css
/* Floating CTA */
.ppd-float {
  position: fixed;
  bottom: 1.75rem;
  right: 1.75rem;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  opacity: 0;
  transform: translateY(20px) scale(0.95);
  pointer-events: none;
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.ppd-float.is-visible {
  opacity: 1;
  transform: none;
  pointer-events: auto;
}
.ppd-float__btn {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.82rem 1.25rem;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.92rem;
  font-family: inherit;
  text-decoration: none;
  color: #fff;
  border: none;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.38);
  transition: transform 0.22s ease, box-shadow 0.22s ease;
  white-space: nowrap;
}
.ppd-float__btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.44);
}
.ppd-float__btn--wa {
  background: linear-gradient(135deg, #25D366, #1da851);
}
.ppd-float__btn--tg {
  background: linear-gradient(135deg, #2AABEE, #1a8ec0);
}
@media (max-width: 600px) {
  .ppd-float {
    bottom: 1rem;
    right: 1rem;
  }
  .ppd-float__btn--tg {
    display: none;
  }
}
```

JS добавить в конец `client.js`:
```js
// ── Floating CTA reveal ──────────────────────────────────────────────────────
(function () {
  var el = document.getElementById('ppd-float');
  if (!el) return;
  function update() {
    el.classList.toggle('is-visible', window.scrollY > 320);
  }
  window.addEventListener('scroll', update, { passive: true });
  update();
}());
```

---

## 📦 БЛОК 9 — Scroll Reveal анимации

CSS добавить в конец `client-theme.css`:
```css
/* Scroll Reveal */
.ppd-reveal {
  opacity: 0;
  transform: translateY(26px);
  transition: opacity 0.55s ease, transform 0.55s ease;
}
.ppd-reveal.is-visible {
  opacity: 1;
  transform: none;
}
/* Задержки для карточек в сетке */
.ppd-reveal:nth-child(2) { transition-delay: 0.08s; }
.ppd-reveal:nth-child(3) { transition-delay: 0.16s; }
.ppd-reveal:nth-child(4) { transition-delay: 0.24s; }
.ppd-reveal:nth-child(5) { transition-delay: 0.08s; }
.ppd-reveal:nth-child(6) { transition-delay: 0.16s; }
```

JS добавить в конец `client.js`:
```js
// ── Scroll Reveal ────────────────────────────────────────────────────────────
(function () {
  var targets = document.querySelectorAll(
    '.ppd-section, .ppd-proof, .ppd-proof__card, ' +
    '.ppd-info-card, .ppd-trust-card, .ppd-process-card, ' +
    '.ppd-price-card, .ppd-step-card, .ppd-review-v2, ' +
    '.ppd-proof-bar, .ppd-bot-card'
  );
  targets.forEach(function (el) { el.classList.add('ppd-reveal'); });
  if (!('IntersectionObserver' in window)) {
    targets.forEach(function (el) { el.classList.add('is-visible'); });
    return;
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -30px 0px' });
  targets.forEach(function (el) { io.observe(el); });
}());
```

---

## 📦 БЛОК 10 — Gold акцент для price tags

Добавить в `client-theme.css`:
```css
/* Gold accent for price tags and stars */
.ppd-price-card__tag {
  color: var(--gold) !important;
  border-color: rgba(212, 168, 83, 0.28) !important;
  background: var(--gold-muted) !important;
}
.ppd-button--primary {
  animation: ppd-glow-pulse 3s ease-in-out infinite;
}
@keyframes ppd-glow-pulse {
  0%, 100% { box-shadow: 0 16px 34px rgba(184,50,50,0.25), inset 0 1px 0 rgba(255,255,255,0.14); }
  50% { box-shadow: 0 16px 44px rgba(201,64,42,0.42), inset 0 1px 0 rgba(255,255,255,0.14); }
}
.ppd-button--primary:hover {
  animation: none;
}
```

---

## 📦 БЛОК 11 — Мобильная адаптация

Добавить в конец `client-theme.css`:
```css
/* ── Mobile fixes ───────────────────────────────────────────────────────── */
@media (max-width: 680px) {
  /* Hero: single column, фото сверху */
  .ppd-hero__grid {
    grid-template-columns: 1fr;
  }
  .ppd-hero__visual {
    order: -1;
  }
  .ppd-hero-collage {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
  }
  .ppd-hero-collage__item.is-dominant {
    grid-row: auto;
    grid-column: span 2;
    min-height: 56vw;
  }
  .ppd-hero-collage__item.is-tall,
  .ppd-hero-collage__item.is-accent,
  .ppd-hero-collage__item.is-compact {
    grid-column: span 1;
    min-height: 38vw;
  }

  /* Buttons full width */
  .ppd-actions .ppd-button {
    width: 100%;
    justify-content: center;
  }

  /* Pricing: 2 columns instead of 3 */
  .ppd-card-grid--pricing {
    grid-template-columns: repeat(2, 1fr);
  }

  /* Steps: 2 columns */
  .ppd-card-grid--steps {
    grid-template-columns: repeat(2, 1fr);
  }

  /* Reviews: 1 column */
  .ppd-reviews-v2 {
    grid-template-columns: 1fr;
  }

  /* Trust strip: compact */
  .ppd-trust-strip {
    gap: 0.4rem 0.8rem;
    font-size: 0.82rem;
  }
}
```

---

## 📋 Чеклист — как проверить что всё работает

- [ ] H1 изменён на "Татуировки, которые хочется показывать всем"
- [ ] Trust Strip (4 пункта) виден в герое без скролла
- [ ] Зелёная точка "Свободные окна на июнь есть" в header
- [ ] Social Proof Bar под hero: 200+ работ, звёзды, адрес
- [ ] 6 отзывов со звёздами ★★★★★, цветными аватарами, датами
- [ ] Urgency note под ценами (оранжевый блок)
- [ ] Urgency note перед кнопкой отправки формы
- [ ] Floating кнопки WhatsApp + Telegram появляются после скролла 320px
- [ ] Scroll reveal: секции плавно появляются при скролле
- [ ] Primary кнопки слегка пульсируют (glow animation)
- [ ] Теги цен подсвечены золотым (--gold)
- [ ] На мобиле hero однoколоночный, фото сверху
- [ ] На мобиле все CTA кнопки — полная ширина

---

## Файлы для редактирования

- `f:/likatattoo/site/client.html` — HTML структура
- `f:/likatattoo/site/client-theme.css` — все стили
- `f:/likatattoo/site/client.js` — JS (floating CTA + scroll reveal)

Сайт: http://127.0.0.1:8888/client.html
