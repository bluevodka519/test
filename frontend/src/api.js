async function getJson(url) {
  const resp = await fetch(url)
  if (!resp.ok) {
    let detail = ''
    try { detail = (await resp.json()).detail || '' } catch { /* not JSON */ }
    throw new Error(`HTTP ${resp.status}${detail ? `: ${detail}` : ''}`)
  }
  return resp.json()
}

export const fetchOrders = () => getJson('/api/orders')
export const fetchOrder = (orderNo) => getJson(`/api/orders/${encodeURIComponent(orderNo)}`)
