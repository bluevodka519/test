<script setup>
import { onMounted, ref } from 'vue'
import { fetchOrder } from '../api'
import { auDate, CARRIER_LABELS } from '../format'
import LineItem from './LineItem.vue'
import OrderSummary from './OrderSummary.vue'
import TrackingPanel from './TrackingPanel.vue'

const props = defineProps({ orderNo: String })
const detail = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    detail.value = await fetchOrder(props.orderNo)
  } catch (e) {
    error.value = `Could not load order ${props.orderNo} (${e.message}).`
  }
})

const statusClass = (s) => ({ completed: 'ok', 'in transit': 'info' }[(s || '').toLowerCase()] || 'warn')
</script>

<template>
  <div v-if="error" class="banner bad">{{ error }}</div>
  <p v-else-if="!detail" class="muted">Loading order and live tracking…</p>

  <div v-else class="detail">
    <header class="header">
      <div>
        <h2>Order Details</h2>
        <div class="muted">
          Order number <span class="mono">{{ detail.order.order_no }}</span> · {{ auDate(detail.order.order_date) }}
        </div>
      </div>
      <div class="pills">
        <span v-if="detail.order.is_test" class="pill warn">TEST DATA</span>
        <span class="pill" :class="statusClass(detail.order.status)">{{ detail.order.status }}</span>
      </div>
    </header>

    <div v-if="detail.order.test_note" class="banner warn small">{{ detail.order.test_note }}</div>
    <div v-if="detail.warnings.length" class="banner warn">
      <strong>{{ detail.warnings.length }} issue{{ detail.warnings.length > 1 ? 's' : '' }} found — affected lines are excluded from totals</strong>
      <ul><li v-for="w in detail.warnings" :key="w">{{ w }}</li></ul>
    </div>

    <div class="grid">
      <div class="left">
        <section class="panel">
          <h3>SKU Details</h3>
          <div class="muted small">{{ detail.shipments.reduce((n, s) => n + s.lines.length, 0) }} line(s) · prices in AUD · RRP includes GST, unit price and subtotal shown ex GST</div>
          <p v-if="!detail.shipments.length" class="muted">No SKU lines for this order number.</p>
          <div v-for="s in detail.shipments" :key="s.tracking_ref" class="group">
            <div class="group-head small">
              {{ s.tracking_ref }} · {{ CARRIER_LABELS[s.carrier] || 'Unknown courier' }}
              <span class="mono">{{ s.tracking_no }}</span>
            </div>
            <LineItem v-for="l in s.lines" :key="l.position" :line="l" />
          </div>
          <OrderSummary :totals="detail.totals" />
        </section>

        <section class="panel">
          <h3>Shipping Information</h3>
          <address>
            <strong>{{ detail.order.customer }}</strong><br />
            {{ detail.order.company }}<br />
            {{ detail.order.address.street }}<br />
            {{ detail.order.address.suburb }} {{ detail.order.address.state }} {{ detail.order.address.postcode }}
          </address>
          <div class="contact small muted">
            <span>{{ detail.order.phone }}</span>
            <span>{{ detail.order.email }}</span>
          </div>
        </section>
      </div>

      <div class="right">
        <h3 class="section-title">Logistics Tracking</h3>
        <TrackingPanel v-for="s in detail.shipments" :key="s.tracking_ref" :shipment="s" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail { display: flex; flex-direction: column; gap: 14px; max-width: 1180px; }
.header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.header h2 { font-size: 22px; }
.pills { display: flex; gap: 6px; }
.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  gap: 16px;
  align-items: start;
}
.left, .right { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.section-title { font-size: 15px; }
.panel h3 { font-size: 15px; }
.group { margin-top: 10px; }
.group-head {
  display: flex;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--grey-soft);
  color: var(--muted);
  font-weight: 700;
}
address { font-style: normal; margin-top: 8px; }
.contact { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 6px; }

@media (max-width: 1000px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
