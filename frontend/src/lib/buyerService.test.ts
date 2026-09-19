import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockGetSession } = vi.hoisted(() => ({
  mockGetSession: vi.fn(),
}));

vi.mock('./supabaseClient', () => ({
  supabase: {
    auth: { getSession: mockGetSession },
  },
}));

import {
  fetchRequirements,
  createRequirement,
  updateRequirement,
  deleteRequirement,
} from './buyerService';

const FAKE_TOKEN = 'fake-buyer-token';

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

const REQUIREMENT = {
  id: 'req-uuid-001',
  user_id: 'buyer-uid-001',
  crop: 'Tomato',
  quantity_kg: 500,
  quality: 'Standard',
  delivery_state: 'Karnataka',
  delivery_district: 'Bangalore',
  budget_per_kg: 25.5,
  needed_by: '2026-10-01',
  notes: 'Fresh only',
  is_active: true,
  created_at: '2026-09-19T08:00:00Z',
};

beforeEach(() => {
  vi.restoreAllMocks();
});

// ── fetchRequirements ─────────────────────────────────────────────────────────

describe('fetchRequirements', () => {
  it('returns list of requirements on success', async () => {
    withSession();
    mockFetch(200, { requirements: [REQUIREMENT] });
    const result = await fetchRequirements();
    expect(result).toHaveLength(1);
    expect(result[0].crop).toBe('Tomato');
  });

  it('sends Authorization header', async () => {
    withSession();
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ requirements: [] }),
    });
    vi.stubGlobal('fetch', spy);
    await fetchRequirements();
    expect(spy).toHaveBeenCalledWith(
      '/api/buyer/requirements',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${FAKE_TOKEN}` }),
      }),
    );
  });

  it('throws when not authenticated', async () => {
    withoutSession();
    await expect(fetchRequirements()).rejects.toThrow('Not authenticated.');
  });

  it('throws with detail message on non-ok response', async () => {
    withSession();
    mockFetch(403, { detail: 'Only buyers can access this endpoint.' });
    await expect(fetchRequirements()).rejects.toThrow('Only buyers can access this endpoint.');
  });

  it('throws generic HTTP error if detail missing', async () => {
    withSession();
    mockFetch(500, {});
    await expect(fetchRequirements()).rejects.toThrow('HTTP 500');
  });
});

// ── createRequirement ─────────────────────────────────────────────────────────

describe('createRequirement', () => {
  it('creates and returns requirement on success', async () => {
    withSession();
    mockFetch(200, REQUIREMENT);
    const result = await createRequirement({
      crop: 'Tomato',
      quantity_kg: 500,
      quality: 'Standard',
    });
    expect(result.crop).toBe('Tomato');
    expect(result.id).toBe('req-uuid-001');
  });

  it('sends POST with JSON body and Authorization header', async () => {
    withSession();
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(REQUIREMENT),
    });
    vi.stubGlobal('fetch', spy);
    await createRequirement({ crop: 'Wheat', quantity_kg: 100, quality: 'Premium' });
    const [url, opts] = spy.mock.calls[0];
    expect(url).toBe('/api/buyer/requirements');
    expect(opts.method).toBe('POST');
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(opts.headers.Authorization).toBe(`Bearer ${FAKE_TOKEN}`);
    expect(JSON.parse(opts.body)).toMatchObject({ crop: 'Wheat', quantity_kg: 100 });
  });

  it('throws when not authenticated', async () => {
    withoutSession();
    await expect(createRequirement({ crop: 'X', quantity_kg: 1, quality: 'Any' })).rejects.toThrow('Not authenticated.');
  });

  it('throws with detail on validation error', async () => {
    withSession();
    mockFetch(422, { detail: 'Crop is required.' });
    await expect(createRequirement({ crop: '', quantity_kg: 1, quality: 'Any' })).rejects.toThrow('Crop is required.');
  });

  it('throws generic error on 500', async () => {
    withSession();
    mockFetch(500, {});
    await expect(createRequirement({ crop: 'Onion', quantity_kg: 200, quality: 'Low' })).rejects.toThrow('HTTP 500');
  });
});

// ── updateRequirement ─────────────────────────────────────────────────────────

describe('updateRequirement', () => {
  it('updates and returns requirement on success', async () => {
    withSession();
    const updated = { ...REQUIREMENT, quantity_kg: 1000 };
    mockFetch(200, updated);
    const result = await updateRequirement('req-uuid-001', { quantity_kg: 1000 });
    expect(result.quantity_kg).toBe(1000);
  });

  it('sends PATCH to correct URL with Authorization', async () => {
    withSession();
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(REQUIREMENT),
    });
    vi.stubGlobal('fetch', spy);
    await updateRequirement('req-uuid-001', { is_active: false });
    const [url, opts] = spy.mock.calls[0];
    expect(url).toBe('/api/buyer/requirements/req-uuid-001');
    expect(opts.method).toBe('PATCH');
    expect(opts.headers.Authorization).toBe(`Bearer ${FAKE_TOKEN}`);
    expect(JSON.parse(opts.body)).toMatchObject({ is_active: false });
  });

  it('throws when not authenticated', async () => {
    withoutSession();
    await expect(updateRequirement('req-uuid-001', {})).rejects.toThrow('Not authenticated.');
  });

  it('throws 403 on cross-user access', async () => {
    withSession();
    mockFetch(403, { detail: 'Access denied.' });
    await expect(updateRequirement('other-uuid', {})).rejects.toThrow('Access denied.');
  });

  it('throws 404 on missing requirement', async () => {
    withSession();
    mockFetch(404, { detail: 'Requirement not found.' });
    await expect(updateRequirement('missing-id', {})).rejects.toThrow('Requirement not found.');
  });
});

// ── deleteRequirement ─────────────────────────────────────────────────────────

describe('deleteRequirement', () => {
  it('resolves without error on success', async () => {
    withSession();
    mockFetch(200, { ok: true });
    await expect(deleteRequirement('req-uuid-001')).resolves.toBeUndefined();
  });

  it('sends DELETE to correct URL with Authorization', async () => {
    withSession();
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ok: true }),
    });
    vi.stubGlobal('fetch', spy);
    await deleteRequirement('req-uuid-001');
    const [url, opts] = spy.mock.calls[0];
    expect(url).toBe('/api/buyer/requirements/req-uuid-001');
    expect(opts.method).toBe('DELETE');
    expect(opts.headers.Authorization).toBe(`Bearer ${FAKE_TOKEN}`);
  });

  it('throws when not authenticated', async () => {
    withoutSession();
    await expect(deleteRequirement('req-uuid-001')).rejects.toThrow('Not authenticated.');
  });

  it('throws 403 on cross-user attempt', async () => {
    withSession();
    mockFetch(403, { detail: 'Access denied.' });
    await expect(deleteRequirement('other-uuid')).rejects.toThrow('Access denied.');
  });

  it('throws 404 if not found', async () => {
    withSession();
    mockFetch(404, { detail: 'Requirement not found.' });
    await expect(deleteRequirement('missing-id')).rejects.toThrow('Requirement not found.');
  });
});
