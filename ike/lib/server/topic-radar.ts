import { XMLParser } from "fast-xml-parser";
import type { NewsRadarSource, NewsSignal, TopicCandidate } from "@/lib/domain/pipeline";
import { getTopicRadarSnapshot, replaceRadarSignals } from "@/lib/data/repository";
import { createId, nowIso } from "@/lib/server/store";

const parser = new XMLParser({
  ignoreAttributes: false,
  parseTagValue: false,
  trimValues: true,
});

type FeedEntry = {
  title: string;
  url: string;
  summary: string;
  publishedAt: string;
};

type TopicProfile = {
  clusterKey: string;
  tags: string[];
  title: string;
  angle: string;
  recommendedFormat: string;
};

const curatedFallbackSources: NewsRadarSource[] = [
  {
    id: "radar_fed",
    label: "Federal Reserve",
    category: "official",
    url: "https://www.federalreserve.gov/feeds/press_all.xml",
    trustLevel: "high",
    region: "US",
    enabled: true,
  },
  {
    id: "radar_ecb",
    label: "European Central Bank",
    category: "official",
    url: "https://www.ecb.europa.eu/rss/press.html",
    trustLevel: "high",
    region: "EU",
    enabled: true,
  },
  {
    id: "radar_imf",
    label: "IMF",
    category: "official",
    url: "https://www.imf.org/en/News/RSS",
    trustLevel: "high",
    region: "Global",
    enabled: true,
  },
  {
    id: "radar_bis",
    label: "BIS",
    category: "research",
    url: "https://www.bis.org/list/pressreleases/index.rss",
    trustLevel: "high",
    region: "Global",
    enabled: true,
  },
];

function forceArray<T>(value: T | T[] | undefined): T[] {
  if (!value) {
    return [];
  }

  return Array.isArray(value) ? value : [value];
}

function stripHtml(value: string) {
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function normalizeUrl(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  if (value && typeof value === "object") {
    if ("@_href" in value && typeof value["@_href"] === "string") {
      return value["@_href"];
    }

    if ("href" in value && typeof value.href === "string") {
      return value.href;
    }
  }

  return "";
}

function coerceDate(value: unknown) {
  if (typeof value === "string" && value.trim()) {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) {
      return date.toISOString();
    }
  }

  return nowIso();
}

function readEntriesFromXml(xml: string): FeedEntry[] {
  const parsed = parser.parse(xml);
  const rssItems = forceArray(parsed?.rss?.channel?.item);
  const atomItems = forceArray(parsed?.feed?.entry);
  const items = [...rssItems, ...atomItems];

  return items
    .map((item) => {
      const title = typeof item.title === "string" ? item.title : item.title?.["#text"];
      const link = normalizeUrl(item.link);
      const summary =
        typeof item.description === "string"
          ? item.description
          : typeof item.summary === "string"
            ? item.summary
            : typeof item.content === "string"
              ? item.content
              : "";
      const publishedAt = coerceDate(item.pubDate ?? item.published ?? item.updated);

      if (!title || !link) {
        return null;
      }

      return {
        title: stripHtml(title),
        url: link,
        summary: stripHtml(summary).slice(0, 400),
        publishedAt,
      } satisfies FeedEntry;
    })
    .filter(Boolean) as FeedEntry[];
}

