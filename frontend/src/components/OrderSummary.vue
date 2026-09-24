<script setup>
import { aud } from '../format'

defineProps({ totals: Object, feeIsEstimate: Boolean })
</script>

<template>
  <div class="summary">
    <div class="row"><span>Subtotal (ex GST)</span><span>{{ aud(totals.subtotal_ex_gst) }}</span></div>
    <div class="row"><span>GST (10% of Subtotal)</span><span>{{ aud(totals.gst) }}</span></div>
    <div class="row">
      <span>Shipment Fee<sup v-if="feeIsEstimate">*</sup></span>
      <span>{{ aud(totals.shipment_fee) }}</span>
    </div>
    <div class="row total"><span>Total <small>(Subtotal + GST + Shipment Fee)</small></span><span>{{ aud(totals.total) }}</span></div>
    <p v-if="feeIsEstimate" class="footnote">
      * Shipment fee is an estimate based on parcel weight, size and destination.
    </p>
  </div>
</template>

<style scoped>
.summary { margin-top: 8px; padding-top: 10px; border-top: 2px solid var(--line); }
.row { display: flex; justify-content: space-between; padding: 3px 0; }
.row span:last-child { font-variant-numeric: tabular-nums; font-weight: 600; }
.total {
  margin-top: 6px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
  color: var(--navy);
  font-size: 16px;
  font-weight: 800;
}
.total small { font-size: 11px; font-weight: 400; color: var(--muted); }
.footnote { margin: 8px 0 0; font-size: 12px; color: var(--muted); }
</style>
