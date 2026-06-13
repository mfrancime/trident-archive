// OpenSky Network — Real-time flight tracking
// Free for research. 4,000 API credits/day (no auth), 8,000 with account.
// Tracks all aircraft with ADS-B transponders including many military.

import { safeFetch } from '../utils/fetch.mjs';

const BASE = 'https://opensky-network.org/api';

// Get all current flights (global state vector)
export async function getAllFlights() {
  return safeFetch(`${BASE}/states/all`, { timeout: 30000 });
}

// Get flights in a bounding box (lat/lon)
export async function getFlightsInArea(lamin, lomin, lamax, lomax) {
  const params = new URLSearchParams({
    lamin: String(lamin),
    lomin: String(lomin),
    lamax: String(lamax),
    lomax: String(lomax),
  });
  return safeFetch(`${BASE}/states/all?${params}`, { timeout: 20000 });
}

// Get flights by specific aircraft (ICAO24 hex codes)
export async function getFlightsByIcao(icao24List) {
  const icao = Array.isArray(icao24List) ? icao24List : [icao24List];
  const params = icao.map(i => `icao24=${i}`).join('&');
  return safeFetch(`${BASE}/states/all?${params}`, { timeout: 20000 });
}

// Get departures from an airport in a time range
export async function getDepartures(airportIcao, begin, end) {
  const params = new URLSearchParams({
    airport: airportIcao,
    begin: String(Math.floor(begin / 1000)),
    end: String(Math.floor(end / 1000)),
  });
  return safeFetch(`${BASE}/flights/departure?${params}`);
}

// Get arrivals at an airport
export async function getArrivals(airportIcao, begin, end) {
  const params = new URLSearchParams({
    airport: airportIcao,
    begin: String(Math.floor(begin / 1000)),
    end: String(Math.floor(end / 1000)),
  });
  return safeFetch(`${BASE}/flights/arrival?${params}`);
}

// Key hotspot regions for monitoring
const HOTSPOTS = {
  middleEast: { lamin: 12, lomin: 30, lamax: 42, lomax: 65, label: 'Middle East' },
  taiwan: { lamin: 20, lomin: 115, lamax: 28, lomax: 125, label: 'Taiwan Strait' },
  ukraine: { lamin: 44, lomin: 22, lamax: 53, lomax: 41, label: 'Ukraine Region' },
  baltics: { lamin: 53, lomin: 19, lamax: 60, lomax: 29, label: 'Baltic Region' },
  southChinaSea: { lamin: 5, lomin: 105, lamax: 23, lomax: 122, label: 'South China Sea' },
  koreanPeninsula: { lamin: 33, lomin: 124, lamax: 43, lomax: 132, label: 'Korean Peninsula' },
};

// Briefing — check hotspot regions for flight activity
// Sequential requests with delay to avoid 429 rate limits (free tier: ~100 req/day)
export async function briefing() {
  // Only query 3 highest-priority hotspots to conserve rate limit budget
  const PRIORITY_KEYS = ['middleEast', 'ukraine', 'taiwan'];
  const hotspotEntries = Object.entries(HOTSPOTS).filter(([k]) => PRIORITY_KEYS.includes(k));

  const results = [];
  for (const [key, box] of hotspotEntries) {
    const data = await getFlightsInArea(box.lamin, box.lomin, box.lamax, box.lomax);

    // Detect rate-limit / error
    if (data?.error || data?.rateLimited) {
      results.push({
        region: box.label,
        key,
        totalAircraft: 0,
        byCountry: {},
        noCallsign: 0,
        highAltitude: 0,
        status: data?.rateLimited ? 'rate_limited' : 'error',
        message: data?.error,
      });
      // If rate-limited, skip remaining regions
      if (data?.rateLimited) {
        for (const [k2, b2] of hotspotEntries.filter(([k]) => !results.some(r => r.key === k))) {
          results.push({ region: b2.label, key: k2, totalAircraft: 0, byCountry: {}, noCallsign: 0, highAltitude: 0, status: 'skipped' });
        }
        break;
      }
      continue;
    }

    const states = data?.states || [];
    results.push({
      region: box.label,
      key,
      totalAircraft: states.length,
      byCountry: states.reduce((acc, s) => {
        const country = s[2] || 'Unknown';
        acc[country] = (acc[country] || 0) + 1;
        return acc;
      }, {}),
      noCallsign: states.filter(s => !s[1]?.trim()).length,
      highAltitude: states.filter(s => s[7] && s[7] > 12000).length,
    });

    // 12s delay between requests to stay well under rate limit
    if (hotspotEntries.indexOf([key, box]) < hotspotEntries.length - 1) {
      await new Promise(r => setTimeout(r, 12000));
    }
  }

  // Add remaining regions as not-queried
  for (const [key, box] of Object.entries(HOTSPOTS)) {
    if (!results.some(r => r.key === key)) {
      results.push({ region: box.label, key, totalAircraft: 0, byCountry: {}, noCallsign: 0, highAltitude: 0, status: 'not_queried' });
    }
  }

  const anyRateLimited = results.some(r => r.status === 'rate_limited');
  return {
    source: 'OpenSky',
    timestamp: new Date().toISOString(),
    hotspots: results,
    ...(anyRateLimited && { status: 'degraded', message: 'Rate limited — some regions skipped' }),
  };
}

if (process.argv[1]?.endsWith('opensky.mjs')) {
  const data = await briefing();
  console.log(JSON.stringify(data, null, 2));
}
