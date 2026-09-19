import { supabase } from './supabaseClient';

export interface BuyerRequirement {
  id: string;
  user_id: string;
  crop: string;
  quantity_kg: number;
  quality: string;
  delivery_state: string | null;
  delivery_district: string | null;
  budget_per_kg: number | null;
  needed_by: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
}

export interface BuyerRequirementCreate {
  crop: string;
  quantity_kg: number;
  quality: string;
  delivery_state?: string | null;
  delivery_district?: string | null;
  budget_per_kg?: number | null;
  needed_by?: string | null;
  notes?: string | null;
}

export interface BuyerRequirementUpdate {
  crop?: string;
  quantity_kg?: number;
  quality?: string;
  delivery_state?: string | null;
  delivery_district?: string | null;
  budget_per_kg?: number | null;
  needed_by?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

async function getAuthHeader(): Promise<string> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated.');
  return `Bearer ${session.access_token}`;
}

export async function fetchRequirements(): Promise<BuyerRequirement[]> {
  const auth = await getAuthHeader();
  const resp = await fetch('/api/buyer/requirements', {
    headers: { Authorization: auth },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  const data = await resp.json() as { requirements: BuyerRequirement[] };
  return data.requirements;
}

export async function createRequirement(payload: BuyerRequirementCreate): Promise<BuyerRequirement> {
  const auth = await getAuthHeader();
  const resp = await fetch('/api/buyer/requirements', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: auth },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<BuyerRequirement>;
}

export async function updateRequirement(id: string, updates: BuyerRequirementUpdate): Promise<BuyerRequirement> {
  const auth = await getAuthHeader();
  const resp = await fetch(`/api/buyer/requirements/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: auth },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<BuyerRequirement>;
}

export async function deleteRequirement(id: string): Promise<void> {
  const auth = await getAuthHeader();
  const resp = await fetch(`/api/buyer/requirements/${id}`, {
    method: 'DELETE',
    headers: { Authorization: auth },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
}
