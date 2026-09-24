<script setup>
import { computed } from 'vue'
import { aud, auDateTime, CARRIER_LABELS, FEE_LABELS, TRACKING_LABELS } from '../format'

const props = defineProps({ shipment: Object })
const t = computed(() => props.shipment.tracking)
const fee = computed(() => props.shipment.fee)

const trackingPill = computed(() => ({
  OK: 'ok', NO_DATA: 'warn', UNAVAILABLE: 'bad', NOT_CONFIGURED: 'warn', NOT_IMPLEMENTED: '', NOT_REQUESTED: '',
}[t.value.status]))
const feePill = computed(() => ({
  COURIER_QUOTE: 'ok', FORMULA_ESTIMATE: 'info', NOT_AVAILABLE: '', NO_ITEMS: '',
}[fee.value.source]))
</script>

<template>
  <section class="panel card">
    <header class="head">
      <div>
        <h3>{{ CARRIER_LABELS[shipment.carrier] || shipment.logistics_company || 'Unknown courier' }}</h3>
        <div class="muted small">
          {{ shipment.tracking_ref }} · Tracking <span class="mono">{{ shipment.tracking_no || '—' }}</span>
        </div>
      </div>
      <span class="pill" :class="trackingPill">
        {{ t.status === 'OK' && t.current_status ? t.current_status : TRACKING_LABELS[t.status] }}
      </span>
    </header>

    <!-- Live result -->
    <template v-if="t.status === 'OK'">
      <div class="current">
        <div class="small muted">Last update</div>
        <strong>{{ auDateTime(t.last_update) }}</strong>
      </div>
      <ol class="timeline">
        <li v-for="(ev, i) in t.events" :key="i" :class="{ latest: i === 0 }">
          <strong>{{ ev.description || 'Event' }}</strong>
          <div class="small muted">
            {{ auDateTime(ev.date) }}<span v-if="ev.location"> · {{ ev.location }}</span>
          </div>
        </li>
      </ol>
      <p v-if="t.message" class="small muted source">{{ t.message }}</p>
    </template>

    <!-- Any non-live state: never invent a result -->
    <div v-else class="state" :class="trackingPill">
      <strong>{{ TRACKING_LABELS[t.status] }}</strong>
      <p>{{ t.message || 'No live tracking result.' }}</p>
    </div>

    <footer class="fee">
      <div class="fee-top">
        <span>Shipment Fee</span>
        <span class="pill" :class="feePill">{{ FEE_LABELS[fee.source] }}</span>
        <strong>{{ aud(fee.amount) }}</strong>
      </div>
      <p class="small muted">{{ fee.note }}</p>
      <p v-if="fee.parcel" class="small muted">
        Parcel: {{ fee.parcel.item_count }} items · {{ fee.parcel.weight_kg }} kg ·
        {{ fee.parcel.length_cm }}×{{ fee.parcel.width_cm }}×{{ fee.parcel.height_cm }} cm ·
        cubic {{ fee.parcel.cubic_kg }} kg<span v-if="fee.chargeable_kg"> · chargeable {{ fee.chargeable_kg }} kg</span>
      </p>
    </footer>
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
  background: var(--grey-soft);
  font-size: 13px;
}
.state p { margin: 2px 0 0; }
.state.warn { background: var(--amber-soft); color: #5e3a00; }
.state.bad { background: var(--red-soft); color: #6b2121; }
.source { margin: 0; }
.fee { border-top: 1px dashed var(--line); padding-top: 10px; }
.fee-top { display: flex; align-items: center; gap: 8px; }
.fee-top strong { margin-left: auto; font-size: 15px; }
.fee p { margin: 4px 0 0; }
</style>
