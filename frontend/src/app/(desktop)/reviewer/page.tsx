"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import FlagDialog from "@/components/reviewer/FlagDialog";
import VendorsTable from "@/components/reviewer/VendorsTable";
import { ApiError } from "@/lib/api";
import { reviewerApi } from "@/lib/reviewerApi";
import type { ReviewerSummary, ReviewSort, VendorRow } from "@/lib/types";

/**
 * Reviewer landing page: the vendors table plus a KPI row.
 *
 * Filtering, sorting, and pagination are all sent to the server rather than
 * applied to the fetched page. That is a correctness requirement, not a
 * preference: filtering client-side would silently hide a flagged stall
 * beyond the current page -- in the one screen whose job is finding the
 * stalls that need attention -- and sorting by hygiene sorts on a derived
 * column that does not exist client-side.
 */

const PAGE_SIZE = 25;

const BAND_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "good", label: "Good" },
  { value: "fair", label: "Fair" },
  { value: "poor", label: "Needs work" },
  { value: "bad", label: "Poor" },
  { value: "none", label: "Not assessed" },
];

const SORTABLE: ReviewSort[] = [
  "stall_name",
  "hygiene",
  "last_scan",
  "last_activity",
];

export default function ReviewerDashboard() {
  const router = useRouter();
  const [rows, setRows] = useState<VendorRow[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<ReviewerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Query state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [band, setBand] = useState("");
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [hasScanOnly, setHasScanOnly] = useState(false);
  const [sort, setSort] = useState<ReviewSort>("last_activity");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);

  const [flagTarget, setFlagTarget] = useState<VendorRow | null>(null);

  // Debounce the search so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await reviewerApi.vendors({
        search: debouncedSearch || undefined,
        band: band || undefined,
        flagged: flaggedOnly ? true : undefined,
        hasScan: hasScanOnly ? true : undefined,
        sort,
        order,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setRows(response.items);
      setTotal(response.total);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login?next=/reviewer");
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "Could not load the vendors list."
      );
    } finally {
      setLoading(false);
    }
  }, [band, debouncedSearch, flaggedOnly, hasScanOnly, order, page, router, sort]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  useEffect(() => {
    reviewerApi
      .summary()
      .then(setSummary)
      .catch(() => {
        // The KPI row is supplementary; the table still works without it, so
        // a failure here must not blank the page.
      });
  }, [rows.length]);

  const handleSort = (key: ReviewSort) => {
    if (!SORTABLE.includes(key)) return;
    if (sort === key) {
      setOrder(order === "asc" ? "desc" : "asc");
    } else {
      setSort(key);
      // Names read better A-Z; dates and scores read better worst-first.
      setOrder(key === "stall_name" ? "asc" : "desc");
    }
    setPage(0);
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Vendors</h1>
          <p className="mt-1 text-sm text-gray-600">
            Every registered stall, with its latest hygiene assessment and
            label check.
          </p>
        </div>
      </div>

      {/* KPI row */}
      {summary && (
        <dl className="mt-6 grid grid-cols-5 gap-4">
          <StatTile label="Stalls" value={summary.total_stalls} />
          <StatTile
            label="Assessed"
            value={summary.assessed_stalls}
            note={`${summary.total_stalls - summary.assessed_stalls} not yet`}
          />
          <StatTile
            label="Flagged"
            value={summary.flagged_stalls}
            tone={summary.flagged_stalls > 0 ? "alert" : "neutral"}
          />
          <StatTile
            label="Average score"
            value={
              summary.average_score === null
                ? "—"
                : summary.average_score.toFixed(1)
            }
          />
          <StatTile
            label="Checks (7 days)"
            value={summary.checks_last_7_days}
          />
        </dl>
      )}

      {/* Score band distribution */}
      {summary && summary.bands && (
        <div className="mt-4 rounded-lg bg-white p-4 ring-1 ring-inset ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]">
          <h3 className="text-sm font-bold text-text-primary mb-3 font-['Plus_Jakarta_Sans']">Score Distribution</h3>
          <div className="grid grid-cols-5 gap-2">
            <div className="text-center p-2 rounded bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200 text-xs">
              <span className="block font-semibold text-lg">{summary.bands.good}</span>
              80-100 (Good)
            </div>
            <div className="text-center p-2 rounded bg-blue-50 text-blue-800 ring-1 ring-blue-200 text-xs">
              <span className="block font-semibold text-lg">{summary.bands.fair}</span>
              60-79 (Fair)
            </div>
            <div className="text-center p-2 rounded bg-amber-50 text-amber-800 ring-1 ring-amber-200 text-xs">
              <span className="block font-semibold text-lg">{summary.bands.poor}</span>
              40-59 (Poor)
            </div>
            <div className="text-center p-2 rounded bg-red-50 text-red-800 ring-1 ring-red-200 text-xs">
              <span className="block font-semibold text-lg">{summary.bands.bad}</span>
              0-39 (Bad)
            </div>
            <div className="text-center p-2 rounded bg-surface-soft text-text-primary/50 ring-1 ring-border-default/10 text-[11px] font-semibold font-['Plus_Jakarta_Sans']">
              <span className="block font-bold text-lg text-text-primary/70">{summary.bands.none}</span>
              Not Assessed
            </div>
          </div>
        </div>
      )}

      {/* Filters: one row above the table */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search stall or vendor…"
          className="w-64 rounded-md border-0 px-3 py-2 text-sm text-text-primary shadow-[0_2px_8px_rgba(16,34,15,0.06)] ring-1 ring-inset ring-border-default/20 placeholder:text-text-primary/40 focus:ring-2 focus:ring-inset focus:ring-surface-dark font-['Inter'] bg-white"
        />

        <select
          value={band}
          onChange={(event) => {
            setBand(event.target.value);
            setPage(0);
          }}
          className="rounded-md border-0 py-2 pl-3 pr-8 text-sm text-text-primary shadow-[0_2px_8px_rgba(16,34,15,0.06)] ring-1 ring-inset ring-border-default/20 focus:ring-2 focus:ring-inset focus:ring-surface-dark font-['Inter'] bg-white"
        >
          {BAND_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-2 text-sm text-text-primary font-medium font-['Plus_Jakarta_Sans']">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(event) => {
              setFlaggedOnly(event.target.checked);
              setPage(0);
            }}
            className="h-4 w-4 rounded border-border-default/20 text-[#0B4516] focus:ring-[#0B4516]"
          />
          Flagged only
        </label>

        <label className="flex items-center gap-2 text-sm text-text-primary font-medium font-['Plus_Jakarta_Sans'] ml-2">
          <input
            type="checkbox"
            checked={hasScanOnly}
            onChange={(event) => {
              setHasScanOnly(event.target.checked);
              setPage(0);
            }}
            className="h-4 w-4 rounded border-border-default/20 text-[#0B4516] focus:ring-[#0B4516]"
          />
          Has product scan
        </label>

        <span className="ml-auto text-[11px] font-bold text-text-primary/60 font-['Plus_Jakarta_Sans'] uppercase tracking-widest">
          {total === 0
            ? "No stalls"
            : `Showing ${page * PAGE_SIZE + 1}–${Math.min(
                (page + 1) * PAGE_SIZE,
                total
              )} of ${total}`}
        </span>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200"
        >
          {error}
        </p>
      )}

      <div className="mt-4">
        <VendorsTable
          rows={rows}
          sort={sort}
          order={order}
          onSort={handleSort}
          onFlag={setFlagTarget}
          loading={loading}
        />
      </div>

      {pageCount > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded-md border border-border-default/20 bg-white px-3 py-1.5 text-sm font-bold font-['Plus_Jakarta_Sans'] text-text-primary hover:bg-[#EDF2C8]/50 disabled:opacity-40 transition-colors shadow-sm"
          >
            Previous
          </button>
          <span className="text-sm font-medium text-text-primary/60 font-['Inter']">
            Page {page + 1} of {pageCount}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={page >= pageCount - 1}
            className="rounded-md border border-border-default/20 bg-white px-3 py-1.5 text-sm font-bold font-['Plus_Jakarta_Sans'] text-text-primary hover:bg-[#EDF2C8]/50 disabled:opacity-40 transition-colors shadow-sm"
          >
            Next
          </button>
        </div>
      )}

      {flagTarget && (
        <FlagDialog
          stallId={flagTarget.stall_id}
          stallName={flagTarget.stall_name}
          onClose={() => setFlagTarget(null)}
          onFlagged={() => {
            setFlagTarget(null);
            void load();
          }}
        />
      )}
    </div>
  );
}

function StatTile({
  label,
  value,
  note,
  tone = "neutral",
}: {
  label: string;
  value: number | string;
  note?: string;
  tone?: "neutral" | "alert";
}) {
  return (
    <div className="rounded-xl bg-white px-5 py-4 ring-1 ring-inset ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]">
      <dt className="text-[10px] font-extrabold uppercase tracking-widest text-text-primary/50 font-['Plus_Jakarta_Sans']">
        {label}
      </dt>
      <dd
        className={`mt-2 text-3xl font-extrabold tabular-nums font-['Plus_Jakarta_Sans'] ${
          tone === "alert" ? "text-[#E53935]" : "text-text-primary"
        }`}
      >
        {value}
      </dd>
      {note && <p className="mt-1 text-xs font-medium text-text-primary/50 font-['Inter']">{note}</p>}
    </div>
  );
}
