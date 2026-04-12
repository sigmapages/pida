
const B2_CONFIG = {
  keyId: 'your key id here',
  applicationKey: 'your key here',
  bucketId: 'your bucket id here',
  bucketName: 'your bucket name',
  apiUrl: 'https://api004.backblazeb2.com'
};

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE',
  'Access-Control-Allow-Headers': 'Content-Type, x-pida-sdk-version',
};

// --- HELPER FUNCTIONS ---
async function getB2Token() {
  const auth = btoa(`${B2_CONFIG.keyId}:${B2_CONFIG.applicationKey}`);
  const res = await fetch(`${B2_CONFIG.apiUrl}/b2api/v2/b2_authorize_account`, {
    headers: { 'Authorization': `Basic ${auth}` }
  });
  return res.json();
}

async function b2Upload(path, body, contentType = 'b2/x-auto') {
  const auth = await getB2Token();
  const upUrlRes = await fetch(`${auth.apiUrl}/b2api/v2/b2_get_upload_url`, {
    method: 'POST',
    headers: { 'Authorization': auth.authorizationToken },
    body: JSON.stringify({ bucketId: B2_CONFIG.bucketId })
  });
  const upUrlData = await upUrlRes.json();
  return fetch(upUrlData.uploadUrl, {
    method: 'POST',
    headers: {
      'Authorization': upUrlData.authorizationToken,
      'X-Bz-File-Name': encodeURIComponent(path),
      'Content-Type': contentType,
      'X-Bz-Content-Sha1': 'do_not_verify'
    },
    body: body
  });
}

async function b2List(prefix) {
  const auth = await getB2Token();
  const res = await fetch(`${auth.apiUrl}/b2api/v2/b2_list_file_names`, {
    method: 'POST',
    headers: { 'Authorization': auth.authorizationToken },
    body: JSON.stringify({
      bucketId: B2_CONFIG.bucketId,
      prefix: prefix,
      maxFileCount: 1000
    })
  });
  const data = await res.json();
  return data.files || [];
}

async function b2Download(fileName) {
  const auth = await getB2Token();
  const cleanPath = fileName.startsWith('/') ? fileName.slice(1) : fileName;
  const url = `${auth.downloadUrl}/file/${B2_CONFIG.bucketName}/${cleanPath}`;
  return fetch(url, {
    headers: { 'Authorization': auth.authorizationToken }
  });
}

// --- HÀM XÓA FILE (PHẢI CÓ ĐỂ CHẠY LỆNH CLEAR) ---
async function b2Delete(fileName) {
  const auth = await getB2Token();
  // B2 yêu cầu fileId để xóa, nên phải lấy version trước
  const list = await fetch(`${auth.apiUrl}/b2api/v2/b2_list_file_versions`, {
    method: 'POST',
    headers: { 'Authorization': auth.authorizationToken },
    body: JSON.stringify({ bucketId: B2_CONFIG.bucketId, fileName: fileName, maxFileCount: 1 })
  });
  const data = await list.json();
  if (data.files && data.files.length > 0) {
    await fetch(`${auth.apiUrl}/b2api/v2/b2_delete_file_version`, {
      method: 'POST',
      headers: { 'Authorization': auth.authorizationToken },
      body: JSON.stringify({ fileName: fileName, fileId: data.files[0].fileId })
    });
  }
}

// --- MAIN FETCH HANDLER ---
export default {
  async fetch(request) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders });
    const url = new URL(request.url);

    try {
      // 1. HEALTH CHECK
      if (url.pathname === '/' || url.pathname === '/health') {
        return new Response(JSON.stringify({ status: "PIDA Native Online", version: "0.1.8.8" }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      // 2. CHALLENGE
      if (url.pathname === '/challenge') {
        const address = url.searchParams.get('address');
        const challenge = crypto.randomUUID();
        await b2Upload(`challenges/${address}`, challenge, 'text/plain');
        return new Response(JSON.stringify({ challenge }), { headers: corsHeaders });
      }

      // 3. SEND MESSAGE
      if (url.pathname === '/send' && request.method === 'POST') {
        const { msg } = await request.json();
        await b2Upload(`msgs/${msg.to}/${msg.id}`, JSON.stringify(msg));
        return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
      }

      // 4. UPLOAD FILE THẬT
      if (url.pathname === '/upload' && request.method === 'POST') {
        const fileId = url.searchParams.get('id');
        const binaryData = await request.arrayBuffer();
        await b2Upload(`files/${fileId}`, binaryData, 'application/octet-stream');
        return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
      }

      // 5. DOWNLOAD FILE THẬT
      if (url.pathname.startsWith('/f/')) {
        const parts = url.pathname.split('/');
        const fileId = parts[2];
        const fileName = parts[3] ? decodeURIComponent(parts[3]) : fileId;
        const res = await b2Download(`files/${fileId}`);
        if (res.status !== 200) {
          return new Response("💀 File not found on B2!", { status: 404, headers: corsHeaders });
        }
        return new Response(res.body, {
          headers: {
            ...corsHeaders,
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': `attachment; filename="${fileName}"`
          }
        });
      }

      // 6. CLEAR BUCKET (DỌN RÁC)
      if (url.pathname === '/clear' && request.method === 'POST') {
    const auth = await getB2Token();
    
    // Dùng b2_list_file_versions thay vì b2_list_file_names để thấy CẢ FILE ẨN
    const listRes = await fetch(`${auth.apiUrl}/b2api/v2/b2_list_file_versions`, {
        method: 'POST',
        headers: { 'Authorization': auth.authorizationToken },
        body: JSON.stringify({ bucketId: B2_CONFIG.bucketId, maxFileCount: 1000 })
    });
    
    const data = await listRes.json();
    const files = data.files || [];
    let count = 0;

    if (files.length > 0) {
        for (const file of files) {
            // Xóa chính xác từng version ID của file
            await fetch(`${auth.apiUrl}/b2api/v2/b2_delete_file_version`, {
                method: 'POST',
                headers: { 'Authorization': auth.authorizationToken },
                body: JSON.stringify({ 
                    fileName: file.fileName, 
                    fileId: file.fileId 
                })
            });
            count++;
        }
    }
    
    return new Response(JSON.stringify({ success: true, deleted: count }), { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
    });
}

      // 7. GET MESSAGES
      if (url.pathname === '/get' && request.method === 'POST') {
        const { address } = await request.json();
        const files = await b2List(`msgs/${address}/`);
        let messages = [];
        for (const file of files) {
          const res = await b2Download(file.fileName);
          const text = await res.text();
          try {
            messages.push(JSON.parse(text));
          } catch (e) {
            messages.push({
              id: file.fileName.split('/').pop(),
              from: "Unknown",
              content: text,
              type: "text",
              timestamp: Date.now()
            });
          }
        }
        return new Response(JSON.stringify({ messages }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      return new Response("Invalid endpoint", { status: 404, headers: corsHeaders });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }
};
