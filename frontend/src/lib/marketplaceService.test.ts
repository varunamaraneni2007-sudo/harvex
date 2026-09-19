import { beforeEach, describe, expect, it, vi } from 'vitest';
const { getSession, upload, remove, createSignedUrl } = vi.hoisted(()=>({getSession:vi.fn(),upload:vi.fn(),remove:vi.fn(),createSignedUrl:vi.fn()}));
vi.mock('./supabaseClient',()=>({supabase:{auth:{getSession},storage:{from:()=>({upload,remove,createSignedUrl})}}}));
import { getListings, placeOrder, uploadProductPhoto } from './marketplaceService';

beforeEach(()=>{vi.restoreAllMocks();getSession.mockResolvedValue({data:{session:{access_token:'jwt'}}});upload.mockResolvedValue({error:null});});
describe('marketplace service',()=>{
  it('requires authentication',async()=>{getSession.mockResolvedValue({data:{session:null}});await expect(getListings()).rejects.toThrow(/authenticated/i);});
  it('sends buyer order through protected API',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({order_id:'o1',status:'Pending'})}));await placeOrder('Tomato',120,'Premium');const [,init]=(vi.mocked(fetch).mock.calls[0]);expect(JSON.parse(init!.body as string).quantity_kg).toBe(120);expect((init!.headers as Record<string,string>).Authorization).toBe('Bearer jwt');});
  it('rejects non-image uploads',async()=>{const file=new File(['x'],'bad.txt',{type:'text/plain'});await expect(uploadProductPhoto('u1',file)).rejects.toThrow(/image/i);});
});
