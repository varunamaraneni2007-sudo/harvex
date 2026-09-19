import { supabase } from './supabaseClient';

export type UserRole = 'farmer' | 'buyer';

export interface Profile {
  id: string;
  role: UserRole;
  full_name: string | null;
  phone: string | null;
  state: string | null;
  district: string | null;
  company_name: string | null;
  business_type: string | null;
  created_at: string;
}

export interface ProfileUpdate {
  full_name?: string | null;
  phone?: string | null;
  state?: string | null;
  district?: string | null;
  company_name?: string | null;
  business_type?: string | null;
}

/**
 * Fetch the authenticated user's profile from the backend.
 * Returns null when no profile exists yet (first login after registration).
 *
 * Pass accessToken when calling from inside an onAuthStateChange callback to
 * avoid calling getSession() while Supabase's internal state is still settling,
 * which can transiently return null and incorrectly show the role-selection page
 * to an existing user.
 */
export async function fetchProfile(accessToken?: string): Promise<Profile | null> {
  let token = accessToken;
  if (!token) {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return null;
    token = session.access_token;
  }
  const resp = await fetch('/api/profile', {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`Failed to fetch profile: ${resp.status}`);
  return resp.json() as Promise<Profile>;
}

/**
 * Update mutable profile fields. Role cannot be changed after creation.
 */
export async function updateProfile(updates: ProfileUpdate): Promise<Profile> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated.');

  const resp = await fetch('/api/profile', {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<Profile>;
}

/**
 * Create the user's profile with the chosen role.
 * Throws if the profile already exists or the server returns an error.
 */
export async function createProfile(role: UserRole, fullName?: string): Promise<Profile> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated.');

  const resp = await fetch('/api/profile', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({ role, full_name: fullName ?? null }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<Profile>;
}
