/**
 * Step 27 — Buyer Registration: roleService unit tests.
 *
 * Tests are pure logic tests (no DOM/component rendering) so they run in
 * Vitest's node environment without jsdom.  Supabase and fetch are both
 * mocked so no live credentials are needed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// vi.hoisted() runs before module evaluation, so the variable is available
// inside the vi.mock() factory which is also hoisted.
const { mockGetSession } = vi.hoisted(() => ({
  mockGetSession: vi.fn(),
}));

vi.mock('./supabaseClient', () => ({
  supabase: {
    auth: { getSession: mockGetSession },
  },
}));

import { createProfile, fetchProfile, selectRole, updateProfile } from './roleService';

// ── Helpers ───────────────────────────────────────────────────────────────────

const FAKE_TOKEN = 'fake-jwt-token';

function withSession() {
  mockGetSession.mockResolvedValue({
    data: { session: { access_token: FAKE_TOKEN } },
  });
}

function withoutSession() {
  mockGetSession.mockResolvedValue({ data: { session: null } });
}

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    }),
  );
}

const BUYER_PROFILE = {
  id: 'buyer-uid-001',
  role: 'buyer' as const,
  full_name: 'Priya Sharma',
  phone: null,
  state: null,
  district: null,
  created_at: '2026-09-19T08:00:00Z',
};

const FARMER_PROFILE = {
  id: 'farmer-uid-001',
  role: 'farmer' as const,
  full_name: 'Ravi Kumar',
  phone: null,
  state: 'Andhra Pradesh',
  district: 'Guntur',
  created_at: '2026-09-19T07:00:00Z',
};

beforeEach(() => {
  vi.restoreAllMocks();
  mockGetSession.mockReset();
});

// ── createProfile — buyer ─────────────────────────────────────────────────────

describe('createProfile — buyer', () => {
  it('POSTs to /api/profile with role=buyer and returns the profile', async () => {
    withSession();
    mockFetch(201, BUYER_PROFILE);

    const profile = await createProfile('buyer', 'Priya Sharma');

    const fetchMock = vi.mocked(globalThis.fetch as typeof fetch);
    const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(calls).toHaveLength(1);
    const [url, opts] = calls[0] as [string, RequestInit & { headers: Record<string, string>; body: string }];
    expect(url).toBe('/api/profile');
    expect(opts.method).toBe('POST');
    expect(opts.headers['Authorization']).toBe(`Bearer ${FAKE_TOKEN}`);

    const body = JSON.parse(opts.body);
    expect(body.role).toBe('buyer');
    expect(body.full_name).toBe('Priya Sharma');

    expect(profile.role).toBe('buyer');
    expect(profile.id).toBe('buyer-uid-001');
  });

  it('sends null full_name when name is omitted', async () => {
    withSession();
    mockFetch(201, { ...BUYER_PROFILE, full_name: null });

    await createProfile('buyer');

    const fetchMock = vi.mocked(globalThis.fetch as typeof fetch);
    const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    const body = JSON.parse((calls[0] as [string, { body: string }])[1].body);
    expect(body.full_name).toBeNull();
  });

  it('throws when not authenticated', async () => {
    withoutSession();

    await expect(createProfile('buyer', 'Priya')).rejects.toThrow(/not authenticated/i);
  });

  it('throws with the API error detail on 409 (profile already exists)', async () => {
    withSession();
    mockFetch(409, { detail: 'Profile already exists.' });

    await expect(createProfile('buyer', 'Priya')).rejects.toThrow('Profile already exists.');
  });

  it('throws on server error 500', async () => {
    withSession();
    mockFetch(500, { detail: 'Internal server error' });

    await expect(createProfile('buyer', 'Priya')).rejects.toThrow();
  });
});

describe('createProfile — farmer', () => {
  it('POSTs with role=farmer', async () => {
    withSession();
    mockFetch(201, FARMER_PROFILE);

    const profile = await createProfile('farmer', 'Ravi Kumar');

    const fetchMock = vi.mocked(globalThis.fetch as typeof fetch);
    const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    const body = JSON.parse((calls[0] as [string, { body: string }])[1].body);
    expect(body.role).toBe('farmer');
    expect(profile.role).toBe('farmer');
  });
});

// ── fetchProfile ──────────────────────────────────────────────────────────────

describe('fetchProfile', () => {
  it('returns null when no profile exists (404) — new user before role selection', async () => {
    withSession();
    mockFetch(404, { detail: 'Not found' });

    const result = await fetchProfile();
    expect(result).toBeNull();
  });

  it('returns buyer profile when one exists', async () => {
    withSession();
    mockFetch(200, BUYER_PROFILE);

    const profile = await fetchProfile();
    expect(profile).not.toBeNull();
    expect(profile!.role).toBe('buyer');
    expect(profile!.id).toBe('buyer-uid-001');
  });

  it('returns farmer profile when one exists', async () => {
    withSession();
    mockFetch(200, FARMER_PROFILE);

    const profile = await fetchProfile();
    expect(profile!.role).toBe('farmer');
    expect(profile!.state).toBe('Andhra Pradesh');
  });

  it('returns null when not authenticated', async () => {
    withoutSession();

    const result = await fetchProfile();
    expect(result).toBeNull();
  });

  it('throws on server error', async () => {
    withSession();
    mockFetch(500, {});

    await expect(fetchProfile()).rejects.toThrow();
  });
});

// ── updateProfile ─────────────────────────────────────────────────────────────

describe('updateProfile', () => {
  it('PATCHes /api/profile with provided fields', async () => {
    withSession();
    mockFetch(200, { ...BUYER_PROFILE, full_name: 'Priya Nair', state: 'Kerala' });

    const updated = await updateProfile({ full_name: 'Priya Nair', state: 'Kerala' });

    const fetchMock = vi.mocked(globalThis.fetch as typeof fetch);
    const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    const [url, opts] = calls[0] as [string, RequestInit & { body: string }];
    expect(url).toBe('/api/profile');
    expect(opts.method).toBe('PATCH');
    const body = JSON.parse(opts.body);
    expect(body.full_name).toBe('Priya Nair');
    expect(updated.state).toBe('Kerala');
  });

  it('throws with API error detail on failure', async () => {
    withSession();
    mockFetch(422, { detail: 'Invalid phone number format' });

    await expect(updateProfile({ phone: 'bad' })).rejects.toThrow('Invalid phone number format');
  });
});

// ── Role-routing: existing users skip role selection ──────────────────────────

describe('fetchProfile with accessToken — existing-user routing', () => {
  it('existing farmer: returns farmer profile when token is passed directly', async () => {
    // getSession must NOT be called — token is provided by the auth callback
    mockFetch(200, FARMER_PROFILE);

    const profile = await fetchProfile('direct-farmer-token');

    expect(profile).not.toBeNull();
    expect(profile!.role).toBe('farmer');
    // getSession was never called (no withSession() setup needed)
    expect(mockGetSession).not.toHaveBeenCalled();
  });

  it('existing buyer: returns buyer profile when token is passed directly', async () => {
    mockFetch(200, BUYER_PROFILE);

    const profile = await fetchProfile('direct-buyer-token');

    expect(profile).not.toBeNull();
    expect(profile!.role).toBe('buyer');
    expect(mockGetSession).not.toHaveBeenCalled();
  });

  it('new user: returns null when profile does not exist yet (404)', async () => {
    withSession();
    mockFetch(404, {});

    const profile = await fetchProfile();
    expect(profile).toBeNull();
  });

  it('role cannot be changed: createProfile throws 409 when profile already exists', async () => {
    withSession();
    mockFetch(409, { detail: 'Profile already exists. Role cannot be changed.' });

    await expect(createProfile('buyer', 'Existing User')).rejects.toThrow(
      'Profile already exists. Role cannot be changed.',
    );
  });

  it('existing farmer token is forwarded in Authorization header without calling getSession', async () => {
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(FARMER_PROFILE),
    });
    vi.stubGlobal('fetch', spy);

    await fetchProfile('token-from-callback');

    const [url, opts] = (spy.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }]);
    expect(url).toBe('/api/profile');
    expect(opts.headers['Authorization']).toBe('Bearer token-from-callback');
    expect(mockGetSession).not.toHaveBeenCalled();
  });
});

describe('selectRole — profile-independent authentication flow', () => {
  it('continues without GET /api/profile after an existing-profile conflict', async () => {
    withSession();
    mockFetch(409, { detail: 'Profile already exists. Role cannot be changed.' });

    const profile = await selectRole('farmer', 'Existing Farmer');

    expect(profile).toBeNull();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/profile',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('still surfaces non-conflict profile creation errors', async () => {
    withSession();
    mockFetch(500, { detail: 'Database unavailable.' });

    await expect(selectRole('farmer', 'New User')).rejects.toThrow('Database unavailable.');
  });
});

// ── Buyer registration flow (service layer) ───────────────────────────────────

describe('Buyer registration flow', () => {
  it('new user has null profile before role selection, then registers as buyer', async () => {
    withSession();

    vi.stubGlobal(
      'fetch',
      vi.fn()
        // Step 1: GET profile — no profile yet (404)
        .mockResolvedValueOnce({ ok: false, status: 404, json: () => Promise.resolve({}) })
        // Step 2: POST profile — create buyer profile (201)
        .mockResolvedValueOnce({ ok: true, status: 201, json: () => Promise.resolve(BUYER_PROFILE) }),
    );

    const profileBefore = await fetchProfile();
    expect(profileBefore).toBeNull();

    const created = await createProfile('buyer', 'Priya Sharma');
    expect(created.role).toBe('buyer');
    expect(created.id).toBe('buyer-uid-001');
  });

  it('buyer profile has role=buyer, not farmer', async () => {
    withSession();
    mockFetch(201, BUYER_PROFILE);

    const profile = await createProfile('buyer', 'Priya');
    expect(profile.role).toBe('buyer');
    expect(profile.role).not.toBe('farmer');
  });

  it('farmer and buyer registrations produce distinct profiles with different roles', async () => {
    withSession();

    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce({ ok: true, status: 201, json: () => Promise.resolve(FARMER_PROFILE) })
        .mockResolvedValueOnce({ ok: true, status: 201, json: () => Promise.resolve(BUYER_PROFILE) }),
    );

    const farmer = await createProfile('farmer', 'Ravi Kumar');
    const buyer = await createProfile('buyer', 'Priya Sharma');

    expect(farmer.role).toBe('farmer');
    expect(buyer.role).toBe('buyer');
    expect(farmer.id).not.toBe(buyer.id);
  });

  it('buyer with existing profile gets 409 on second registration attempt', async () => {
    withSession();
    mockFetch(409, { detail: 'Profile already exists.' });

    await expect(createProfile('buyer', 'Priya')).rejects.toThrow('Profile already exists.');
  });
});
