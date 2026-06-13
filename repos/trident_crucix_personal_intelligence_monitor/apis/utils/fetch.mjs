// Shared fetch utility with timeout, retries, and error handling

const RATE_LIMIT_PATTERNS = [
  /limit requests/i,
  /rate limit/i,
  /too many requests/i,
  /throttl/i,
];

export async function safeFetch(url, opts = {}) {
  const { timeout = 15000, retries = 2, headers = {}, retryDelay = 3000 } = opts;
  let lastError;
  for (let i = 0; i <= retries; i++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { 'User-Agent': 'Crucix/1.0', ...headers },
      });
      clearTimeout(timer);

      // Handle HTTP 429 explicitly
      if (res.status === 429) {
        const retryAfter = res.headers.get('x-rate-limit-retry-after-seconds') || res.headers.get('retry-after');
        const err = new Error(`HTTP 429: Rate limited${retryAfter ? ` (retry after ${retryAfter}s)` : ''}`);
        err.rateLimited = true;
        err.retryAfterSeconds = parseInt(retryAfter) || 60;
        throw err;
      }

      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }

      const text = await res.text();

      // Detect rate-limit responses that come back as 200 OK with plain text
      if (RATE_LIMIT_PATTERNS.some(p => p.test(text.slice(0, 200)))) {
        const err = new Error(`Rate limited: ${text.slice(0, 100)}`);
        err.rateLimited = true;
        err.retryAfterSeconds = 10;
        throw err;
      }

      try { return JSON.parse(text); } catch {
        // Non-JSON response — return as rawText but log a warning
        return { rawText: text.slice(0, 500), _nonJson: true };
      }
    } catch (e) {
      lastError = e;
      if (i < retries) {
        // Rate-limited? Wait longer
        const delay = e.rateLimited
          ? Math.min(e.retryAfterSeconds * 1000, 15000)
          : retryDelay * (i + 1);
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }
  return { error: lastError?.message || 'Unknown error', source: url, rateLimited: !!lastError?.rateLimited };
}

export function ago(hours) {
  return new Date(Date.now() - hours * 3600000).toISOString();
}

export function today() {
  return new Date().toISOString().split('T')[0];
}

export function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split('T')[0];
}
