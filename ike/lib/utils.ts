import { clsx, type ClassValue } from "clsx";
import { format, formatDistanceToNowStrict } from "date-fns";
import { enUS, ru } from "date-fns/locale";
import type { Locale } from "@/lib/i18n";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function resolveDateLocale(locale: Locale) {
  return locale === "ru" ? ru : enUS;
}

export function formatDate(value: string | null, locale: Locale = "en") {
  if (!value) {
    return locale === "ru" ? "Без дедлайна" : "No deadline";
  }

  return format(new Date(value), "dd MMM yyyy", { locale: resolveDateLocale(locale) });
}

export function formatDateTime(value: string, locale: Locale = "en") {
  return format(new Date(value), "dd MMM yyyy, HH:mm", { locale: resolveDateLocale(locale) });
}

export function formatRelative(value: string, locale: Locale = "en") {
  return formatDistanceToNowStrict(new Date(value), {
    addSuffix: true,
    locale: resolveDateLocale(locale),
  });
}

export function slugifyFileName(name: string) {
  return name.replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/-+/g, "-");
}

export function parseJsonSafe<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}
