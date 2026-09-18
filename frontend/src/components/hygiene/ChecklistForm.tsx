"use client";

import { useState } from "react";

import type { ChecklistItem } from "@/lib/types";

/**
 * Self-declared compliance checklist.
 *
 * Worth 30% of the score by design, so this screen says so plainly. A vendor
 * who understands that ticking boxes cannot rescue a failing visual score is
 * less likely to treat the checklist as a formality -- and the honest ones
 * are the ones this tool is meant to help.
 */
export default function ChecklistForm({
  items,
  submitting,
  onSubmit,
}: {
  items: ChecklistItem[];
  submitting: boolean;
  onSubmit: (answers: Record<string, boolean>) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, boolean>>({});

  const answeredCount = Object.keys(answers).length;

  return (
    <div className="p-5 pb-8">
      <h1 className="text-xl font-bold text-gray-900">
        A few questions about your stall
      </h1>
      <p className="mt-1 text-sm text-gray-500">
        These cannot be seen in a photo. They count for 30% of your score —
        the photos count for the other 70%.
      </p>

      <ul className="mt-6 space-y-3">
        {items.map((item) => {
          const value = answers[item.code];
          return (
            <li
              key={item.code}
              className="rounded-xl bg-white p-4 ring-1 ring-inset ring-gray-200"
            >
              <p className="text-sm font-semibold text-gray-900">
                {item.label}
              </p>
              <p className="mt-0.5 text-xs text-gray-500">{item.help_text}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {(
                  [
                    { label: "Yes", val: true },
                    { label: "No", val: false },
                  ] as const
                ).map((option) => {
                  const selected = value === option.val;
                  return (
                    <button
                      key={option.label}
                      type="button"
                      aria-pressed={selected}
                      onClick={() =>
                        setAnswers((previous) => ({
                          ...previous,
                          [item.code]: option.val,
                        }))
                      }
                      className={`min-h-[44px] rounded-lg border px-3 text-sm font-semibold ${
                        selected
                          ? option.val
                            ? "border-emerald-600 bg-emerald-50 text-emerald-900"
                            : "border-amber-600 bg-amber-50 text-amber-900"
                          : "border-gray-300 bg-white text-gray-600"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 text-xs text-gray-500">
        {answeredCount} of {items.length} answered. Unanswered questions count
        as not satisfied.
      </p>

      <button
        type="button"
        onClick={() => onSubmit(answers)}
        disabled={submitting}
        className="mt-5 w-full rounded-full bg-blue-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
      >
        {submitting ? "Scoring your stall…" : "Finish and see my score"}
      </button>
    </div>
  );
}
