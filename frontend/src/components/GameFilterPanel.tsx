"use client";

import { useLocale, useTranslations } from "next-intl";
import FilterChips, { type ChipOption } from "@/components/FilterChips";
import {
  PLAYER_OPTIONS,
  PLAYTIME_OPTIONS,
  cycleTag,
  tagState,
  type GameFilterState,
} from "@/lib/gameFilters";

export interface FacetBucket {
  name: string;
  name_zh?: string;
  count: number;
}

export interface Facets {
  total: number;
  categories: FacetBucket[];
  mechanics: FacetBucket[];
  players: { value: number; count: number }[];
  playtime: { max: number; count: number }[];
  weight: { band: string; min: number | null; max: number | null; count: number }[];
}

export interface TagVocabulary {
  name: string;
  name_zh: string;
  count: number;
}

interface Props {
  filters: GameFilterState;
  onChange: (next: GameFilterState) => void;
  facets: Facets | null;
  categories: TagVocabulary[];
  mechanics: TagVocabulary[];
}

const WEIGHT_BAND_KEYS = ["light", "medium", "heavy"] as const;

const controlStyle = {
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  color: "#CBD5E1",
};

function toggleStyle(active: boolean) {
  return active
    ? { background: "rgba(34,197,94,0.16)", border: "1px solid rgba(34,197,94,0.5)", color: "#86EFAC" }
    : controlStyle;
}

export default function GameFilterPanel({ filters, onChange, facets, categories, mechanics }: Props) {
  const t = useTranslations("games");
  const locale = useLocale();
  const isZh = locale.startsWith("zh");

  const facetCount = (buckets: FacetBucket[] | undefined, name: string) =>
    buckets?.find((bucket) => bucket.name === name)?.count;

  const options = (vocabulary: TagVocabulary[], buckets: FacetBucket[] | undefined): ChipOption[] =>
    vocabulary.map((tag) => ({
      name: tag.name,
      label: isZh && tag.name_zh ? tag.name_zh : tag.name,
      count: facetCount(buckets, tag.name),
    }));

  const playerCount = (value: number) =>
    facets?.players.find((bucket) => bucket.value === value)?.count;

  const playtimeCount = (max: number) =>
    facets?.playtime.find((bucket) => bucket.max === max)?.count;

  const weightCount = (band: string) =>
    facets?.weight.find((bucket) => bucket.band === band)?.count;

  return (
    <div
      className="mb-6 flex flex-col gap-5 rounded-xl p-5"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <div className="flex flex-wrap items-end gap-5">
        <div>
          <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--color-text-secondary)" }}>
            {t("playersExact")}
          </label>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => onChange({ ...filters, players: "", bestAtPlayers: false, page: 1 })}
              className="rounded-full px-2.5 py-1 text-xs"
              style={toggleStyle(!filters.players)}
            >
              {t("playersAny")}
            </button>
            {PLAYER_OPTIONS.map((value) => {
              const count = playerCount(value);
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => onChange({ ...filters, players: String(value), page: 1 })}
                  className="rounded-full px-2.5 py-1 text-xs"
                  style={{ ...toggleStyle(filters.players === String(value)), opacity: count === 0 ? 0.35 : 1 }}
                >
                  {value}
                  {count !== undefined && <span style={{ opacity: 0.65 }}> {count}</span>}
                </button>
              );
            })}
          </div>
          {filters.players && (
            <label className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
              <input
                type="checkbox"
                checked={filters.bestAtPlayers}
                onChange={(event) => onChange({ ...filters, bestAtPlayers: event.target.checked, page: 1 })}
              />
              {t("bestAtPlayers")}
            </label>
          )}
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--color-text-secondary)" }}>
            {t("playtimeUnder")}
          </label>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => onChange({ ...filters, playtimeMax: "", page: 1 })}
              className="rounded-full px-2.5 py-1 text-xs"
              style={toggleStyle(!filters.playtimeMax)}
            >
              {t("anyLength")}
            </button>
            {PLAYTIME_OPTIONS.map((value) => {
              const count = playtimeCount(value);
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => onChange({ ...filters, playtimeMax: String(value), page: 1 })}
                  className="rounded-full px-2.5 py-1 text-xs"
                  style={{ ...toggleStyle(filters.playtimeMax === String(value)), opacity: count === 0 ? 0.35 : 1 }}
                >
                  ≤{value} {t("minutes")}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--color-text-secondary)" }}>
            {t("complexity")}
          </label>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => onChange({ ...filters, weightBand: "", page: 1 })}
              className="rounded-full px-2.5 py-1 text-xs"
              style={toggleStyle(!filters.weightBand)}
            >
              {t("complexityAny")}
            </button>
            {WEIGHT_BAND_KEYS.map((band, index) => {
              const count = weightCount(band);
              const label = [t("complexityLight"), t("complexityMedium"), t("complexityHeavy")][index];
              return (
                <button
                  key={band}
                  type="button"
                  onClick={() => onChange({ ...filters, weightBand: band, page: 1 })}
                  className="rounded-full px-2.5 py-1 text-xs"
                  style={toggleStyle(filters.weightBand === band)}
                >
                  {label}
                  {count !== undefined && <span style={{ opacity: 0.65 }}> {count}</span>}
                </button>
              );
            })}
          </div>
        </div>

        <label className="flex items-center gap-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
          <input
            type="checkbox"
            checked={!filters.includeExpansions}
            onChange={(event) => onChange({ ...filters, includeExpansions: !event.target.checked, page: 1 })}
          />
          {t("hideExpansions")}
        </label>
      </div>

      <FilterChips
        title={t("categoryFilter")}
        hint={t("includeTag")}
        searchPlaceholder={t("tagSearch")}
        options={options(categories, facets?.categories)}
        stateOf={(name) => tagState(filters, "categories", name)}
        onToggle={(name) => onChange(cycleTag(filters, "categories", name))}
        moreLabel={t("showMore")}
        lessLabel={t("showLess")}
      />

      <FilterChips
        title={t("mechanicFilter")}
        searchPlaceholder={t("tagSearch")}
        options={options(mechanics, facets?.mechanics)}
        stateOf={(name) => tagState(filters, "mechanics", name)}
        onToggle={(name) => onChange(cycleTag(filters, "mechanics", name))}
        moreLabel={t("showMore")}
        lessLabel={t("showLess")}
      />
    </div>
  );
}
