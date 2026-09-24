<script setup>
import { computed } from 'vue'
import { DEBUG } from '../debug'
import { aud, auDateTime, CARRIER_LABELS, CUSTOMER_TRACKING, FEE_LABELS, TRACKING_LABELS } from '../format'

const props = defineProps({ shipment: Object, index: Number })
const t = computed(() => props.shipment.tracking)
const fee = computed(() => props.shipment.fee)
const customer = computed(() => CUSTOMER_TRACKING[t.value.status] || CUSTOMER_TRACKING.UNAVAILABLE)

const trackingPill = computed(() => (t.value.status === 'OK' ? 'ok' : 'warn'))
const feePill = computed(() => ({ COURIER_QUOTE: 'ok', FORMULA_ESTIMATE: 'info' }[fee.value.source] || ''))
const pillText = computed(() => {
  if (t.value.status === 'OK') return t.value.current_status || 'In progress'
  return DEBUG ? TRACKING_LABELS[t.value.status] : customer.value.pill
})
</script>

<template>
  <section class="panel card">
    <header class="head">
      <div>
        <h3>{{ CARRIER_LABELS[shipment.carrier] || shipment.logistics_company || 'Courier' }}</h3>
        <div class="muted small">
          <template v-if="DEBUG">{{ shipment.tracking_ref }}</template>
          <template v-else>Parcel {{ index }}</template>
          · Tracking no. <span class="mono">{{ shipment.tracking_no || '—' }}</span>
        </div>
      </div>
      <span class="pill" :class="trackingPill">{{ pillText }}</span>
    </header>

    <!-- Live result -->
    <template v-if="t.status === 'OK'">
      <div class="current">
        <div class="small muted">Last update</div>
        <strong>{{ auDateTime(t.last_update) }}</strong>
      </div>
      <ol class="timeline">
        <li v-for="(ev, i) in t.events" :key="i" :class="{ latest: i === 0 }">
          <strong>{{ ev.description || 'Update' }}</strong>
          <div class="small muted">
            {{ auDateTime(ev.date) }}<span v-if="ev.location"> · {{ ev.location }}</span>
          </div>
        </li>
      </ol>
    </template>

    <!-- Any non-live state: never invent a result -->
    <div v-else class="state">
      <p>{{ customer.text }}</p>
    </div>

    <footer class="fee">
      <div class="fee-top">
        <span>Shipment Fee</span>
        <span v-if="fee.source === 'COURIER_QUOTE' || fee.source === 'FORMULA_ESTIMATE'" class="pill" :class="feePill">
          {{ FEE_LABELS[fee.source] }}
        </span>
        <strong>{{ aud(fee.amount) }}</strong>
      </div>
    </footer>

    <!-- Internal details: open the page with ?debug -->
    <div v-if="DEBUG" class="debug small">
      <div><strong>Tracking</strong> [{{ t.status }}] {{ t.message || '—' }}</div>
      <div><strong>Fee</strong> [{{ fee.source }}] {{ fee.note || '—' }}</div>
      <div v-if="fee.parcel">
        <strong>Parcel</strong> {{ fee.parcel.item_count }} items · {{ fee.parcel.weight_kg }} kg ·
        {{ fee.parcel.length_cm }}×{{ fee.parcel.width_cm }}×{{ fee.parcel.height_cm }} cm ·
        cubic {{ fee.parcel.cubic_kg }} kg<span v-if="fee.chargeable_kg"> · chargeable {{ fee.chargeable_kg }} kg</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.card { display: flex; flex-direction: column; gap: 12px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.head h3 { font-size: 15px; }
.current { padding: 10px 12px; border-radius: 8px; background: var(--blue-soft); }
.timeline { list-style: none; margin: 0; padding: 0; }
.timeline li {
  position: relative;
  padding: 0 0 14px 20px;
  border-left: 2px solid #c9dde6;
  margin-left: 5px;
}
.timeline li:last-child { border-left-color: transparent; padding-bottom: 0; }
.timeline li::before {
  content: "";
  position: absolute;
  left: -6px;
  top: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #9fbfcd;
}
.timeline li.latest::before { background: var(--teal); }
.state {
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--amber-soft);
  color: #5e3a00;
  font-size: 13px;
}
.state p { margin: 0; }
.fee { border-top: 1px dashed var(--line); padding-top: 10px; }
.fee-top { display: flex; align-items: center; gap: 8px; }
.fee-top strong { margin-left: auto; font-size: 15px; }
.debug {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border: 1px dashed #b9c6cf;
  border-radius: 6px;
  background: #f6f8fa;
  color: var(--muted);
  font-family: Consolas, "Courier New", monospace;
}
</style>
