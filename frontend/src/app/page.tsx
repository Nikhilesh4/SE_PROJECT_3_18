"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/authSession";

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);

  useEffect(() => {
    const syncAuth = () => setIsLoggedIn(Boolean(getToken()));
    syncAuth();
    window.addEventListener("storage", syncAuth);
    window.addEventListener("auth-changed", syncAuth);
    return () => {
      window.removeEventListener("storage", syncAuth);
      window.removeEventListener("auth-changed", syncAuth);
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 relative overflow-hidden">
      {/* Background gradient effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-to-b from-indigo-100 via-sky-50 to-transparent rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-indigo-100/60 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-sky-100/60 rounded-full blur-3xl" />
      </div>

      {/* Hero Section */}
      <main className="relative pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-sm font-medium mb-8">
            <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
            AI-Powered Opportunity Discovery
          </div>

          {/* Heading */}
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
            <span className="text-slate-900">Find Your Next</span>
            <br />
            <span className="bg-gradient-to-r from-indigo-600 via-sky-600 to-indigo-500 bg-clip-text text-transparent">
              Opportunity
            </span>
          </h1>

          {/* Subheading */}
          <p className="text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto mb-10 leading-relaxed">
            UniCompass aggregates internships, hackathons, research positions, and
            online courses from multiple sources — then matches them to your skills
            and interests using AI.
          </p>

          {/* CTA Buttons — auth-aware */}
          <div className="flex items-center justify-center gap-4 min-h-[52px]">
            {isLoggedIn === null ? (
              // Still hydrating — show a subtle skeleton to avoid layout shift
              <div className="h-12 w-64 rounded-xl bg-slate-200 animate-pulse" />
            ) : isLoggedIn ? (
              // ── Authenticated State ──────────────────────────────
              <>
                <Link
                  href="/feed"
                  className="px-8 py-3.5 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all text-base shadow-md shadow-indigo-200"
                >
                  Go to Feed →
                </Link>
                <Link
                  href="/profile"
                  className="px-8 py-3.5 rounded-xl font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 transition-all text-base"
                >
                  View Profile
                </Link>
              </>
            ) : (
              // ── Guest State ──────────────────────────────────────
              <>
                <Link
                  href="/register"
                  className="px-8 py-3.5 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all text-base shadow-md shadow-indigo-200"
                >
                  Get Started — It&apos;s Free
                </Link>
                <Link
                  href="/login"
                  className="px-8 py-3.5 rounded-xl font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 transition-all text-base"
                >
                  Sign In
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Feature Cards */}
        <div className="max-w-5xl mx-auto mt-24 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            {
              icon: "🔍",
              title: "Smart Discovery",
              desc: "Aggregates opportunities from RSS feeds, Adzuna, Jooble, and more.",
            },
            {
              icon: "📚",
              title: "Online Courses",
              desc: "Discover free & paid MOOCs from Class Central, Coursera, edX, and freeCodeCamp.",
            },
            {
              icon: "🤖",
              title: "AI Profile Matching",
              desc: "Upload your resume and get opportunities ranked by relevance.",
            },
            {
              icon: "⚡",
              title: "Real-Time Alerts",
              desc: "Get notified instantly when new opportunities match your profile.",
            },
          ].map((feature) => (
            <div
              key={feature.title}
              className="p-6 rounded-2xl bg-white border border-slate-200 hover:border-indigo-200 hover:shadow-md transition-all group"
            >
              <div className="text-3xl mb-4">{feature.icon}</div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2 group-hover:text-indigo-600 transition-colors">
                {feature.title}
              </h3>
              <p className="text-sm text-slate-600 leading-relaxed">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
