import Link from "next/link";

import SignOutButton from "@/components/reviewer/SignOutButton";

export default function DesktopLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#FFFCEB]">
      {/* Sidebar — DESIGN.md forest-green */}
      <aside className="w-64 bg-[#0B4516] text-[#FFFCEB] flex-shrink-0 flex flex-col">
        <div className="p-4 h-16 flex items-center gap-3 border-b border-[#35C56D]/20">
          <div className="w-8 h-8 rounded-full bg-[#FFFCEB]/15 flex items-center justify-center">
            <span className="text-[#FFFCEB] text-sm font-bold font-['Plus_Jakarta_Sans']">S</span>
          </div>
          <div className="flex flex-col">
            <h1 className="text-sm font-bold tracking-tight font-['Plus_Jakarta_Sans']">SafeStreet AI</h1>
            <span className="text-[9px] text-[#FFFCEB]/40 uppercase tracking-widest font-semibold">Reviewer Portal</span>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
          <ul className="space-y-1 px-3">
            <li>
              <Link href="/reviewer" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[#FFFCEB]/80 hover:bg-[#35C56D]/15 hover:text-[#FFFCEB] transition-colors text-sm font-semibold font-['Plus_Jakarta_Sans']">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
                Vendors
              </Link>
            </li>
            <li>
              <Link href="/reviewer/flagged" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[#FFFCEB]/80 hover:bg-[#35C56D]/15 hover:text-[#FFFCEB] transition-colors text-sm font-semibold font-['Plus_Jakarta_Sans']">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" /></svg>
                Flagged Stalls
              </Link>
            </li>
            <li>
              <Link href="/reviewer/map" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[#FFFCEB]/80 hover:bg-[#35C56D]/15 hover:text-[#FFFCEB] transition-colors text-sm font-semibold font-['Plus_Jakarta_Sans']">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>
                Hygiene Map
              </Link>
            </li>
            <li>
              <Link href="/reviewer/analytics" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[#FFFCEB]/80 hover:bg-[#35C56D]/15 hover:text-[#FFFCEB] transition-colors text-sm font-semibold font-['Plus_Jakarta_Sans']">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                Analytics
              </Link>
            </li>
            <li>
              <Link href="/reviewer/audit" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[#FFFCEB]/80 hover:bg-[#35C56D]/15 hover:text-[#FFFCEB] transition-colors text-sm font-semibold font-['Plus_Jakarta_Sans']">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" /></svg>
                Audit Trail
              </Link>
            </li>
          </ul>
        </nav>

        <div className="p-4 border-t border-[#35C56D]/20">
          <SignOutButton />
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white border-b border-[#10220F]/10 flex items-center px-8 shadow-[0_2px_8px_rgba(16,34,15,0.04)]">
          <h2 className="text-base font-bold text-[#10220F] font-['Plus_Jakarta_Sans']">Reviewer Dashboard</h2>
        </header>
        <div className="flex-1 overflow-y-auto p-8 bg-[#FFFCEB]">
          {children}
        </div>
      </main>
    </div>
  );
}
