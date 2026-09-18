import BottomNav from "@/components/mobile/BottomNav";

/**
 * Mobile-first shell for vendor and consumer routes.
 *
 * Constrained to a phone-width column even on a desktop browser so the
 * layout is always reviewed at its real proportions, and padded at the
 * bottom so content is never hidden behind the fixed nav.
 */
export default function MobileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-[#FFFCEB]" suppressHydrationWarning>
      <main className="relative mx-auto w-full max-w-md flex-1 overflow-y-auto bg-white shadow-[0_4px_14px_rgba(16,34,15,0.10)]">
        {children}
      </main>

      <BottomNav />
      {/* Spacer matching the nav height so the last element stays reachable. */}
      <div
        className="h-16"
        style={{ marginBottom: "env(safe-area-inset-bottom)" }}
        aria-hidden="true"
        suppressHydrationWarning
      />
    </div>
  );
}
