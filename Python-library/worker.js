/**
 * PIDA Relay Server - Cloudflare Worker
 * KV Namespace: PIDA_KV
 */

const DIFFICULTY = 4; // Độ khó PoW (khớp với Client)
const DEFAULT_TTL = 345600; // 4 ngày (giây)
const CHALLENGE_TTL = 300; // 5 phút

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
};

// Helper xác thực PoW
async function verifyPoW(data, nonce, hash) {
    if (!hash.startsWith('0'.repeat(DIFFICULTY))) return false;
    const msgUint8 = new TextEncoder().encode(data + nonce);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const actualHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return actualHash === hash;
}

export default {
    async fetch(request, env) {
        // Handle CORS
        if (request.method === 'OPTIONS') {
            return new Response(null, { headers: corsHeaders });
        }

        const url = new URL(request.url);

        try {
            // 1. CẤP CHALLENGE (Để xác thực quyền nhận tin)
            if (url.pathname === '/challenge') {
                const address = url.searchParams.get('address');
                if (!address) return new Response('Missing address', { status: 400 });
                
                const challenge = crypto.randomUUID();
                // Lưu challenge vào KV với TTL ngắn
                await env.PIDA_KV.put(`c:${address}`, challenge, { expirationTtl: CHALLENGE_TTL });
                
                return new Response(JSON.stringify({ challenge }), { 
                    headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
                });
            }

            // 2. GỬI TIN NHẮN (Yêu cầu PoW & Lưu KV với TTL)
            if (url.pathname === '/send' && request.method === 'POST') {
                const { msg, pow } = await request.json();
                
                // Kiểm tra PoW chống Spam
                const isValid = await verifyPoW(msg.id, pow.nonce, pow.hash);
                if (!isValid) return new Response('PoW Validation Failed', { status: 403 });

                // Lưu tin nhắn vào KV
                // Key format: m:UUID_NGUOI_NHAN:ID_TIN_NHAN
                const kvKey = `m:${msg.to}:${msg.id}`;
                await env.PIDA_KV.put(kvKey, JSON.stringify(msg), { expirationTtl: DEFAULT_TTL });

                return new Response(JSON.stringify({ success: true }), { 
                    headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
                });
            }

            // 3. NHẬN TIN NHẮN (Xác thực Chữ ký ECDSA)
            if (url.pathname === '/get' && request.method === 'POST') {
                const { address, signature, challenge } = await request.json();
                
                // Kiểm tra challenge trong KV
                const storedChallenge = await env.PIDA_KV.get(`c:${address}`);
                if (!storedChallenge || storedChallenge !== challenge) {
                    return new Response('Challenge expired or invalid', { status: 401 });
                }

                // Xóa challenge sau khi dùng (One-time use)
                await env.PIDA_KV.delete(`c:${address}`);

                // Lấy danh sách tin nhắn từ KV theo prefix
                const list = await env.PIDA_KV.list({ prefix: `m:${address}:` });
                const messages = [];
                for (const key of list.keys) {
                    const val = await env.PIDA_KV.get(key.name);
                    if (val) messages.append(JSON.parse(val));
                }

                return new Response(JSON.stringify({ messages }), { 
                    headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
                });
            }

            // 4. XÁC NHẬN ĐÃ NHẬN (ACK) - Xóa tin khỏi KV
            if (url.pathname === '/ack' && request.method === 'POST') {
                const { id, address } = await request.json();
                await env.PIDA_KV.delete(`m:${address}:${id}`);
                return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
            }

            return new Response("PIDA Relay v2.7 Online", { status: 200, headers: corsHeaders });

        } catch (err) {
            return new Response(err.message, { status: 500, headers: corsHeaders });
        }
    }
}