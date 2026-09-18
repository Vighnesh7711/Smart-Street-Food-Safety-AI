"use client";

import { useState } from "react";

import { resolveImageUrl } from "@/lib/api";
import type { StallImageDetail } from "@/lib/types";

/**
 * Submitted stall photos with their detected indicators.
 *
 * Two things to be honest about:
 *
 *  1. **Boxes are percentages, not pixels.** The detector runs on a
 *     *downscaled* copy of the photo, so its bounding boxes are in that
 *     reduced coordinate space. The backend records those dimensions
 *     (`box_space`), and dividing by them gives a percentage that is correct
 *     at any display size -- and stays correct if the downscale rule ever
 *     changes, which a hardcoded assumption would not.
 *
 *  2. **The overlay is additive, never the only way to see a finding.** The
 *     heuristic provider emits no bounding box at all for several indicators
 *     (utensils, drains), and COCO-backed detections carry a box that may be
 *     a coarse guess. Every detection is therefore listed in text beneath its
 *     photo, whether or not it has a box.
 */

const BOX_STYLES = [
  "border-red-500",
  "border-amber-500",
  "border-orange-500",
  "border-blue-500",
];

export default function StallImageGallery({
  images,
}: {
  images: StallImageDetail[];
}) {
  const [selected, setSelected] = useState<number>(images[0]?.id ?? 0);

  if (images.length === 0) {
    return (
      <div className="rounded-xl bg-white p-8 text-center ring-1 ring-inset ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]">
        <p className="text-sm font-bold text-text-primary/50 font-['Plus_Jakarta_Sans']">
          No stall photos have been submitted yet.
        </p>
      </div>
    );
  }

  const current = images.find((image) => image.id === selected) ?? images[0];
  const url = resolveImageUrl(current.image_url);
  // Captured outside the map so TypeScript keeps the null-check narrowing
  // inside the callback.
  const boxSpace = current.box_space;

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Thumbnails */}
      <div className="col-span-1 space-y-2">
        {images.map((image) => {
          const thumb = resolveImageUrl(image.image_url);
          const active = image.id === current.id;
          return (
            <button
              key={image.id}
              type="button"
              onClick={() => setSelected(image.id)}
              aria-pressed={active}
              className={`block w-full overflow-hidden rounded-xl text-left ring-2 transition-all ${
                active ? "ring-[#35C56D] shadow-md" : "ring-transparent hover:ring-border-default/20"
              }`}
            >
              {thumb ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={thumb}
                  alt={image.view_display_name}
                  className="h-24 w-full object-cover"
                />
              ) : (
                <div className="flex h-24 w-full items-center justify-center bg-brand-bg text-[11px] font-bold text-text-primary/40 font-['Plus_Jakarta_Sans'] uppercase tracking-widest">
                  No image
                </div>
              )}
              <div className="bg-white px-3 py-2 border-t border-border-default/10">
                <div className="text-xs font-bold capitalize text-text-primary font-['Plus_Jakarta_Sans']">
                  {image.view_display_name}
                </div>
                <div className="text-[10px] text-text-primary/60 font-['Inter'] mt-0.5">
                  {image.detected_at
                    ? new Date(image.detected_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                      })
                    : ""}
                  {image.detections.length > 0 &&
                    ` · ${image.detections.length} finding${
                      image.detections.length === 1 ? "" : "s"
                    }`}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected image + findings */}
      <div className="col-span-2">
        <div className="relative overflow-hidden rounded-xl bg-[#0B4516] ring-1 ring-inset ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]">
          {url ? (
            // Plain <img>: this is a user upload served by the API, so
            // next/image would add nothing and would need the API host
            // allow-listed.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={url}
              alt={current.view_display_name}
              className="block max-h-[28rem] w-full object-contain"
            />
          ) : (
            <div className="flex h-72 items-center justify-center text-sm font-bold text-[#FFFCEB]/40 font-['Plus_Jakarta_Sans']">
              Image unavailable
            </div>
          )}

          {/* Detection boxes, positioned as percentages of the coordinate
              space the detector used. */}
          {url &&
            boxSpace &&
            current.detections.map((detection, index) =>
              detection.bbox ? (
                <div
                  key={`${detection.code}-${index}`}
                  className={`pointer-events-none absolute border-2 ${
                    BOX_STYLES[index % BOX_STYLES.length]
                  }`}
                  style={{
                    left: `${(detection.bbox[0] / boxSpace.width) * 100}%`,
                    top: `${(detection.bbox[1] / boxSpace.height) * 100}%`,
                    width: `${
                      ((detection.bbox[2] - detection.bbox[0]) / boxSpace.width) *
                      100
                    }%`,
                    height: `${
                      ((detection.bbox[3] - detection.bbox[1]) /
                        boxSpace.height) *
                      100
                    }%`,
                  }}
                >
                  <span
                    className={`absolute -top-5 left-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium text-white ${
                      index % BOX_STYLES.length === 0
                        ? "bg-red-600"
                        : index % BOX_STYLES.length === 1
                          ? "bg-amber-600"
                          : index % BOX_STYLES.length === 2
                            ? "bg-orange-600"
                            : "bg-blue-600"
                    }`}
                  >
                    {detection.display_name}
                  </span>
                </div>
              ) : null
            )}
        </div>

        {/* Findings, listed regardless of whether they had a box. */}
        <div className="mt-4 rounded-xl bg-white p-5 ring-1 ring-inset ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]">
          <h4 className="text-[11px] font-extrabold uppercase tracking-widest text-text-primary/50 font-['Plus_Jakarta_Sans'] mb-4">
            Detected in this view
          </h4>

          {current.detections.length === 0 ? (
            <p className="mt-2 text-sm text-text-primary/50 font-['Inter']">
              Nothing detected in this photo.
            </p>
          ) : (
            <ul className="mt-2 space-y-2">
              {current.detections.map((detection, index) => (
                <li
                  key={`${detection.code}-list-${index}`}
                  className="flex items-start gap-2 text-sm"
                >
                  <span
                    className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-sm ${
                      index % BOX_STYLES.length === 0
                        ? "bg-red-500"
                        : index % BOX_STYLES.length === 1
                          ? "bg-amber-500"
                          : index % BOX_STYLES.length === 2
                            ? "bg-orange-500"
                            : "bg-blue-500"
                    }`}
                    aria-hidden="true"
                  />
                  <div className="flex flex-col">
                    <div className="text-text-primary font-bold font-['Plus_Jakarta_Sans']">
                      {detection.display_name}
                      <span className="ml-2 text-xs font-semibold tabular-nums text-text-primary/60 font-['Inter']">
                        {Math.round(detection.confidence * 100)}% confidence
                      </span>
                      {/* The raw provider label is shown because the detection
                          is a placeholder mapping -- a reviewer should be able
                          to see that "bottle" became "visible waste". */}
                      {detection.raw_labels.length > 0 && (
                        <span className="ml-2 text-[10px] text-text-primary/40 font-semibold font-['Inter']">
                          (from {detection.raw_labels.join(", ")})
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-text-primary/60 mt-1 font-['Inter']">
                      <span className="font-bold bg-surface-soft rounded px-1.5 py-0.5 uppercase tracking-widest">{detection.view}</span>
                      {detection.penalty > 0 && <span className="ml-2 font-bold text-[#E53935] font-['Plus_Jakarta_Sans']">-{detection.penalty} penalty</span>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {current.quality_issues.length > 0 && (
            <p className="mt-4 rounded-lg bg-[#FFE714]/15 px-3 py-2 text-xs font-medium text-[#10220F] ring-1 ring-inset ring-[#FFE714]/30 font-['Inter']">
              Photo quality: {current.quality_issues.join(", ").replace(/_/g, " ")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
