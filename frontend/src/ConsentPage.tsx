import { useState } from 'react';
import { recordConsent } from './lib/consentService';

interface ConsentPageProps {
  onConsented: () => void;
}

export default function ConsentPage({ onConsented }: ConsentPageProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);

  const handleConsent = async () => {
    if (!checked) return;
    setLoading(true);
    setError(null);
    try {
      await recordConsent();
      onConsented();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-green-50/60 via-white to-white px-4 py-10">
      <div className="w-full max-w-lg">

        {/* Header */}
        <div className="text-center mb-8">
          <span className="text-4xl">🌾</span>
          <h1 className="mt-3 text-2xl font-bold text-gray-900">Your Data & Privacy</h1>
          <p className="mt-2 text-sm text-gray-500">
            Before you use the Harvex farmer tools, please review how your information is used.
          </p>
        </div>

        {/* Content card */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm divide-y divide-gray-50">

          <section className="px-6 py-5">
            <h2 className="text-sm font-semibold text-gray-800 mb-2">What we collect</h2>
            <ul className="space-y-1 text-sm text-gray-600 list-disc list-inside">
              <li>Crop type, quantity, and quality grade</li>
              <li>Harvest date and expected shelf life</li>
              <li>Your farm location (district / city level)</li>
              <li>Your account email and display name</li>
            </ul>
          </section>

          <section className="px-6 py-5">
            <h2 className="text-sm font-semibold text-gray-800 mb-2">Why we need it</h2>
            <p className="text-sm text-gray-600">
              Harvex uses your produce details and location to match your harvest
              against nearby mandis, wholesale buyers, and cold storage facilities.
              Without this information the decision engine cannot generate market
              allocations or transport-cost estimates.
            </p>
          </section>

          <section className="px-6 py-5">
            <h2 className="text-sm font-semibold text-gray-800 mb-2">How it is used</h2>
            <ul className="space-y-1 text-sm text-gray-600 list-disc list-inside">
              <li>To calculate optimised market allocation plans</li>
              <li>To estimate transport cost and spoilage risk for each buyer</li>
              <li>To surface market prices and distances relevant to your location</li>
              <li>To save your submission history linked to your account</li>
            </ul>
          </section>

          <section className="px-6 py-5">
            <h2 className="text-sm font-semibold text-gray-800 mb-2">Who can see your data</h2>
            <p className="text-sm text-gray-600">
              Your farm submissions are <span className="font-medium text-gray-800">not publicly displayed</span>.
              Only you can view your history. Where Harvex surfaces produce
              availability to buyers, only aggregate or anonymised signals are
              used — your individual records are not shared without your
              explicit action.
            </p>
          </section>

          <section className="px-6 py-5">
            <h2 className="text-sm font-semibold text-gray-800 mb-2">Your control</h2>
            <p className="text-sm text-gray-600">
              You decide what produce information you submit each session.
              You can stop using Harvex at any time. This is a hackathon
              prototype — your data is stored securely in Supabase but is
              not subject to formal regulatory audits at this stage.
            </p>
          </section>

        </div>

        {/* Checkbox + action */}
        <div className="mt-6 space-y-4">
          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              className="mt-0.5 w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500 cursor-pointer"
            />
            <span className="text-sm text-gray-700 leading-relaxed">
              I have read and understood how Harvex collects and uses my farm data,
              and I agree to proceed on that basis.
            </span>
          </label>

          {error && (
            <div className="px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            onClick={handleConsent}
            disabled={!checked || loading}
            className="w-full py-3 rounded-xl font-semibold text-sm text-white bg-green-600 hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {loading ? 'Saving…' : 'I agree — continue to Harvex'}
          </button>
        </div>

      </div>
    </div>
  );
}
