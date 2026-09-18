import React, { useState } from 'react';

// ── API Types ─────────────────────────────────────────────────────────────────

interface OpportunityResult {
  market_name: string;
  location: string;
  allocated_qty_kg: number;
  price_per_kg: number;
  gross_revenue: number;
  transport_cost: number;
  spoilage_loss_kg: number;
  spoilage_loss_value: number;
  net_value: number;
  rank: number;
}

interface RecommendationResponse {
  crop: string;
  quantity_kg: number;
  quality: string;
  farmer_location: string;
  opportunities: OpportunityResult[];
  summary: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type View = 'home' | 'form' | 'results';

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
  const [results, setResults] = useState<RecommendationResponse | null>(null);

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
      const response = await fetch('/api/recommend', {
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

      const data: RecommendationResponse = await response.json();
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
                      Calculating…
                    </>
                  ) : (
                    'Find Market Opportunities →'
                  )}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── RESULTS VIEW ── */}
        {view === 'results' && results && (
          <div className="w-full max-w-2xl space-y-6">
            {/* Summary banner */}
            <div className="bg-green-50 border border-green-200 rounded-2xl p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-gray-900 mb-1">Market Opportunities</h2>
                  <p className="text-sm text-gray-600">{results.summary}</p>
                </div>
                <span className="text-3xl flex-shrink-0">📊</span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
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

            {/* Opportunity cards */}
            {results.opportunities.length === 0 ? (
              <div className="bg-white border border-gray-100 rounded-2xl p-8 text-center text-gray-500">
                No viable market opportunities found for this produce.
              </div>
            ) : (
              <div className="space-y-4">
                {results.opportunities.map((opp) => (
                  <div
                    key={opp.market_name}
                    className={`bg-white rounded-2xl border shadow-sm p-5 ${
                      opp.rank === 1 ? 'border-green-300 ring-1 ring-green-200' : 'border-gray-100'
                    }`}
                  >
                    {/* Card header */}
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                              opp.rank === 1
                                ? 'bg-green-600 text-white'
                                : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            #{opp.rank}
                          </span>
                          <h3 className="font-semibold text-gray-900">{opp.market_name}</h3>
                          {opp.rank === 1 && (
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                              Best
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">📍 {opp.location}</p>
                      </div>
                      <div className="text-right flex-shrink-0 ml-4">
                        <p className="text-lg font-bold text-green-700">{fmt(opp.net_value)}</p>
                        <p className="text-xs text-gray-400">expected net</p>
                      </div>
                    </div>

                    {/* Metrics grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-3 border-t border-gray-50">
                      <div>
                        <p className="text-gray-400 mb-0.5">Price / kg</p>
                        <p className="font-medium text-gray-800">₹{opp.price_per_kg}</p>
                      </div>
                      <div>
                        <p className="text-gray-400 mb-0.5">Allocated</p>
                        <p className="font-medium text-gray-800">{opp.allocated_qty_kg} kg</p>
                      </div>
                      <div>
                        <p className="text-gray-400 mb-0.5">Gross Revenue</p>
                        <p className="font-medium text-gray-800">{fmt(opp.gross_revenue)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400 mb-0.5">Transport</p>
                        <p className="font-medium text-red-500">−{fmt(opp.transport_cost)}</p>
                      </div>
                      <div className="col-span-2">
                        <p className="text-gray-400 mb-0.5">Spoilage Loss</p>
                        <p className="font-medium text-red-500">
                          −{fmt(opp.spoilage_loss_value)}{' '}
                          <span className="text-gray-400">({opp.spoilage_loss_kg} kg)</span>
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
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
