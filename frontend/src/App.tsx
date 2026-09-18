import React, { useState, useEffect } from 'react';

// ── API Types ─────────────────────────────────────────────────────────────────

interface ChannelAllocation {
  market_name: string;
  location: string;
  quantity_kg: number;
  price_per_kg: number;
  gross_revenue: number;
  transport_cost: number;
  spoilage_loss_kg: number;
  spoilage_loss_value: number;
  net_value: number;
}

interface AllocationStrategy {
  strategy_name: string;
  strategy_description: string;
  allocations: ChannelAllocation[];
  total_quantity_allocated: number;
  total_gross_revenue: number;
  total_transport_cost: number;
  total_spoilage_loss_value: number;
  total_net_value: number;
}

interface OptimizeResponse {
  crop: string;
  quantity_kg: number;
  quality: string;
  farmer_location: string;
  recommended: AllocationStrategy;
  alternatives: AllocationStrategy[];
}

interface WhatIfPlan {
  allocations: ChannelAllocation[];
  total_quantity_allocated: number;
  total_gross_revenue: number;
  total_transport_cost: number;
  total_spoilage_loss_value: number;
  total_net_value: number;
}

interface WhatIfResponse {
  crop: string;
  quantity_kg: number;
  quality: string;
  farmer_location: string;
  scenario_description: string;
  current_plan: WhatIfPlan;
  whatif_plan: WhatIfPlan;
  delta_net_value: number;
}

interface Market {
  market_name: string;
  location: string;
}

interface DistanceInfo {
  market_name: string;
  location: string;
  distance_km: number | null;
  travel_time_minutes: number | null;
  transport_cost_per_kg: number;
  maps_live: boolean;
}

interface PlanResult {
  plan_label: string;
  plan_name: string;
  plan_description: string;
  plan_tradeoff: string;
  allocations: ChannelAllocation[];
  total_quantity_allocated: number;
  total_gross_revenue: number;
  total_transport_cost: number;
  total_spoilage_loss_value: number;
  total_net_value: number;
}

interface PlansResponse {
  crop: string;
  quantity_kg: number;
  quality: string;
  farmer_location: string;
  plan_a: PlanResult;
  plan_b: PlanResult;
  plan_c: PlanResult;
}

