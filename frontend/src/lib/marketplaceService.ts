import { supabase } from './supabaseClient';

export interface CropListing {
  id: string; farmer_id: string; crop_name: string; available_quantity_kg: number;
  price_per_kg: number; quality: 'Premium'|'Standard'|'Low'; harvest_date: string;
  location: string; status: string; photo_paths: string[];
  profiles?: { public_id: string; full_name: string|null; average_rating: number; total_ratings: number };
}

async function token(): Promise<string> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated.');
  return session.access_token;
}

async function api<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}`, ...(init.headers ?? {}) } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as {detail?: string}).detail ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getListings(crop = ''): Promise<CropListing[]> {
  const result = await api<{listings: CropListing[]}>(`/api/crop-listings${crop ? `?crop=${encodeURIComponent(crop)}` : ''}`);
  return result.listings;
}

export async function uploadProductPhoto(userId: string, file: File): Promise<string> {
  if (!file.type.startsWith('image/') || file.size > 8 * 1024 * 1024) throw new Error('Use an image smaller than 8 MB.');
  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
  const path = `${userId}/${crypto.randomUUID()}/${safeName}`;
  const { error } = await supabase.storage.from('product-photos').upload(path, file, { upsert: false, contentType: file.type });
  if (error) throw error;
  return path;
}

export async function removeProductPhoto(path: string): Promise<void> {
  const { error } = await supabase.storage.from('product-photos').remove([path]);
  if (error) throw error;
}

export async function photoUrl(path: string): Promise<string> {
  const { data, error } = await supabase.storage.from('product-photos').createSignedUrl(path, 600);
  if (error) throw error;
  return data.signedUrl;
}

export async function createListing(payload: Omit<CropListing,'id'|'farmer_id'|'profiles'>): Promise<CropListing> {
  return api('/api/farmer/listings', { method: 'POST', body: JSON.stringify(payload) });
}

export async function placeOrder(crop_name: string, quantity_kg: number, quality?: string): Promise<{order_id:string;status:string}> {
  return api('/api/marketplace/orders', { method: 'POST', body: JSON.stringify({ crop_name, quantity_kg, quality }) });
}

export async function getOrders(): Promise<unknown[]> {
  return (await api<{orders:unknown[]}>('/api/marketplace/orders')).orders;
}

export async function updateOrderItem(itemId:string,status:string): Promise<unknown> {
  return api(`/api/farmer/order-items/${encodeURIComponent(itemId)}`,{method:'PATCH',body:JSON.stringify({status})});
}

export async function rateOrderItem(order_item_id:string,rating:number,review_text:string): Promise<unknown> {
  return api('/api/marketplace/ratings',{method:'POST',body:JSON.stringify({order_item_id,rating,review_text})});
}
