"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { fetchPublicStallsMap } from "@/lib/api";
import type { PublicStallLocation } from "@/lib/types";

// Leaflet requires window, so we must load the map dynamically
const ReviewerMap = dynamic(() => import("./ReviewerMapComponent"), { ssr: false });

export default function MapPage() {
  const [stalls, setStalls] = useState<PublicStallLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPublicStallsMap()
      .then((data) => {
        setStalls(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load stalls for map");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-gray-900">Hygiene Map</h1>
        <p className="mt-1 text-sm text-gray-600">
          Geospatial view of all registered stalls and their latest hygiene scores.
        </p>
      </div>
      
      <div className="relative flex-1 rounded-lg overflow-hidden ring-1 ring-inset ring-gray-200">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
            <p className="text-sm text-gray-500">Loading map data…</p>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}
        {!loading && !error && <ReviewerMap stalls={stalls} />}
      </div>
    </div>
  );
}
