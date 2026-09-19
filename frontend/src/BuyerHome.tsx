import type { User } from '@supabase/supabase-js';
import type { Profile } from './lib/roleService';

interface BuyerHomeProps {
  user: User;
  profile: Profile;
  onGoToMarketplace: () => void;
}

export default function BuyerHome({ user, profile, onGoToMarketplace }: BuyerHomeProps) {
  const firstName = (profile.full_name ?? user.email?.split('@')[0] ?? 'Buyer').split(' ')[0];
  const location = [profile.district, profile.state].filter(Boolean).join(', ');

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">

      {/* ── Welcome header ── */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-500 rounded-2xl px-6 py-7 text-white shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-blue-100 text-sm font-medium mb-1">Welcome back</p>
            <h1 className="text-2xl font-extrabold tracking-tight">
              {firstName} 🏪
            </h1>
            {location && (
              <p className="text-blue-100 text-sm mt-1 flex items-center gap-1">
                <span>📍</span> {location}
              </p>
            )}
          </div>
          <span className="text-5xl opacity-20 select-none">🏪</span>
        </div>
      </div>

      {/* ── Primary CTA ── */}
      <button
        onClick={onGoToMarketplace}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-2xl px-6 py-6 text-left shadow-sm transition active:scale-[0.98] group"
      >
        <div className="flex items-center gap-4">
          <div className="text-3xl">🏪</div>
          <div className="flex-1">
            <div className="font-bold text-lg">Browse Produce Marketplace</div>
            <div className="text-blue-100 text-sm mt-0.5">
              Discover fresh produce from verified farmers across India
            </div>
          </div>
          <span className="text-blue-200 text-xl group-hover:translate-x-1 transition-transform">→</span>
        </div>
      </button>

      {/* ── Coming soon cards ── */}
      <div>
        <h2 className="font-bold text-gray-900 mb-3 px-1">Coming Soon</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 opacity-70">
            <div className="flex items-start gap-3">
              <div className="text-2xl">👤</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-bold text-gray-900 text-sm">Buyer Profile</div>
                  <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-400 rounded-full font-medium">
                    Soon
                  </span>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                  Set your business details, preferred commodities, and procurement capacity
                  to get matched with the right farmers.
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 opacity-70">
            <div className="flex items-start gap-3">
              <div className="text-2xl">📋</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-bold text-gray-900 text-sm">Buyer Requirements</div>
                  <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-400 rounded-full font-medium">
                    Soon
                  </span>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                  Post your procurement needs — crop, quantity, quality grade, and delivery
                  window — and let farmers find you.
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 opacity-70">
            <div className="flex items-start gap-3">
              <div className="text-2xl">🤝</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-bold text-gray-900 text-sm">Direct Farmer Connect</div>
                  <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-400 rounded-full font-medium">
                    Soon
                  </span>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                  Message verified farmers directly, negotiate prices, and schedule
                  pickups without intermediaries.
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 opacity-70">
            <div className="flex items-start gap-3">
              <div className="text-2xl">📊</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-bold text-gray-900 text-sm">Price Intelligence</div>
                  <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-400 rounded-full font-medium">
                    Soon
                  </span>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                  Live APMC mandi prices, historical trends, and demand forecasts to
                  help you time your procurement decisions.
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* ── How it works ── */}
      <div className="bg-blue-50 border border-blue-100 rounded-2xl px-6 py-5">
        <h3 className="font-bold text-blue-900 text-sm mb-3">How Harvex works for buyers</h3>
        <ol className="space-y-2.5">
          {[
            { n: '1', text: 'Browse the marketplace to see available produce from farmers across India.' },
            { n: '2', text: 'Filter by crop, state, quality grade, and price to find what you need.' },
            { n: '3', text: 'Connect directly with farmers and agree on fair prices backed by live mandi data.' },
          ].map(({ n, text }) => (
            <li key={n} className="flex items-start gap-3">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                {n}
              </span>
              <span className="text-sm text-blue-800 leading-relaxed">{text}</span>
            </li>
          ))}
        </ol>
        <button
          onClick={onGoToMarketplace}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl transition active:scale-[0.98]"
        >
          Go to Marketplace →
        </button>
      </div>

    </div>
  );
}
