import { useState } from 'react';
import type { UserRole, Profile } from './lib/roleService';
import { selectRole } from './lib/roleService';

interface RoleSelectPageProps {
  fullName: string | null;
  onRoleSelected: (role: UserRole, profile?: Profile) => void;
}

export default function RoleSelectPage({ fullName, onRoleSelected }: RoleSelectPageProps) {
  const [selected, setSelected] = useState<UserRole | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const p = await selectRole(selected, fullName ?? undefined);
      // Existing accounts keep their immutable database role. The POST
      // returns that profile, so never route from the browser selection alone.
      onRoleSelected(p?.role ?? selected, p ?? undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const roles: { value: UserRole; label: string; desc: string; icon: string }[] = [
    {
      value: 'farmer',
      label: 'Farmer',
      desc: 'I grow produce and want to find the best markets to sell at.',
      icon: '🌾',
    },
    {
      value: 'consumer',
      label: 'Consumer',
      desc: 'I want to buy fresh produce directly from farmers.',
      icon: '🧺',
    },
    {
      value: 'buyer',
      label: 'Market / Buyer',
      desc: 'I purchase agricultural produce from farmers and mandis.',
      icon: '🏪',
    },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-green-50/60 via-white to-white px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <span className="text-4xl">🌱</span>
          <h1 className="mt-3 text-2xl font-bold text-gray-900">
            Welcome{fullName ? `, ${fullName}` : ''}!
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            How will you use Harvex? You can't change this later.
          </p>
        </div>

        <div className="space-y-3 mb-6">
          {roles.map((r) => (
            <button
              key={r.value}
              onClick={() => setSelected(r.value)}
              className={`w-full text-left px-5 py-4 rounded-2xl border-2 transition ${
                selected === r.value
                  ? 'border-green-500 bg-green-50'
                  : 'border-gray-200 bg-white hover:border-green-300'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">{r.icon}</span>
                <div>
                  <div className="font-semibold text-gray-900 text-sm">{r.label}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{r.desc}</div>
                </div>
                {selected === r.value && (
                  <span className="ml-auto text-green-500 text-lg">✓</span>
                )}
              </div>
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          onClick={handleConfirm}
          disabled={!selected || loading}
          className="w-full py-3 rounded-xl font-semibold text-sm text-white bg-green-600 hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {loading ? 'Saving…' : 'Continue'}
        </button>
      </div>
    </div>
  );
}
