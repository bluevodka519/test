// Customer view by default. Add ?debug to the URL to see the technical
// details (API error reasons, fee formulas, parcel maths, data warnings).
export const DEBUG = (() => {
  try {
    return new URLSearchParams(window.location.search).has('debug')
  } catch {
    return false
  }
})()
