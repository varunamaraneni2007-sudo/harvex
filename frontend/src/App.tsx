import React, { useState } from 'react';

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

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type View = 'home' | 'form' | 'results';

// ── Strategy card ─────────────────────────────────────────────────────────────

function StrategyCard({
  strategy,
  isRecommended,
}: {
  strategy: AllocationStrategy;
  isRecommended: boolean;
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

  const resetAll = () => {
    setCrop('');
    setQuantity('');
    setQuality('Standard');
    setShelfLife('');
    setFarmerLocation('');
    setHarvestDate('');
    setApiError(null);
    setResults(null);
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

    try {
      const response = await fetch('/api/decision/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          crop,
          quantity_kg: parseFloat(quantity),
          quality,
          farmer_location: farmerLocation,
          harvest_date: harvestDate,
          shelf_life_days: parseInt(shelfLife, 10),
        }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data: OptimizeResponse = await response.json();
      setResults(data);
      setView('results');
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
                    Optimised across {(results.recommended.allocations.length +
                      results.alternatives.reduce((s, a) => s + a.allocations.length, 0) > 0)
                      ? results.recommended.allocations.length
                      : 0}{' '}
                    market channel
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
              </div>
            </div>

            {/* Recommended strategy */}
            {results.recommended.allocations.length === 0 ? (
              <div className="bg-white border border-gray-100 rounded-2xl p-8 text-center text-gray-500">
                No viable market allocation found for this produce.
              </div>
            ) : (
              <StrategyCard strategy={results.recommended} isRecommended />
            )}

            {/* Alternative strategies */}
            {results.alternatives.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 px-1">
                  Alternative Strategies
                </h3>
                <div className="space-y-4">
                  {results.alternatives.map((alt) => (
                    <StrategyCard key={alt.strategy_name} strategy={alt} isRecommended={false} />
                  ))}
                </div>
              </div>
            )}

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