interface SubmissionResponse {
  optimize: OptimizeResponse;
  plans: PlansResponse;
  saved: boolean;
  farmer_input_id: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function deltaClass(d: number): string {
  if (d > 0) return 'text-green-600';
  if (d < 0) return 'text-red-500';
  return 'text-gray-500';
}

function deltaSign(d: number): string {
  if (d > 0) return '+';
  return '';
}

function fmtTime(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

function DistanceBadge({
  marketName,
  distances,
}: {
  marketName: string;
  distances: Map<string, DistanceInfo>;
}) {
  const d = distances.get(marketName);
  if (!d?.maps_live || d.distance_km === null) return null;
  const parts: string[] = [`${d.distance_km} km`];
  if (d.travel_time_minutes !== null) parts.push(fmtTime(d.travel_time_minutes));
  return (
    <span className="text-[10px] text-blue-400 ml-1 tabular-nums whitespace-nowrap">
      · {parts.join(' · ')}
    </span>
  );
}

type View = 'home' | 'form' | 'results';

// ── Strategy card ─────────────────────────────────────────────────────────────

function StrategyCard({
  strategy,
  isRecommended,
  distances,
}: {
  strategy: AllocationStrategy;
  isRecommended: boolean;
  distances: Map<string, DistanceInfo>;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${
        isRecommended ? 'border-green-300 ring-1 ring-green-200' : 'border-gray-100'
      }`}
    >
      {/* Header */}
      <div className={`px-6 pt-5 ${isRecommended ? 'pb-0' : 'pb-5'}`}>
        {isRecommended && (
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-bold bg-green-600 text-white px-2.5 py-0.5 rounded-full tracking-wide">
              RECOMMENDED
            </span>
            <span className="text-xs text-gray-400">Harvest Strategy</span>
          </div>
        )}

        <h3 className={`font-bold text-gray-900 ${isRecommended ? 'text-lg' : 'text-base'}`}>
          {strategy.strategy_name}
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">{strategy.strategy_description}</p>

        {/* Allocation rows */}
        <div className={`space-y-2 ${isRecommended ? 'mt-5' : 'mt-4'}`}>
          {strategy.allocations.map((ch) => (
            <div key={ch.market_name} className="flex items-center gap-3">
              <span
                className={`font-semibold text-gray-800 tabular-nums text-right flex-shrink-0 ${
                  isRecommended ? 'text-sm w-20' : 'text-xs w-16'
                }`}
              >
                {ch.quantity_kg} kg
              </span>
              <span className="text-gray-300 font-bold">→</span>
              <div className="flex-1 min-w-0">
                <span
                  className={`font-medium text-gray-900 ${isRecommended ? 'text-sm' : 'text-xs'}`}
                >
                  {ch.market_name}
                </span>
                <span className="text-xs text-gray-400 ml-1">({ch.location})</span>
                <DistanceBadge marketName={ch.market_name} distances={distances} />
              </div>
              <span
                className={`font-semibold text-green-700 flex-shrink-0 tabular-nums ${
                  isRecommended ? 'text-sm' : 'text-xs'
                }`}
              >
                {fmt(ch.net_value)}
              </span>
            </div>
          ))}
        </div>

        {/* Total row */}
        <div
          className={`flex items-center justify-between mt-4 pt-4 border-t border-gray-100 ${
            isRecommended ? 'pb-5' : 'pb-0'
          }`}
        >
          <span className="text-xs text-gray-400">
            {strategy.total_quantity_allocated} kg allocated
          </span>
          <div className="text-right">
            <span className="text-xs text-gray-400 mr-1">Total Expected Net Value</span>
            <span
              className={`font-bold text-green-700 ${isRecommended ? 'text-xl' : 'text-base'}`}
            >
              {fmt(strategy.total_net_value)}
            </span>
          </div>
        </div>
      </div>

      {/* Expandable breakdown (recommended card only) */}
      {isRecommended && (
        <>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="w-full px-6 py-2.5 text-xs text-gray-400 hover:text-gray-600 bg-gray-50 border-t border-gray-100 flex items-center justify-center gap-1 transition-colors"
          >
            {expanded ? '▲ Hide breakdown' : '▼ Show full breakdown'}
          </button>

          {expanded && (
            <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
              <table className="w-full text-xs mt-3">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-200">
                    <th className="text-left pb-2 font-medium">Channel</th>
                    <th className="text-right pb-2 font-medium">Qty (kg)</th>
                    <th className="text-right pb-2 font-medium">₹/kg</th>
                    <th className="text-right pb-2 font-medium">Gross</th>
                    <th className="text-right pb-2 font-medium">Transport</th>
                    <th className="text-right pb-2 font-medium">Spoilage</th>
                    <th className="text-right pb-2 font-medium">Net</th>
                  </tr>
                </thead>
                <tbody>
                  {strategy.allocations.map((ch) => (
                    <tr key={ch.market_name} className="border-b border-gray-100 last:border-0">
                      <td className="py-2 text-gray-700 font-medium">{ch.market_name}</td>
                      <td className="py-2 text-right text-gray-600 tabular-nums">{ch.quantity_kg}</td>
                      <td className="py-2 text-right text-gray-600 tabular-nums">₹{ch.price_per_kg}</td>
                      <td className="py-2 text-right text-gray-600 tabular-nums">{fmt(ch.gross_revenue)}</td>
                      <td className="py-2 text-right text-red-400 tabular-nums">−{fmt(ch.transport_cost)}</td>
                      <td className="py-2 text-right text-red-400 tabular-nums">−{fmt(ch.spoilage_loss_value)}</td>
                      <td className="py-2 text-right text-green-700 font-semibold tabular-nums">
                        {fmt(ch.net_value)}
                      </td>
                    </tr>
                  ))}
                  <tr className="font-semibold text-gray-800 bg-white">
                    <td className="pt-3 pb-1">Total</td>
                    <td className="pt-3 pb-1 text-right tabular-nums">
                      {strategy.total_quantity_allocated}
                    </td>
                    <td />
                    <td className="pt-3 pb-1 text-right tabular-nums">{fmt(strategy.total_gross_revenue)}</td>
                    <td className="pt-3 pb-1 text-right text-red-400 tabular-nums">
                      −{fmt(strategy.total_transport_cost)}
                    </td>
                    <td className="pt-3 pb-1 text-right text-red-400 tabular-nums">
                      −{fmt(strategy.total_spoilage_loss_value)}
                    </td>
                    <td className="pt-3 pb-1 text-right text-green-700 tabular-nums">
                      {fmt(strategy.total_net_value)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── What-If Plan column ───────────────────────────────────────────────────────

function PlanColumn({ plan, label, accent }: { plan: WhatIfPlan; label: string; accent: string }) {
  return (
    <div className="flex-1 min-w-0">
      <div className={`text-xs font-bold uppercase tracking-widest mb-3 ${accent}`}>{label}</div>
      {plan.allocations.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No viable allocation</p>
      ) : (
        <div className="space-y-1.5 mb-3">
          {plan.allocations.map((ch) => (
            <div key={ch.market_name} className="flex items-center justify-between gap-2 text-xs">
              <span className="text-gray-600 truncate">{ch.market_name}</span>
              <span className="tabular-nums text-gray-700 flex-shrink-0">{ch.quantity_kg} kg</span>
            </div>
          ))}
        </div>
      )}
      <div className="border-t border-gray-100 pt-2 space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-gray-400">Qty allocated</span>
          <span className="tabular-nums text-gray-700">{plan.total_quantity_allocated} kg</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Gross revenue</span>
          <span className="tabular-nums text-gray-700">{fmt(plan.total_gross_revenue)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Transport cost</span>
          <span className="tabular-nums text-red-400">−{fmt(plan.total_transport_cost)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Spoilage loss</span>
          <span className="tabular-nums text-red-400">−{fmt(plan.total_spoilage_loss_value)}</span>
        </div>
        <div className="flex justify-between font-semibold mt-1 pt-1 border-t border-gray-100">
          <span className="text-gray-700">Net value</span>
          <span className={`tabular-nums ${accent}`}>{fmt(plan.total_net_value)}</span>
        </div>
      </div>
    </div>
  );
}

// ── Plan A / B / C card ───────────────────────────────────────────────────────

const PLAN_COLORS: Record<string, { badge: string; accent: string; border: string }> = {
  A: { badge: 'bg-green-600', accent: 'text-green-700', border: 'border-green-200' },
  B: { badge: 'bg-blue-600',  accent: 'text-blue-700',  border: 'border-blue-200'  },
  C: { badge: 'bg-orange-500', accent: 'text-orange-600', border: 'border-orange-200' },
};

function PlanCard({ plan, distances }: { plan: PlanResult; distances: Map<string, DistanceInfo> }) {
  const [expanded, setExpanded] = useState(false);
  const colors = PLAN_COLORS[plan.plan_label] ?? PLAN_COLORS['A'];

  return (
    <div className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${colors.border}`}>
      <div className="px-6 pt-5 pb-5">
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs font-bold text-white px-2.5 py-0.5 rounded-full tracking-wide ${colors.badge}`}>
            PLAN {plan.plan_label}
          </span>
          <span className="text-sm font-bold text-gray-900">{plan.plan_name}</span>
        </div>
        <p className="text-xs text-gray-500 mb-4">{plan.plan_description}</p>

        <div className="space-y-2 mb-4">
          {plan.allocations.map((ch) => (
            <div key={ch.market_name} className="flex items-center gap-3">
              <span className="text-xs font-semibold text-gray-800 tabular-nums w-16 text-right flex-shrink-0">
                {ch.quantity_kg} kg
              </span>
              <span className="text-gray-300">→</span>
              <div className="flex-1 min-w-0">
                <span className="text-xs font-medium text-gray-900">{ch.market_name}</span>
                <span className="text-xs text-gray-400 ml-1">({ch.location})</span>
                <DistanceBadge marketName={ch.market_name} distances={distances} />
              </div>
              <span className={`text-xs font-semibold tabular-nums flex-shrink-0 ${colors.accent}`}>
                {fmt(ch.net_value)}
              </span>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-gray-100">
          <span className="text-xs text-gray-400">{plan.total_quantity_allocated} kg · {plan.allocations.length} market{plan.allocations.length !== 1 ? 's' : ''}</span>
          <div className="text-right">
            <span className="text-xs text-gray-400 mr-1">Net value</span>
            <span className={`text-base font-bold ${colors.accent}`}>{fmt(plan.total_net_value)}</span>
          </div>
        </div>

        <div className="mt-3 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 text-xs text-amber-800">
          ⚡ {plan.plan_tradeoff}
        </div>
      </div>

      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full px-6 py-2.5 text-xs text-gray-400 hover:text-gray-600 bg-gray-50 border-t border-gray-100 flex items-center justify-center gap-1 transition-colors"
      >
        {expanded ? '▲ Hide breakdown' : '▼ Show full breakdown'}
      </button>

      {expanded && (
        <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
          <table className="w-full text-xs mt-3">
            <thead>
              <tr className="text-gray-400 border-b border-gray-200">
                <th className="text-left pb-2 font-medium">Channel</th>
                <th className="text-right pb-2 font-medium">Qty</th>
                <th className="text-right pb-2 font-medium">₹/kg</th>
                <th className="text-right pb-2 font-medium">Gross</th>
                <th className="text-right pb-2 font-medium">Transport</th>
                <th className="text-right pb-2 font-medium">Spoilage</th>
                <th className="text-right pb-2 font-medium">Net</th>
              </tr>
            </thead>
            <tbody>
              {plan.allocations.map((ch) => (
                <tr key={ch.market_name} className="border-b border-gray-100 last:border-0">
                  <td className="py-2 text-gray-700 font-medium">{ch.market_name}</td>
                  <td className="py-2 text-right text-gray-600 tabular-nums">{ch.quantity_kg}</td>
                  <td className="py-2 text-right text-gray-600 tabular-nums">₹{ch.price_per_kg}</td>
                  <td className="py-2 text-right text-gray-600 tabular-nums">{fmt(ch.gross_revenue)}</td>
                  <td className="py-2 text-right text-red-400 tabular-nums">−{fmt(ch.transport_cost)}</td>
                  <td className="py-2 text-right text-red-400 tabular-nums">−{fmt(ch.spoilage_loss_value)}</td>
                  <td className={`py-2 text-right font-semibold tabular-nums ${colors.accent}`}>{fmt(ch.net_value)}</td>
                </tr>
              ))}
              <tr className="font-semibold text-gray-800 bg-white">
                <td className="pt-3 pb-1">Total</td>
                <td className="pt-3 pb-1 text-right tabular-nums">{plan.total_quantity_allocated}</td>
                <td />
                <td className="pt-3 pb-1 text-right tabular-nums">{fmt(plan.total_gross_revenue)}</td>
                <td className="pt-3 pb-1 text-right text-red-400 tabular-nums">−{fmt(plan.total_transport_cost)}</td>
                <td className="pt-3 pb-1 text-right text-red-400 tabular-nums">−{fmt(plan.total_spoilage_loss_value)}</td>
                <td className={`pt-3 pb-1 text-right tabular-nums ${colors.accent}`}>{fmt(plan.total_net_value)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [view, setView] = useState<View>('home');

  // Form state
  const [crop, setCrop] = useState('');
  const [quantity, setQuantity] = useState('');
  const [quality, setQuality] = useState('Standard');
  const [shelfLife, setShelfLife] = useState('');
  const [farmerLocation, setFarmerLocation] = useState('');
  const [harvestDate, setHarvestDate] = useState('');

  // API state
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [results, setResults] = useState<OptimizeResponse | null>(null);

  // Plans A/B/C state
  const [plansResult, setPlansResult] = useState<PlansResponse | null>(null);
  const [decisionSaved, setDecisionSaved] = useState(false);

  // Distance data (fetched non-blocking after submission)
  const [distances, setDistances] = useState<Map<string, DistanceInfo>>(new Map());
  const [mapsLive, setMapsLive] = useState<boolean | null>(null);

  // What-If state
  const [markets, setMarkets] = useState<Market[]>([]);
  const [wiTransport, setWiTransport] = useState(0);
  const [wiPrice, setWiPrice] = useState(0);
  const [wiShelf, setWiShelf] = useState(0);
  const [wiCancelled, setWiCancelled] = useState('');
  const [wiCapacity, setWiCapacity] = useState(0);
  const [wiResult, setWiResult] = useState<WhatIfResponse | null>(null);
  const [wiLoading, setWiLoading] = useState(false);
  const [wiError, setWiError] = useState<string | null>(null);

  // Fetch markets list when entering results
  useEffect(() => {
    if (view === 'results' && markets.length === 0) {
      fetch('/api/markets')
        .then((r) => r.json())
        .then((data: Market[]) => setMarkets(data))
        .catch(() => {/* non-critical */});
    }
  }, [view]);

  const resetAll = () => {
    setCrop('');
    setQuantity('');
    setQuality('Standard');
    setShelfLife('');
    setFarmerLocation('');
    setHarvestDate('');
    setApiError(null);
    setResults(null);
    setPlansResult(null);
    setDecisionSaved(false);
    setDistances(new Map());
    setMapsLive(null);
    setWiResult(null);
    setWiTransport(0);
    setWiPrice(0);
    setWiShelf(0);
    setWiCancelled('');
    setWiCapacity(0);
  };

  const handleStart = () => {
    resetAll();
    setView('form');
  };

  const handleBackToHome = () => {
    resetAll();
    setView('home');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setApiError(null);

    const payload = {
      crop,
      quantity_kg: parseFloat(quantity),
      quality,
      farmer_location: farmerLocation,
      harvest_date: harvestDate,
      shelf_life_days: parseInt(shelfLife, 10),
    };

    try {
      const response = await fetch('/api/submission', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const data: SubmissionResponse = await response.json();
      setResults(data.optimize);
      setPlansResult(data.plans);
      setDecisionSaved(data.saved);
      setWiResult(null);
      setView('results');

      // Fetch road distances non-blocking — doesn't delay the results view
      fetch(`/api/distances?farmer_location=${encodeURIComponent(farmerLocation)}`)
        .then((r) => r.json())
        .then((dists: DistanceInfo[]) => {
          setDistances(new Map(dists.map((d) => [d.market_name, d])));
          setMapsLive(dists.some((d) => d.maps_live));
        })
        .catch(() => { /* non-critical — fallback display handles absence */ });
    } catch (err) {
      setApiError(
        err instanceof Error
          ? err.message
          : 'Failed to connect to the server. Is the backend running?'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunWhatIf = async () => {
    if (!results) return;
    setWiLoading(true);
    setWiError(null);
    try {
      const response = await fetch('/api/decision/whatif', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          produce: {
            crop,
            quantity_kg: results.quantity_kg,
            quality: results.quality,
            farmer_location: results.farmer_location,
            harvest_date: harvestDate,
            shelf_life_days: parseInt(shelfLife, 10),
          },
          scenario: {
            transport_cost_increase_pct: wiTransport,
            price_decrease_pct: wiPrice,
            shelf_life_reduction_days: wiShelf,
            cancelled_market: wiCancelled || null,
            capacity_reduction_pct: wiCapacity,
          },
        }),
      });
      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      const data: WhatIfResponse = await response.json();
      setWiResult(data);
    } catch (err) {
      setWiError(err instanceof Error ? err.message : 'What-If request failed.');
    } finally {
      setWiLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50/50 to-white text-gray-800 flex flex-col">
      {/* Navigation Header */}
      <header className="border-b border-gray-100 bg-white/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">🌱</span>
            <span className="text-xl font-bold text-green-700 tracking-tight">Farm2Value</span>
          </div>
          <span className="text-xs font-medium text-gray-500 bg-green-50 text-green-700 px-3 py-1 rounded-full border border-green-100">
            Hackathon Prototype
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl mx-auto px-6 py-12 flex flex-col items-center justify-center w-full">

        {/* ── HOME VIEW ── */}
        {view === 'home' && (
          <div className="text-center max-w-xl mx-auto">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-100 text-green-800 text-sm font-medium mb-6">
              🌾 From Harvest to Value
            </div>
            <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 tracking-tight mb-4">
              Farm2Value
            </h1>
            <p className="text-xl text-gray-600 font-normal mb-8">
              Make smarter farm-to-market selling decisions.
            </p>
            <button
              onClick={handleStart}
              className="inline-flex items-center justify-center px-8 py-4 text-base font-semibold text-white bg-green-600 hover:bg-green-700 rounded-xl shadow-md hover:shadow-lg transition-all transform active:scale-95"
            >
              Start Selling Decision
            </button>
          </div>
        )}

        {/* ── FORM VIEW ── */}
        {view === 'form' && (
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Farmer Produce Details</h2>
                <p className="text-sm text-gray-500 mt-1">Enter your harvest details to begin</p>
              </div>
              <button
                onClick={handleBackToHome}
                className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
                type="button"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="crop" className="block text-sm font-medium text-gray-700 mb-1">
                  1. Crop / Produce
                </label>
                <input
                  id="crop"
                  type="text"
                  required
                  placeholder="e.g., Tomatoes, Onions, Wheat"
                  value={crop}
                  onChange={(e) => setCrop(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm transition"
                />
              </div>

              <div>
                <label htmlFor="quantity" className="block text-sm font-medium text-gray-700 mb-1">
                  2. Quantity (kg)
                </label>
                <input
                  id="quantity"
                  type="number"
                  min="1"
                  required
                  placeholder="e.g., 500"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm transition"
                />
              </div>

              <div>
                <label htmlFor="quality" className="block text-sm font-medium text-gray-700 mb-1">
                  3. Quality
                </label>
                <select
                  id="quality"
                  value={quality}
                  onChange={(e) => setQuality(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm bg-white transition"
                >
                  <option value="Premium">Premium</option>
                  <option value="Standard">Standard</option>
                  <option value="Low">Low</option>
                </select>
              </div>

              <div>
                <label htmlFor="shelfLife" className="block text-sm font-medium text-gray-700 mb-1">
                  4. Remaining shelf life (days)
                </label>
                <input
                  id="shelfLife"
                  type="number"
                  min="1"
                  required
                  placeholder="e.g., 7"
                  value={shelfLife}
                  onChange={(e) => setShelfLife(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm transition"
                />
              </div>

              <div>
                <label htmlFor="farmerLocation" className="block text-sm font-medium text-gray-700 mb-1">
                  5. Your Location
                </label>
                <input
                  id="farmerLocation"
                  type="text"
                  required
                  placeholder="e.g., Vijayawada, Guntur"
                  value={farmerLocation}
                  onChange={(e) => setFarmerLocation(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm transition"
                />
              </div>

              <div>
                <label htmlFor="harvestDate" className="block text-sm font-medium text-gray-700 mb-1">
                  6. Harvest Date
                </label>
                <input
                  id="harvestDate"
                  type="date"
                  required
                  value={harvestDate}
                  onChange={(e) => setHarvestDate(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm transition"
                />
              </div>

              {apiError && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
                  ⚠️ {apiError}
                </div>
              )}

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-3 px-4 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-semibold rounded-xl shadow transition active:scale-[0.98] flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Optimising Allocation…
                    </>
                  ) : (
                    'Find Best Allocation →'
                  )}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── RESULTS VIEW ── */}
        {view === 'results' && results && (
          <div className="w-full max-w-2xl space-y-6">
            {/* Context banner */}
            <div className="bg-green-50 border border-green-200 rounded-2xl p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-gray-900 mb-0.5">
                    Harvest Allocation Plan
                  </h2>
                  <p className="text-sm text-gray-500">
                    Optimised across {results.recommended.allocations.length} market channel
                    {results.recommended.allocations.length !== 1 ? 's' : ''} for maximum value
                  </p>
                </div>
                <span className="text-3xl flex-shrink-0">📊</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="bg-white border border-gray-200 rounded-full px-3 py-1 text-gray-600">
                  🌾 {results.crop}
                </span>
                <span className="bg-white border border-gray-200 rounded-full px-3 py-1 text-gray-600">
                  ⚖️ {results.quantity_kg} kg
                </span>
                <span className="bg-white border border-gray-200 rounded-full px-3 py-1 text-gray-600">
                  ⭐ {results.quality}
                </span>
                <span className="bg-white border border-gray-200 rounded-full px-3 py-1 text-gray-600">
                  📍 {results.farmer_location}
                </span>
                {decisionSaved && (
                  <span className="bg-green-100 border border-green-300 text-green-700 rounded-full px-3 py-1 font-medium">
                    ✓ Decision saved
                  </span>
                )}
                {mapsLive === true && (
                  <span className="bg-blue-50 border border-blue-200 text-blue-600 rounded-full px-3 py-1 font-medium">
                    🗺 Live road distances
                  </span>
                )}
                {mapsLive === false && (
                  <span className="bg-gray-50 border border-gray-200 text-gray-400 rounded-full px-3 py-1">
                    🗺 Estimated distances
                  </span>
                )}
              </div>
            </div>

            {/* Recommended strategy */}
            {results.recommended.allocations.length === 0 ? (
              <div className="bg-white border border-gray-100 rounded-2xl p-8 text-center text-gray-500">
                No viable market allocation found for this produce.
              </div>
            ) : (
              <StrategyCard strategy={results.recommended} isRecommended distances={distances} />
            )}

            {/* Alternative strategies */}
            {results.alternatives.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 px-1">
                  Alternative Strategies
                </h3>
                <div className="space-y-4">
                  {results.alternatives.map((alt) => (
                    <StrategyCard key={alt.strategy_name} strategy={alt} isRecommended={false} distances={distances} />
                  ))}
                </div>
              </div>
            )}

            {/* ── PLAN A / B / C ── */}
            {plansResult && (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
                    Selling Strategies
                  </h3>
                  <span className="text-xs text-gray-300">Plan A · B · C</span>
                </div>

                {/* Comparison mini-table */}
                <div className="grid grid-cols-3 gap-3">
                  {([plansResult.plan_a, plansResult.plan_b, plansResult.plan_c] as PlanResult[]).map((plan) => {
                    const colors = PLAN_COLORS[plan.plan_label] ?? PLAN_COLORS['A'];
                    return (
                      <div key={plan.plan_label} className={`bg-white border rounded-xl p-3 text-center ${colors.border}`}>
                        <div className={`text-[10px] font-bold uppercase tracking-widest mb-0.5 ${colors.accent}`}>
                          Plan {plan.plan_label}
                        </div>
                        <div className="text-[10px] text-gray-500 mb-2 leading-tight">{plan.plan_name}</div>
                        <div className={`text-sm font-bold tabular-nums ${colors.accent}`}>
                          {fmt(plan.total_net_value)}
                        </div>
                        <div className="text-[10px] text-gray-400 mt-0.5">
                          {plan.total_quantity_allocated} kg · {plan.allocations.length} mkt{plan.allocations.length !== 1 ? 's' : ''}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Individual plan cards */}
                <PlanCard plan={plansResult.plan_a} distances={distances} />
                <PlanCard plan={plansResult.plan_b} distances={distances} />
                <PlanCard plan={plansResult.plan_c} distances={distances} />
              </div>
            )}

            {/* ── WHAT-IF SIMULATOR ── */}
            <div className="bg-white rounded-2xl border border-amber-200 shadow-sm overflow-hidden">
              <div className="px-6 pt-5 pb-4 border-b border-amber-100 bg-amber-50">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">🔮</span>
                  <h3 className="text-base font-bold text-gray-900">What-If Simulator</h3>
                </div>
                <p className="text-xs text-gray-500">
                  Adjust market conditions to see how your net value changes.
                </p>
              </div>

              <div className="px-6 py-5 space-y-4">
                {/* Transport cost increase */}
                <div>
                  <div className="flex justify-between text-xs text-gray-600 mb-1">
                    <label className="font-medium">Transport cost increase</label>
                    <span className="tabular-nums font-semibold text-amber-700">+{wiTransport}%</span>
                  </div>
                  <input
                    type="range" min={0} max={100} step={5}
                    value={wiTransport}
                    onChange={(e) => setWiTransport(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-[10px] text-gray-300 mt-0.5">
                    <span>0%</span><span>100%</span>
                  </div>
                </div>

                {/* Price decrease */}
                <div>
                  <div className="flex justify-between text-xs text-gray-600 mb-1">
                    <label className="font-medium">Market price decrease</label>
                    <span className="tabular-nums font-semibold text-amber-700">−{wiPrice}%</span>
                  </div>
                  <input
                    type="range" min={0} max={50} step={5}
                    value={wiPrice}
                    onChange={(e) => setWiPrice(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-[10px] text-gray-300 mt-0.5">
                    <span>0%</span><span>50%</span>
                  </div>
                </div>

                {/* Shelf life reduction */}
                <div>
                  <div className="flex justify-between text-xs text-gray-600 mb-1">
                    <label className="font-medium">Shelf life reduction</label>
                    <span className="tabular-nums font-semibold text-amber-700">−{wiShelf} day{wiShelf !== 1 ? 's' : ''}</span>
                  </div>
                  <input
                    type="range" min={0} max={3} step={1}
                    value={wiShelf}
                    onChange={(e) => setWiShelf(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-[10px] text-gray-300 mt-0.5">
                    <span>0 days</span><span>−3 days</span>
                  </div>
                </div>

                {/* Capacity reduction */}
                <div>
                  <div className="flex justify-between text-xs text-gray-600 mb-1">
                    <label className="font-medium">Market capacity reduction</label>
                    <span className="tabular-nums font-semibold text-amber-700">−{wiCapacity}%</span>
                  </div>
                  <input
                    type="range" min={0} max={100} step={10}
                    value={wiCapacity}
                    onChange={(e) => setWiCapacity(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-[10px] text-gray-300 mt-0.5">
                    <span>0%</span><span>100%</span>
                  </div>
                </div>

                {/* Cancelled buyer */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    Cancelled buyer
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setWiCancelled('')}
                      className={`text-xs px-3 py-1.5 rounded-full border transition ${
                        wiCancelled === ''
                          ? 'bg-amber-500 text-white border-amber-500'
                          : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'
                      }`}
                    >
                      None
                    </button>
                    {markets.map((m) => (
                      <button
                        key={m.market_name}
                        type="button"
                        onClick={() => setWiCancelled(wiCancelled === m.market_name ? '' : m.market_name)}
                        className={`text-xs px-3 py-1.5 rounded-full border transition ${
                          wiCancelled === m.market_name
                            ? 'bg-amber-500 text-white border-amber-500'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'
                        }`}
                      >
                        {m.market_name}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleRunWhatIf}
                  disabled={wiLoading}
                  className="w-full py-2.5 px-4 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-white font-semibold rounded-xl shadow transition active:scale-[0.98] flex items-center justify-center gap-2 text-sm"
                >
                  {wiLoading ? (
                    <>
                      <span className="inline-block w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Running simulation…
                    </>
                  ) : (
                    '▶ Run What-If Simulation'
                  )}
                </button>

                {wiError && (
                  <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-xs">
                    ⚠️ {wiError}
                  </div>
                )}
              </div>

              {/* Comparison panel */}
              {wiResult && (
                <div className="border-t border-amber-100 bg-amber-50/40 px-6 py-5">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-xs font-bold text-gray-700 uppercase tracking-widest">Comparison</h4>
                    <span className="text-xs bg-amber-100 text-amber-800 rounded-full px-2.5 py-0.5 font-medium">
                      {wiResult.scenario_description}
                    </span>
                  </div>

                  {/* Side-by-side columns */}
                  <div className="flex gap-6">
                    <PlanColumn plan={wiResult.current_plan} label="Current Plan" accent="text-green-700" />
                    <div className="w-px bg-gray-200 flex-shrink-0" />
                    <PlanColumn plan={wiResult.whatif_plan} label="What-If Plan" accent="text-amber-700" />
                  </div>

                  {/* Delta banner */}
                  <div className={`mt-4 rounded-xl px-4 py-3 text-center ${
                    wiResult.delta_net_value < 0 ? 'bg-red-50 border border-red-100' : 'bg-green-50 border border-green-100'
                  }`}>
                    <div className="text-xs text-gray-500 mb-0.5">Net value impact</div>
                    <div className={`text-xl font-bold tabular-nums ${deltaClass(wiResult.delta_net_value)}`}>
                      {deltaSign(wiResult.delta_net_value)}{fmt(wiResult.delta_net_value)}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {wiResult.delta_net_value < 0
                        ? 'You stand to lose this much under this scenario.'
                        : wiResult.delta_net_value > 0
                        ? 'Your net value improves under this scenario.'
                        : 'No change in net value.'}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Action buttons */}
            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setView('form')}
                className="flex-1 py-2.5 px-4 rounded-lg border border-gray-200 text-gray-700 text-sm font-medium hover:bg-gray-50 transition"
              >
                Edit Details
              </button>
              <button
                onClick={handleBackToHome}
                className="flex-1 py-2.5 px-4 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition"
              >
                Start Again
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="py-6 border-t border-gray-100 text-center text-xs text-gray-400">
        Farm2Value &copy; 2026 · Built for Problem Statement 3: From Harvest to Value
      </footer>
    </div>
  );
}
