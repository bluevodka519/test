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

// Technical status names, shown in the ?debug view only.
export const TRACKING_LABELS = {
  OK: 'Live',
  NO_DATA: 'No data',
  UNAVAILABLE: 'Unavailable',
  NOT_CONFIGURED: 'Not configured',
  NOT_IMPLEMENTED: 'Not implemented',
  NOT_REQUESTED: 'Not requested',
}

// What a customer sees for each tracking state. Internal reasons (HTTP codes,
// missing configuration, retired services) are deliberately not exposed.
export const CUSTOMER_TRACKING = {
  NO_DATA: {
    pill: 'Awaiting update',
    text: 'No tracking updates yet. Updates appear once the carrier scans the parcel.',
  },
  UNAVAILABLE: {
    pill: 'Tracking unavailable',
    text: 'Tracking details are temporarily unavailable. Please check again later, or use the tracking number on the carrier\'s website.',
  },
  NOT_CONFIGURED: {
    pill: 'Tracking unavailable',
    text: 'Tracking details are temporarily unavailable. Please check again later, or use the tracking number on the carrier\'s website.',
  },
  NOT_IMPLEMENTED: {
    pill: 'Tracking unavailable',
    text: 'Online tracking is not available for this carrier. Please use the tracking number on the carrier\'s website.',
  },
  NOT_REQUESTED: { pill: 'Loading', text: 'Loading tracking details…' },
}

export const FEE_LABELS = {
  COURIER_QUOTE: 'Carrier rate',
  FORMULA_ESTIMATE: 'Estimated',
  NOT_AVAILABLE: 'Not available',
  NO_ITEMS: 'No items',
}

// Customer wording for line problems (the ?debug view shows the raw message).
export const CUSTOMER_LINE_STATUS = {
  SKU_NOT_FOUND: { pill: 'Unavailable', text: 'Product details are unavailable for this item. It is not included in the total.' },
  INVALID_QTY: { pill: 'Check quantity', text: 'The quantity for this item needs to be confirmed. It is not included in the total.' },
  BAD_PRODUCT_DATA: { pill: 'Price pending', text: 'The price for this item is being confirmed. It is not included in the total.' },
}

export const CARRIER_LABELS = {
  AUSPOST: 'Australia Post',
  STARTRACK: 'StarTrack',
  TNT: 'TNT',
}
