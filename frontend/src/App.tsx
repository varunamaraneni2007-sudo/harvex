import React, { useState, useEffect, useRef } from 'react';
import type { User } from '@supabase/supabase-js';
import { supabase } from './lib/supabaseClient';
import AuthPage from './AuthPage';
import RoleSelectPage from './RoleSelectPage';
import ConsentPage from './ConsentPage';
import FarmerProfilePage from './FarmerProfilePage';
import type { UserRole, Profile } from './lib/roleService';
import { fetchProfile } from './lib/roleService';
import { fetchConsent } from './lib/consentService';

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

interface Market {
  market_name: string;
  location: string;
}

interface MarketDiscoveryResult {
  market_id: string;
  market_name: string;
  state: string;
  district: string;
  market_type: string;
  source: string;
  commodities: string[];
  lat: number | null;
  lng: number | null;
  active: boolean;
}

interface PriceInfo {
  market_id: string;
  commodity: string;
  min_price_per_kg: number | null;
  modal_price_per_kg: number | null;
  max_price_per_kg: number | null;
  price_date: string | null;
  source: string;
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
  explanation: string | null;
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
  explanation: string | null;
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
    <span className="text-xs text-blue-400 ml-1 tabular-nums whitespace-nowrap">
      · {parts.join(' · ')}
    </span>
  );
}

