import Link from "next/link";

/**
 * Editorial landing page for Smart Street Food Safety AI.
 * Adapted from the reference HTML with DESIGN.md tokens.
 */
export default function Home() {
  return (
    <main className="w-full min-h-screen bg-[#FFFCEB]">
      {/* ===== HEADER / NAV ===== */}
      <header className="fixed top-0 w-full z-50 bg-[#FFFCEB]/90 backdrop-blur-xl border-b border-[#10220F]/10">
        <div className="h-16 max-w-7xl mx-auto px-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-[#0B4516] flex items-center justify-center">
              <span className="text-[#FFFCEB] text-lg font-bold font-['Plus_Jakarta_Sans']">S</span>
            </div>
            <div className="flex flex-col">
              <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#10220F] text-sm leading-tight">SafeStreet AI</span>
              <span className="text-[10px] font-semibold text-[#10220F]/50 uppercase tracking-widest">Civic Food Safety</span>
            </div>
          </div>

          <nav className="hidden lg:flex items-center gap-1 p-1 rounded-full bg-[#EDF2C8]/60">
            <Link href="#ecosystem" className="px-4 py-1.5 rounded-full text-xs font-semibold text-[#10220F]/70 hover:bg-[#EDF2C8] transition-colors">The Ecosystem</Link>
            <Link href="#dual-journey" className="px-4 py-1.5 rounded-full text-xs font-semibold text-[#10220F]/70 hover:bg-[#EDF2C8] transition-colors">For Vendors</Link>
            <Link href="#map" className="px-4 py-1.5 rounded-full text-xs font-semibold bg-[#0B4516] text-[#FFFCEB]">Hygiene Map</Link>
            <Link href="#scoring" className="px-4 py-1.5 rounded-full text-xs font-semibold text-[#10220F]/70 hover:bg-[#EDF2C8] transition-colors">How It Works</Link>
            <Link href="/reviewer" className="px-4 py-1.5 rounded-full text-xs font-semibold text-[#10220F]/70 hover:bg-[#EDF2C8] transition-colors">Reviewer Portal</Link>
          </nav>

          <div className="flex items-center gap-2">
            <Link href="/consumer" className="hidden sm:inline-flex items-center px-4 py-2 rounded-full text-xs font-semibold bg-[#0B4516] text-[#FFFCEB] hover:bg-[#0B4516]/90 transition-colors">
              Explore Map
            </Link>
            <Link href="/login" className="w-8 h-8 rounded-full bg-[#0B4516] flex items-center justify-center">
              <svg className="w-4 h-4 text-[#FFFCEB]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
            </Link>
          </div>
        </div>
      </header>

      {/* ===== HERO SECTION ===== */}
      <section className="relative w-full overflow-hidden px-5 pt-28 pb-16 lg:pt-36 lg:pb-24">
        <div className="absolute top-1/4 -right-40 w-96 h-96 bg-[#35C56D]/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-10 -left-20 w-80 h-80 bg-[#FFE714]/15 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center relative z-10">
          {/* Left Column */}
          <div className="flex flex-col gap-5">
            <div className="inline-flex items-center gap-2 self-start px-3 py-1 rounded-full bg-[#0B4516]/10 text-[#0B4516]">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              <span className="text-[10px] font-bold uppercase tracking-widest font-['Plus_Jakarta_Sans']">Spatial Civic Surveillance • Mumbai</span>
            </div>

            <h1 className="font-['Plus_Jakarta_Sans'] text-[#10220F] text-4xl sm:text-5xl lg:text-[56px] font-extrabold tracking-tight leading-[1.08]">
              Street food is everywhere.{" "}
              <span className="text-[#0B4516] underline decoration-[#FFE714] decoration-wavy decoration-4 underline-offset-4">
                Now, its hygiene story is too.
              </span>
            </h1>

            <p className="text-[#10220F]/70 text-base lg:text-lg max-w-xl font-['Inter'] leading-relaxed">
              Discover local chaat, dosa, and pav bhaji stalls through real-time AI hygiene intelligence. From oil freshness to covered storage, every cart tells an open story.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link href="/consumer" className="px-6 py-3 rounded-full bg-[#0B4516] text-[#FFFCEB] font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-lg hover:bg-[#0B4516]/90 transition-all flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>
                Explore Hygiene Map
              </Link>
              <Link href="#dual-journey" className="px-6 py-3 rounded-full bg-[#EDF2C8] text-[#10220F] font-['Plus_Jakarta_Sans'] font-bold text-sm hover:bg-[#D8E86B] transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" /></svg>
                How Citizens Scan
              </Link>
            </div>

            {/* Telemetry Pills */}
            <div className="grid grid-cols-3 gap-3 pt-4">
              <div className="p-3 rounded-xl bg-white border border-[#10220F]/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)] flex flex-col">
                <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#0B4516] text-xl">142</span>
                <span className="text-[10px] font-semibold text-[#10220F]/50 font-['Plus_Jakarta_Sans']">Verified Stalls</span>
              </div>
              <div className="p-3 rounded-xl bg-white border border-[#10220F]/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)] flex flex-col">
                <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#35C56D] text-xl">88%</span>
                <span className="text-[10px] font-semibold text-[#10220F]/50 font-['Plus_Jakarta_Sans']">Oil Compliance</span>
              </div>
              <div className="p-3 rounded-xl bg-white border border-[#10220F]/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)] flex flex-col">
                <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#FFE714] text-xl drop-shadow-sm">Zero-App</span>
                <span className="text-[10px] font-semibold text-[#10220F]/50 font-['Plus_Jakarta_Sans']">Web QR Scan</span>
              </div>
            </div>
          </div>

          {/* Right Column: GIS Map Card */}
          <div className="relative">
            <div className="relative w-full rounded-2xl overflow-hidden bg-white border border-[#10220F]/10 shadow-[0_4px_14px_rgba(16,34,15,0.10)]">
              <div className="w-full px-4 py-3 bg-[#0B4516] text-[#FFFCEB] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#35C56D] animate-pulse" />
                  <span className="text-xs font-semibold font-['Plus_Jakarta_Sans']">Live Civic Feed • Mumbai</span>
                </div>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#FFFCEB]/15">Radius: 1.2 km</span>
              </div>

              <div className="relative w-full h-[380px] bg-gradient-to-br from-[#EDF2C8] to-[#F7F5C7] flex items-center justify-center overflow-hidden">
                {/* SVG Radar */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="58%" cy="48%" r="90" fill="none" stroke="#35C56D" strokeWidth="1.5" strokeDasharray="4 4" className="animate-pulse" />
                  <circle cx="58%" cy="48%" r="160" fill="none" stroke="#0B4516" strokeWidth="1" opacity="0.25" />
                </svg>

                {/* Map Pin 1 */}
                <div className="absolute top-16 left-8 p-1.5 rounded-full bg-[#35C56D] text-white shadow-md flex items-center gap-1 text-[11px] font-bold font-['Plus_Jakarta_Sans']">
                  🍜 <span className="pr-1">Gupta Pav Bhaji</span>
                </div>

                {/* Map Pin 2 */}
                <div className="absolute bottom-20 left-16 p-1.5 rounded-full bg-[#FFE714] text-[#10220F] shadow-md flex items-center gap-1 text-[11px] font-bold font-['Plus_Jakarta_Sans']">
                  ⚠️ <span className="pr-1">Oil Re-test Due</span>
                </div>

                {/* Featured Stall Card */}
                <div className="absolute top-24 right-4 w-64 sm:w-72 rounded-xl bg-white shadow-xl p-4 border border-[#10220F]/10 z-20">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex flex-col">
                      <span className="px-2 py-0.5 rounded-full bg-[#35C56D]/15 text-[#0B4516] text-[10px] font-bold self-start mb-1 flex items-center gap-1">
                        ✓ FSSAI Verified
                      </span>
                      <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-[#10220F] text-sm">Sharma Ji Chaat Corner</h2>
                      <span className="text-[10px] text-[#10220F]/50">Lakhamshi Napoo Rd, Matunga</span>
                    </div>
                    <div className="w-12 h-12 rounded-full bg-[#35C56D]/15 flex flex-col items-center justify-center shrink-0">
                      <span className="font-['Plus_Jakarta_Sans'] font-extrabold text-[#0B4516] text-lg leading-none">88</span>
                      <span className="text-[8px] font-bold text-[#35C56D] uppercase">High</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-[10px] font-semibold text-[#10220F] font-['Plus_Jakarta_Sans']">
                    <div className="flex items-center gap-1 bg-[#EDF2C8]/60 px-2 py-1 rounded">💧 RO Water</div>
                    <div className="flex items-center gap-1 bg-[#EDF2C8]/60 px-2 py-1 rounded">🛢️ TPM 14%</div>
                    <div className="flex items-center gap-1 bg-[#EDF2C8]/60 px-2 py-1 rounded">🛡️ 4-Angle Pass</div>
                    <div className="flex items-center gap-1 bg-[#EDF2C8]/60 px-2 py-1 rounded">🕐 Today 8:30 AM</div>
                  </div>
                </div>
              </div>

              <div className="p-3 bg-[#EDF2C8]/40 flex items-center justify-between text-[10px] font-semibold text-[#10220F]/60 font-['Plus_Jakarta_Sans']">
                <span>OpenCivic StreetGrid v4.2</span>
                <span className="text-[#0B4516] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#35C56D]" /> 4,892 Scans Today
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== NARRATIVE: 5-STAGE PIPELINE ===== */}
      <section className="w-full px-5 py-16 bg-[#FFFCEB]" id="ecosystem">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5 flex flex-col gap-4">
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#FFE714] font-['Plus_Jakarta_Sans'] drop-shadow-sm">The Living City</span>
            <h2 className="font-['Plus_Jakarta_Sans'] text-[#10220F] text-3xl lg:text-4xl font-extrabold tracking-tight leading-tight">
              40 Million Street Vendors Feed Working India Daily.
            </h2>
            <p className="text-[#10220F]/70 text-sm leading-relaxed font-['Inter']">
              From sunrise chaiwalas outside railway terminals to midnight dosa carts beside college hubs, informal gastronomy is the lifeblood of urban culture. Vendors take immense pride in their recipes, yet lacked a credible, low-cost proof of hygiene. SafeStreet AI builds that bridge without punitive fines.
            </p>
          </div>

          <div className="lg:col-span-7 bg-white rounded-2xl p-6 border border-[#10220F]/10 shadow-[0_4px_14px_rgba(16,34,15,0.10)]">
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#0B4516] font-['Plus_Jakarta_Sans'] mb-4 block">The Civic Transformation Pipeline</span>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
              {[
                { num: "01", label: "UNKNOWN", title: "Invisible Practices", desc: "No data on oil freshness or water purity.", color: "#E53935" },
                { num: "02", label: "VISIBLE", title: "Street Geotagging", desc: "Carts mapped into ward directories.", color: "#FFE714" },
                { num: "03", label: "UNDERSTAND", title: "AI Explanations", desc: "Camera feeds become hygiene tokens.", color: "#0B4516" },
                { num: "04", label: "ACTIONABLE", title: "Vendor Guidance", desc: "Daily prompts in Hindi/Marathi.", color: "#35C56D" },
                { num: "05", label: "TRUST", title: "Transparent Carts", desc: "Consumer scans with confidence.", color: "#0B4516" },
              ].map((step) => (
                <div key={step.num} className="flex flex-col gap-1 p-3 rounded-xl bg-[#FFFCEB] border border-[#10220F]/08">
                  <span className="text-[10px] font-extrabold tracking-widest font-['Plus_Jakarta_Sans']" style={{ color: step.color }}>{step.num} • {step.label}</span>
                  <span className="text-xs font-bold text-[#10220F] font-['Plus_Jakarta_Sans']">{step.title}</span>
                  <p className="text-[10px] text-[#10220F]/50 font-['Inter']">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ===== DUAL JOURNEY SHOWCASE ===== */}
      <section className="w-full px-5 py-16 bg-[#EDF2C8]/40" id="dual-journey">
        <div className="max-w-7xl mx-auto flex flex-col gap-8">
          <div className="flex flex-col gap-2">
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#0B4516] font-['Plus_Jakarta_Sans']">Stakeholder Journeys</span>
            <h2 className="font-['Plus_Jakarta_Sans'] text-[#10220F] text-3xl lg:text-4xl font-extrabold tracking-tight">
              Designed for Streets, Screens & Municipal Transparency
            </h2>
          </div>

          {/* Consumer Journey Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {[
              { icon: "🗺️", title: "1. Geospatial Discovery", desc: "Open your mobile browser to scan certified food stalls within walking distance. Filter by cuisine, FSSAI verification, or high cleanliness score.", tag: "No app download • Web-first PWA", tagColor: "#0B4516" },
              { icon: "📱", title: "2. Countertop QR Scan", desc: "While waiting for your Sev Puri, point your standard camera at the cart's acrylic standee. Instantly load the stall's tamper-evident telemetry sheet.", tag: "Verified in < 1.4 seconds on 4G", tagColor: "#FFE714" },
              { icon: "⭐", title: "3. Explainable Safety & Feedback", desc: "See why the cart earned 88/100: Oil freshness (TPM 14%), potable water test date, and hairnet check. Leave civic feedback to support the vendor.", tag: "Grassroots accountability", tagColor: "#35C56D" },
            ].map((card) => (
              <div key={card.title} className="p-6 rounded-2xl bg-white border border-[#10220F]/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)] flex flex-col justify-between">
                <div className="flex flex-col gap-3">
                  <span className="text-2xl">{card.icon}</span>
                  <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-[#10220F] text-base">{card.title}</h3>
                  <p className="text-sm text-[#10220F]/60 font-['Inter'] leading-relaxed">{card.desc}</p>
                </div>
                <div className="mt-4 p-2 rounded-lg bg-[#EDF2C8]/60 text-[11px] font-semibold font-['Plus_Jakarta_Sans']" style={{ color: card.tagColor }}>
                  {card.tag}
                </div>
              </div>
            ))}
          </div>

          {/* Vendor Journey Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {[
              { icon: "📸", title: "1. Guided 4-Angle Morning Check", desc: "AI audio in Hindi or Marathi guides 4 snapshots: Work Counter, Prep Area, Food Covers, and Waste Bin.", tag: "Voice-guided in 8 Indian languages", tagColor: "#0B4516" },
              { icon: "🔍", title: "2. Oil Label & Ingestion OCR", desc: "Point phone camera at packaged cooking oil or ingredient pouches. Edge AI reads manufacturing batch dates and warns against banned adulterants.", tag: "Protects vendors against counterfeits", tagColor: "#FFE714" },
              { icon: "🏆", title: "3. Countertop Trust Standee", desc: "Score automatically updates the acrylic standee. Higher hygiene scores directly drive up to 34% more daily footfall.", tag: "Micro-certification unlocks PM SVANidhi", tagColor: "#35C56D" },
            ].map((card) => (
              <div key={card.title} className="p-6 rounded-2xl bg-white border border-[#10220F]/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)] flex flex-col justify-between">
                <div className="flex flex-col gap-3">
                  <span className="text-2xl">{card.icon}</span>
                  <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-[#10220F] text-base">{card.title}</h3>
                  <p className="text-sm text-[#10220F]/60 font-['Inter'] leading-relaxed">{card.desc}</p>
                </div>
                <div className="mt-4 p-2 rounded-lg bg-[#EDF2C8]/60 text-[11px] font-semibold font-['Plus_Jakarta_Sans']" style={{ color: card.tagColor }}>
                  {card.tag}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== SCORING EXPLAINER ===== */}
      <section className="w-full px-5 py-16 bg-[#FFFCEB]" id="scoring">
        <div className="max-w-7xl mx-auto flex flex-col gap-8">
          <div className="text-center max-w-2xl mx-auto flex flex-col gap-2">
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#0B4516] font-['Plus_Jakarta_Sans']">Algorithmic Accountability</span>
            <h2 className="font-['Plus_Jakarta_Sans'] text-[#10220F] text-3xl lg:text-4xl font-extrabold tracking-tight">
              Transparent 4-Tier Scoring Metric
            </h2>
            <p className="text-sm text-[#10220F]/60 font-['Inter']">
              No black boxes. Stall scores are open, reproducible, and explainable to both vendors and patrons.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { range: "80 – 100", label: "High Hygiene", desc: "Exemplary compliance. Fresh cooking oil, clean covered prep surface, verified potable water source.", color: "#35C56D", bgColor: "#35C56D15", status: "Fully Certified Cart" },
              { range: "60 – 79", label: "Moderate / Safe", desc: "Safe baseline met. Minor advisories such as unclipped storage lids or end-of-day oil change.", color: "#0B4516", bgColor: "#0B451615", status: "Standard Guidance Active" },
              { range: "40 – 59", label: "Needs Improvement", desc: "Elevated TPM oil readings or uncovered prepped ingredients. Instant SMS coaching sent.", color: "#F59E0B", bgColor: "#F59E0B15", status: "Remediation Window Open" },
              { range: "0 – 39", label: "Immediate Action", desc: "Critical water contamination or unpotable oil breach detected. Ward health inspectors dispatched.", color: "#E53935", bgColor: "#E5393515", status: "Field Support Dispatched" },
            ].map((tier) => (
              <div key={tier.range} className="p-5 rounded-2xl bg-white border border-[#10220F]/10 shadow-[0_2px_8px_rgba(16,34,15,0.06)] flex flex-col justify-between">
                <div className="flex flex-col gap-2">
                  <span className="px-3 py-1 rounded-full font-['Plus_Jakarta_Sans'] font-extrabold text-lg self-start" style={{ backgroundColor: tier.bgColor, color: tier.color }}>
                    {tier.range}
                  </span>
                  <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-[#10220F] text-base mt-2">{tier.label}</h3>
                  <p className="text-xs text-[#10220F]/50 font-['Inter'] leading-relaxed">{tier.desc}</p>
                </div>
                <div className="mt-4 pt-2 text-[11px] font-bold font-['Plus_Jakarta_Sans']" style={{ color: tier.color }}>
                  Status: {tier.status}
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-xl bg-white border border-[#10220F]/10 flex items-start gap-3 text-xs text-[#10220F]/60 font-['Inter']">
            <span className="text-lg">⚖️</span>
            <p>
              <strong className="text-[#10220F]">Civic Open Disclosure Notice:</strong> SafeStreet AI provides civic decision support and community transparency. It operates in synergy with FSSAI hygiene guidelines and does not replace statutory inspection certificates.
            </p>
          </div>
        </div>
      </section>

      {/* ===== FINAL CTA ===== */}
      <section className="w-full px-5 py-16 bg-[#0B4516]">
        <div className="max-w-7xl mx-auto rounded-3xl bg-[#0B4516] border border-[#35C56D]/20 p-8 sm:p-12 relative overflow-hidden flex flex-col items-center text-center gap-5">
          <div className="absolute -top-16 -right-16 w-64 h-64 bg-[#35C56D]/20 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-16 -left-16 w-64 h-64 bg-[#FFE714]/10 rounded-full blur-3xl pointer-events-none" />

          <span className="px-4 py-1 rounded-full bg-[#FFFCEB]/10 text-[10px] font-bold text-[#FFFCEB] uppercase tracking-widest font-['Plus_Jakarta_Sans'] relative z-10">
            Civic Partnership • Open To All Cities
          </span>

          <h2 className="font-['Plus_Jakarta_Sans'] text-[#FFFCEB] text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight max-w-2xl relative z-10">
            Bring transparency to your street.
          </h2>

          <p className="text-[#FFFCEB]/70 text-base max-w-xl relative z-10 font-['Inter']">
            Whether you are a hungry foodie looking for clean pani puri, a vendor wanting to display your pride, or an urban planner mapping safety metrics — get started today.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-2 relative z-10">
            <Link href="/consumer" className="px-8 py-3.5 rounded-full bg-[#FFFCEB] text-[#0B4516] font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-lg hover:bg-white transition-all flex items-center gap-2">
              🗺️ Launch Interactive Map
            </Link>
            <Link href="/login" className="px-8 py-3.5 rounded-full bg-[#FFE714] text-[#10220F] font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-lg hover:bg-[#FFE714]/90 transition-all flex items-center gap-2">
              🏪 Vendor Onboarding
            </Link>
          </div>

          <div className="pt-4 flex items-center gap-6 text-[10px] font-semibold text-[#FFFCEB]/50 font-['Plus_Jakarta_Sans'] relative z-10">
            <span className="flex items-center gap-1">✓ Zero Hardware Setup</span>
            <span className="flex items-center gap-1">✓ Works on Any Smartphone</span>
            <span className="flex items-center gap-1">✓ Public Civic API</span>
          </div>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="w-full bg-[#0B4516] border-t border-[#35C56D]/20">
        <div className="max-w-7xl mx-auto px-5 py-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-8">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">🛡️</span>
                <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#FFFCEB]">SafeStreet AI</span>
              </div>
              <p className="text-xs text-[#FFFCEB]/50 font-['Inter'] leading-relaxed">
                Open civic infrastructure bridging informal street gastronomy with certified bio-safety standards and digital empowerment.
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#35C56D] text-sm">Public Network</span>
              <ul className="flex flex-col gap-1.5 text-xs text-[#FFFCEB]/50 font-['Inter']">
                <li className="hover:text-[#FFFCEB] transition-colors cursor-pointer">Independent Food Safety Registry</li>
                <li className="hover:text-[#FFFCEB] transition-colors cursor-pointer">Vendor Micro-Certification Standards</li>
                <li className="hover:text-[#FFFCEB] transition-colors cursor-pointer">Rapid Test Strip Distribution</li>
              </ul>
            </div>
            <div className="flex flex-col gap-3">
              <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#35C56D] text-sm">Regulatory Notice</span>
              <p className="text-xs text-[#FFFCEB]/50 font-['Inter'] leading-relaxed">
                Data provided for civic transparency under urban health observation frameworks. Scores reflect AI and lab verified batch tests.
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <span className="font-['Plus_Jakarta_Sans'] font-bold text-[#35C56D] text-sm">Quick Links</span>
              <ul className="flex flex-col gap-1.5 text-xs text-[#FFFCEB]/50 font-['Inter']">
                <li><Link href="/login" className="hover:text-[#FFFCEB] transition-colors">Vendor Login</Link></li>
                <li><Link href="/reviewer" className="hover:text-[#FFFCEB] transition-colors">Reviewer Dashboard</Link></li>
                <li><Link href="/consumer" className="hover:text-[#FFFCEB] transition-colors">Consumer Map</Link></li>
              </ul>
            </div>
          </div>

          <div className="pt-6 border-t border-[#35C56D]/10 flex flex-col sm:flex-row items-center justify-between gap-4 text-[10px] text-[#FFFCEB]/40 font-['Inter']">
            <p>© 2024 Smart Street Food Safety AI. Developed for Public Civic Safety.</p>
            <div className="flex items-center gap-4">
              <span className="hover:text-[#FFFCEB] transition-colors cursor-pointer">Civic Terms</span>
              <span className="hover:text-[#FFFCEB] transition-colors cursor-pointer">Privacy</span>
              <span className="hover:text-[#FFFCEB] transition-colors cursor-pointer">Open API</span>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
