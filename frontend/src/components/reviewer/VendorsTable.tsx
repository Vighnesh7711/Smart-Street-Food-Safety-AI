"use client";

import Link from "next/link";

import { FlagBadge, HygieneStatus, ScanStatusPill } from "@/components/reviewer/StatusPill";
import type { ReviewSort, VendorRow } from "@/lib/types";

/**
 * The vendors table.
 *
 * Presentational: all query state lives in the page, which passes the
 * current sort down and receives sort changes back. Keeping sort state in
 * one place is what stops the header arrows and the request from disagreeing.
 */

export interface Column {
  key: ReviewSort;
  label: string;
  align?: "left" | "right";
}

export const COLUMNS: Column[] = [
  { key: "stall_name", label: "Stall" },
  { key: "hygiene", label: "Hygiene", align: "left" },
  { key: "last_scan", label: "Last label check", align: "left" },
  { key: "last_activity", label: "Last activity", align: "right" },
];

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function VendorsTable({
  rows,
  sort,
  order,
  onSort,
  onFlag,
  loading,
}: {
  rows: VendorRow[];
  sort: ReviewSort;
  order: "asc" | "desc";
  onSort: (key: ReviewSort) => void;
  onFlag: (row: VendorRow) => void;
  loading: boolean;
}) {
  if (!loading && rows.length === 0) {
    return (
      <div className="rounded-lg bg-white p-12 text-center ring-1 ring-inset ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]">
        <p className="text-sm font-medium text-text-primary font-['Plus_Jakarta_Sans']">No stalls match.</p>
        <p className="mt-1 text-sm text-text-primary/60 font-['Inter']">
          Try clearing a filter or widening your search.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg bg-white ring-1 ring-inset ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]">
      <table className="min-w-full divide-y divide-border-default/10">
        <thead className="bg-[#0B4516]">
          <tr>
            {COLUMNS.map((column) => {
              const active = sort === column.key;
              return (
                <th
                  key={column.key}
                  scope="col"
                  className={`px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[#FFFCEB] font-['Plus_Jakarta_Sans'] ${
                    column.align === "right" ? "text-right" : "text-left"
                  }`}
                  aria-sort={
                    active
                      ? order === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <button
                    type="button"
                    onClick={() => onSort(column.key)}
                    className="inline-flex items-center gap-1 hover:text-[#FFE714] transition-colors"
                  >
                    {column.label}
                    <span aria-hidden="true" className={active ? "text-[#FFE714]" : "text-[#FFFCEB]/40"}>
                      {active ? (order === "asc" ? "▲" : "▼") : "↕"}
                    </span>
                  </button>
                </th>
              );
            })}
            <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[#FFFCEB] font-['Plus_Jakarta_Sans']">
              Flag
            </th>
            <th scope="col" className="px-4 py-3">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>

        <tbody className="divide-y divide-border-default/10">
          {rows.map((row) => (
            <tr key={row.stall_id} className="hover:bg-brand-bg transition-colors">
              <td className="px-4 py-3">
                <Link
                  href={`/reviewer/${row.stall_id}`}
                  className="text-sm font-bold text-text-primary hover:text-[#0B4516] font-['Plus_Jakarta_Sans']"
                >
                  {row.stall_name}
                </Link>
                <div className="text-xs text-text-primary/60 font-['Inter']">
                  {row.food_category ?? "Uncategorised"}
                  {row.vendor_name ? ` · ${row.vendor_name}` : ""}
                </div>
              </td>

              <td className="px-4 py-3">
                <HygieneStatus band={row.band} score={row.latest_score} />
                {row.latest_score_at && (
                  <div className="mt-1 text-xs text-text-primary/50 font-['Inter']">
                    {formatDate(row.latest_score_at)}
                  </div>
                )}
              </td>

              <td className="px-4 py-3">
                <ScanStatusPill status={row.latest_scan_status} />
                {row.latest_scan_at && (
                  <div className="mt-1 text-xs text-text-primary/50 font-['Inter']">
                    {formatDate(row.latest_scan_at)}
                  </div>
                )}
              </td>

              <td className="px-4 py-3 text-right text-sm tabular-nums text-text-primary/70 font-['Inter']">
                {formatDate(row.last_activity_at)}
              </td>

              <td className="px-4 py-3">
                <FlagBadge count={row.open_flag_count} />
              </td>

              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => onFlag(row)}
                  className="rounded-full border border-border-default/20 bg-white px-4 py-1.5 text-[11px] font-bold tracking-wide text-text-primary hover:bg-[#0B4516] hover:text-[#FFFCEB] transition-colors font-['Plus_Jakarta_Sans']"
                >
                  Flag
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {loading && (
        <div className="border-t border-border-default/10 px-4 py-3 text-center text-sm text-text-primary/40 font-['Plus_Jakarta_Sans'] font-medium">
          Loading…
        </div>
      )}
    </div>
  );
}
