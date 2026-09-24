// Money arrives from the API as exact strings ("1234.50"). Format the string
// directly so no floating-point arithmetic ever touches an amount.
export function aud(value) {
  if (value === null || value === undefined || value === '') return '—'
  const [whole, frac = '00'] = String(value).replace('-', '').split('.')
  const sign = String(value).startsWith('-') ? '-' : ''
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${sign}A$${grouped}.${frac.padEnd(2, '0').slice(0, 2)}`
}

// "2025-11-30" -> "30/11/2025" (Australian order)
export function auDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso || '—'
}

export function auDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-AU', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: 'numeric', minute: '2-digit', timeZone: 'Australia/Sydney', timeZoneName: 'short',
  })
}

export const TRACKING_LABELS = {
  OK: 'Live',
  NO_DATA: 'No data',
  UNAVAILABLE: 'Unavailable',
  NOT_CONFIGURED: 'Not configured',
  NOT_IMPLEMENTED: 'Not implemented',
  NOT_REQUESTED: 'Not requested',
}

export const FEE_LABELS = {
  COURIER_QUOTE: 'Courier quote',
  FORMULA_ESTIMATE: 'Estimate (formula)',
  NOT_AVAILABLE: 'Not available',
  NO_ITEMS: 'No items',
}

export const CARRIER_LABELS = {
  AUSPOST: 'Australia Post',
  STARTRACK: 'StarTrack',
  TNT: 'TNT',
}
