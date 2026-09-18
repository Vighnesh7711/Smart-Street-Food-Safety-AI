"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { reviewerApi } from "@/lib/reviewerApi";

/**
 * Flag-for-follow-up dialog.
 *
 * The reason is required, and the stall name sits in the header: a reviewer
 * working down a 200-row table should be able to confirm they are flagging
 * the row they meant without closing the dialog and counting.
 */
export default function FlagDialog({
  stallId,
  stallName,
  onClose,
  onFlagged,
}: {
  stallId: number;
  stallName: string;
  onClose: () => void;
  onFlagged: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Escape closes. Without this the only way out is the Cancel button, which
  // is the kind of thing that gets noticed only when someone is in a hurry.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const trimmed = reason.trim();
  const valid = trimmed.length >= 3 && trimmed.length <= 500;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await reviewerApi.createFlag(stallId, trimmed);
      onFlagged();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not save the flag."
      );
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="flag-dialog-title"
      onClick={(event) => {
        // Click the backdrop to dismiss. The inner panel stops propagation.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        onSubmit={submit}
        className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl border border-border-default/10"
      >
        <h2
          id="flag-dialog-title"
          className="text-lg font-extrabold text-text-primary font-['Plus_Jakarta_Sans']"
        >
          Flag for follow-up
        </h2>
        <p className="mt-1 text-sm text-text-primary/60 font-['Inter']">
          <span className="font-bold text-text-primary font-['Plus_Jakarta_Sans']">{stallName}</span>
        </p>

        <label
          htmlFor="flag-reason"
          className="mt-5 block text-sm font-bold text-text-primary font-['Plus_Jakarta_Sans']"
        >
          Reason <span className="text-[#E53935]">*</span>
        </label>
        <p className="mt-1 text-xs text-text-primary/50 font-['Inter']">
          Short and specific — whoever follows this up sees only this text.
        </p>
        <textarea
          id="flag-reason"
          ref={inputRef}
          rows={3}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={500}
          className="mt-2 block w-full rounded-md border-0 px-3 py-2 text-sm text-text-primary shadow-sm ring-1 ring-inset ring-border-default/20 placeholder:text-text-primary/40 focus:ring-2 focus:ring-inset focus:ring-[#0B4516] font-['Inter'] bg-white"
          placeholder="e.g. Waste water pooling beside the prep table"
        />

        <div className="mt-1 flex justify-between text-[11px] font-bold font-['Plus_Jakarta_Sans']">
          <span className={valid ? "text-text-primary/40" : "text-[#E53935]"}>
            {trimmed.length < 3 ? "At least 3 characters" : ""}
          </span>
          <span className="tabular-nums text-text-primary/40">{trimmed.length}/500</span>
        </div>

        {error && (
          <p
            role="alert"
            className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200"
          >
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border-default/20 bg-white px-5 py-2 text-sm font-bold text-text-primary hover:bg-brand-bg transition-colors font-['Plus_Jakarta_Sans']"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!valid || submitting}
            className="rounded-full bg-[#E53935] px-5 py-2 text-sm font-bold text-white hover:bg-[#E53935]/90 disabled:opacity-50 transition-colors font-['Plus_Jakarta_Sans']"
          >
            {submitting ? "Saving…" : "Flag stall"}
          </button>
        </div>
      </form>
    </div>
  );
}