function inferTopicProfile(text: string): TopicProfile {
  const haystack = text.toLowerCase();

  if (/(rate|rates|cut|cuts|policy rate|easing|tightening|central bank|fed|ecb)/.test(haystack)) {
    return {
      clusterKey: "rates-signal-vs-weakness",
      tags: ["rates", "central banks", "growth", "inflation"],
      title: "Вот что на самом деле сигнализирует разворот ставок",
      angle: "Не обсуждать только движение ставки, а разобрать, какую скрытую слабость или нормализацию оно показывает.",
      recommendedFormat: "Question-led contradiction explainer",
    };
  }

  if (/(tariff|trade|shipping|logistics|freight|supply chain|trade friction)/.test(haystack)) {
    return {
      clusterKey: "trade-frictions-renew-goods-inflation",
      tags: ["trade", "inflation", "shipping", "geopolitics"],
      title: "Возвращается ли инфляция через торговлю и логистику",
      angle: "Собрать ролик не про общий CPI, а про новый канал инфляции через trade friction и supply chain.",
      recommendedFormat: "Why-now macro-political breakdown",
    };
  }

  if (/(oil|energy|gas|commodity|commodities|food prices)/.test(haystack)) {
    return {
      clusterKey: "commodity-shock-pressure",
      tags: ["commodities", "energy", "food", "inflation"],
      title: "Новый сырьевой шок или временный всплеск",
      angle: "Показать, что именно в commodity move выглядит структурным, а что может быстро остыть.",
      recommendedFormat: "Concrete examples explainer",
    };
  }

  if (/(credit|bank|banking|lending|delinquen|defaults|financial conditions)/.test(haystack)) {
    return {
      clusterKey: "credit-strain-under-calm-markets",
      tags: ["credit", "banking", "markets", "growth"],
      title: "Почему рынки спокойны, если кредит уже сжимается",
      angle: "Построить ролик на расхождении между спокойными рынками и скрытым кредитным напряжением.",
      recommendedFormat: "Signal-decoding explainer",
    };
  }

  if (/(jobs|labor|employment|unemployment|wages|payroll)/.test(haystack)) {
    return {
      clusterKey: "labor-softening-before-headlines",
      tags: ["labor", "wages", "growth"],
      title: "Что рынок труда скрывает до плохих headline",
      angle: "Разобрать опережающие признаки охлаждения до громких headline по безработице.",
      recommendedFormat: "Data-led narrative explainer",
    };
  }

  return {
    clusterKey: "macro-watch-general",
    tags: ["macro", "policy"],
    title: "Новая макро-тема под наблюдением",
    angle: "Требуется ручная редакторская доупаковка, но сигнал уже выглядит интересным.",
    recommendedFormat: "Editorial review needed",
  };
}

function scoreRecency(publishedAt: string) {
  const ageHours = Math.max(1, (Date.now() - new Date(publishedAt).getTime()) / (1000 * 60 * 60));
  return Math.max(35, 100 - ageHours * 2.4);
}

function inferCompetitionPressure(clusterKey: string) {
  switch (clusterKey) {
    case "rates-signal-vs-weakness":
      return 74;
    case "trade-frictions-renew-goods-inflation":
      return 63;
    case "commodity-shock-pressure":
      return 69;
    case "credit-strain-under-calm-markets":
      return 42;
    case "labor-softening-before-headlines":
      return 57;
    default:
      return 48;
  }
}

function inferProductionEffort(clusterKey: string): TopicCandidate["productionEffort"] {
  switch (clusterKey) {
    case "credit-strain-under-calm-markets":
    case "commodity-shock-pressure":
      return "high";
    case "trade-frictions-renew-goods-inflation":
    case "rates-signal-vs-weakness":
      return "medium";
    default:
      return "medium";
  }
}

function buildPackagingHooks(profile: TopicProfile) {
  switch (profile.clusterKey) {
    case "rates-signal-vs-weakness":
      return [
        "Почему снижение ставки может быть плохой новостью",
        "Рынок радуется сигналу, который должен пугать",
      ];
    case "trade-frictions-renew-goods-inflation":
      return [
        "Инфляция возвращается через торговлю, а не через спрос",
        "Новый механизм роста цен, который недооценивают",
      ];
    case "credit-strain-under-calm-markets":
      return [
        "Рынки спокойны, но кредит уже трещит",
        "Слабость экономики пока спрятана от headline",
      ];
    default:
      return [
        "Главная макро-тема, которую рынок пока читает слишком поверхностно",
        "Что на самом деле сигнализирует новый поворот в данных",
      ];
    }
}

