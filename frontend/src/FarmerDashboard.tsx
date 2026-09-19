import { useState, useEffect } from 'react';
import type { User } from '@supabase/supabase-js';
import { supabase } from './lib/supabaseClient';
import type { Profile } from './lib/roleService';

interface FarmerInput {
  id: string;
  crop: string;
  quantity_kg: number;
  quality: string;
  farmer_location: string;
  harvest_date: string;
  shelf_life_days: number;
  created_at: string;
}

interface RecommendedResult {
  plan_name: string;
  total_allocated_kg: number;
  gross_revenue: number;
  transport_cost: number;
  spoilage_loss: number;
  expected_net_value: number;
}

interface Submission {
  farmer_input: FarmerInput;
  recommended_result: RecommendedResult | null;
}

interface FarmerDashboardProps {
  user: User;
  profile: Profile;
  onStartPlanner: () => void;
  onGoToMarketplace: () => void;
  onGoToProfile: () => void;
}

function fmt(n: number): string {
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return mins <= 1 ? 'just now' : `${mins} minutes ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours === 1 ? '1 hour ago' : `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  return new Date(isoDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function profileCompletion(profile: Profile): { pct: number; missing: string[] } {
  const fields: [keyof Profile, string][] = [
    ['full_name', 'Full name'],
    ['phone', 'Phone number'],
    ['state', 'State'],
    ['district', 'District'],
  ];
  const missing = fields.filter(([k]) => !profile[k]).map(([, label]) => label);
  const pct = Math.round(((fields.length - missing.length) / fields.length) * 100);
  return { pct, missing };
}

export default function FarmerDashboard({
  user,
  profile,
  onStartPlanner,
  onGoToMarketplace,
  onGoToProfile,
}: FarmerDashboardProps) {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { setLoading(false); return; }
        const resp = await fetch('/api/farmer/submissions?limit=5', {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
        const data: { submissions: Submission[] } = await resp.json();
        if (!cancelled) setSubmissions(data.submissions);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load recent activity.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const firstName = (profile.full_name ?? user.email?.split('@')[0] ?? 'Farmer').split(' ')[0];
  const location = [profile.district, profile.state].filter(Boolean).join(', ');
  const { pct: completionPct, missing: missingFields } = profileCompletion(profile);

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">

      {/* ── Welcome header ── */}
      <div className="bg-gradient-to-r from-green-600 to-emerald-500 rounded-2xl px-6 py-7 text-white shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-green-100 text-sm font-medium mb-1">Welcome back</p>
            <h1 className="text-2xl font-extrabold tracking-tight">
              {firstName} 🌾
            </h1>
            {location && (
              <p className="text-green-100 text-sm mt-1 flex items-center gap-1">
                <span>📍</span> {location}
              </p>
            )}
          </div>
          <span className="text-5xl opacity-20 select-none">🌾</span>
        </div>
      </div>

      {/* ── Quick actions ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button
          onClick={onStartPlanner}
          className="bg-green-600 hover:bg-green-700 text-white rounded-2xl px-5 py-5 text-left shadow-sm transition active:scale-[0.98] group"
        >
          <div className="text-2xl mb-2">🚀</div>
          <div className="font-bold text-sm">New Harvest Plan</div>
          <div className="text-green-100 text-xs mt-0.5">Get optimal market allocation</div>
        </button>

        <button
          onClick={onGoToMarketplace}
          className="bg-white border border-gray-100 hover:border-green-200 hover:bg-green-50 text-gray-800 rounded-2xl px-5 py-5 text-left shadow-sm transition active:scale-[0.98]"
        >
          <div className="text-2xl mb-2">🏪</div>
          <div className="font-bold text-sm">Browse Marketplace</div>
          <div className="text-gray-400 text-xs mt-0.5">Discover buyers and mandis</div>
        </button>

        <button
          onClick={onGoToProfile}
          className="bg-white border border-gray-100 hover:border-green-200 hover:bg-green-50 text-gray-800 rounded-2xl px-5 py-5 text-left shadow-sm transition active:scale-[0.98]"
        >
          <div className="text-2xl mb-2">👤</div>
          <div className="font-bold text-sm">My Profile</div>
          <div className="text-gray-400 text-xs mt-0.5">
            {completionPct < 100 ? `${completionPct}% complete` : 'All details filled'}
          </div>
        </button>
      </div>

      {/* ── Profile completion nudge ── */}
      {completionPct < 100 && (
        <div
          className="bg-amber-50 border border-amber-200 rounded-2xl px-5 py-4 flex items-start gap-3 cursor-pointer hover:bg-amber-100 transition"
          onClick={onGoToProfile}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onGoToProfile()}
        >
          <span className="text-amber-500 text-xl flex-shrink-0 mt-0.5">⚠️</span>
          <div>
            <p className="text-sm font-semibold text-amber-800">Complete your profile</p>
            <p className="text-xs text-amber-700 mt-0.5">
              Missing: {missingFields.join(', ')}. A complete profile helps Harvex surface
              more relevant market opportunities.
            </p>
          </div>
          <span className="ml-auto text-amber-400 text-sm flex-shrink-0">→</span>
        </div>
      )}

      {/* ── Recent decisions ── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
          <h2 className="font-bold text-gray-900">Recent Harvest Decisions</h2>
          {submissions.length > 0 && (
            <button
              onClick={onStartPlanner}
              className="text-xs text-green-600 hover:text-green-700 font-semibold transition"
            >
              + New Plan
            </button>
          )}
        </div>

        {loading && (
          <div className="px-6 py-10 flex flex-col items-center gap-3 text-gray-400">
            <span className="inline-block w-5 h-5 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Loading recent activity…</span>
          </div>
        )}

        {!loading && error && (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-red-500">{error}</p>
            <p className="text-xs text-gray-400 mt-1">Recent decisions could not be loaded.</p>
          </div>
        )}

        {!loading && !error && submissions.length === 0 && (
          <div className="px-6 py-12 text-center">
            <div className="text-4xl mb-3">🌱</div>
            <p className="font-semibold text-gray-700">No harvest plans yet</p>
            <p className="text-sm text-gray-400 mt-1 mb-5">
              Create your first plan to see allocation recommendations here.
            </p>
            <button
              onClick={onStartPlanner}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-xl transition active:scale-[0.98]"
            >
              Start Selling Decision →
            </button>
          </div>
        )}

        {!loading && !error && submissions.length > 0 && (
          <ul className="divide-y divide-gray-50">
            {submissions.map(({ farmer_input: fi, recommended_result: res }) => (
              <li key={fi.id} className="px-6 py-4 flex items-center gap-4 hover:bg-gray-50/50 transition">
                <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center text-lg">
                  🌾
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-gray-900 text-sm">{fi.crop}</span>
                    <span className="text-xs text-gray-400">{fi.quantity_kg} kg · {fi.quality}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      fi.quality === 'Premium' ? 'bg-yellow-50 text-yellow-700' :
                      fi.quality === 'Standard' ? 'bg-blue-50 text-blue-700' :
                      'bg-gray-100 text-gray-500'
                    }`}>
                      {fi.quality}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-xs text-gray-400">📍 {fi.farmer_location}</span>
                    <span className="text-xs text-gray-300">·</span>
                    <span className="text-xs text-gray-400">{timeAgo(fi.created_at)}</span>
                  </div>
                </div>
                {res && (
                  <div className="text-right flex-shrink-0">
                    <div className="text-sm font-bold text-green-700">{fmt(res.expected_net_value)}</div>
                    <div className="text-xs text-gray-400">net value</div>
                  </div>
                )}
                {!res && (
                  <div className="text-right flex-shrink-0">
                    <div className="text-xs text-gray-300 italic">No result saved</div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Feature cards row ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="text-2xl mb-3">🔮</div>
          <div className="font-bold text-gray-900 text-sm mb-1">What-If Simulator</div>
          <p className="text-xs text-gray-500 leading-relaxed mb-4">
            Simulate price drops, transport disruptions, or buyer cancellations to
            understand the risk to your plan before it happens.
          </p>
          <button
            onClick={onStartPlanner}
            className="text-xs font-semibold text-green-600 hover:text-green-700 transition"
          >
            Create a plan first →
          </button>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="text-2xl mb-3">📊</div>
          <div className="font-bold text-gray-900 text-sm mb-1">Market Allocation Engine</div>
          <p className="text-xs text-gray-500 leading-relaxed mb-4">
            Linear programming optimises how your harvest is split across mandis,
            wholesale buyers, retail chains, and cold storage for maximum net value.
          </p>
          <button
            onClick={onStartPlanner}
            className="text-xs font-semibold text-green-600 hover:text-green-700 transition"
          >
            Run a new plan →
          </button>
        </div>
      </div>

    </div>
  );
}
