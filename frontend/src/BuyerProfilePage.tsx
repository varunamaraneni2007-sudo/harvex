import { useState } from 'react';
import type { User } from '@supabase/supabase-js';
import type { Profile, ProfileUpdate } from './lib/roleService';
import { updateProfile } from './lib/roleService';

interface BuyerProfilePageProps {
  user: User;
  profile: Profile;
  onProfileUpdated: (p: Profile) => void;
}

const BUSINESS_TYPES = [
  'Wholesale Buyer',
  'Retail Chain',
  'Food Processor',
  'Exporter',
  'Cold Storage',
  'Restaurant / Hotel',
  'Other',
];

export default function BuyerProfilePage({ user, profile, onProfileUpdated }: BuyerProfilePageProps) {
  const [fullName, setFullName] = useState(profile.full_name ?? '');
  const [phone, setPhone] = useState(profile.phone ?? '');
  const [state, setState] = useState(profile.state ?? '');
  const [district, setDistrict] = useState(profile.district ?? '');
  const [companyName, setCompanyName] = useState(profile.company_name ?? '');
  const [businessType, setBusinessType] = useState(profile.business_type ?? '');

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  const isDirty =
    fullName !== (profile.full_name ?? '') ||
    phone !== (profile.phone ?? '') ||
    state !== (profile.state ?? '') ||
    district !== (profile.district ?? '') ||
    companyName !== (profile.company_name ?? '') ||
    businessType !== (profile.business_type ?? '');

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (phone.trim() && !/^[0-9+\-() ]{7,20}$/.test(phone.trim())) {
      errors.phone = 'Enter a valid phone number (digits, +, -, spaces).';
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const updates: ProfileUpdate = {
        full_name: fullName.trim() || null,
        phone: phone.trim() || null,
        state: state.trim() || null,
        district: district.trim() || null,
        company_name: companyName.trim() || null,
        business_type: businessType.trim() || null,
      };
      const updated = await updateProfile(updates);
      onProfileUpdated(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const inputCls =
    'w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm transition bg-white placeholder:text-gray-300';
  const inputErrCls =
    'w-full px-4 py-3 rounded-xl border border-red-300 focus:ring-2 focus:ring-red-400 focus:border-red-400 outline-none text-sm transition bg-white placeholder:text-gray-300';
  const readonlyCls =
    'w-full px-4 py-3 rounded-xl border border-gray-100 bg-gray-50 text-sm text-gray-500 cursor-not-allowed select-none';

  const joinedDate = new Date(profile.created_at).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'long', year: 'numeric',
  });

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-100 text-3xl mb-3">
          🏪
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Buyer Profile</h1>
        <p className="mt-1 text-sm text-gray-500">Manage your business information</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">

        {/* Account — read-only */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
          <div className="px-6 py-4">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Account</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Email</label>
                <div className={readonlyCls}>{user.email}</div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Role</label>
                <div className={readonlyCls + ' flex items-center gap-2'}>
                  <span className="text-blue-600">🏪</span>
                  <span>Buyer</span>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Member since</label>
                <div className={readonlyCls}>{joinedDate}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Personal details */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
          <div className="px-6 py-4">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Personal Details</h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="fullName" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Full Name
                </label>
                <input
                  id="fullName"
                  type="text"
                  placeholder="Your full name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  maxLength={120}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="phone" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Phone Number
                </label>
                <input
                  id="phone"
                  type="tel"
                  placeholder="e.g. +91 98765 43210"
                  value={phone}
                  onChange={(e) => { setPhone(e.target.value); setFieldErrors((fe) => ({ ...fe, phone: '' })); }}
                  maxLength={20}
                  className={fieldErrors.phone ? inputErrCls : inputCls}
                />
                {fieldErrors.phone && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.phone}</p>
                )}
              </div>
            </div>
          </div>

          {/* Business details */}
          <div className="px-6 py-4 border-t border-gray-50">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Business Details</h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="companyName" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Company / Business Name
                </label>
                <input
                  id="companyName"
                  type="text"
                  placeholder="e.g. FreshMart Pvt Ltd"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  maxLength={150}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="businessType" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Business Type
                </label>
                <select
                  id="businessType"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  className={inputCls}
                >
                  <option value="">Select type…</option>
                  {BUSINESS_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Location */}
          <div className="px-6 py-4 border-t border-gray-50">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Business Location</h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="state" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  State
                </label>
                <input
                  id="state"
                  type="text"
                  placeholder="e.g. Andhra Pradesh"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  maxLength={80}
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="district" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  District
                </label>
                <input
                  id="district"
                  type="text"
                  placeholder="e.g. Vijayawada"
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  maxLength={80}
                  className={inputCls}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Feedback */}
        {saveError && (
          <div className="px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
            {saveError}
          </div>
        )}
        {saved && (
          <div className="px-4 py-3 rounded-xl bg-green-50 border border-green-200 text-sm text-green-700 flex items-center gap-2">
            <span>✓</span> Profile saved successfully.
          </div>
        )}

        <button
          type="submit"
          disabled={saving || !isDirty}
          className="w-full py-3 rounded-xl font-semibold text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {saving ? 'Saving…' : isDirty ? 'Save Changes' : 'No Changes'}
        </button>
      </form>
    </div>
  );
}
