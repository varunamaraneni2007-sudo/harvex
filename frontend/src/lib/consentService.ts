import { supabase } from './supabaseClient';

export interface ConsentRecord {
  id: string;
  user_id: string;
  consented_at: string;
  version: string;
}

async function authHeader(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated.');
  return { Authorization: `Bearer ${session.access_token}` };
}

/**
 * Check whether the farmer has given consent for the current version.
 * Returns the consent record, or null if none exists yet.
 */
export async function fetchConsent(): Promise<ConsentRecord | null> {
  const headers = await authHeader();
  const resp = await fetch('/api/consent', { headers });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`Failed to check consent: ${resp.status}`);
  return resp.json() as Promise<ConsentRecord>;
}

/**
 * Record the farmer's explicit consent. Idempotent — safe to call even
 * if consent was already recorded.
 */
export async function recordConsent(): Promise<ConsentRecord> {
  const headers = await authHeader();
  const resp = await fetch('/api/consent', {
    method: 'POST',
    headers,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<ConsentRecord>;
}