function inferCompetitorCluster(topicLabel: string) {
  return inferTopicProfile(topicLabel).clusterKey;
}

function buildCompetitorMomentumMap(
  competitorSignals: Array<{ topicLabel: string; viewsPerDay: number; performanceBand: string }>,
) {
  const grouped = new Map<string, Array<{ viewsPerDay: number; performanceBand: string }>>();

  for (const signal of competitorSignals) {
    const clusterKey = inferCompetitorCluster(signal.topicLabel);
    const current = grouped.get(clusterKey) ?? [];
    current.push({ viewsPerDay: signal.viewsPerDay, performanceBand: signal.performanceBand });
    grouped.set(clusterKey, current);
  }

  return grouped;
}

function createTopicCandidates(
  signals: NewsSignal[],
  competitorSignals: Array<{ topicLabel: string; viewsPerDay: number; performanceBand: string }>,
) {
  const grouped = new Map<string, NewsSignal[]>();
  const competitorMomentumMap = buildCompetitorMomentumMap(competitorSignals);

  for (const signal of signals) {
    const current = grouped.get(signal.clusterKey) ?? [];
    current.push(signal);
    grouped.set(signal.clusterKey, current);
  }

  return [...grouped.entries()].map(([clusterKey, group]) => {
    const newest = [...group].sort(
      (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime(),
    )[0];
    const titleText = group.map((item) => `${item.title} ${item.summary}`).join(" ");
    const profile = inferTopicProfile(titleText);
    const authorityAvg =
      group.reduce((sum, item) => sum + item.authorityScore, 0) / Math.max(group.length, 1);
    const recencyScore =
      group.reduce((sum, item) => sum + scoreRecency(item.publishedAt), 0) / Math.max(group.length, 1);
    const crossSourceBoost = Math.min(18, (new Set(group.map((item) => item.sourceLabel)).size - 1) * 9);
    const evidenceStrength = Math.round(authorityAvg * 100);
    const momentumScore = Math.round(Math.min(100, recencyScore + crossSourceBoost));
    const macroRelevanceScore = Math.round(
      Math.min(100, 74 + group.length * 5 + (profile.tags.includes("geopolitics") ? 6 : 0)),
    );
    const noveltyScore = Math.round(
      Math.min(100, 68 + (profile.clusterKey !== "macro-watch-general" ? 10 : 0) + crossSourceBoost / 2),
    );
    const competitionPressure = inferCompetitionPressure(clusterKey);
    const competitorClusterSignals = competitorMomentumMap.get(clusterKey) ?? [];
    const competitorMomentumScore = competitorClusterSignals.length
      ? Math.min(
          100,
          Math.round(
            competitorClusterSignals.reduce((sum, item) => sum + Math.min(100, item.viewsPerDay / 450), 0) /
              competitorClusterSignals.length +
              competitorClusterSignals.filter((item) => item.performanceBand === "breakout").length * 8,
          ),
        )
      : 38;
    const viralityScore = Math.round(
      Math.min(
        100,
        momentumScore * 0.31 +
          noveltyScore * 0.23 +
          macroRelevanceScore * 0.14 +
          competitorMomentumScore * 0.22 +
          (100 - competitionPressure) * 0.1,
      ),
    );
    const monetizationFitScore = Math.round(
      Math.min(100, macroRelevanceScore * 0.55 + viralityScore * 0.25 + evidenceStrength * 0.2),
    );
    const youtubePotentialScore = Math.round(
      Math.min(
        100,
        viralityScore * 0.35 +
          evidenceStrength * 0.22 +
          macroRelevanceScore * 0.18 +
          monetizationFitScore * 0.13 +
          (100 - competitionPressure) * 0.06 +
          competitorMomentumScore * 0.06,
      ),
    );
    const productionEffort = inferProductionEffort(clusterKey);
    const timingWindowDays = Math.max(4, Math.min(14, Math.round(recencyScore / 10)));
    const researchCostUsd = productionEffort === "high" ? 38 : productionEffort === "medium" ? 28 : 20;
    const scriptingCostUsd = productionEffort === "high" ? 27 : productionEffort === "medium" ? 24 : 18;
    const totalCostUsd = researchCostUsd + scriptingCostUsd;
    const breakEvenViews = Math.round(totalCostUsd / 0.002);

    const status: TopicCandidate["status"] =
      youtubePotentialScore >= 82 ? "hot" : youtubePotentialScore >= 72 ? "watch" : "cooling";
    const decision: TopicCandidate["decision"] =
      youtubePotentialScore >= 80 ? "shoot_now" : youtubePotentialScore >= 70 ? "hold_watch" : "skip";

    return {
      id: createId("candidate"),
      title: profile.title,
      angle: profile.angle,
      summary: newest.summary || newest.title,
      whyNow: `Signals from ${new Set(group.map((item) => item.sourceLabel)).size} authoritative source(s) are converging over the last two weeks.`,
      youtubePotentialScore,
      viralityScore,
      evidenceStrength,
      noveltyScore,
      momentumScore,
      competitorMomentumScore,
      macroRelevanceScore,
      competitionPressure,
      monetizationFitScore,
      timingWindowDays,
      productionEffort,
      decision,
      packagingHooks: buildPackagingHooks(profile),
      economics: {
        researchCostUsd,
        scriptingCostUsd,
        totalCostUsd,
        breakEvenViews,
      },
      recommendedFormat: profile.recommendedFormat,
      status,
      clusterKey,
      signalIds: group.map((item) => item.id),
      tags: [...new Set(group.flatMap((item) => item.tags))],
      createdAt: nowIso(),
      updatedAt: nowIso(),
    } satisfies TopicCandidate;
  });
}

async function fetchFeed(source: NewsRadarSource) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(source.url, {
      headers: {
        "user-agent": "ike-topic-radar/0.1",
        accept: "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
      },
      signal: controller.signal,
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Feed request failed: ${response.status}`);
    }

    const xml = await response.text();
    return readEntriesFromXml(xml)
      .slice(0, 12)
      .map((entry) => {
        const profile = inferTopicProfile(`${entry.title} ${entry.summary}`);
        return {
          id: createId("signal"),
          sourceId: source.id,
          sourceLabel: source.label,
          title: entry.title,
          url: entry.url,
          summary: entry.summary || entry.title,
          publishedAt: entry.publishedAt,
          tags: profile.tags,
          clusterKey: profile.clusterKey,
          authorityScore: source.trustLevel === "high" ? 0.94 : 0.8,
        } satisfies NewsSignal;
      });
  } finally {
    clearTimeout(timeout);
  }
}

export async function refreshTopicRadar() {
  const current = await getTopicRadarSnapshot();
  const sources = current.sources.length ? current.sources : curatedFallbackSources;
  const enabledSources = sources.filter((source) => source.enabled);

  const settled = await Promise.allSettled(enabledSources.map((source) => fetchFeed(source)));
  const signals = settled.flatMap((result) => (result.status === "fulfilled" ? result.value : []));

  if (!signals.length) {
    return {
      usedFallback: true,
      sources,
      signals: current.signals,
      candidates: current.candidates,
    };
  }

  const filteredSignals = signals
    .filter((signal) => Date.now() - new Date(signal.publishedAt).getTime() <= 1000 * 60 * 60 * 24 * 14)
    .sort((a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime());

  const candidates = createTopicCandidates(filteredSignals, current.competitorSignals).sort(
    (a, b) => b.youtubePotentialScore - a.youtubePotentialScore,
  );

  await replaceRadarSignals({
    sources,
    signals: filteredSignals,
    candidates,
  });

  return {
    usedFallback: false,
    sources,
    signals: filteredSignals,
    candidates,
  };
}