type View = 'home' | 'form' | 'results' | 'marketplace' | 'profile';

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
        isRecommended
          ? 'border-green-300 ring-2 ring-green-100'
          : 'border-gray-100'
      }`}
    >
      <div className={`px-6 pt-5 ${isRecommended ? 'pb-0' : 'pb-5'}`}>
        {isRecommended && (
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-bold bg-green-600 text-white px-3 py-1 rounded-full tracking-wide">
              ✓ RECOMMENDED
            </span>
            <span className="text-xs text-gray-400">Optimal harvest strategy</span>
          </div>
        )}

        <h3 className={`font-bold text-gray-900 ${isRecommended ? 'text-lg' : 'text-base'}`}>
          {strategy.strategy_name}
        </h3>
        <p className="text-sm text-gray-500 mt-1">{strategy.strategy_description}</p>

        <div className={`space-y-2.5 ${isRecommended ? 'mt-5' : 'mt-4'}`}>
          {strategy.allocations.map((ch) => (
            <div key={ch.market_name} className="flex items-center gap-3">
              <span
                className={`font-semibold text-gray-800 tabular-nums text-right flex-shrink-0 ${
                  isRecommended ? 'text-sm w-20' : 'text-sm w-16'
                }`}
              >
                {ch.quantity_kg} kg
              </span>
              <span className="text-gray-300 font-bold">→</span>
              <div className="flex-1 min-w-0">
                <span className={`font-medium text-gray-900 ${isRecommended ? 'text-sm' : 'text-sm'}`}>
                  {ch.market_name}
                </span>
                <span className="text-xs text-gray-400 ml-1">({ch.location})</span>
                <DistanceBadge marketName={ch.market_name} distances={distances} />
              </div>
              <span
                className={`font-semibold text-green-700 flex-shrink-0 tabular-nums ${
                  isRecommended ? 'text-sm' : 'text-sm'
                }`}
              >
                {fmt(ch.net_value)}
              </span>
            </div>
          ))}
        </div>

        <div
          className={`flex items-center justify-between mt-4 pt-4 border-t border-gray-100 ${
            isRecommended ? 'pb-5' : 'pb-0'
          }`}
        >
          <span className="text-xs text-gray-400">
            {strategy.total_quantity_allocated} kg allocated
          </span>
          <div className="text-right">
            <span className="text-xs text-gray-400 mr-2">Total Net Value</span>
            <span
              className={`font-bold text-green-700 ${isRecommended ? 'text-2xl' : 'text-base'}`}
            >
              {fmt(strategy.total_net_value)}
            </span>
          </div>
        </div>
      </div>

      {isRecommended && (
        <>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="w-full px-6 py-3 text-xs text-gray-400 hover:text-gray-600 bg-gray-50 border-t border-gray-100 flex items-center justify-center gap-1.5 transition-colors font-medium"
          >
            {expanded ? '▲ Hide breakdown' : '▼ Show full cost breakdown'}
          </button>

          {expanded && (
            <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
              <div className="overflow-x-auto">
                <table className="w-full text-xs mt-3 min-w-[480px]">
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
        <p className="text-sm text-gray-400 italic">No viable allocation</p>
      ) : (
        <div className="space-y-2 mb-3">
          {plan.allocations.map((ch) => (
            <div key={ch.market_name} className="flex items-center justify-between gap-2 text-sm">
              <span className="text-gray-600 truncate">{ch.market_name}</span>
              <span className="tabular-nums text-gray-700 flex-shrink-0 font-medium">{ch.quantity_kg} kg</span>
            </div>
          ))}
        </div>
      )}
      <div className="border-t border-gray-200 pt-2.5 space-y-1.5 text-sm">
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
        <div className="flex justify-between font-semibold mt-2 pt-2 border-t border-gray-200">
          <span className="text-gray-700">Net value</span>
          <span className={`tabular-nums ${accent}`}>{fmt(plan.total_net_value)}</span>
        </div>
      </div>
    </div>
  );
}

// ── Plan A / B / C card ───────────────────────────────────────────────────────

const PLAN_COLORS: Record<string, { badge: string; accent: string; border: string; bg: string }> = {
  A: { badge: 'bg-green-600',  accent: 'text-green-700',  border: 'border-green-200',  bg: 'bg-green-50' },
  B: { badge: 'bg-blue-600',   accent: 'text-blue-700',   border: 'border-blue-200',   bg: 'bg-blue-50'  },
  C: { badge: 'bg-orange-500', accent: 'text-orange-600', border: 'border-orange-200', bg: 'bg-orange-50' },
};

function PlanCard({ plan, distances }: { plan: PlanResult; distances: Map<string, DistanceInfo> }) {
  const [expanded, setExpanded] = useState(false);
  const colors = PLAN_COLORS[plan.plan_label] ?? PLAN_COLORS['A'];

  return (
    <div className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${colors.border}`}>
      <div className="px-6 pt-5 pb-5">
        <div className="flex items-center gap-2 mb-2">
          <span className={`text-xs font-bold text-white px-3 py-1 rounded-full tracking-wide ${colors.badge}`}>
            PLAN {plan.plan_label}
          </span>
          <span className="text-base font-bold text-gray-900">{plan.plan_name}</span>
        </div>
        <p className="text-sm text-gray-500 mb-4">{plan.plan_description}</p>

        <div className="space-y-2.5 mb-4">
          {plan.allocations.map((ch) => (
            <div key={ch.market_name} className="flex items-center gap-3">
              <span className="text-sm font-semibold text-gray-800 tabular-nums w-16 text-right flex-shrink-0">
                {ch.quantity_kg} kg
              </span>
              <span className="text-gray-300 font-bold">→</span>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-gray-900">{ch.market_name}</span>
                <span className="text-xs text-gray-400 ml-1">({ch.location})</span>
                <DistanceBadge marketName={ch.market_name} distances={distances} />
              </div>
              <span className={`text-sm font-semibold tabular-nums flex-shrink-0 ${colors.accent}`}>
                {fmt(ch.net_value)}
              </span>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            {plan.total_quantity_allocated} kg · {plan.allocations.length} market{plan.allocations.length !== 1 ? 's' : ''}
          </span>
          <div className="text-right">
            <span className="text-xs text-gray-400 mr-1">Net value</span>
            <span className={`text-lg font-bold ${colors.accent}`}>{fmt(plan.total_net_value)}</span>
          </div>
        </div>

        <div className={`mt-3 rounded-xl px-3 py-2.5 text-sm text-amber-800 border border-amber-100 bg-amber-50`}>
          ⚡ {plan.plan_tradeoff}
        </div>
      </div>

      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full px-6 py-3 text-xs text-gray-400 hover:text-gray-600 bg-gray-50 border-t border-gray-100 flex items-center justify-center gap-1.5 transition-colors font-medium"
      >
        {expanded ? '▲ Hide breakdown' : '▼ Show full breakdown'}
      </button>

      {expanded && (
        <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
          <div className="overflow-x-auto">
            <table className="w-full text-xs mt-3 min-w-[480px]">
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
        </div>
      )}
    </div>
  );
}

// ── (BuyerCard removed — discovery view now uses ApmcCard) ───────────────────

// ── APMC market card (discovery view) ────────────────────────────────────────

const MARKET_TYPE_STYLE: Record<string, string> = {
  'APMC':              'bg-green-100 text-green-700',
  'Wholesale':         'bg-blue-100 text-blue-700',
  'Commission Agent':  'bg-purple-100 text-purple-700',
};

function ApmcCard({
  market,
  priceInfo,
  onUseInPlan,
  hasResults,
}: {
  market: MarketDiscoveryResult;
  priceInfo?: PriceInfo;
  onUseInPlan: () => void;
  hasResults: boolean;
}) {
  const typeStyle = MARKET_TYPE_STYLE[market.market_type] || 'bg-gray-100 text-gray-600';
  const commodityDisplay = market.commodities.includes('all')
    ? 'All crops accepted'
    : market.commodities.slice(0, 4).join(', ') + (market.commodities.length > 4 ? ' …' : '');

  const fmtPrice = (v: number | null) =>
    v !== null && v !== undefined ? `₹${v.toFixed(2)}/kg` : '—';

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div>
            <h3 className="font-bold text-gray-900 text-base leading-snug">{market.market_name}</h3>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${typeStyle}`}>
                {market.market_type}
              </span>
              <span className="text-xs text-gray-400">📍 {market.district}, {market.state}</span>
            </div>
          </div>
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-500 flex-shrink-0 whitespace-nowrap">
            {market.source}
          </span>
        </div>

        <div className="bg-gray-50 rounded-xl px-3 py-2 mb-3">
          <div className="text-xs text-gray-400 font-medium mb-0.5">Commodities</div>
          <div className="text-sm text-gray-700">{commodityDisplay}</div>
        </div>

        {/* Current Market Price section */}
        {priceInfo ? (
          <div className="bg-green-50 border border-green-100 rounded-xl px-3 py-2.5 mb-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-green-700">Current Market Price</span>
              <span className="text-xs text-gray-400">
                {priceInfo.price_date ? `as of ${priceInfo.price_date}` : ''}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-gray-400 mb-0.5">Min</div>
                <div className="text-sm font-semibold text-gray-800">{fmtPrice(priceInfo.min_price_per_kg)}</div>
              </div>
              <div className="border-x border-green-100">
                <div className="text-xs text-green-600 font-semibold mb-0.5">Modal</div>
                <div className="text-sm font-bold text-green-700">{fmtPrice(priceInfo.modal_price_per_kg)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400 mb-0.5">Max</div>
                <div className="text-sm font-semibold text-gray-800">{fmtPrice(priceInfo.max_price_per_kg)}</div>
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-1.5 text-center">
              Wholesale/mandi · {priceInfo.source}
            </div>
          </div>
        ) : (
          <div className="bg-gray-50 rounded-xl px-3 py-2 mb-3 text-center">
            <span className="text-xs text-gray-400">No current price available</span>
          </div>
        )}

        <button
          onClick={onUseInPlan}
          className="w-full py-2 px-3 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-xl transition active:scale-[0.98]"
        >
          {hasResults ? '→ View My Plan' : '+ Plan with this Market'}
        </button>
      </div>
    </div>
  );
}

// ── Places types ─────────────────────────────────────────────────────────────

interface PlaceSelection {
  address: string;
  placeId: string;
  lat: number | null;
  lng: number | null;
}

interface PlaceSuggestion {
  place_id: string;
  description: string;
  main_text: string;
  secondary_text: string;
}

// ── Places Location Selector ──────────────────────────────────────────────────

function PlacesLocationSelector({
  selected,
  onSelect,
  onClear,
  inputCls,
}: {
  selected: PlaceSelection | null;
  onSelect: (place: PlaceSelection) => void;
  onClear: () => void;
  inputCls: string;
}) {
  const [inputText, setInputText] = useState('');
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [mapsAvailable, setMapsAvailable] = useState<boolean | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  // Stable billing session token for the lifetime of this component instance
  const sessionToken = useRef(`${Date.now()}-${Math.random().toString(36).slice(2)}`).current;
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced autocomplete fetch whenever inputText changes
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!inputText.trim() || inputText.trim().length < 2) {
      setSuggestions([]);
      setDropdownOpen(false);
      return;
    }

    debounceRef.current = setTimeout(() => {
      setLoading(true);
      fetch(
        `/api/places/autocomplete?input=${encodeURIComponent(inputText)}&session_token=${encodeURIComponent(sessionToken)}`
      )
        .then((r) => r.json())
        .then((data) => {
          setMapsAvailable(data.maps_configured ?? false);
          const sugg: PlaceSuggestion[] = data.suggestions || [];
          setSuggestions(sugg);
          if (sugg.length > 0) setDropdownOpen(true);
        })
        .catch(() => {
          setMapsAvailable(false);
          setSuggestions([]);
        })
        .finally(() => setLoading(false));
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [inputText, sessionToken]);

  function handleSelectSuggestion(s: PlaceSuggestion) {
    setDropdownOpen(false);
    setSuggestions([]);
    setInputText('');
    setDetailLoading(true);
    fetch(`/api/places/details?place_id=${encodeURIComponent(s.place_id)}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.place) {
          onSelect({
            address: data.place.formatted_address || s.description,
            placeId: data.place.place_id || s.place_id,
            lat: data.place.lat ?? null,
            lng: data.place.lng ?? null,
          });
        } else {
          onSelect({ address: s.description, placeId: s.place_id, lat: null, lng: null });
        }
      })
      .catch(() => {
        onSelect({ address: s.description, placeId: s.place_id, lat: null, lng: null });
      })
      .finally(() => setDetailLoading(false));
  }

  function handleFallbackConfirm() {
    const text = inputText.trim();
    if (text) {
      onSelect({ address: text, placeId: '', lat: null, lng: null });
      setInputText('');
    }
  }

  // ── Confirmed chip view ───────────────────────────────────────────────────
  if (selected) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 rounded-xl border border-green-300 bg-green-50">
        <span className="text-green-600 flex-shrink-0">📍</span>
        <span className="flex-1 text-sm text-gray-800 font-medium truncate">{selected.address}</span>
        {selected.placeId && (
          <span className="text-xs font-medium text-green-600 flex-shrink-0">✓ Verified</span>
        )}
        <button
          type="button"
          onClick={onClear}
          className="text-gray-300 hover:text-gray-600 text-sm ml-1 flex-shrink-0 transition"
          aria-label="Change location"
        >✕</button>
      </div>
    );
  }

  // ── Input + dropdown view ─────────────────────────────────────────────────
  return (
    <div className="relative">
      <div className="relative">
        <input
          type="text"
          placeholder="Type your village, town or city…"
          value={detailLoading ? 'Loading place details…' : inputText}
          disabled={detailLoading}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              if (mapsAvailable === false) handleFallbackConfirm();
            }
          }}
          onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
          autoComplete="off"
          className={`${inputCls} ${detailLoading ? 'text-gray-400' : ''}`}
        />
        {(loading || detailLoading) && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-300 text-xs pointer-events-none">
            Searching…
          </span>
        )}
      </div>

      {/* Suggestions dropdown */}
      {dropdownOpen && suggestions.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
          {suggestions.map((s) => (
            <button
              key={s.place_id}
              type="button"
              onMouseDown={(e) => e.preventDefault()} // prevent blur before click
              onClick={() => handleSelectSuggestion(s)}
              className="w-full text-left px-4 py-3 hover:bg-green-50 transition border-b border-gray-50 last:border-b-0"
            >
              <div className="flex items-start gap-2">
                <span className="text-green-500 flex-shrink-0 mt-0.5 text-sm">📍</span>
                <div>
                  <div className="text-sm font-medium text-gray-800">
                    {s.main_text || s.description}
                  </div>
                  {s.secondary_text && (
                    <div className="text-xs text-gray-400 mt-0.5">{s.secondary_text}</div>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Fallback hint when Maps API not configured */}
      {mapsAvailable === false && inputText.trim().length >= 2 && (
        <div className="mt-1.5 flex items-center gap-2">
          <span className="text-xs text-gray-400 flex-1">
            Location search unavailable — press <kbd className="font-mono bg-gray-100 px-1 rounded">Enter</kbd> or click Use to continue.
          </span>
          <button
            type="button"
            onClick={handleFallbackConfirm}
            className="text-xs px-2.5 py-1 rounded-lg bg-green-600 text-white hover:bg-green-700 transition font-medium"
          >
            Use ↵
          </button>
        </div>
      )}
    </div>
  );
}

// ── Crop Catalogue ────────────────────────────────────────────────────────────

const CROP_CATALOGUE = [
  { category: 'Vegetables', emoji: '🥦', crops: ['Tomato','Onion','Potato','Brinjal','Cabbage','Cauliflower','Carrot','Green Chilli','Okra','Bottle Gourd','Bitter Gourd','Ridge Gourd','Cucumber','Spinach'] },
  { category: 'Fruits',     emoji: '🍎', crops: ['Mango','Banana','Papaya','Guava','Pomegranate','Watermelon','Muskmelon','Orange','Grapes','Apple'] },
  { category: 'Flowers',    emoji: '🌸', crops: ['Rose','Marigold','Jasmine','Chrysanthemum','Tuberose'] },
  { category: 'Cereals',    emoji: '🌾', crops: ['Rice','Maize','Wheat','Sorghum','Pearl Millet'] },
  { category: 'Pulses',     emoji: '🫘', crops: ['Chickpea','Pigeon Pea','Green Gram','Black Gram','Lentil'] },
  { category: 'Spices',     emoji: '🌶️', crops: ['Turmeric','Ginger','Garlic','Coriander','Cumin','Red Chilli'] },
  { category: 'Oilseeds',   emoji: '🌻', crops: ['Groundnut','Sesame','Sunflower','Soybean'] },
];

// ── Crop Selector Component ───────────────────────────────────────────────────

function CropSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState(CROP_CATALOGUE[0].category);
  const [otherMode, setOtherMode] = useState(false);
  const [otherText, setOtherText] = useState('');

  const allCrops = CROP_CATALOGUE.flatMap((c) => c.crops);
  const isOtherValue = value && !allCrops.includes(value);

  const searchLower = search.trim().toLowerCase();
  const searchResults = searchLower
    ? CROP_CATALOGUE.flatMap((c) => c.crops.filter((cr) => cr.toLowerCase().includes(searchLower)))
    : null;

  const activeCategoryObj = CROP_CATALOGUE.find((c) => c.category === activeCategory)!;

  function selectCrop(name: string) {
    onChange(name);
    setOpen(false);
    setSearch('');
    setOtherMode(false);
  }

  function handleOtherSubmit() {
    const v = otherText.trim();
    if (v) { onChange(v); setOpen(false); setSearch(''); setOtherMode(false); setOtherText(''); }
  }

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm transition bg-white text-left flex items-center justify-between"
      >
        {value ? (
          <span className="flex items-center gap-2">
            <span className="font-medium text-gray-800">{value}</span>
            {isOtherValue && <span className="text-xs text-gray-400">(custom)</span>}
          </span>
        ) : (
          <span className="text-gray-300">Select a crop…</span>
        )}
        <span className="text-gray-400 ml-2">{open ? '▲' : '▼'}</span>
      </button>

      {/* Clear button when a crop is selected */}
      {value && !open && (
        <button
          type="button"
          onClick={() => { onChange(''); setOtherText(''); }}
          className="absolute right-9 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500 text-sm px-1"
          aria-label="Clear crop"
        >✕</button>
      )}

      {/* Dropdown panel */}
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-2xl shadow-xl overflow-hidden">
          {/* Search */}
          <div className="p-3 border-b border-gray-100">
            <input
              autoFocus
              type="text"
              placeholder="Search crops…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none"
            />
          </div>

          {searchResults ? (
            /* Search results grid */
            <div className="p-3 max-h-56 overflow-y-auto">
              {searchResults.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No crops matched. Use "Other" below.</p>
              ) : (
                <div className="grid grid-cols-3 gap-1.5">
                  {searchResults.map((cr) => (
                    <button
                      key={cr}
                      type="button"
                      onClick={() => selectCrop(cr)}
                      className={`text-xs px-2 py-1.5 rounded-lg text-left transition font-medium ${
                        value === cr
                          ? 'bg-green-600 text-white'
                          : 'bg-gray-50 text-gray-700 hover:bg-green-50 hover:text-green-700'
                      }`}
                    >
                      {cr}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Category browser */
            <div className="flex">
              {/* Category tabs */}
              <div className="flex flex-col border-r border-gray-100 min-w-[110px]">
                {CROP_CATALOGUE.map((cat) => (
                  <button
                    key={cat.category}
                    type="button"
                    onClick={() => setActiveCategory(cat.category)}
                    className={`text-xs px-3 py-2.5 text-left transition font-medium ${
                      activeCategory === cat.category
                        ? 'bg-green-50 text-green-700 border-r-2 border-green-500'
                        : 'text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    {cat.emoji} {cat.category}
                  </button>
                ))}
              </div>
              {/* Crop grid */}
              <div className="flex-1 p-3 max-h-56 overflow-y-auto">
                <div className="grid grid-cols-2 gap-1.5">
                  {activeCategoryObj.crops.map((cr) => (
                    <button
                      key={cr}
                      type="button"
                      onClick={() => selectCrop(cr)}
                      className={`text-xs px-2 py-1.5 rounded-lg text-left transition font-medium ${
                        value === cr
                          ? 'bg-green-600 text-white'
                          : 'bg-gray-50 text-gray-700 hover:bg-green-50 hover:text-green-700'
                      }`}
                    >
                      {cr}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Other / custom crop */}
          <div className="border-t border-gray-100 p-3">
            {otherMode ? (
              <div className="flex gap-2">
                <input
                  autoFocus
                  type="text"
                  placeholder="Type crop name…"
                  value={otherText}
                  onChange={(e) => setOtherText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleOtherSubmit(); } }}
                  className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-gray-200 focus:ring-2 focus:ring-green-500 outline-none"
                />
                <button
                  type="button"
                  onClick={handleOtherSubmit}
                  className="px-3 py-1.5 text-sm rounded-lg bg-green-600 text-white font-medium hover:bg-green-700 transition"
                >OK</button>
                <button
                  type="button"
                  onClick={() => setOtherMode(false)}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition"
                >Cancel</button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setOtherMode(true)}
                className="w-full text-xs text-gray-400 hover:text-green-700 hover:bg-green-50 rounded-lg py-1.5 transition text-center font-medium"
              >
                + Other (type a crop name)
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  // ── Auth state ──────────────────────────────────────────────────────────────
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [role, setRole] = useState<UserRole | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [roleLoading, setRoleLoading] = useState(false);
  const [hasConsent, setHasConsent] = useState(false);
  const [consentLoading, setConsentLoading] = useState(false);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      const nextUser = session?.user ?? null;
      setUser(nextUser);
      if (event === 'INITIAL_SESSION') {
        if (nextUser) {
          setRoleLoading(true);
          fetchProfile()
            .then(async (p) => {
              const r = p?.role ?? null;
              setRole(r);
              setProfile(p);
              if (r === 'farmer') {
                setConsentLoading(true);
                const c = await fetchConsent().catch(() => null);
                setHasConsent(c !== null);
                setConsentLoading(false);
              }
            })
            .catch(() => { setRole(null); setProfile(null); })
            .finally(() => { setRoleLoading(false); setAuthLoading(false); });
        } else {
          setRole(null);
          setProfile(null);
          setHasConsent(false);
          setAuthLoading(false);
        }
      } else if (event === 'SIGNED_IN') {
        setRoleLoading(true);
        fetchProfile()
          .then(async (p) => {
            const r = p?.role ?? null;
            setRole(r);
            setProfile(p);
            if (r === 'farmer') {
              setConsentLoading(true);
              const c = await fetchConsent().catch(() => null);
              setHasConsent(c !== null);
              setConsentLoading(false);
            }
          })
          .catch(() => { setRole(null); setProfile(null); })
          .finally(() => setRoleLoading(false));
      } else if (event === 'SIGNED_OUT') {
        setRole(null);
        setProfile(null);
        setHasConsent(false);
      }
    });
    // Fallback: if INITIAL_SESSION never fires (e.g. client throws), clear loading
    supabase.auth.getSession().catch(() => {
      setUser(null);
      setRole(null);
      setAuthLoading(false);
    });
    return () => subscription.unsubscribe();
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setView('home');
  };

  const [view, setView] = useState<View>('home');

  // Form state
  const [crop, setCrop] = useState('');
  const [quantity, setQuantity] = useState('');
  const [quality, setQuality] = useState('Standard');
  const [shelfLife, setShelfLife] = useState('');
  const [farmerLocation, setFarmerLocation] = useState('');
  const [farmerPlaceId, setFarmerPlaceId] = useState('');
  const [farmerLat, setFarmerLat] = useState<number | null>(null);
  const [farmerLng, setFarmerLng] = useState<number | null>(null);
  const [harvestDate, setHarvestDate] = useState('');

  // API state
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [results, setResults] = useState<OptimizeResponse | null>(null);

  // Plans A/B/C state
  const [plansResult, setPlansResult] = useState<PlansResponse | null>(null);
  const [decisionSaved, setDecisionSaved] = useState(false);

  // Explanation state
  const [explanation, setExplanation] = useState<string | null>(null);
  const [explanationOpen, setExplanationOpen] = useState(false);

  // Distance data (fetched non-blocking after submission)
  const [distances, setDistances] = useState<Map<string, DistanceInfo>>(new Map());
  const [mapsLive, setMapsLive] = useState<boolean | null>(null);

  // Market discovery state
  const [discData, setDiscData] = useState<MarketDiscoveryResult[]>([]);
  const [discPrices, setDiscPrices] = useState<Map<string, PriceInfo>>(new Map());
  const [mpLoading, setMpLoading] = useState(false);
  const [mpError, setMpError] = useState<string | null>(null);
  const [mpState, setMpState] = useState('');
  const [mpDistrict, setMpDistrict] = useState('');
  const [mpSearchQ, setMpSearchQ] = useState('');
  const [mpCommodity, setMpCommodity] = useState('');
  const [availableStates, setAvailableStates] = useState<string[]>([]);

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
  const [wiExplanation, setWiExplanation] = useState<string | null>(null);
  const [wiExplanationOpen, setWiExplanationOpen] = useState(false);

  // Fetch markets list when entering results
  useEffect(() => {
    if (view === 'results' && markets.length === 0) {
      fetch('/api/markets')
        .then((r) => r.json())
        .then((data: Market[]) => setMarkets(data))
        .catch(() => {/* non-critical */});
    }
  }, [view]);

  // Load available states when entering discovery view
  useEffect(() => {
    if (view === 'marketplace' && availableStates.length === 0) {
      fetch('/api/markets/states')
        .then((r) => r.json())
        .then((data: { states: string[] }) => setAvailableStates(data.states || []))
        .catch(() => {/* non-critical */});
    }
  }, [view]);

  const fetchDiscovery = async () => {
    setMpLoading(true);
    setMpError(null);
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (mpState) params.set('state', mpState);
      if (mpDistrict.trim()) params.set('district', mpDistrict.trim());
      if (mpSearchQ.trim()) params.set('q', mpSearchQ.trim());
      if (mpCommodity.trim()) params.set('commodity', mpCommodity.trim());
      const resp = await fetch(`/api/markets/discover?${params.toString()}`);
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
      const data: { markets: MarketDiscoveryResult[]; total: number } = await resp.json();
      setDiscData(data.markets);

      // Fetch current mandi prices for the searched commodity (if any)
      if (mpCommodity.trim()) {
        const priceParams = new URLSearchParams({
          commodity: mpCommodity.trim(),
          limit: '200',
        });
        try {
          const priceResp = await fetch(`/api/market-prices?${priceParams.toString()}`);
          if (priceResp.ok) {
            const priceData: { prices: PriceInfo[] } = await priceResp.json();
            const priceMap = new Map<string, PriceInfo>();
            for (const p of priceData.prices) {
              priceMap.set(p.market_id, p);
            }
            setDiscPrices(priceMap);
          }
        } catch {
          // Price fetch is non-critical; discovery results still show
        }
      } else {
        setDiscPrices(new Map());
      }
    } catch (err) {
      setMpError(err instanceof Error ? err.message : 'Failed to load markets.');
    } finally {
      setMpLoading(false);
    }
  };

  const handleUseInMyPlan = (_market: MarketDiscoveryResult) => {
    if (results) {
      setView('results');
    } else {
      setView('form');
    }
  };

  const resetAll = () => {
    setCrop('');
    setQuantity('');
    setQuality('Standard');
    setShelfLife('');
    setFarmerLocation('');
    setFarmerPlaceId('');
    setFarmerLat(null);
    setFarmerLng(null);
    setHarvestDate('');
    setApiError(null);
    setResults(null);
    setPlansResult(null);
    setDecisionSaved(false);
    setExplanation(null);
    setExplanationOpen(false);
    setDistances(new Map());
    setMapsLive(null);
    setWiResult(null);
    setWiExplanation(null);
    setWiExplanationOpen(false);
    setWiTransport(0);
    setWiPrice(0);
    setWiShelf(0);
    setWiCancelled('');
    setWiCapacity(0);
    setDiscData([]);
    setDiscPrices(new Map());
    setMpState('');
    setMpDistrict('');
    setMpSearchQ('');
    setMpCommodity('');
    setMpError(null);
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
      const { data: { session: activeSession } } = await supabase.auth.getSession();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (activeSession) headers['Authorization'] = `Bearer ${activeSession.access_token}`;
      const response = await fetch('/api/submission', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const data: SubmissionResponse = await response.json();
      setResults(data.optimize);
      setPlansResult(data.plans);
      setDecisionSaved(data.saved);
      setExplanation(data.explanation ?? null);
      setExplanationOpen(false);
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
      setWiExplanation(data.explanation ?? null);
      setWiExplanationOpen(false);
    } catch (err) {
      setWiError(err instanceof Error ? err.message : 'What-If request failed.');
    } finally {
      setWiLoading(false);
    }
  };

  // ── Shared input class ──────────────────────────────────────────────────────
  const inputCls =
    'w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none text-sm transition bg-white placeholder:text-gray-300';
  const filterInputCls =
    'w-full px-3 py-2.5 text-sm rounded-xl border border-gray-200 focus:ring-2 focus:ring-green-500 focus:border-green-500 outline-none transition bg-white placeholder:text-gray-300';

  // ── Auth gating ────────────────────────────────────────────────────────────
  if (authLoading || roleLoading || consentLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-green-50/60 via-white to-white">
        <div className="flex flex-col items-center gap-4">
          <span className="text-3xl">🌱</span>
          <span className="inline-block w-6 h-6 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-400">Loading…</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthPage mode={authMode} onModeChange={setAuthMode} />;
  }

  const displayName =
    (user.user_metadata?.full_name as string | undefined) ||
    user.email?.split('@')[0] ||
    'Farmer';

  // Role selection screen — shown once after first login
  if (!role) {
    return (
      <RoleSelectPage
        fullName={(user.user_metadata?.full_name as string | undefined) ?? null}
        onRoleSelected={(r, p) => {
          setRole(r);
          setProfile(p ?? null);
          if (r !== 'farmer') setHasConsent(true);
        }}
      />
    );
  }

  // Consent gate — farmers only, shown once until consent is recorded
  if (role === 'farmer' && !hasConsent) {
    return <ConsentPage onConsented={() => setHasConsent(true)} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50/60 via-white to-white text-gray-800 flex flex-col">

      {/* ── Navigation Header ── */}
      <header className="border-b border-gray-100 bg-white/90 backdrop-blur sticky top-0 z-10 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <button
            onClick={() => setView('home')}
            className="flex items-center space-x-2 hover:opacity-75 transition"
          >
            <span className="text-2xl">🌱</span>
            <span className="text-xl font-bold text-green-700 tracking-tight">Farm2Value</span>
          </button>

          <nav className="flex items-center gap-1">
            {(view === 'results' || view === 'form' || view === 'marketplace') && (
              <>
                <button
                  onClick={() => results ? setView('results') : setView('form')}
                  className={`text-sm px-3 py-1.5 rounded-lg font-medium transition ${
                    view === 'results' || view === 'form'
                      ? 'bg-green-100 text-green-700'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Planner
                </button>
                <button
                  onClick={() => setView('marketplace')}
                  className={`text-sm px-3 py-1.5 rounded-lg font-medium transition ${
                    view === 'marketplace'
                      ? 'bg-green-100 text-green-700'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Marketplace
                </button>
                <button
                  onClick={handleBackToHome}
                  className="text-sm px-3 py-1.5 rounded-lg font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition"
                >
                  Home
                </button>
              </>
            )}
            {view === 'home' && (
              <span className="text-xs font-semibold text-green-700 bg-green-50 px-3 py-1 rounded-full border border-green-200">
                Hackathon Prototype
              </span>
            )}

            {/* User info + profile + logout */}
            <div className="flex items-center gap-2 ml-2 border-l border-gray-100 pl-3">
              {role && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium hidden sm:inline ${
                  role === 'farmer' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
                }`}>
                  {role === 'farmer' ? '🌾 Farmer' : '🏪 Buyer'}
                </span>
              )}
              {role === 'farmer' && (
                <button
                  onClick={() => setView('profile')}
                  className={`text-xs px-2.5 py-1.5 rounded-lg font-medium transition ${
                    view === 'profile'
                      ? 'bg-green-100 text-green-700'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                  }`}
                  title="My Profile"
                >
                  Profile
                </button>
              )}
              <span className="text-xs text-gray-500 hidden sm:inline truncate max-w-[140px]" title={user.email}>
                {displayName}
              </span>
              <button
                onClick={handleLogout}
                className="text-xs px-2.5 py-1.5 rounded-lg font-medium text-gray-500 hover:text-red-600 hover:bg-red-50 transition"
                title="Sign out"
              >
                Sign out
              </button>
            </div>
          </nav>
        </div>
      </header>

      {/* ── Main Content ── */}
      <main className="flex-1 max-w-5xl mx-auto px-4 sm:px-6 py-10 flex flex-col items-center w-full">

        {/* ── HOME VIEW ── */}
        {view === 'home' && (
          <div className="w-full max-w-3xl mx-auto">
            <div className="text-center py-12">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-100 text-green-800 text-sm font-semibold mb-8 border border-green-200">
                🌾 From Harvest to Value
              </div>
              <h1 className="text-5xl sm:text-6xl font-extrabold text-gray-900 tracking-tight mb-5">
                Farm2Value
              </h1>
              <p className="text-xl text-gray-500 font-normal mb-10 max-w-md mx-auto leading-relaxed">
                Maximise your harvest income with AI-powered market allocation and buyer discovery.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
                <button
                  onClick={handleStart}
                  className="inline-flex items-center justify-center px-8 py-4 text-base font-semibold text-white bg-green-600 hover:bg-green-700 rounded-2xl shadow-lg hover:shadow-xl transition-all active:scale-95"
                >
                  Start Selling Decision →
                </button>
                <button
                  onClick={() => {
                    setView('marketplace');
                  }}
                  className="inline-flex items-center justify-center px-6 py-4 text-base font-semibold text-green-700 bg-white border-2 border-green-200 hover:border-green-400 hover:bg-green-50 rounded-2xl shadow-sm transition-all active:scale-95"
                >
                  🏪 Browse Marketplace
                </button>
              </div>

              {/* Feature highlights */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-left">
                {[
                  {
                    icon: '📊',
                    title: 'Smart Allocation',
                    desc: 'Linear programming optimises which markets get your produce to maximise net value.',
                  },
                  {
                    icon: '🔮',
                    title: 'What-If Scenarios',
                    desc: 'Simulate transport disruptions, price drops, or buyer cancellations before they happen.',
                  },
                  {
                    icon: '🏪',
                    title: 'Buyer Marketplace',
                    desc: 'Discover mandis, wholesale hubs, retail chains, and cold storage buyers near you.',
                  },
                ].map((f) => (
                  <div key={f.title} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                    <div className="text-2xl mb-3">{f.icon}</div>
                    <div className="font-semibold text-gray-900 mb-1.5">{f.title}</div>
                    <div className="text-sm text-gray-500 leading-relaxed">{f.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── FORM VIEW ── */}
        {view === 'form' && (
          <div className="w-full max-w-lg">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
              <div className="mb-7">
                <h2 className="text-2xl font-bold text-gray-900">Farmer Produce Details</h2>
                <p className="text-sm text-gray-400 mt-1">Enter your harvest details to get an optimal allocation plan.</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                    Crop / Produce <span className="text-red-400">*</span>
                  </label>
                  {/* Hidden native input keeps browser form validation working */}
                  <input type="text" required value={crop} onChange={() => {}} className="sr-only" tabIndex={-1} aria-hidden />
                  <CropSelector value={crop} onChange={setCrop} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="quantity" className="block text-sm font-semibold text-gray-700 mb-1.5">
                      Quantity (kg) <span className="text-red-400">*</span>
                    </label>
                    <input
                      id="quantity"
                      type="number"
                      min="1"
                      required
                      placeholder="e.g. 500"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label htmlFor="quality" className="block text-sm font-semibold text-gray-700 mb-1.5">
                      Quality Grade
                    </label>
                    <select
                      id="quality"
                      value={quality}
                      onChange={(e) => setQuality(e.target.value)}
                      className={inputCls}
                    >
                      <option value="Premium">Premium</option>
                      <option value="Standard">Standard</option>
                      <option value="Low">Low</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="shelfLife" className="block text-sm font-semibold text-gray-700 mb-1.5">
                      Shelf Life (days) <span className="text-red-400">*</span>
                    </label>
                    <input
                      id="shelfLife"
                      type="number"
                      min="1"
                      required
                      placeholder="e.g. 7"
                      value={shelfLife}
                      onChange={(e) => setShelfLife(e.target.value)}
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label htmlFor="harvestDate" className="block text-sm font-semibold text-gray-700 mb-1.5">
                      Harvest Date <span className="text-red-400">*</span>
                    </label>
                    <input
                      id="harvestDate"
                      type="date"
                      required
                      value={harvestDate}
                      onChange={(e) => setHarvestDate(e.target.value)}
                      className={inputCls}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                    Where is your farm? <span className="text-red-400">*</span>
                  </label>
                  {/* Hidden input keeps native form validation — required blocks submit when empty */}
                  <input type="text" required value={farmerLocation} onChange={() => {}} className="sr-only" tabIndex={-1} aria-hidden />
                  <PlacesLocationSelector
                    selected={farmerLocation ? { address: farmerLocation, placeId: farmerPlaceId, lat: farmerLat, lng: farmerLng } : null}
                    onSelect={(place) => {
                      setFarmerLocation(place.address);
                      setFarmerPlaceId(place.placeId);
                      setFarmerLat(place.lat);
                      setFarmerLng(place.lng);
                    }}
                    onClear={() => {
                      setFarmerLocation('');
                      setFarmerPlaceId('');
                      setFarmerLat(null);
                      setFarmerLng(null);
                    }}
                    inputCls={inputCls}
                  />
                </div>

                {apiError && (
                  <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm flex items-start gap-2">
                    <span className="flex-shrink-0">⚠️</span>
                    <span>{apiError}</span>
                  </div>
                )}

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-3.5 px-4 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-semibold rounded-xl shadow-md transition active:scale-[0.98] flex items-center justify-center gap-2"
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
          </div>
        )}

        {/* ── RESULTS VIEW ── */}
        {view === 'results' && results && (
          <div className="w-full max-w-3xl space-y-6">

            {/* Context banner */}
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-2xl p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-gray-900 mb-0.5">
                    Harvest Allocation Plan
                  </h2>
                  <p className="text-sm text-gray-500">
                    Optimised across {results.recommended.allocations.length} market channel
                    {results.recommended.allocations.length !== 1 ? 's' : ''} for maximum value
                  </p>
                </div>
                <span className="text-3xl flex-shrink-0">📊</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {[
                  { icon: '🌾', val: results.crop },
                  { icon: '⚖️', val: `${results.quantity_kg} kg` },
                  { icon: '⭐', val: results.quality },
                  { icon: '📍', val: results.farmer_location },
                ].map(({ icon, val }) => (
                  <span key={val} className="bg-white border border-gray-200 rounded-full px-3 py-1 text-xs text-gray-600 font-medium">
                    {icon} {val}
                  </span>
                ))}
                {decisionSaved && (
                  <span className="bg-green-100 border border-green-300 text-green-700 rounded-full px-3 py-1 text-xs font-semibold">
                    ✓ Decision saved
                  </span>
                )}
                {mapsLive === true && (
                  <span className="bg-blue-50 border border-blue-200 text-blue-600 rounded-full px-3 py-1 text-xs font-medium">
                    🗺 Live road distances
                  </span>
                )}
                {mapsLive === false && (
                  <span className="bg-gray-50 border border-gray-200 text-gray-400 rounded-full px-3 py-1 text-xs">
                    🗺 Estimated distances
                  </span>
                )}
              </div>
            </div>

            {/* Recommended strategy */}
            {results.recommended.allocations.length === 0 ? (
              <div className="bg-white border border-gray-100 rounded-2xl p-10 text-center">
                <div className="text-4xl mb-3">😔</div>
                <p className="text-gray-500 font-medium">No viable market allocation found for this produce.</p>
                <p className="text-sm text-gray-400 mt-1">Try adjusting quality, quantity, or shelf life.</p>
              </div>
            ) : (
              <StrategyCard strategy={results.recommended} isRecommended distances={distances} />
            )}

            {/* AI Explanation */}
            {explanation && (
              <div className="bg-white rounded-2xl border border-purple-100 shadow-sm overflow-hidden">
                <button
                  onClick={() => setExplanationOpen((v) => !v)}
                  className="w-full px-6 py-4 flex items-center justify-between gap-3 text-left hover:bg-purple-50/40 transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-lg">💡</span>
                    <div>
                      <span className="text-sm font-semibold text-gray-800 block">Why this recommendation?</span>
                      <span className="text-xs text-gray-400">AI-generated explanation</span>
                    </div>
                  </div>
                  <span className="text-xs text-purple-400 font-medium flex-shrink-0">
                    {explanationOpen ? '▲ Close' : '▼ Read'}
                  </span>
                </button>
                {explanationOpen && (
                  <div className="px-6 pb-6 border-t border-purple-50 bg-purple-50/20">
                    <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap mt-4">{explanation}</p>
                  </div>
                )}
              </div>
            )}

            {/* Alternative strategies */}
            {results.alternatives.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3 px-1">
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
                <div className="flex items-center justify-between px-1">
                  <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                    Selling Strategies
                  </h3>
                  <span className="text-xs text-gray-300">Plan A · B · C</span>
                </div>

                {/* Comparison mini-table */}
                <div className="grid grid-cols-3 gap-3">
                  {([plansResult.plan_a, plansResult.plan_b, plansResult.plan_c] as PlanResult[]).map((plan) => {
                    const colors = PLAN_COLORS[plan.plan_label] ?? PLAN_COLORS['A'];
                    return (
                      <div key={plan.plan_label} className={`bg-white border rounded-2xl p-4 text-center shadow-sm ${colors.border}`}>
                        <div className={`text-xs font-bold uppercase tracking-widest mb-1 ${colors.accent}`}>
                          Plan {plan.plan_label}
                        </div>
                        <div className="text-xs text-gray-400 mb-2.5 leading-tight">{plan.plan_name}</div>
                        <div className={`text-base font-bold tabular-nums ${colors.accent}`}>
                          {fmt(plan.total_net_value)}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">
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
              <div className="px-6 pt-5 pb-4 border-b border-amber-100 bg-gradient-to-r from-amber-50 to-yellow-50">
                <div className="flex items-center gap-2.5 mb-1">
                  <span className="text-xl">🔮</span>
                  <h3 className="text-base font-bold text-gray-900">What-If Simulator</h3>
                </div>
                <p className="text-sm text-gray-500">
                  Adjust market conditions to see how your net value changes.
                </p>
              </div>

              <div className="px-6 py-5 space-y-5">
                {/* Transport cost increase */}
                <div>
                  <div className="flex justify-between text-sm text-gray-600 mb-1.5">
                    <label className="font-medium">Transport cost increase</label>
                    <span className="tabular-nums font-bold text-amber-700">+{wiTransport}%</span>
                  </div>
                  <input
                    type="range" min={0} max={100} step={5}
                    value={wiTransport}
                    onChange={(e) => setWiTransport(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-xs text-gray-300 mt-0.5">
                    <span>0%</span><span>100%</span>
                  </div>
                </div>

                {/* Price decrease */}
                <div>
                  <div className="flex justify-between text-sm text-gray-600 mb-1.5">
                    <label className="font-medium">Market price decrease</label>
                    <span className="tabular-nums font-bold text-amber-700">−{wiPrice}%</span>
                  </div>
                  <input
                    type="range" min={0} max={50} step={5}
                    value={wiPrice}
                    onChange={(e) => setWiPrice(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-xs text-gray-300 mt-0.5">
                    <span>0%</span><span>50%</span>
                  </div>
                </div>

                {/* Shelf life reduction */}
                <div>
                  <div className="flex justify-between text-sm text-gray-600 mb-1.5">
                    <label className="font-medium">Shelf life reduction</label>
                    <span className="tabular-nums font-bold text-amber-700">−{wiShelf} day{wiShelf !== 1 ? 's' : ''}</span>
                  </div>
                  <input
                    type="range" min={0} max={3} step={1}
                    value={wiShelf}
                    onChange={(e) => setWiShelf(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-xs text-gray-300 mt-0.5">
                    <span>0 days</span><span>−3 days</span>
                  </div>
                </div>

                {/* Capacity reduction */}
                <div>
                  <div className="flex justify-between text-sm text-gray-600 mb-1.5">
                    <label className="font-medium">Market capacity reduction</label>
                    <span className="tabular-nums font-bold text-amber-700">−{wiCapacity}%</span>
                  </div>
                  <input
                    type="range" min={0} max={100} step={10}
                    value={wiCapacity}
                    onChange={(e) => setWiCapacity(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-xs text-gray-300 mt-0.5">
                    <span>0%</span><span>100%</span>
                  </div>
                </div>

                {/* Cancelled buyer */}
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-2">
                    Cancelled buyer
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setWiCancelled('')}
                      className={`text-sm px-3 py-1.5 rounded-full border transition ${
                        wiCancelled === ''
                          ? 'bg-amber-500 text-white border-amber-500 font-semibold'
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
                        className={`text-sm px-3 py-1.5 rounded-full border transition ${
                          wiCancelled === m.market_name
                            ? 'bg-amber-500 text-white border-amber-500 font-semibold'
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
                  className="w-full py-3 px-4 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-white font-semibold rounded-xl shadow transition active:scale-[0.98] flex items-center justify-center gap-2"
                >
                  {wiLoading ? (
                    <>
                      <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Running simulation…
                    </>
                  ) : (
                    '▶ Run What-If Simulation'
                  )}
                </button>

                {wiError && (
                  <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm flex items-start gap-2">
                    <span>⚠️</span><span>{wiError}</span>
                  </div>
                )}
              </div>

              {/* Comparison panel */}
              {wiResult && (
                <div className="border-t border-amber-100 bg-amber-50/30 px-6 py-5">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-5">
                    <h4 className="text-xs font-bold text-gray-700 uppercase tracking-widest">Scenario Comparison</h4>
                    <span className="text-xs bg-amber-100 text-amber-800 rounded-full px-3 py-1 font-medium">
                      {wiResult.scenario_description}
                    </span>
                  </div>

                  {/* Side-by-side on sm+, stacked on mobile */}
                  <div className="flex flex-col sm:flex-row gap-5 sm:gap-6">
                    <PlanColumn plan={wiResult.current_plan} label="Current Plan" accent="text-green-700" />
                    <div className="hidden sm:block w-px bg-gray-200 flex-shrink-0" />
                    <div className="block sm:hidden border-t border-gray-200" />
                    <PlanColumn plan={wiResult.whatif_plan} label="What-If Plan" accent="text-amber-700" />
                  </div>

                  {/* Delta banner */}
                  <div className={`mt-5 rounded-2xl px-4 py-4 text-center ${
                    wiResult.delta_net_value < 0
                      ? 'bg-red-50 border border-red-100'
                      : 'bg-green-50 border border-green-100'
                  }`}>
                    <div className="text-xs text-gray-500 mb-1">Net value impact</div>
                    <div className={`text-2xl font-bold tabular-nums ${deltaClass(wiResult.delta_net_value)}`}>
                      {deltaSign(wiResult.delta_net_value)}{fmt(wiResult.delta_net_value)}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {wiResult.delta_net_value < 0
                        ? 'You stand to lose this much under this scenario.'
                        : wiResult.delta_net_value > 0
                        ? 'Your net value improves under this scenario.'
                        : 'No change in net value.'}
                    </div>
                  </div>

                  {/* What-If AI Explanation */}
                  {wiExplanation && (
                    <div className="mt-4 border border-purple-100 rounded-2xl overflow-hidden">
                      <button
                        onClick={() => setWiExplanationOpen((v) => !v)}
                        className="w-full px-5 py-3 flex items-center justify-between gap-2 text-left hover:bg-purple-50/40 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span>💡</span>
                          <span className="text-sm font-semibold text-gray-700">What does this mean?</span>
                        </div>
                        <span className="text-xs text-purple-400 font-medium">{wiExplanationOpen ? '▲ Close' : '▼ Read'}</span>
                      </button>
                      {wiExplanationOpen && (
                        <div className="px-5 pb-5 border-t border-purple-50 bg-purple-50/20">
                          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap mt-4">{wiExplanation}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Action buttons */}
            <div className="grid grid-cols-3 gap-3 pt-2">
              <button
                onClick={() => setView('form')}
                className="py-3 px-4 rounded-xl border border-gray-200 text-gray-700 text-sm font-medium hover:bg-gray-50 transition"
              >
                Edit Details
              </button>
              <button
                onClick={() => setView('marketplace')}
                className="py-3 px-4 rounded-xl border border-green-200 text-green-700 text-sm font-semibold hover:bg-green-50 transition"
              >
                Find Buyers →
              </button>
              <button
                onClick={handleBackToHome}
                className="py-3 px-4 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700 transition"
              >
                Start Again
              </button>
            </div>
          </div>
        )}

        {/* ── MARKETPLACE VIEW (AGMARKNET discovery) ── */}
        {view === 'marketplace' && (
          <div className="w-full max-w-3xl space-y-6">

            {/* Header */}
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-900">Discover APMC Markets</h2>
              <p className="text-sm text-gray-500 mt-1">
                Real Indian agricultural markets from AGMARKNET / data.gov.in
              </p>
            </div>

            {/* Filters panel */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">
              <div className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                Filter Markets
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1.5">State</label>
                  {availableStates.length > 0 ? (
                    <select
                      value={mpState}
                      onChange={(e) => setMpState(e.target.value)}
                      className={filterInputCls}
                    >
                      <option value="">All states</option>
                      {availableStates.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      placeholder="e.g. Maharashtra"
                      value={mpState}
                      onChange={(e) => setMpState(e.target.value)}
                      className={filterInputCls}
                    />
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1.5">District</label>
                  <input
                    type="text"
                    placeholder="e.g. Nashik"
                    value={mpDistrict}
                    onChange={(e) => setMpDistrict(e.target.value)}
                    className={filterInputCls}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1.5">Search</label>
                  <input
                    type="text"
                    placeholder="Market name or location"
                    value={mpSearchQ}
                    onChange={(e) => setMpSearchQ(e.target.value)}
                    className={filterInputCls}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1.5">Commodity</label>
                  <input
                    type="text"
                    placeholder="e.g. Onion"
                    value={mpCommodity}
                    onChange={(e) => setMpCommodity(e.target.value)}
                    className={filterInputCls}
                  />
                </div>
              </div>

              <button
                onClick={fetchDiscovery}
                disabled={mpLoading}
                className="w-full py-3 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-semibold rounded-xl shadow transition active:scale-[0.98] flex items-center justify-center gap-2"
              >
                {mpLoading ? (
                  <>
                    <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Searching Markets…
                  </>
                ) : (
                  '🔍 Search APMC Markets'
                )}
              </button>

              {mpError && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm flex items-start gap-2">
                  <span>⚠️</span><span>{mpError}</span>
                </div>
              )}
            </div>

            {/* Results header */}
            {discData.length > 0 && (
              <div className="flex items-center justify-between px-1">
                <span className="text-sm font-medium text-gray-600">
                  {discData.length} market{discData.length !== 1 ? 's' : ''} found
                </span>
                <span className="text-xs text-gray-400">Source: AGMARKNET / data.gov.in</span>
              </div>
            )}

            {/* APMC cards */}
            {discData.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {discData.map((market) => (
                  <ApmcCard
                    key={market.market_id}
                    market={market}
                    priceInfo={discPrices.get(market.market_id)}
                    onUseInPlan={() => handleUseInMyPlan(market)}
                    hasResults={!!results}
                  />
                ))}
              </div>
            )}

            {/* Empty state after search */}
            {!mpLoading && discData.length === 0 && !mpError && (mpState || mpDistrict || mpSearchQ || mpCommodity) && (
              <div className="bg-white border border-gray-100 rounded-2xl p-12 text-center">
                <div className="text-4xl mb-3">🏪</div>
                <p className="text-gray-600 font-medium">No markets match your filters.</p>
                <p className="text-sm text-gray-400 mt-1">Try a different state or clear the district filter.</p>
              </div>
            )}

            {/* Initial prompt before search */}
            {!mpLoading && discData.length === 0 && !mpError && !(mpState || mpDistrict || mpSearchQ || mpCommodity) && (
              <div className="bg-white border border-gray-100 rounded-2xl p-12 text-center">
                <div className="text-4xl mb-3">🗺</div>
                <p className="text-gray-600 font-medium">Search real APMC markets across India.</p>
                <p className="text-sm text-gray-400 mt-1">Filter by state, district, or commodity and click Search.</p>
              </div>
            )}
          </div>
        )}

        {/* ── PROFILE VIEW ── */}
        {view === 'profile' && role === 'farmer' && profile && (
          <FarmerProfilePage
            user={user}
            profile={profile}
            onProfileUpdated={(updated) => setProfile(updated)}
          />
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="py-6 border-t border-gray-100 text-center text-xs text-gray-400">
        Farm2Value &copy; 2026 · Built for Problem Statement 3: From Harvest to Value
      </footer>
    </div>
  );
}
