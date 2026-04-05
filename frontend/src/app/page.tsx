import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-950 relative overflow-hidden">
      {/* Background gradient effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-to-b from-violet-600/20 via-indigo-600/10 to-transparent rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl" />
      </div>

      {/* Hero Section */}
      <main className="relative pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300 text-sm font-medium mb-8">
            <span className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
            AI-Powered Opportunity Discovery
          </div>

          {/* Heading */}
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
            <span className="text-white">Find Your Next</span>
            <br />
            <span className="bg-gradient-to-r from-violet-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Opportunity
            </span>
          </h1>

          {/* Subheading */}
          <p className="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            UniCompass aggregates internships, hackathons, research positions,
            and courses from multiple sources — then matches them to your
            skills and interests using AI.
          </p>

          {/* CTA Buttons */}
          <div className="flex items-center justify-center gap-4">
            <Link
              href="/register"
              className="px-8 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 transition-all text-base"
            >
              Get Started — It&apos;s Free
            </Link>
            <Link
              href="/login"
              className="px-8 py-3.5 rounded-xl font-semibold text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white transition-all text-base"
            >
              Sign In
            </Link>
          </div>
        </div>

        {/* Feature Cards */}
        <div className="max-w-5xl mx-auto mt-24 grid grid-cols-1 sm:grid-cols-3 gap-6">
          {[
            {
              icon: "🔍",
              title: "Smart Discovery",
              desc: "Aggregates opportunities from RSS feeds, Adzuna, Jooble, and more.",
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
              className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/[0.08] hover:border-white/20 transition-all group"
            >
              <div className="text-3xl mb-4">{feature.icon}</div>
              <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-violet-300 transition-colors">
                {feature.title}
              </h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
