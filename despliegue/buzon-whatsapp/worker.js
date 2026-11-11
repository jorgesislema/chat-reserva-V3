/**
 * Buzón de WhatsApp (Cloudflare Worker + D1).
 *
 * Meta llama a  https://<worker>.workers.dev/webhook  (dirección pública fija).
 * El Worker verifica la firma, guarda el cuerpo crudo y responde 200 al
 * instante. La PC del negocio recoge los lotes con  GET /buzon  y los borra con
 * POST /buzon/confirmar (ambas rutas exigen  Authorization: Bearer BUZON_TOKEN).
 *
 * Secretos del Worker (wrangler secret put ...): WHATSAPP_VERIFY_TOKEN,
 * WHATSAPP_APP_SECRET, BUZON_TOKEN. Nunca se escriben en este archivo.
 */

const MAX_CUERPO = 512 * 1024;
const RETENCION_MS = 7 * 24 * 3600 * 1000;

function iguales(a, b) {
  // Comparación en tiempo constante (longitud incluida).
  a = String(a || ''); b = String(b || '');
  let dif = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    dif |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return dif === 0;
}

function aBase64(buf) {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(bin);
}

async function firmaValida(secreto, buf, cabecera) {
  const clave = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secreto),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const mac = new Uint8Array(await crypto.subtle.sign('HMAC', clave, buf));
  const hex = Array.from(mac).map((b) => b.toString(16).padStart(2, '0')).join('');
  return iguales('sha256=' + hex, cabecera);
}

async function registrar(env, tipo, bytes) {
  try {
    await env.DB.prepare('INSERT INTO eventos (cuando, tipo, bytes) VALUES (?, ?, ?)')
      .bind(Date.now(), tipo, bytes).run();
    await env.DB.prepare('DELETE FROM eventos WHERE cuando < ?').bind(Date.now() - RETENCION_MS).run();
  } catch (e) { /* el registro nunca rompe el webhook */ }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);

    if (url.pathname === '/webhook') {
      if (req.method === 'GET') {
        const ok = url.searchParams.get('hub.mode') === 'subscribe'
          && env.WHATSAPP_VERIFY_TOKEN
          && iguales(url.searchParams.get('hub.verify_token'), env.WHATSAPP_VERIFY_TOKEN);
        return ok ? new Response(url.searchParams.get('hub.challenge') || '', { status: 200 })
                  : new Response('forbidden', { status: 403 });
      }
      if (req.method === 'POST') {
        const buf = await req.arrayBuffer();
        if (buf.byteLength > MAX_CUERPO) return new Response('too large', { status: 413 });
        const firma = req.headers.get('X-Hub-Signature-256') || '';
        if (!env.WHATSAPP_APP_SECRET || !(await firmaValida(env.WHATSAPP_APP_SECRET, buf, firma))) {
          // Se anota el rechazo (sin el contenido) para poder diagnosticar.
          await registrar(env, firma ? 'firma_invalida' : 'sin_firma', buf.byteLength);
          return new Response('forbidden', { status: 403 });
        }
        await registrar(env, 'recibido', buf.byteLength);
        await env.DB.prepare('INSERT INTO buzon (recibido, cuerpo_b64, firma) VALUES (?, ?, ?)')
          .bind(Date.now(), aBase64(buf), firma).run();
        return new Response('ok', { status: 200 });
      }
      return new Response('method not allowed', { status: 405 });
    }

    if (url.pathname === '/buzon' || url.pathname === '/buzon/confirmar') {
      const auth = req.headers.get('Authorization') || '';
      if (!env.BUZON_TOKEN || !iguales(auth, 'Bearer ' + env.BUZON_TOKEN)) {
        return json({ error: 'unauthorized' }, 401);
      }
      if (url.pathname === '/buzon' && req.method === 'GET') {
        const limite = Math.min(100, Math.max(1, parseInt(url.searchParams.get('limite') || '50', 10) || 50));
        const { results } = await env.DB.prepare(
          'SELECT id, recibido, cuerpo_b64, firma FROM buzon ORDER BY id LIMIT ?').bind(limite).all();
        return json({ pendientes: results || [] });
      }
      if (url.pathname === '/buzon' && req.method === 'POST') {
        // Diagnóstico: últimos eventos del webhook (sin contenido de mensajes).
        const { results } = await env.DB.prepare(
          'SELECT cuando, tipo, bytes FROM eventos ORDER BY id DESC LIMIT 20').all();
        return json({ eventos: results || [] });
      }
      if (url.pathname === '/buzon/confirmar' && req.method === 'POST') {
        let ids = [];
        try { ids = ((await req.json()) || {}).ids || []; } catch (e) { ids = []; }
        ids = ids.map((x) => parseInt(x, 10)).filter((x) => Number.isInteger(x)).slice(0, 100);
        for (const id of ids) {
          await env.DB.prepare('DELETE FROM buzon WHERE id = ?').bind(id).run();
        }
        await env.DB.prepare('DELETE FROM buzon WHERE recibido < ?').bind(Date.now() - RETENCION_MS).run();
        return json({ borrados: ids.length });
      }
      return json({ error: 'method not allowed' }, 405);
    }

    return new Response('not found', { status: 404 });
  },
};
