"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import type { Stall, VendorOnboardResponse } from "@/lib/types";

const MapPicker = dynamic(() => import("@/components/vendor/MapPicker"), {
  ssr: false,
  loading: () => (
    <div className="flex h-64 w-full items-center justify-center rounded-md border border-gray-200 bg-gray-100 text-gray-400 animate-pulse">
      Loading map…
    </div>
  ),
});

/**
 * Kept in sync with the `allowed_categories` values used by
 * category_restriction rules in the seed data. A free-text category that
 * matches none of these simply never triggers an "Application mismatch",
 * which is the correct, conservative outcome.
 */
const FOOD_CATEGORIES = [
  "Snacks",
  "Beverages",
  "Sweets & Confectionery",
  "Dairy",
  "Meat & Poultry",
  "Street Food",
  "Bakery",
  "Pickles & Condiments",
] as const;



export default function VendorProfilePage() {
  const router = useRouter();
  const [view, setView] = useState<"loading" | "form" | "existing">("loading");
  const [existingStall, setExistingStall] = useState<Stall | null>(null);

  const [stallName, setStallName] = useState("");
  const [foodCategory, setFoodCategory] = useState("");
  const [productsUsed, setProductsUsed] = useState("");
  const [address, setAddress] = useState("");
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(
    null
  );
  const [phone, setPhone] = useState("");
  const [language, setLanguage] = useState("en");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VendorOnboardResponse | null>(null);

  /** Decide between the onboarding form and an existing-stall summary. */
  const load = useCallback(async () => {
    try {
      const me = await api.me();
      setLanguage(me.preferred_language ?? "en");

      if (me.vendor_id === null) {
        setView("form");
        return;
      }

      const stalls = await api.myStalls();
      if (stalls.length === 0) {
        setView("form");
        return;
      }

      const stall = stalls[0];
      setExistingStall(stall);
      // Pre-fill so the form doubles as an edit form.
      setStallName(stall.name);
      setFoodCategory(stall.food_category ?? "");
      setAddress(stall.address ?? "");
      if (stall.latitude !== null && stall.longitude !== null) {
        setLocation({ lat: stall.latitude, lng: stall.longitude });
      }
      setView("existing");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // The proxy should have caught this; if the token expired between
        // page load and this call, send them back to sign in.
        router.push("/login?next=/vendor");
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "Could not load your profile."
      );
      setView("form");
    }
  }, [router]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const response = await api.onboardVendor({
        phone_number: phone || null,
        preferred_language: language,
        stall: {
          name: stallName.trim(),
          food_category: foodCategory || null,
          address: address.trim() || null,
          latitude: location?.lat ?? null,
          longitude: location?.lng ?? null,
        },
        food_items: productsUsed
          .split(/[,\n]/)
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setResult(response);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not register your stall. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "block w-full rounded-xl border-0 px-4 py-3 text-base text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-600";
  const labelClass = "block text-sm font-semibold leading-6 text-gray-900";

  // --- Success ---
  if (result) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-green-100 text-4xl">
          ✅
        </div>
        <h2 className="mb-2 text-2xl font-bold text-gray-900">
          {result.created ? "Stall registered!" : "Stall updated"}
        </h2>
        <p className="mb-2 text-center text-gray-500">
          <span className="font-medium text-gray-700">{result.stall.name}</span>{" "}
          is ready. You can now scan product labels.
        </p>
        <p className="mb-8 text-center text-xs text-gray-400">
          Stall ID: {result.stall.qr_code_id}
        </p>
        <Link
          href="/vendor/scan"
          className="w-full rounded-full bg-blue-600 px-4 py-3 text-center text-sm font-semibold text-white shadow-sm hover:bg-blue-500"
        >
          Scan a product label
        </Link>
      </div>
    );
  }

  if (view === "loading") {
    return (
      <div className="flex h-full items-center justify-center p-6 text-gray-400">
        Loading…
      </div>
    );
  }

  return (
    <div className="p-6 pb-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          {view === "existing" ? "Your Stall" : "Create your Stall"}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          {view === "existing"
            ? "Update your stall details at any time."
            : "Fill in the details to register your food stall."}
        </p>
      </div>

      {view === "existing" && existingStall && (
        <div className="mb-6 rounded-xl bg-green-50 p-4 ring-1 ring-inset ring-green-200">
          <p className="text-sm text-green-800">
            Your stall is registered.{" "}
            <Link href="/vendor/scan" className="font-semibold underline">
              Scan a product label →
            </Link>
          </p>
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="mb-5 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200"
        >
          {error}
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label htmlFor="stallName" className={labelClass}>
            Stall Name
          </label>
          <div className="mt-1">
            <input
              id="stallName"
              type="text"
              required
              value={stallName}
              onChange={(e) => setStallName(e.target.value)}
              className={inputClass}
              placeholder="e.g. Ramesh Vada Pav"
            />
          </div>
        </div>

        <div>
          <label htmlFor="foodCategory" className={labelClass}>
            Food Category
          </label>
          <p className="mb-1 text-xs text-gray-500">
            Used to check whether an ingredient is permitted in what you sell.
          </p>
          <div className="mt-1">
            <select
              id="foodCategory"
              value={foodCategory}
              onChange={(e) => setFoodCategory(e.target.value)}
              className={inputClass}
            >
              <option value="">Select a category…</option>
              {FOOD_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="productsUsed" className={labelClass}>
            Products Used <span className="font-normal text-gray-400">(optional)</span>
          </label>
          <div className="mt-1">
            <textarea
              id="productsUsed"
              rows={2}
              value={productsUsed}
              onChange={(e) => setProductsUsed(e.target.value)}
              className={inputClass}
              placeholder="e.g. Refined oil, Tamarind chutney, Sev"
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>Stall Location</label>
          <p className="mb-2 mt-1 text-xs text-gray-500">
            Allow location access to auto-detect your position, or tap the map
            to pin it manually.
          </p>
          <MapPicker
            onLocationSelect={(lat, lng) => setLocation({ lat, lng })}
          />
          {location && (
            <p className="mt-2 text-xs text-green-600">
              📍 Pinned: {location.lat.toFixed(4)}, {location.lng.toFixed(4)}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="address" className={labelClass}>
            Address
          </label>
          <div className="mt-1">
            <input
              id="address"
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className={inputClass}
              placeholder="e.g. Near Station Road"
            />
          </div>
        </div>

        <div>
          <label htmlFor="phone" className={labelClass}>
            Phone <span className="font-normal text-gray-400">(optional)</span>
          </label>
          <div className="mt-1">
            <input
              id="phone"
              type="tel"
              inputMode="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className={inputClass}
              placeholder="+91 98765 43210"
            />
          </div>
        </div>

        <div>
          <label htmlFor="language" className={labelClass}>
            Preferred Language
          </label>
          <p className="mb-1 text-xs text-gray-500">
            Scan results and explanations will be shown in this language.
          </p>
          <div className="mt-1">
            <select
              id="language"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className={inputClass}
            >
              <option value="en">English</option>
              <option value="hi">हिंदी (Hindi)</option>
              <option value="mr">मराठी (Marathi)</option>
            </select>
          </div>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-full bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-60"
          >
            {submitting
              ? "Saving…"
              : view === "existing"
                ? "Save changes"
                : "Register Stall"}
          </button>
        </div>
      </form>
    </div>
  );
}
