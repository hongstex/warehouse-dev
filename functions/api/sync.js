// 编辑器云同步：同一个同步码 = 同一批方案。按方案逐个「最后修改者胜」。
// 请求头 X-Sync-Code: 同步码（只存它的 SHA-256，不存原文）
// GET  /api/sync?since=<st>  → { now, items:[{id,name,t,st,deleted,data}] }  st > since 的
// POST /api/sync  { items:[{id,name,t,deleted,data}] } → { now, applied }

const MAX_BODY = 4 * 1024 * 1024;
const SCHEMA = `CREATE TABLE IF NOT EXISTS designs (space TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', t INTEGER NOT NULL, st INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, data TEXT, PRIMARY KEY (space, id))`;
let ready = false;

const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

async function space(req) {
  const code = (req.headers.get("x-sync-code") || "").trim();
  if (code.length < 8 || code.length > 200) return null;
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("warehouse-edit:" + code));
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function onRequest({ request, env }) {
  if (!env.DB) return json({ error: "no database binding" }, 500);
  const sp = await space(request);
  if (!sp) return json({ error: "同步码无效（至少 8 位）" }, 401);
  if (!ready) { await env.DB.exec(SCHEMA); ready = true; }

  if (request.method === "GET") {
    const since = Number(new URL(request.url).searchParams.get("since")) || 0;
    const { results } = await env.DB.prepare("SELECT id, name, t, st, deleted, data FROM designs WHERE space = ? AND st > ? ORDER BY st").bind(sp, since).all();
    return json({ now: Date.now(), items: results.map((r) => ({ ...r, deleted: !!r.deleted, data: r.data ? JSON.parse(r.data) : null })) });
  }

  if (request.method === "POST") {
    const len = Number(request.headers.get("content-length") || 0);
    if (len > MAX_BODY) return json({ error: "too large" }, 413);
    let body;
    try { body = JSON.parse(await request.text()); } catch (e) { return json({ error: "bad json" }, 400); }
    const items = Array.isArray(body.items) ? body.items.slice(0, 200) : [];
    let now = Date.now();
    const stmts = [];
    for (const it of items) {
      if (!it || typeof it.id !== "string" || !/^[\w-]{1,40}$/.test(it.id) || !Number.isFinite(it.t)) continue;
      const data = it.deleted ? null : JSON.stringify(it.data ?? null);
      if (data && data.length > MAX_BODY) continue;
      stmts.push(env.DB.prepare(
        `INSERT INTO designs (space, id, name, t, st, deleted, data) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
         ON CONFLICT (space, id) DO UPDATE SET name = excluded.name, t = excluded.t, st = excluded.st, deleted = excluded.deleted, data = excluded.data
         WHERE excluded.t > designs.t`
      ).bind(sp, it.id, String(it.name || "").slice(0, 100), Math.round(it.t), now++, it.deleted ? 1 : 0, data));
    }
    const res = stmts.length ? await env.DB.batch(stmts) : [];
    return json({ now, applied: res.reduce((n, r) => n + (r.meta?.changes || 0), 0) });
  }

  return json({ error: "method not allowed" }, 405);
}
