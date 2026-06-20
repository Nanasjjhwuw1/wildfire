// Thin API client. Uses relative /api so it works behind the Vite dev proxy
// and behind nginx in production without code changes.
const BASE = '/api'

async function asJson(resp) {
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      detail = body.detail ? JSON.stringify(body.detail) : detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return resp.json()
}

export const getArea = () => fetch(`${BASE}/area`).then(asJson)
export const getRisk = () => fetch(`${BASE}/risk`).then(asJson)
export const getRiskMl = () => fetch(`${BASE}/risk_ml`).then(asJson)
export const getNational = () => fetch(`${BASE}/national`).then(asJson)
export const getFirepoints = () => fetch(`${BASE}/firepoints`).then(asJson)

export const simulate = (body) =>
  fetch(`${BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(asJson)

export const recommend = (simId) =>
  fetch(`${BASE}/recommend?sim_id=${encodeURIComponent(simId)}`).then(asJson)
