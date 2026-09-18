"use client";

import type { ScanResult } from "@/lib/types";

export default function ProductComparison({
  result1,
  result2,
  onReset,
}: {
  result1: ScanResult;
  result2: ScanResult;
  onReset: () => void;
}) {
  // Simple heuristic for "Better Choice" based on rule strength.
  // Higher rule_strength is generally worse (more violations). Lower is better.
  // If rule_strength is missing or equal, check confidence_score (higher is better).
  // Status check could also be added.

  const getScore = (r: ScanResult) => {
    // If suitable, that's best.
    let statusScore = 0;
    if (r.status === "Suitable") statusScore = 100;
    else if (r.status === "Potential concern") statusScore = 50;
    else if (r.status === "Needs review") statusScore = 40;
    else if (r.status === "Insufficient information") statusScore = 20;
    else statusScore = 0; // Application mismatch or worse

    // Deduct points based on rule strength (assuming higher = worse, e.g. 0 to 1)
    const rulePenalty = (r.rule_strength ?? 0) * 10;
    return statusScore - rulePenalty + (r.confidence_score ?? 0);
  };

  const score1 = getScore(result1);
  const score2 = getScore(result2);

  let betterChoice = 0; // 0 = tie, 1 = result1, 2 = result2
  if (score1 > score2) betterChoice = 1;
  else if (score2 > score1) betterChoice = 2;

  const renderProductColumn = (r: ScanResult, isBetter: boolean, label: string) => (
    <div className={`flex flex-col gap-3 rounded-2xl p-5 ${isBetter ? "bg-surface-dark ring-2 ring-surface-dark shadow-[0_4px_12px_rgba(11,69,22,0.2)]" : "bg-white ring-1 ring-border-default/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)]"}`}>
      <div className="flex justify-between items-start">
        <h3 className={`font-extrabold font-['Plus_Jakarta_Sans'] ${isBetter ? "text-text-inverse" : "text-text-primary"}`}>{label}</h3>
        {isBetter && (
          <span className="rounded-full bg-[#FFE714] px-3 py-1 text-[10px] uppercase tracking-widest font-extrabold text-[#10220F] font-['Plus_Jakarta_Sans']">
            Better Choice
          </span>
        )}
      </div>

      <div className="text-sm">
        <span className={`block text-[11px] font-bold font-['Plus_Jakarta_Sans'] uppercase tracking-widest mb-1 ${isBetter ? "text-text-inverse/70" : "text-text-primary/50"}`}>Status</span>
        <span className={`font-bold font-['Inter'] ${isBetter ? "text-text-inverse" : "text-text-primary"}`}>{r.status}</span>
      </div>

      <div className="text-sm">
        <span className={`block text-[11px] font-bold font-['Plus_Jakarta_Sans'] uppercase tracking-widest mb-1 ${isBetter ? "text-text-inverse/70" : "text-text-primary/50"}`}>Rule Strength</span>
        <span className={`font-bold font-['Inter'] ${isBetter ? "text-text-inverse" : "text-text-primary"}`}>
          {r.rule_strength === null ? "—" : `${Math.round(r.rule_strength * 100)}%`}
        </span>
      </div>

      <div className="text-sm">
        <span className={`block text-[11px] font-bold font-['Plus_Jakarta_Sans'] uppercase tracking-widest mb-1 ${isBetter ? "text-text-inverse/70" : "text-text-primary/50"}`}>Explanation</span>
        <p className={`line-clamp-4 font-medium text-[13px] font-['Inter'] leading-relaxed ${isBetter ? "text-text-inverse/90" : "text-text-primary/80"}`}>{r.explanation_translated || r.explanation}</p>
      </div>
      
      {r.matched_ingredients.length > 0 && (
        <div className="mt-2 text-sm pt-3 border-t border-border-default/10">
           <span className={`block text-[11px] font-bold font-['Plus_Jakarta_Sans'] uppercase tracking-widest mb-2 ${isBetter ? "text-text-inverse/70" : "text-text-primary/50"}`}>Ingredients Found ({r.matched_ingredients.length})</span>
           <div className="flex flex-wrap gap-1.5">
            {r.matched_ingredients.slice(0, 3).map((ing) => (
               <span key={ing.ingredient_id} className={`inline-block rounded-full px-2.5 py-1 text-[10px] font-bold font-['Inter'] ${isBetter ? "bg-white/20 text-white" : "bg-surface-soft text-text-primary/70"}`}>
                 {ing.canonical_name}
               </span>
            ))}
            {r.matched_ingredients.length > 3 && (
               <span className={`inline-block rounded-full px-2.5 py-1 text-[10px] font-bold font-['Inter'] ${isBetter ? "bg-white/20 text-white" : "bg-surface-soft text-text-primary/70"}`}>
                 +{r.matched_ingredients.length - 3} more
               </span>
            )}
           </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="flex h-full flex-col p-5 pb-8 overflow-y-auto bg-brand-bg">
      <h2 className="mb-6 text-2xl font-extrabold text-text-primary font-['Plus_Jakarta_Sans']">Product Comparison</h2>
      
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {renderProductColumn(result1, betterChoice === 1, "Product 1")}
        {renderProductColumn(result2, betterChoice === 2, "Product 2")}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="mt-8 w-full rounded-full bg-surface-dark px-4 py-4 text-sm font-bold text-text-inverse font-['Plus_Jakarta_Sans'] shadow-[0_4px_12px_rgba(11,69,22,0.2)]"
      >
        Done Comparing
      </button>
    </div>
  );
}
