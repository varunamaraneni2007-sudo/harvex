import React, { useState } from 'react';

export default function App() {
  const [showForm, setShowForm] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // Farmer form state
  const [crop, setCrop] = useState('');
  const [quantity, setQuantity] = useState('');
  const [quality, setQuality] = useState('Standard');
  const [shelfLife, setShelfLife] = useState('');

  const handleStart = () => {
    setShowForm(true);
    setIsSubmitted(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitted(true);
  };

  const handleReset = () => {
    setShowForm(false);
    setIsSubmitted(false);
    setCrop('');
    setQuantity('');
    setQuality('Standard');
    setShelfLife('');
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
        {!showForm ? (
          /* Homepage View */
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
        ) : (
          /* Farmer Input Form View */
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Farmer Produce Details</h2>
                <p className="text-sm text-gray-500 mt-1">Enter your harvest details to begin</p>
              </div>
              <button
                onClick={handleReset}
                className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
                type="button"
              >
                Cancel
              </button>
            </div>

            {isSubmitted ? (
              <div className="text-center py-6 space-y-4">
                <div className="w-12 h-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto text-xl">
                  ✓
                </div>
                <h3 className="text-lg font-semibold text-gray-900">Information Saved</h3>
                <div className="bg-gray-50 rounded-xl p-4 text-left text-sm space-y-2 border border-gray-100">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Crop / Produce:</span>
                    <span className="font-medium text-gray-800">{crop || 'Not specified'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Quantity:</span>
                    <span className="font-medium text-gray-800">{quantity} kg</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Quality:</span>
                    <span className="font-medium text-gray-800">{quality}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Remaining Shelf Life:</span>
                    <span className="font-medium text-gray-800">{shelfLife} days</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500">Ready for the next decision step!</p>
                <div className="pt-2 flex gap-3">
                  <button
                    type="button"
                    onClick={() => setIsSubmitted(false)}
                    className="flex-1 py-2.5 px-4 rounded-lg border border-gray-200 text-gray-700 text-sm font-medium hover:bg-gray-50"
                  >
                    Edit Details
                  </button>
                  <button
                    type="button"
                    onClick={handleReset}
                    className="flex-1 py-2.5 px-4 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700"
                  >
                    Back to Home
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                {/* 1. Crop / Produce */}
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

                {/* 2. Quantity (kg) */}
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

                {/* 3. Quality */}
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

                {/* 4. Remaining shelf life (days) */}
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

                {/* Continue Button */}
                <div className="pt-2">
                  <button
                    type="submit"
                    className="w-full py-3 px-4 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-xl shadow transition active:scale-[0.98]"
                  >
                    Continue
                  </button>
                </div>
              </form>
            )}
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
