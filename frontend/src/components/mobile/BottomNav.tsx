"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Thumb-reachable bottom navigation for the mobile (vendor/consumer) shells.
 *
 * Client component because `usePathname` is a client hook — layouts are
 * Server Components by default and cannot use it directly.
 *
 * Large tap targets (min 44px) and safe-area padding are deliberate: this is
 * used one-handed, outdoors, by someone who is also watching a stall.
 */

interface NavItem {
  href: string;
  label: string;
  icon: string;
  /** Not built yet — rendered as a disabled control rather than a dead link
   * that 404s. */
  comingSoon?: boolean;
}

const VENDOR_ITEMS: NavItem[] = [
  { href: "/vendor/scan", label: "Scan", icon: "📷" },
  { href: "/vendor/hygiene", label: "Hygiene", icon: "✨" },
  { href: "/vendor/qr", label: "My QR", icon: "🔳" },
  { href: "/vendor/profile", label: "Profile", icon: "👤" },
];

const CONSUMER_ITEMS: NavItem[] = [
  { href: "/consumer", label: "Map", icon: "🗺️" },
  { href: "/consumer/scan", label: "Scan", icon: "📷" },
  { href: "/consumer/profile", label: "Profile", icon: "👤" },
];

export default function BottomNav() {
  const pathname = usePathname();

  const isConsumer = pathname.startsWith("/consumer") || pathname.startsWith("/stall");
  const items = isConsumer ? CONSUMER_ITEMS : VENDOR_ITEMS;

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-gray-200 bg-white"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label="Main"
    >
      <div className="mx-auto flex max-w-md justify-around" suppressHydrationWarning>
        {items.map((item) => {
          const active =
            pathname === item.href || (item.href !== "/consumer" && pathname.startsWith(`${item.href}/`));

          if (item.comingSoon) {
            return (
              <div
                key={item.href}
                aria-disabled="true"
                className="flex min-h-[56px] flex-1 cursor-not-allowed flex-col items-center justify-center py-2 text-gray-300"
              >
                <span className="text-xl" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="mt-1 text-xs">
                  {item.label}
                  <span className="sr-only"> (coming soon)</span>
                </span>
              </div>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-[56px] flex-1 flex-col items-center justify-center py-2 ${
                active ? "text-blue-600" : "text-gray-500 hover:text-blue-600"
              }`}
            >
              <span className="text-xl" aria-hidden="true">
                {item.icon}
              </span>
              <span className="mt-1 text-xs font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

