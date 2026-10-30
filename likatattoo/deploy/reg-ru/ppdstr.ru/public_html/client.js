(() => {
  const body = document.body;
  if (!body.classList.contains("client-page")) return;

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const money = new Intl.NumberFormat("ru-RU");

  const fallbackCategories = [
    { key: "all", label: "Все" },
    { key: "lettering", label: "Надписи" },
    { key: "minimal", label: "Минимализм" },
    { key: "graphic", label: "Графика" },
    { key: "color", label: "Цвет" },
    { key: "characters", label: "Персонажи" },
    { key: "healed", label: "Зажившие" },
    { key: "sketches", label: "Свободные эскизы" },
    { key: "first", label: "Первая татуировка" },
    { key: "process", label: "Процесс" },
  ];

  const fallbackPortfolio = {
    source: "local-fallback",
    categories: fallbackCategories,
    items: [],
    supporting: { hero: [], process: [], master: null, studio: null },
  };

  const fallbackConsumables = {
    source: "local-fallback",
    minimum_charge: 1600,
    rules: {
      sizeMultipliers: { xs: 0.9, s: 1, m: 1.14, l: 1.28, xl: 1.42 },
      complexityMultipliers: { basic: 0.95, medium: 1.05, high: 1.16, max: 1.3 },
      extraHourPrice: 220,
      colorStepPrice: 95,
    },
    styleEstimates: {
      lettering: { label: "Надпись", baseMin: 3500, baseMax: 6000 },
      minimal: { label: "Минимализм", baseMin: 3500, baseMax: 5500 },
      graphics: { label: "Графика", baseMin: 5000, baseMax: 8000 },
      color: { label: "Цвет", baseMin: 6000, baseMax: 10000 },
      cover: { label: "Перекрытие", baseMin: 7000, baseMax: 12000 },
    },
    items: [],
  };

  const placementMap = {
    wrist: { label: "Запястье", multiplier: 0.96 },
    forearm: { label: "Предплечье", multiplier: 1 },
    shoulder: { label: "Плечо", multiplier: 1.04 },
    thigh: { label: "Бедро", multiplier: 1.1 },
    rib: { label: "Ребра", multiplier: 1.16 },
    ankle: { label: "Голень / щиколотка", multiplier: 1.08 },
    back: { label: "Спина", multiplier: 1.22 },
    other: { label: "Другое место", multiplier: 1.06 },
  };

  const sizeMap = {
    xs: { label: "до 5 см", hours: 1.2 },
    s: { label: "5–10 см", hours: 1.8 },
    m: { label: "10–15 см", hours: 2.7 },
    l: { label: "15–20 см", hours: 3.8 },
    xl: { label: "20+ см", hours: 5.2 },
  };

  const colorMap = {
    mono: { label: "Черно-белая", multiplier: 1, pigments: 0 },
    accent: { label: "1 цветной акцент", multiplier: 1.05, pigments: 1 },
    duo: { label: "2–3 цвета", multiplier: 1.12, pigments: 3 },
    full: { label: "Плотный цвет", multiplier: 1.22, pigments: 5 },
  };

  const requestStyleMap = {
    lettering: "Надпись",
    minimal: "Минимализм",
    graphics: "Графика",
    color: "Цвет",
    characters: "Персонажи / аниме",
  };

  const complexityMap = {
    basic: "Базовая",
    medium: "Средняя",
    high: "Высокая",
    max: "Сложная композиция",
  };

  const hiddenWorkIds = new Set(["character-arm-01"]);
  const hiddenFilterKeys = new Set(["process"]);

  const materialGroupOrder = ["coworking", "needles", "pigment", "transfer", "setup"];

  const materialGroupLabels = {
    coworking: "Рабочее место в коворкинге",
    needles: "Картриджи / иглы",
    pigment: "Краска / пигмент",
    transfer: "Перенос эскиза",
    setup: "Подготовка, защита и уход",
  };

  const state = {
    page: body.dataset.page || "home",
    portfolio: fallbackPortfolio,
    consumables: fallbackConsumables,
    homeFilter: "all",
    worksFilter: "all",
    selectedWork: null,
    calc: null,
    requestDraft: "",
  };

  function formatMoney(value) {
    return `${money.format(Math.round(value))} ₽`;
  }

  function roundStep(value, step) {
    return Math.round(value / step) * step;
  }

  async function fetchJson(url, fallback) {
    if (!url) return fallback;
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(String(response.status));
      return await response.json();
    } catch (error) {
      return fallback;
    }
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      return false;
    }
  }

  function normalizePortfolio(raw) {
    const incomingCategories = Array.isArray(raw?.categories) && raw.categories.length ? raw.categories : fallbackCategories;
    const mergedCategories = [...incomingCategories];
    fallbackCategories.forEach((fallbackCategory) => {
      if (!mergedCategories.some((item) => item.key === fallbackCategory.key)) {
        mergedCategories.push(fallbackCategory);
      }
    });

    return {
      source: raw?.source || "local-fallback",
      categories: mergedCategories,
      items: Array.isArray(raw?.items) ? raw.items : [],
      supporting: raw?.supporting || { hero: [], process: [], master: null, studio: null },
    };
  }

  function categoryLabel(key) {
    const category = (state.portfolio.categories || []).find((item) => item.key === key);
    return category?.label || key;
  }

  function workSessions(item) {
    return item?.sessions || "1 сеанс";
  }

  function isFirstTattooFriendly(item) {
    const haystack = [
      item?.title || "",
      item?.description || "",
      ...(Array.isArray(item?.tags) ? item.tags : []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes("первая татуировка");
  }

  function portfolioItems() {
    const items = Array.isArray(state.portfolio.items) ? state.portfolio.items : [];
    return items.filter((item) => item.collection === "portfolio" && !hiddenWorkIds.has(item.id));
  }

  function materialGroupKey(item) {
    const group = String(item?.calc_group || "").toLowerCase();
    const name = String(item?.name || "").toLowerCase();
    const rowIndex = Number(item?.row_index || 0);

    if (!name) return null;
    if ([4, 16, 18, 26].includes(rowIndex)) return null;
    if (name.includes("ящик") || name.includes("держак") || name.includes("латексный коврик") || name.includes("обезбол")) return null;
    if (group === "coworking" || name.includes("коворкинг")) return "coworking";
    if (group === "needle" || name.includes("картридж") || name.includes("игл")) return "needles";
    if (group === "pigment" || name.includes("краска") || name.includes("пигмент")) return "pigment";
    if (group === "transfer" || name.includes("трансфер") || name.includes("печать эскиза")) return "transfer";
    return "setup";
  }

  function materialGroupDetail(key, context, qty) {
    switch (key) {
      case "coworking":
        return `ориентир по времени: ${Math.max(1, Math.ceil(qty))} ч`;
      case "needles":
        return `${Math.max(1, Math.round(qty))} картриджа под сеанс`;
      case "pigment":
        return context.color === "mono" ? "черный пигмент" : "с учетом цветовых акцентов";
      case "transfer":
        return "лист, гель и печать эскиза";
      case "setup":
        return "барьерка, перчатки, пленка и базовый уход";
      default:
        return "";
    }
  }

  function filterItems(items, filter) {
    if (filter === "all") return items;
    if (filter === "first") return items.filter(isFirstTattooFriendly);
    return items.filter((item) => item.category === filter);
  }

  function homeItems(filter) {
    const items = filterItems(portfolioItems(), filter);
    const curated = items.filter((item) => !item.auto_generated);
    return (curated.length ? curated : items).slice(0, 8);
  }

  function worksItems(filter) {
    return filterItems(portfolioItems(), filter);
  }

  function imageStyle(item) {
    return item?.object_position ? ` style="object-position:${item.object_position}"` : "";
  }

  function cardMarkup(item, options = {}) {
    const { index = 0, mode = "home" } = options;
    const featuredClass =
      item.featured && mode === "home" && index === 0
        ? " is-featured-primary"
        : item.featured && mode === "home" && index === 1
          ? " is-featured-secondary"
          : item.featured && index < 4
            ? " is-featured-tertiary"
            : "";

    return `
      <button class="ppd-work-card${featuredClass}" type="button" data-work-open="${item.id}" data-featured="${item.featured ? "true" : "false"}">
        <span class="ppd-work-card__media">
          <img src="${item.thumb || item.image}" alt="${item.alt || item.title}" loading="lazy"${imageStyle(item)} />
        </span>
        <span class="ppd-work-card__body">
          <span class="ppd-work-card__eyebrow">${item.category_label || categoryLabel(item.category)}</span>
          <strong>${item.title || "Работа"}</strong>
          <span class="ppd-work-card__meta">${item.size || "размер уточняется"} · ${item.place || "место уточняется"} · ${workSessions(item)}</span>
          <span class="ppd-work-card__price">${item.price || "Цена по согласованию"}</span>
          <span class="ppd-work-card__cta">Открыть работу</span>
        </span>
      </button>
    `;
  }

  function bindWorkOpeners(root, items) {
    qsa("[data-work-open]", root).forEach((button) => {
      button.addEventListener("click", () => {
        const work = items.find((item) => item.id === button.dataset.workOpen);
        if (work) openWorkModal(work);
      });
    });
  }

  function renderFilters(root, mode) {
    if (!root) return;
    const categories = state.portfolio.categories || fallbackCategories;
    const active = mode === "home" ? state.homeFilter : state.worksFilter;
    const visibleCategories = categories.filter((category) => !hiddenFilterKeys.has(category.key));

    root.innerHTML = "";
    visibleCategories.forEach((category) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `ppd-filter${category.key === active ? " is-active" : ""}`;
      button.textContent = category.label;
      button.addEventListener("click", () => {
        if (mode === "home") {
          state.homeFilter = category.key;
          renderHomePortfolio();
        } else {
          state.worksFilter = category.key;
          renderWorksPortfolio();
        }
      });
      root.append(button);
    });
  }

  function renderHomePortfolio() {
    const root = qs("[data-home-portfolio]");
    const filters = qs("[data-home-filters]");
    const count = qs("[data-home-portfolio-count]");
    if (!root || !filters) return;

    renderFilters(filters, "home");
    const items = homeItems(state.homeFilter);
    if (count) count.textContent = String(portfolioItems().length);

    if (!items.length) {
      root.innerHTML = `
        <article class="ppd-surface ppd-empty-state">
          <strong>В этой категории пока мало работ</strong>
          <p>Можно переключить фильтр или открыть всю галерею, где есть и процесс, и дополнительные карточки.</p>
        </article>
      `;
      return;
    }

    root.innerHTML = items.map((item, index) => cardMarkup(item, { index, mode: "home" })).join("");
    bindWorkOpeners(root, items);
  }

  function renderWorksPortfolio() {
    const root = qs("[data-works-portfolio]");
    const filters = qs("[data-works-filters]");
    const count = qs("[data-works-count]");
    if (!root || !filters) return;

    renderFilters(filters, "works");
    const items = worksItems(state.worksFilter);
    if (count) count.textContent = String(portfolioItems().length);

    if (!items.length) {
      root.innerHTML = `
        <article class="ppd-surface ppd-empty-state">
          <strong>В этой категории пока нет добавленных карточек</strong>
          <p>Фильтр уже подготовлен, так что новые работы можно спокойно добавлять позже без переделки страницы.</p>
        </article>
      `;
      return;
    }

    root.innerHTML = items.map((item, index) => cardMarkup(item, { index, mode: "works" })).join("");
    bindWorkOpeners(root, items);
  }

  function renderHeroCollage() {
    const root = qs(".ppd-hero-collage");
    if (!root) return;

    const heroItems = Array.isArray(state.portfolio.supporting?.hero)
      ? state.portfolio.supporting.hero.filter(Boolean).slice(0, 4)
      : [];

    if (!heroItems.length) return;

    const heroClasses = ["is-dominant", "is-tall", "is-accent", "is-compact"];
    root.innerHTML = heroItems
      .map(
        (item, index) => `
          <figure class="ppd-hero-collage__item ${heroClasses[index] || ""}">
            <img
              src="${item.image}"
              alt="${item.alt || item.title || "Работа PPDSTR"}"
              loading="${index < 2 ? "eager" : "lazy"}"
              ${index === 0 ? 'fetchpriority="high"' : ""}
              ${imageStyle(item)}
            />
          </figure>
        `
      )
      .join("");
  }

  function renderProcessGallery() {
    const root = qs("[data-process-gallery]");
    if (!root) return;
    const processItems = Array.isArray(state.portfolio.supporting?.process)
      ? state.portfolio.supporting.process.filter(Boolean)
      : [];
    const sessionVideo = body.dataset.processSessionVideo;
    const setupVideo = body.dataset.processSetupVideo || body.dataset.processVideo;
    const setupPoster = body.dataset.processPoster;
    const gallery = [];

    if (sessionVideo) {
      const sessionPoster = processItems[0]?.image || "";
      gallery.push(`
        <figure class="ppd-process-shot ppd-process-shot--video">
          <video muted loop playsinline autoplay preload="metadata" ${sessionPoster ? `poster="${sessionPoster}"` : ""}>
            <source src="${sessionVideo}" type="video/mp4" />
            <source src="${sessionVideo}" type="video/quicktime" />
          </video>
          <figcaption>
            <strong>Живой сеанс</strong>
            <span>Короткий фрагмент работы до финального результата.</span>
          </figcaption>
        </figure>
      `);
    } else if (processItems[0]) {
      gallery.push(`
        <figure class="ppd-process-shot">
          <img src="${processItems[0].image}" alt="${processItems[0].alt || processItems[0].title}" loading="lazy"${imageStyle(processItems[0])} />
        </figure>
      `);
    }

    if (setupVideo) {
      gallery.push(`
        <figure class="ppd-process-shot ppd-process-shot--video">
          <video muted loop playsinline autoplay preload="metadata" ${setupPoster ? `poster="${setupPoster}"` : ""}>
            <source src="${setupVideo}" type="video/mp4" />
            <source src="${setupVideo}" type="video/quicktime" />
          </video>
          <figcaption>
            <strong>Подготовка места</strong>
            <span>Рабочая зона готовится до начала сеанса.</span>
          </figcaption>
        </figure>
      `);
    } else if (processItems[1]) {
      gallery.push(`
        <figure class="ppd-process-shot">
          <img src="${processItems[1].image}" alt="${processItems[1].alt || processItems[1].title}" loading="lazy"${imageStyle(processItems[1])} />
        </figure>
      `);
    }

    if (!gallery.length) return;
    root.innerHTML = gallery.join("");
  }

  function renderMasterImage() {
    const image = qs("[data-master-image]");
    const master = state.portfolio.supporting?.master;
    if (!image || !master?.image) return;
    image.src = master.image;
    image.style.objectPosition = master.object_position || "";
    image.alt = master.alt || master.title || "Мастер PPDSTR";
  }

  function openWorkModal(item) {
    const dialog = qs("[data-work-modal]");
    if (!dialog) return;

    const image = qs("[data-modal-image]", dialog);
    const category = qs("[data-modal-category]", dialog);
    const title = qs("[data-modal-title]", dialog);
    const description = qs("[data-modal-description]", dialog);
    const size = qs("[data-modal-size]", dialog);
    const place = qs("[data-modal-place]", dialog);
    const sessions = qs("[data-modal-sessions]", dialog);
    const price = qs("[data-modal-price]", dialog);
    const tags = qs("[data-modal-tags]", dialog);

    state.selectedWork = item;
    updateRequestSummary();

    if (image) {
      image.src = item.image || item.thumb || "";
      image.alt = item.alt || item.title || "Работа PPDSTR";
    }
    if (category) category.textContent = item.category_label || categoryLabel(item.category);
    if (title) title.textContent = item.title || "Работа PPDSTR";
    if (description) description.textContent = item.description || "Подробности по этой работе можно обсудить в заявке.";
    if (size) size.textContent = item.size || "Уточняется";
    if (place) place.textContent = item.place || "Уточняется";
    if (sessions) sessions.textContent = workSessions(item);
    if (price) price.textContent = item.price || "По согласованию";
    if (tags) {
      const itemTags = Array.isArray(item.tags) ? item.tags : [];
      tags.innerHTML = itemTags.map((tag) => `<span>${tag}</span>`).join("");
    }

    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  function closeWorkModal() {
    const dialog = qs("[data-work-modal]");
    if (!dialog) return;
    if (typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
  }

  function storeSelectedWork(item) {
    if (!item) return;
    sessionStorage.setItem(
      "ppdstr:selected-work",
      JSON.stringify({
        id: item.id,
        title: item.title,
        price: item.price,
        category_label: item.category_label,
      })
    );
  }

  function restoreSelectedWork() {
    try {
      const raw = sessionStorage.getItem("ppdstr:selected-work");
      if (!raw) return;
      const saved = JSON.parse(raw);
      const item = portfolioItems().find((entry) => entry.id === saved.id);
      if (item) state.selectedWork = item;
    } catch (error) {
      return;
    }
  }

  function selectWorkFromModal() {
    if (!state.selectedWork) return;
    storeSelectedWork(state.selectedWork);
    closeWorkModal();

    if (state.page === "works") {
      window.location.href = "./client.html#request";
      return;
    }

    const idea = qs("[name='idea']", qs("[data-request-form]"));
    if (idea && !idea.value.trim()) {
      idea.value = `Хочу похожую работу на «${state.selectedWork.title}».`;
    }
    updateRequestSummary();
    qs("#request")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function bindModal() {
    const dialog = qs("[data-work-modal]");
    const close = qs("[data-close-modal]");
    const request = qs("[data-modal-request]");
    if (!dialog || !close || !request) return;

    close.addEventListener("click", closeWorkModal);
    request.addEventListener("click", selectWorkFromModal);

    dialog.addEventListener("click", (event) => {
      const rect = dialog.getBoundingClientRect();
      const inside =
        rect.top <= event.clientY &&
        event.clientY <= rect.bottom &&
        rect.left <= event.clientX &&
        event.clientX <= rect.right;
      if (!inside) closeWorkModal();
    });
  }

  function calcStyleKey(style) {
    if (style === "characters") return "color";
    return style;
  }

  function estimateHours(context) {
    const base = sizeMap[context.size]?.hours || 2;
    const styleExtra = { lettering: 0, minimal: 0, graphics: 0.2, color: 0.4, characters: 0.55 }[context.style] || 0;
    const complexityExtra = { basic: 0, medium: 0.2, high: 0.55, max: 0.9 }[context.complexity] || 0;
    const placementExtra = { wrist: 0, forearm: 0.05, shoulder: 0.1, thigh: 0.2, rib: 0.35, ankle: 0.15, back: 0.45, other: 0.15 }[context.placement] || 0;
    const colorExtra = { mono: 0, accent: 0.1, duo: 0.3, full: 0.55 }[context.color] || 0;
    const sketchAdjustment = context.hasSketch === "yes" ? -0.1 : 0.15;
    const total = Math.max(1.1, base + styleExtra + complexityExtra + placementExtra + colorExtra + sketchAdjustment);
    return Math.round(total * 10) / 10;
  }

  function itemQuantity(item, context, hours) {
    const group = String(item.calc_group || "").toLowerCase();
    const name = String(item.name || "").toLowerCase();
    const pigments = colorMap[context.color]?.pigments || 0;
    const baseQty = Number(item.base_qty || 1);

    if (group === "coworking" || name.includes("коворкинг")) return Math.max(1, Math.ceil(hours));
    if (group === "needle" || name.includes("картридж") || name.includes("игл")) {
      return 1 + (hours >= 3 ? 1 : 0) + (hours >= 4.5 ? 1 : 0);
    }
    if (group === "pigment" || name.includes("краск") || name.includes("пигмент")) {
      return Math.max(1, pigments || 1);
    }
    if (group === "gloves" || name.includes("перчат")) return Math.max(baseQty, Math.ceil(hours));
    if (group === "film" || name.includes("пленк")) return baseQty + (context.size === "l" || context.size === "xl" ? 1 : 0);
    if (group === "transfer" || name.includes("трансфер")) return 1;
    if (name.includes("пеленк")) return context.size === "xl" ? 2 : 1;
    if (name.includes("скотч") || name.includes("коврик")) return 1;
    return baseQty;
  }

  function currentCalcContext() {
    const form = qs("[data-calc-form]");
    if (!form) return null;
    const data = new FormData(form);
    return {
      style: String(data.get("style") || "lettering"),
      size: String(data.get("size") || "s"),
      placement: String(data.get("placement") || "forearm"),
      color: String(data.get("color") || "mono"),
      complexity: String(data.get("complexity") || "medium"),
      hasSketch: String(data.get("hasSketch") || "no"),
      comment: String(data.get("comment") || "").trim(),
      firstTattoo: data.get("firstTattoo") === "on",
    };
  }

  function calculateEstimate() {
    const context = currentCalcContext();
    if (!context) return null;

    const data = state.consumables || fallbackConsumables;
    const rules = data.rules || fallbackConsumables.rules;
    const styleKey = calcStyleKey(context.style);
    const styleEstimate = data.styleEstimates?.[styleKey] || fallbackConsumables.styleEstimates[styleKey] || fallbackConsumables.styleEstimates.lettering;
    const sizeMultiplier = Number(rules.sizeMultipliers?.[context.size] || 1);
    const complexityMultiplier = Number(rules.complexityMultipliers?.[context.complexity] || 1);
    const placementMultiplier = placementMap[context.placement]?.multiplier || 1;
    const colorMultiplier = colorMap[context.color]?.multiplier || 1;
    const sketchMultiplier = context.hasSketch === "yes" ? 0.98 : 1.03;
    const characterMultiplier = context.style === "characters" ? 1.08 : 1;
    const totalMultiplier = sizeMultiplier * complexityMultiplier * placementMultiplier * colorMultiplier * sketchMultiplier * characterMultiplier;
    const hours = estimateHours(context);
    const hoursLabel = hours < 2 ? "1–2 часа" : hours < 3.5 ? "2–3 часа" : hours < 5 ? "3–5 часов" : "5+ часов";

    const grouped = new Map();
    const items = Array.isArray(data.items) ? data.items : [];
    items.forEach((item) => {
      const groupKey = materialGroupKey(item);
      if (!groupKey) return;
      const qty = itemQuantity(item, context, hours);
      const total = qty * Number(item.unit_price || 0);
      const current = grouped.get(groupKey) || {
        key: groupKey,
        name: materialGroupLabels[groupKey] || item.name,
        qty: 0,
        total: 0,
      };
      current.qty += qty;
      current.total += total;
      grouped.set(groupKey, current);
    });

    const lines = materialGroupOrder
      .map((key) => {
        const line = grouped.get(key);
        if (!line || line.total <= 0) return null;
        return {
          ...line,
          detail: materialGroupDetail(key, context, line.qty),
        };
      })
      .filter(Boolean);

    const rawMaterials = lines.reduce((sum, line) => sum + line.total, 0);
    const materials = Math.max(Number(data.minimum_charge || fallbackConsumables.minimum_charge), roundStep(rawMaterials, 50));

    const min = roundStep(styleEstimate.baseMin * totalMultiplier + Math.max(0, hours - 2) * 550, 500);
    const max = roundStep(styleEstimate.baseMax * totalMultiplier + Math.max(0, hours - 2) * 900, 500);

    return {
      context,
      materials,
      min,
      max,
      hours,
      hoursLabel,
      summary: `${styleEstimate.label}, ${sizeMap[context.size]?.label || context.size}, ${placementMap[context.placement]?.label || context.placement}, ${colorMap[context.color]?.label || context.color}`,
      lines,
      requestText: [
        `Расчет: ${styleEstimate.label}`,
        `Размер: ${sizeMap[context.size]?.label || context.size}`,
        `Место: ${placementMap[context.placement]?.label || context.placement}`,
        `Цветность: ${colorMap[context.color]?.label || context.color}`,
        `Сложность: ${complexityMap[context.complexity] || context.complexity}`,
        `Эскиз: ${context.hasSketch === "yes" ? "есть" : "нужна помощь"}`,
        `Первая татуировка: ${context.firstTattoo ? "да" : "нет"}`,
        `Предварительная стоимость: ${formatMoney(min)} — ${formatMoney(max)}`,
        `Время: ${hoursLabel}`,
        `Расходники: ${formatMoney(materials)}`,
      ].join("\n"),
    };
  }

  function renderCalc() {
    const status = qs("[data-calc-status]");
    const source = qs("[data-calc-source]");
    const range = qs("[data-calc-range]");
    const time = qs("[data-calc-time]");
    const materials = qs("[data-calc-materials]");
    const summary = qs("[data-calc-summary]");
    const breakdown = qs("[data-calc-breakdown]");
    if (!status || !source || !range || !time || !materials || !summary || !breakdown) return;

    const result = calculateEstimate();
    if (!result) return;
    state.calc = result;

    range.textContent = `${formatMoney(result.min)} — ${formatMoney(result.max)}`;
    time.textContent = result.hoursLabel;
    materials.textContent = formatMoney(result.materials);
    summary.textContent = result.summary;
    breakdown.innerHTML = result.lines
      .map(
        (line) => `
          <li>
            <span>
              ${line.name}
              ${line.detail ? `<small>${line.detail}</small>` : ""}
            </span>
            <strong>${formatMoney(line.total)}</strong>
          </li>
        `
      )
      .join("");

    source.textContent =
      state.consumables.source === "google-sheets-csv"
        ? "Источник расходников: Google Таблица коворкинга."
        : "Источник расходников: локальный fallback, пока таблица недоступна.";
    status.dataset.tone = state.consumables.source === "google-sheets-csv" ? "success" : "warning";
    status.textContent =
      state.consumables.source === "google-sheets-csv"
        ? "Список расходников собран из таблицы коворкинга и очищен от служебных позиций. Это предварительный ориентир до просмотра идеи."
        : "Таблица сейчас недоступна, поэтому используется локальный расчет с теми же правилами.";

    updateRequestSummary();
  }

  function updateRequestSummary() {
    const work = qs("[data-request-selected-work]");
    const calc = qs("[data-request-selected-calc]");
    if (work) {
      work.textContent = state.selectedWork ? `${state.selectedWork.title} · ${state.selectedWork.price || "цена по согласованию"}` : "Работа не выбрана";
    }
    if (calc) {
      calc.textContent = state.calc ? `${formatMoney(state.calc.min)} — ${formatMoney(state.calc.max)} · ${state.calc.hoursLabel}` : "Расчет не собран";
    }
  }

  function buildRequestDraft(form) {
    const data = new FormData(form);
    const calcStyle = state.calc ? requestStyleMap[state.calc.context.style] || state.calc.context.style : "—";
    const calcSize = state.calc ? sizeMap[state.calc.context.size]?.label || state.calc.context.size : "—";
    const calcPlacement = state.calc ? placementMap[state.calc.context.placement]?.label || state.calc.context.placement : "—";
    const calcColor = state.calc ? colorMap[state.calc.context.color]?.label || state.calc.context.color : "—";
    const calcComplexity = state.calc ? complexityMap[state.calc.context.complexity] || state.calc.context.complexity : "—";
    const name = String(data.get("name") || "").trim();
    const contact = String(data.get("contact") || "").trim();
    const idea = String(data.get("idea") || "").trim();
    const comment = String(data.get("comment") || "").trim();
    const lines = ["Здравствуйте! Хочу обсудить татуировку.", `Контакт: ${contact || "—"}`, `Идея: ${idea || "—"}`];

    if (name) {
      lines.splice(1, 0, `Имя: ${name}`);
    }

    if (comment) {
      lines.push(`Что важно учесть: ${comment}`);
    }

    if (state.selectedWork) {
      lines.push(`Похожая работа: ${state.selectedWork.title} (${state.selectedWork.price || "цена по согласованию"})`);
    }

    if (state.calc) {
      lines.push("");
      lines.push("Предварительный расчет:");
      lines.push(`Стиль: ${calcStyle}`);
      lines.push(`Размер: ${calcSize}`);
      lines.push(`Место: ${calcPlacement}`);
      lines.push(`Цветность: ${calcColor}`);
      lines.push(`Сложность: ${calcComplexity}`);
      lines.push(`Эскиз: ${state.calc.context.hasSketch === "yes" ? "есть" : "нужна помощь"}`);
      lines.push(`Первая татуировка: ${state.calc.context.firstTattoo ? "да" : "нет"}`);
      lines.push(`Предварительная стоимость: ${formatMoney(state.calc.min)} — ${formatMoney(state.calc.max)}`);
      lines.push(`Время: ${state.calc.hoursLabel}`);
      lines.push(`Расходники: ${formatMoney(state.calc.materials)}`);
    }

    lines.push("Референсы и фото могу дослать в личные сообщения после ответа.");

    return lines.join("\n");
  }

  function updateDraftLinks(text) {
    const encoded = encodeURIComponent(text);
    const whatsapp = qs("[data-open-whatsapp]");
    const telegram = qs("[data-open-telegram]");
    const vk = qs("[data-open-vk]");
    if (whatsapp) whatsapp.href = `https://wa.me/79656066455?text=${encoded}`;
    if (telegram) telegram.href = "https://t.me/ppdstr_bot?start=booking";
    if (vk) vk.href = "https://vk.com/ppdstr23";
  }

  function resolveRequestApiUrl() {
    const configured = document.body?.dataset?.requestApiUrl?.trim();
    if (configured) return configured;
    if (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost") {
      return "http://127.0.0.1:8080/api/booking-request";
    }
    return `${window.location.origin}/api/booking-request`;
  }

  function calcPayloadLabels() {
    if (!state.calc) return null;
    return {
      styleLabel: requestStyleMap[state.calc.context.style] || state.calc.context.style,
      sizeLabel: sizeMap[state.calc.context.size]?.label || state.calc.context.size,
      placementLabel: placementMap[state.calc.context.placement]?.label || state.calc.context.placement,
      colorLabel: colorMap[state.calc.context.color]?.label || state.calc.context.color,
      complexityLabel: complexityMap[state.calc.context.complexity] || state.calc.context.complexity,
      hasSketchLabel: state.calc.context.hasSketch === "yes" ? "есть" : "нужна помощь",
      firstTattooLabel: state.calc.context.firstTattoo ? "да" : "нет",
    };
  }

  function buildRequestPayload(form, draftText) {
    const selectedWork = state.selectedWork
      ? {
          id: state.selectedWork.id || "",
          title: state.selectedWork.title || "",
          price: state.selectedWork.price || "",
          category: state.selectedWork.category || "",
        }
      : null;
    const calcLabels = calcPayloadLabels();

    return {
      name: fdValue(form, "name"),
      contact: fdValue(form, "contact"),
      idea: fdValue(form, "idea"),
      comment: fdValue(form, "comment"),
      consent: form.elements.namedItem("consent")?.checked === true,
      draftText,
      selectedWork,
      calc: state.calc
        ? {
            min: state.calc.min,
            max: state.calc.max,
            materials: state.calc.materials,
            hoursLabel: state.calc.hoursLabel,
            style: state.calc.context.style,
            size: state.calc.context.size,
            placement: state.calc.context.placement,
            color: state.calc.context.color,
            complexity: state.calc.context.complexity,
            hasSketch: state.calc.context.hasSketch,
            firstTattoo: state.calc.context.firstTattoo,
            materialsLabel: formatMoney(state.calc.materials),
            priceRange: `${formatMoney(state.calc.min)} — ${formatMoney(state.calc.max)}`,
            ...calcLabels,
          }
        : null,
    };
  }

  async function submitRequestToApi(payload) {
    const response = await fetch(resolveRequestApiUrl(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    if (!response.ok) {
      throw new Error(data?.error || `Request failed with status ${response.status}`);
    }
    return data;
  }

  function setRequestSubmitting(form, status, isSubmitting) {
    const submitButton = qs("button[type='submit']", form);
    if (submitButton) {
      if (!submitButton.dataset.idleText) submitButton.dataset.idleText = submitButton.textContent.trim();
      submitButton.disabled = isSubmitting;
      submitButton.dataset.busy = isSubmitting ? "true" : "false";
      submitButton.textContent = isSubmitting ? "Отправляем заявку..." : submitButton.dataset.idleText;
    }
    form.classList.toggle("is-busy", isSubmitting);
    if (isSubmitting) {
      status.dataset.tone = "";
      status.textContent = "Отправляем заявку менеджеру и готовим продолжение в чате.";
    }
  }

  function bindRequestFormV2() {
    const form = qs("[data-request-form]");
    const draft = qs("[data-request-draft]");
    const status = qs("[data-request-status]");
    const copyButton = qs("[data-copy-draft]");
    const actions = qs("[data-request-actions]");
    if (!form || !draft || !status || !copyButton || !actions) return;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;

      const text = buildRequestDraft(form);
      const payload = buildRequestPayload(form, text);
      state.requestDraft = text;
      draft.value = text;
      updateDraftLinks(text);
      actions.hidden = true;
      setRequestSubmitting(form, status, true);

      try {
        const data = await submitRequestToApi(payload);
        const copied = await copyText(text);
        const crmHealthy = Boolean(data.crm_synced || data.crm_pending);
        actions.hidden = false;
        setRequestSubmitting(form, status, false);
        status.dataset.tone = crmHealthy ? "success" : "warning";
        status.textContent = data.crm_synced
          ? "Заявка отправлена менеджеру, сохранена в CRM и готова для продолжения в удобном чате. Референсы можно дослать уже туда."
          : data.crm_pending
            ? "Заявка отправлена менеджеру и уже принята сайтом. CRM допишется в фоне, а чат можно открывать прямо сейчас."
            : "Заявка отправлена менеджеру. CRM не подтянулась автоматически, но чат уже готов — можно продолжать там.";
        if (!copied) {
          status.dataset.tone = "warning";
          status.textContent += " Если текст не скопировался автоматически, откройте чат и скопируйте его вручную.";
        }
      } catch (error) {
        const copied = await copyText(text);
        actions.hidden = false;
        setRequestSubmitting(form, status, false);
        status.dataset.tone = copied ? "warning" : "danger";
        status.textContent = copied
          ? "Сайт не смог отправить заявку напрямую в CRM, но текст уже собран. Откройте удобный чат — референсы можно дослать туда же."
          : "Сайт не смог отправить заявку напрямую. Откройте чат и скопируйте текст вручную, чтобы ничего не потерялось.";
      }
    });
    copyButton.addEventListener("click", async () => {
      if (!state.requestDraft) return;
      const copied = await copyText(state.requestDraft);
      status.dataset.tone = copied ? "success" : "warning";
      status.textContent = copied
        ? "Текст заявки скопирован."
        : "Не удалось скопировать автоматически. Выделите текст вручную.";
    });
  }

  function bindBurger() {
    const toggle = qs("[data-nav-toggle]");
    const nav = qs("[data-mobile-nav]");
    if (!toggle || !nav) return;

    const close = () => {
      nav.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", () => {
      const isOpen = toggle.getAttribute("aria-expanded") === "true";
      nav.hidden = isOpen;
      toggle.setAttribute("aria-expanded", String(!isOpen));
    });

    qsa("a", nav).forEach((link) => link.addEventListener("click", close));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
  }

  function bindCalculatorActions() {
    const form = qs("[data-calc-form]");
    if (form) {
      form.addEventListener("input", renderCalc);
      form.addEventListener("change", renderCalc);
    }
  }

  function bindFaq() {
    const items = qsa(".ppd-faq__item");
    if (!items.length) return;

    items.forEach((item) => {
      item.addEventListener("toggle", () => {
        if (!item.open) return;
        items.forEach((other) => {
          if (other !== item) other.open = false;
        });
      });
    });
  }

  function bindMobileCta() {
    const cta = qs(".ppd-mobile-cta");
    const hero = qs(".ppd-hero");
    const request = qs("#request");
    if (!cta || !hero || !request || !("IntersectionObserver" in window) || !window.matchMedia) return;

    const mobileMedia = window.matchMedia("(max-width: 720px)");
    let pastHero = false;
    let requestInView = false;

    const sync = () => {
      const visible = mobileMedia.matches && pastHero && !requestInView;
      cta.classList.toggle("is-visible", visible);
    };

    const heroObserver = new IntersectionObserver(
      ([entry]) => {
        pastHero = !entry.isIntersecting;
        sync();
      },
      { threshold: 0.24 }
    );

    const requestObserver = new IntersectionObserver(
      ([entry]) => {
        requestInView = entry.isIntersecting;
        sync();
      },
      { threshold: 0.18 }
    );

    heroObserver.observe(hero);
    requestObserver.observe(request);

    if (typeof mobileMedia.addEventListener === "function") {
      mobileMedia.addEventListener("change", sync);
    } else if (typeof mobileMedia.addListener === "function") {
      mobileMedia.addListener(sync);
    }

    sync();
  }

  function initRevealObserver() {
    const reveals = qsa(".ppd-reveal");
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    reveals.forEach((el) => observer.observe(el));
  }

  // Roll back the last polish pass to the approved visual baseline:
  // keep the footer simple and preserve the cat mood block in the estimate card.
  function decorateFooter() {
    const footerText = qs(".ppd-footer__text");
    if (!footerText) return;

    footerText.textContent =
      "Сильное портфолио, спокойная консультация и понятный путь от идеи до записи без ощущения сырого прототипа.";
  }

  function composeRequestLayout() {
    qsa(".ppd-calc-panel .ppd-card-grid--calc-inline").forEach((node) => node.remove());

    const form = qs(".ppd-calc-panel");
    const result = qs(".ppd-calculator__result");
    const cards = qs(".ppd-card-grid--calc", result);
    const compose = qs(".ppd-request-compose", result);

    if (!form || !result || !cards || !compose) return;

    cards.classList.add("ppd-card-grid--calc-inline", "is-live");
    form.append(cards);
    result.replaceWith(compose);
  }

  async function init() {
    bindBurger();
    bindModal();
    bindRequestFormV2();
    bindCalculatorActions();
    bindFaq();
    bindMobileCta();
    composeRequestLayout();

    const [portfolio, consumables] = await Promise.all([
      fetchJson(body.dataset.portfolioUrl, fallbackPortfolio),
      fetchJson(body.dataset.consumablesUrl, fallbackConsumables),
    ]);

    state.portfolio = normalizePortfolio(portfolio);
    state.consumables = consumables || fallbackConsumables;
    restoreSelectedWork();

    renderHomePortfolio();
    renderWorksPortfolio();
    renderHeroCollage();
    renderProcessGallery();
    renderMasterImage();
    renderCalc();
    updateRequestSummary();
    decorateFooter();
    initRevealObserver();
  }

  init();
})();

