"use client";

import { useLocale, useTranslations } from "next-intl";
import FilterChips, { type ChipOption } from "@/components/FilterChips";
import {
  AGE_OPTIONS,
  FAMILY_OPTIONS,
  LANGUAGE_OPTIONS,
  PLAYER_OPTIONS,
  PLAYTIME_OPTIONS,
  POPULARITY_OPTIONS,
  YEAR_OPTIONS,
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
  families: { value: string; count: number }[];
  language: { band: string; count: number }[];
  age: { max: number; count: number }[];
  year: { key: string; count: number }[];
  popularity: { min: number; count: number }[];
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

interface Choice {
  key: string;
  label: string;
  count?: number;
}

/**
 * One single-select dimension: an "any" escape hatch followed by its options,
 * each carrying how many games it would leave. The counts come from the facet
 * endpoint, which measures each dimension with itself removed — so the number
 * on a chip is what you get by clicking it, not what you have now.
 */
function ChoiceRow({
  label, anyLabel, choices, selected, onSelect, size = "sm",
}: {
  label: string;
  anyLabel: string;
  choices: Choice[];
  selected: string;
  onSelect: (key: string) => void;
  size?: "sm" | "lg";
}) {
  const padding = size === "lg" ? "px-3.5 py-1.5 text-sm" : "px-2.5 py-1 text-xs";
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--color-text-secondary)" }}>
        {label}
      </label>
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => onSelect("")}
          className={`rounded-full ${padding}`}
          style={toggleStyle(!selected)}
        >
          {anyLabel}
        </button>
        {choices.map((choice) => (
          <button
            key={choice.key}
            type="button"
            onClick={() => onSelect(choice.key)}
            className={`rounded-full ${padding}`}
            style={{ ...toggleStyle(selected === choice.key), opacity: choice.count === 0 ? 0.35 : 1 }}
          >
            {choice.label}
            {choice.count !== undefined && <span style={{ opacity: 0.65 }}> {choice.count}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function GameFilterPanel({ filters, onChange, facets, categories, mechanics }: Props) {
  const t = useTranslations("games");
  const locale = useLocale();
  const isZh = locale.startsWith("zh");

  const set = (patch: Partial<GameFilterState>) => onChange({ ...filters, ...patch, page: 1 });

  const facetCount = (buckets: FacetBucket[] | undefined, name: string) =>
    buckets?.find((bucket) => bucket.name === name)?.count;

  const options = (vocabulary: TagVocabulary[], buckets: FacetBucket[] | undefined): ChipOption[] =>
    vocabulary.map((tag) => ({
      name: tag.name,
      label: isZh && tag.name_zh ? tag.name_zh : tag.name,
      count: facetCount(buckets, tag.name),
    }));

  const familyChoices: Choice[] = FAMILY_OPTIONS.map((name) => ({
    key: name,
    label: t(`family_${name}`),
    count: facets?.families.find((bucket) => bucket.value === name)?.count,
  }));

  const playerChoices: Choice[] = PLAYER_OPTIONS.map((value) => ({
    key: String(value),
    label: String(value),
    count: facets?.players.find((bucket) => bucket.value === value)?.count,
  }));

  const playtimeChoices: Choice[] = PLAYTIME_OPTIONS.map((value) => ({
    key: String(value),
    label: `≤${value} ${t("minutes")}`,
    count: facets?.playtime.find((bucket) => bucket.max === value)?.count,
  }));

  const weightChoices: Choice[] = WEIGHT_BAND_KEYS.map((band, index) => ({
    key: band,
    label: [t("complexityLight"), t("complexityMedium"), t("complexityHeavy")][index],
    count: facets?.weight.find((bucket) => bucket.band === band)?.count,
  }));

  const languageChoices: Choice[] = LANGUAGE_OPTIONS.map((band, index) => ({
    key: band,
    label: [t("languageLow"), t("languageMedium"), t("languageHigh")][index],
    count: facets?.language.find((bucket) => bucket.band === band)?.count,
  }));

  const ageChoices: Choice[] = AGE_OPTIONS.map((age) => ({
    key: String(age),
    label: t("ageFrom", { age }),
    count: facets?.age.find((bucket) => bucket.max === age)?.count,
  }));

  const yearChoices: Choice[] = YEAR_OPTIONS.map((key, index) => ({
    key,
    label: [t("yearRecent"), t("yearModern"), t("yearClassic")][index],
    count: facets?.year.find((bucket) => bucket.key === key)?.count,
  }));

  const popularityChoices: Choice[] = POPULARITY_OPTIONS.map((edge, index) => ({
    key: String(edge),
    label: [t("popularitySome"), t("popularityHot")][index],
    count: facets?.popularity.find((bucket) => bucket.min === edge)?.count,
  }));

  return (
    <div
      className="mb-6 flex flex-col gap-5 rounded-xl p-5"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <ChoiceRow
        label={t("familyFilter")}
        anyLabel={t("familyAny")}
        choices={familyChoices}
        selected={filters.family}
        onSelect={(family) => set({ family })}
        size="lg"
      />

      <div className="flex flex-wrap items-start gap-5">
        <div>
          <ChoiceRow
            label={t("playersExact")}
            anyLabel={t("playersAny")}
            choices={playerChoices}
            selected={filters.players}
            onSelect={(players) => set({ players, bestAtPlayers: players ? filters.bestAtPlayers : false })}
          />
          {filters.players && (
            <label className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
              <input
                type="checkbox"
                checked={filters.bestAtPlayers}
                onChange={(event) => set({ bestAtPlayers: event.target.checked })}
              />
              {t("bestAtPlayers")}
            </label>
          )}
        </div>

        <ChoiceRow
          label={t("playtimeUnder")}
          anyLabel={t("anyLength")}
          choices={playtimeChoices}
          selected={filters.playtimeMax}
          onSelect={(playtimeMax) => set({ playtimeMax })}
        />

        <ChoiceRow
          label={t("complexity")}
          anyLabel={t("complexityAny")}
          choices={weightChoices}
          selected={filters.weightBand}
          onSelect={(weightBand) => set({ weightBand })}
        />
      </div>

      <div className="flex flex-wrap items-start gap-5">
        <ChoiceRow
          label={t("languageFilter")}
          anyLabel={t("languageAny")}
          choices={languageChoices}
          selected={filters.languageBand}
          onSelect={(languageBand) => set({ languageBand })}
        />

        <ChoiceRow
          label={t("ageFilter")}
          anyLabel={t("ageAny")}
          choices={ageChoices}
          selected={filters.ageMax}
          onSelect={(ageMax) => set({ ageMax })}
        />

        <ChoiceRow
          label={t("yearFilter")}
          anyLabel={t("yearAny")}
          choices={yearChoices}
          selected={filters.yearRange}
          onSelect={(yearRange) => set({ yearRange })}
        />

        <ChoiceRow
          label={t("popularityFilter")}
          anyLabel={t("popularityAny")}
          choices={popularityChoices}
          selected={filters.minRatings}
          onSelect={(minRatings) => set({ minRatings })}
        />

        <label className="mt-5 flex items-center gap-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
          <input
            type="checkbox"
            checked={!filters.includeExpansions}
            onChange={(event) => set({ includeExpansions: !event.target.checked })}
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
