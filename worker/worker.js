export default {
  async fetch(request, env) {
    const url = new URL(request.url)

    // ===== CORS =====
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: corsHeaders()
      })
    }

    try {
      // ================= SEND MESSAGE =================
      if (url.pathname === "/send" && request.method === "POST") {
        const body = await request.json()

        const {
          toUUID,
          fromUUID,
          fromNick,
          cipher,
          iv
        } = body

        if (!toUUID || !fromUUID || !cipher || !iv) {
          return json({ error: "Missing field" }, 400)
        }

        const msg = {
          id: crypto.randomUUID(),
          fromUUID,
          fromNick: fromNick || "",
          cipher,
          iv,
          createdAt: Date.now()
        }

        const key = `inbox:${toUUID}`
        const raw = await env.PIDA_KV.get(key)
        const list = raw ? JSON.parse(raw) : []

        list.push(msg)

        await env.PIDA_KV.put(
          key,
          JSON.stringify(list),
          { expirationTtl: 60 * 60 * 24 * 5 } // 5 ngày
        )

        return json({ ok: true })
      }

      // ================= GET INBOX =================
      if (url.pathname.startsWith("/inbox/") && request.method === "GET") {
        const uuid = url.pathname.split("/").pop()
        const data = await env.PIDA_KV.get(`inbox:${uuid}`)
        return json(data ? JSON.parse(data) : [])
      }

      // ================= ACK (CLEAR SERVER) =================
      if (url.pathname.startsWith("/ack/") && request.method === "POST") {
        const uuid = url.pathname.split("/").pop()
        await env.PIDA_KV.delete(`inbox:${uuid}`)
        return json({ ok: true })
      }

      // ================= FALLBACK =================
      return json({ error: "Not found" }, 404)

    } catch (err) {
      return json({
        error: "Worker exception",
        message: err.message
      }, 500)
    }
  }
}

// ===== HELPERS =====
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders()
    }
  })
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
  }
          }
