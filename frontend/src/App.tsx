import React, { useState } from 'react';
import {
  Sprout,
  ArrowLeft,
  AlertCircle,
  MapPin,
  Calendar,
  Clock,
  Scale,
  Sparkles,
  RefreshCw,
  TrendingUp,
  Truck,
  Star,
  Building2,
  ShoppingCart,
  Store,
  Users,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FarmerProduceForm {
  crop: string;
  quantity: string;
  quality: 'Premium' | 'Standard' | 'Low';
  location: string;
  harvest_date: string;
  shelf_life_days: string;
}

interface FormErrors {
  crop?: string;
  quantity?: string;
  quality?: string;
  location?: string;
  harvest_date?: string;
  shelf_life_days?: string;
}

interface ValidatedProduceData {
  crop: string;
  quantity: number;
  quality: string;
  location: string;
  harvest_date: string;
  shelf_life_days: number;
}

interface Opportunity {
  id: number;
  name: string;
  type: string;
  price_per_kg: number;
  maximum_capacity_kg: number;
  distance_km: number;
  estimated_transport_cost: number;
  estimated_travel_time_minutes: number;
  demand_level: 'High' | 'Medium' | 'Low';
  minimum_quality: 'Premium' | 'Standard' | 'Low';
  spoilage_risk: 'High' | 'Medium' | 'Low';
}

type AppView = 'home' | 'form' | 'opportunities';

// ---------------------------------------------------------------------------
// Helper utilities
// ---------------------------------------------------------------------------

const getTodayString = () => new Date().toISOString().split('T')[0];

function buyerTypeIcon(type: string) {
  switch (type) {
    case 'Direct Buyer':  return <Users className="w-4 h-4" />;
    case 'Wholesale Buyer': return <Building2 className="w-4 h-4" />;
    case 'Local Market':  return <Store className="w-4 h-4" />;
    case 'Retail Buyer':  return <ShoppingCart className="w-4 h-4" />;
    default:              return <Building2 className="w-4 h-4" />;
  }
}

function buyerTypeColor(type: string) {
  switch (type) {
    case 'Direct Buyer':    return 'bg-blue-50 text-blue-700 border-blue-200';
    case 'Wholesale Buyer': return 'bg-violet-50 text-violet-700 border-violet-200';
    case 'Local Market':    return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'Retail Buyer':    return 'bg-pink-50 text-pink-700 border-pink-200';
    default:                return 'bg-stone-50 text-stone-700 border-stone-200';
  }
}

function demandBadge(level: string) {
  switch (level) {
    case 'High':   return 'bg-green-100 text-green-800';
    case 'Medium': return 'bg-yellow-100 text-yellow-800';
    case 'Low':    return 'bg-red-100 text-red-800';
    default:       return 'bg-stone-100 text-stone-700';
  }
}

function spoilageRiskBadge(risk: string) {
  switch (risk) {
    case 'Low':    return 'bg-green-100 text-green-800';
    case 'Medium': return 'bg-yellow-100 text-yellow-800';
    case 'High':   return 'bg-red-100 text-red-800';
    default:       return 'bg-stone-100 text-stone-700';
  }
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------

export default function App() {
  const [view, setView] = useState<AppView>('home');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingOpportunities, setIsLoadingOpportunities] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [produceData, setProduceData] = useState<ValidatedProduceData | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);

  const [formData, setFormData] = useState<FarmerProduceForm>({
    crop: '',
    quantity: '',
    quality: 'Standard',
    location: '',
    harvest_date: getTodayString(),
    shelf_life_days: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});

  // Reset to homepage
  const handleReset = () => {
    setView('home');
    setProduceData(null);
    setOpportunities([]);
    setApiError(null);
    setErrors({});
    setFormData({
      crop: '',
      quantity: '',
      quality: 'Standard',
      location: '',
      harvest_date: getTodayString(),
      shelf_life_days: '',
    });
  };

  // Client-side validation
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    if (!formData.crop.trim()) newErrors.crop = 'Please enter produce or crop name';

    const qty = parseFloat(formData.quantity);
    if (!formData.quantity.trim() || isNaN(qty) || qty <= 0)
      newErrors.quantity = 'Quantity must be a positive number greater than 0';

    if (!['Premium', 'Standard', 'Low'].includes(formData.quality))
      newErrors.quality = 'Please select a valid quality grade';

    if (!formData.location.trim())
      newErrors.location = 'Please enter your farm location or district';

    if (!formData.harvest_date)
      newErrors.harvest_date = 'Please select a harvest date';
    else if (formData.harvest_date > getTodayString())
      newErrors.harvest_date = 'Harvest date cannot be in the future';

    const shelf = parseInt(formData.shelf_life_days, 10);
    if (!formData.shelf_life_days.trim() || isNaN(shelf) || shelf <= 0)
      newErrors.shelf_life_days = 'Shelf life must be at least 1 day';
    else if (shelf > 365)
      newErrors.shelf_life_days = 'Shelf life must be 365 days or less';

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Submit form → validate on backend → fetch opportunities
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);
    if (!validateForm()) return;

    setIsSubmitting(true);
    const payload = {
      crop: formData.crop.trim(),
      quantity: parseFloat(formData.quantity),
      quality: formData.quality,
      location: formData.location.trim(),
      harvest_date: formData.harvest_date,
      shelf_life_days: parseInt(formData.shelf_life_days, 10),
    };

    try {
      // Step 1: validate produce input
      const res = await fetch('http://localhost:8000/api/decision/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        const msg = err?.detail
          ? (Array.isArray(err.detail) ? err.detail.map((d: any) => d.msg).join(', ') : err.detail)
          : `Server error (${res.status})`;
        throw new Error(msg);
      }

      const result = await res.json();
      setProduceData(result.data);
      setIsSubmitting(false);

      // Step 2: fetch opportunities
      setIsLoadingOpportunities(true);
      const oppRes = await fetch('http://localhost:8000/api/opportunities');
      if (!oppRes.ok) throw new Error('Failed to load opportunities');
      const oppData: Opportunity[] = await oppRes.json();
      setOpportunities(oppData);
      setView('opportunities');
    } catch (err: any) {
      setApiError(err.message || 'Could not connect to the backend server.');
    } finally {
      setIsSubmitting(false);
      setIsLoadingOpportunities(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-[#FAF9F5] text-stone-800 flex flex-col font-sans">

      {/* ── Navigation ── */}
      <header className="border-b border-stone-200/80 bg-white/90 backdrop-blur sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <div onClick={handleReset} className="flex items-center space-x-2.5 cursor-pointer group">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center text-white shadow-sm group-hover:bg-emerald-700 transition">
              <Sprout className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xl font-bold text-emerald-900 tracking-tight block leading-tight">Farm2Value</span>
              <span className="text-[10px] uppercase font-semibold text-emerald-700 tracking-wider">From Harvest to Value</span>
            </div>
          </div>
          <span className="text-xs font-medium bg-emerald-50 text-emerald-800 px-3 py-1 rounded-full border border-emerald-200/60">
            Problem Statement 3
          </span>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 max-w-5xl mx-auto px-4 sm:px-6 py-10 flex flex-col items-center justify-start w-full">

        {/* ════════════════ HOME ════════════════ */}
        {view === 'home' && (
          <div className="text-center max-w-xl mx-auto py-16">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-100/70 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-6 shadow-sm">
              <Sparkles className="w-3.5 h-3.5" />
              From Harvest to Value
            </div>
            <h1 className="text-5xl font-black text-stone-900 tracking-tight mb-4 leading-tight">Farm2Value</h1>
            <p className="text-xl text-stone-600 mb-10 max-w-md mx-auto">
              Make smarter farm-to-market selling decisions.
            </p>
            <button
              onClick={() => { setView('form'); setApiError(null); }}
              className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-white bg-emerald-700 hover:bg-emerald-800 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-95"
            >
              Start Selling Decision <span className="text-emerald-200">→</span>
            </button>
          </div>
        )}

        {/* ════════════════ FORM ════════════════ */}
        {view === 'form' && (
          <div className="w-full max-w-xl bg-white rounded-2xl shadow-sm border border-stone-200/90 overflow-hidden">
            {/* Header */}
            <div className="bg-gradient-to-r from-emerald-800 to-emerald-900 px-6 sm:px-8 py-5 text-white flex items-center gap-3">
              <button
                type="button"
                onClick={handleReset}
                className="p-1.5 -ml-1.5 rounded-lg text-emerald-200 hover:text-white hover:bg-emerald-700/50 transition"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h2 className="text-xl font-bold tracking-tight">Farmer Produce Input</h2>
                <p className="text-xs text-emerald-200">Step 1 of 2 — Enter your produce details</p>
              </div>
            </div>

            <div className="p-6 sm:p-8">
              {apiError && (
                <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3 text-amber-900 text-sm">
                  <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-semibold block">Error:</strong>
                    <span>{apiError}</span>
                  </div>
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate className="space-y-5">
                {/* 1. Produce / Crop */}
                <Field label="1. Produce / Crop" error={errors.crop}>
                  <IconInput icon={<Sprout className="w-4 h-4" />} error={!!errors.crop}>
                    <input
                      type="text"
                      placeholder="e.g., Tomatoes, Onions, Potatoes"
                      value={formData.crop}
                      onChange={e => { setFormData({ ...formData, crop: e.target.value }); if (errors.crop) setErrors({ ...errors, crop: undefined }); }}
                      className="bg-transparent w-full outline-none text-sm placeholder:text-stone-400"
                    />
                  </IconInput>
                </Field>

                {/* 2. Quantity */}
                <Field label="2. Quantity (kg)" error={errors.quantity}>
                  <IconInput icon={<Scale className="w-4 h-4" />} error={!!errors.quantity}>
                    <input
                      type="number"
                      step="any"
                      min="0.1"
                      placeholder="e.g., 500"
                      value={formData.quantity}
                      onChange={e => { setFormData({ ...formData, quantity: e.target.value }); if (errors.quantity) setErrors({ ...errors, quantity: undefined }); }}
                      className="bg-transparent w-full outline-none text-sm placeholder:text-stone-400"
                    />
                  </IconInput>
                </Field>

                {/* 3. Quality */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1.5">
                    3. Quality Grade <span className="text-red-500">*</span>
                  </label>
                  <div className="grid grid-cols-3 gap-2.5">
                    {(['Premium', 'Standard', 'Low'] as const).map(tier => (
                      <button
                        key={tier}
                        type="button"
                        onClick={() => { setFormData({ ...formData, quality: tier }); if (errors.quality) setErrors({ ...errors, quality: undefined }); }}
                        className={`py-2.5 px-3 rounded-xl border text-sm font-semibold transition text-center ${
                          formData.quality === tier
                            ? 'bg-emerald-700 text-white border-emerald-700 shadow-sm'
                            : 'bg-stone-50 border-stone-200 text-stone-700 hover:bg-stone-100'
                        }`}
                      >
                        {tier}
                      </button>
                    ))}
                  </div>
                  {errors.quality && <ErrorMsg msg={errors.quality} />}
                </div>

                {/* 4. Location */}
                <Field label="4. Farmer Location" error={errors.location}>
                  <IconInput icon={<MapPin className="w-4 h-4" />} error={!!errors.location}>
                    <input
                      type="text"
                      placeholder="e.g., Nashik District, Maharashtra"
                      value={formData.location}
                      onChange={e => { setFormData({ ...formData, location: e.target.value }); if (errors.location) setErrors({ ...errors, location: undefined }); }}
                      className="bg-transparent w-full outline-none text-sm placeholder:text-stone-400"
                    />
                  </IconInput>
                </Field>

                {/* 5. Harvest date */}
                <Field label="5. Harvest Date" error={errors.harvest_date}>
                  <IconInput icon={<Calendar className="w-4 h-4" />} error={!!errors.harvest_date}>
                    <input
                      type="date"
                      max={getTodayString()}
                      value={formData.harvest_date}
                      onChange={e => { setFormData({ ...formData, harvest_date: e.target.value }); if (errors.harvest_date) setErrors({ ...errors, harvest_date: undefined }); }}
                      className="bg-transparent w-full outline-none text-sm"
                    />
                  </IconInput>
                </Field>

                {/* 6. Shelf life */}
                <Field label="6. Remaining Shelf Life (days)" error={errors.shelf_life_days}>
                  <IconInput icon={<Clock className="w-4 h-4" />} error={!!errors.shelf_life_days}>
                    <input
                      type="number"
                      min="1"
                      max="365"
                      placeholder="e.g., 5"
                      value={formData.shelf_life_days}
                      onChange={e => { setFormData({ ...formData, shelf_life_days: e.target.value }); if (errors.shelf_life_days) setErrors({ ...errors, shelf_life_days: undefined }); }}
                      className="bg-transparent w-full outline-none text-sm placeholder:text-stone-400"
                    />
                  </IconInput>
                </Field>

                {/* Buttons */}
                <div className="pt-4 flex gap-3">
                  <button
                    type="button"
                    onClick={handleReset}
                    className="py-3 px-5 rounded-xl border border-stone-300 hover:bg-stone-50 text-stone-700 font-semibold text-sm transition"
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || isLoadingOpportunities}
                    className="flex-1 py-3 px-5 bg-emerald-700 hover:bg-emerald-800 disabled:bg-emerald-400 text-white font-semibold rounded-xl shadow-md transition flex items-center justify-center gap-2"
                  >
                    {isSubmitting || isLoadingOpportunities ? (
                      <><RefreshCw className="w-4 h-4 animate-spin" /> Loading...</>
                    ) : (
                      'Continue'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ════════════════ OPPORTUNITIES ════════════════ */}
        {view === 'opportunities' && produceData && (
          <div className="w-full">
            {/* Produce summary bar */}
            <div className="bg-white border border-stone-200 rounded-2xl px-5 py-4 mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm shadow-sm">
              <button
                onClick={() => setView('form')}
                className="flex items-center gap-1.5 text-emerald-700 hover:text-emerald-900 font-semibold transition"
              >
                <ArrowLeft className="w-4 h-4" /> Back to Form
              </button>
              <div className="h-5 border-l border-stone-200 hidden sm:block" />
              <span className="font-semibold text-stone-900">{produceData.crop}</span>
              <span className="text-stone-500">·</span>
              <span className="text-stone-600">{produceData.quantity} kg</span>
              <span className="text-stone-500">·</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${
                produceData.quality === 'Premium' ? 'bg-amber-50 text-amber-800 border-amber-200' :
                produceData.quality === 'Standard' ? 'bg-blue-50 text-blue-800 border-blue-200' :
                'bg-stone-100 text-stone-700 border-stone-200'
              }`}>{produceData.quality}</span>
              <span className="text-stone-500">·</span>
              <span className="text-stone-600 flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{produceData.location}</span>
              <span className="text-stone-500">·</span>
              <span className="text-stone-600 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{produceData.shelf_life_days} days shelf life</span>
            </div>

            {/* Section title */}
            <div className="flex items-center gap-3 mb-4">
              <TrendingUp className="w-5 h-5 text-emerald-700" />
              <h2 className="text-xl font-bold text-stone-900">Available Selling Opportunities</h2>
              <span className="ml-auto text-xs text-stone-400 font-medium bg-stone-100 px-2.5 py-1 rounded-full">
                {opportunities.length} options · Demo Data
              </span>
            </div>

            {/* Opportunity Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {opportunities.map(opp => (
                <div
                  key={opp.id}
                  className="bg-white rounded-2xl border border-stone-200 shadow-sm hover:shadow-md hover:border-emerald-200 transition-all p-5 flex flex-col gap-4"
                >
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-stone-900 text-sm leading-snug line-clamp-2">{opp.name}</h3>
                    </div>
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border shrink-0 ${buyerTypeColor(opp.type)}`}>
                      {buyerTypeIcon(opp.type)}
                      {opp.type}
                    </span>
                  </div>

                  {/* Price — highlighted */}
                  <div className="bg-emerald-50 border border-emerald-100 rounded-xl px-4 py-3 text-center">
                    <p className="text-xs text-emerald-700 font-medium mb-0.5">Price per kg</p>
                    <p className="text-2xl font-black text-emerald-800">₹{opp.price_per_kg.toFixed(2)}</p>
                  </div>

                  {/* Stats grid */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <Stat icon={<Scale className="w-3.5 h-3.5 text-stone-400" />} label="Max Capacity" value={`${opp.maximum_capacity_kg.toLocaleString()} kg`} />
                    <Stat icon={<MapPin className="w-3.5 h-3.5 text-stone-400" />} label="Distance" value={`${opp.distance_km} km`} />
                    <Stat icon={<Truck className="w-3.5 h-3.5 text-stone-400" />} label="Transport Cost" value={`₹${opp.estimated_transport_cost.toLocaleString()}`} />
                    <Stat icon={<Clock className="w-3.5 h-3.5 text-stone-400" />} label="Travel Time" value={`${opp.estimated_travel_time_minutes} min`} />
                  </div>

                  {/* Badges row */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${demandBadge(opp.demand_level)}`}>
                      Demand: {opp.demand_level}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${spoilageRiskBadge(opp.spoilage_risk)}`}>
                      Spoilage Risk: {opp.spoilage_risk}
                    </span>
                  </div>

                  {/* Min quality required */}
                  <div className="flex items-center gap-1.5 text-xs text-stone-500 border-t border-stone-100 pt-3 mt-auto">
                    <Star className="w-3.5 h-3.5 text-amber-500" />
                    <span>Minimum Quality Required: <strong className="text-stone-700">{opp.minimum_quality}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="py-6 border-t border-stone-200/80 text-center text-xs text-stone-400 mt-10">
        Farm2Value &copy; 2026 · Problem Statement 3: From Harvest to Value · <span className="italic">Sample data for demo purposes only</span>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small reusable components
// ---------------------------------------------------------------------------

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-stone-700 mb-1.5">
        {label} <span className="text-red-500">*</span>
      </label>
      {children}
      {error && <ErrorMsg msg={error} />}
    </div>
  );
}

function IconInput({ icon, error, children }: { icon: React.ReactNode; error: boolean; children: React.ReactNode }) {
  return (
    <div className={`flex items-center gap-2 px-3.5 py-2.5 rounded-xl border transition ${
      error
        ? 'border-red-400 bg-red-50/30 focus-within:ring-1 focus-within:ring-red-500'
        : 'border-stone-300 bg-white focus-within:border-emerald-600 focus-within:ring-1 focus-within:ring-emerald-600'
    }`}>
      <span className="text-stone-400 shrink-0">{icon}</span>
      {children}
    </div>
  );
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <p className="text-xs text-red-600 mt-1.5 flex items-center gap-1">
      <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {msg}
    </p>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-stone-50 rounded-lg px-2.5 py-2 flex items-center gap-1.5">
      {icon}
      <div className="min-w-0">
        <p className="text-stone-400 text-[10px] leading-tight">{label}</p>
        <p className="font-semibold text-stone-700 text-xs truncate">{value}</p>
      </div>
    </div>
  );
}
