<script setup>
import { computed } from 'vue'
import { aud } from '../format'
import ProductImage from './ProductImage.vue'

const props = defineProps({ line: Object })
const ok = computed(() => props.line.status === 'OK')
const statusText = {
  SKU_NOT_FOUND: 'SKU not found',
  INVALID_QTY: 'Invalid quantity',
  BAD_PRODUCT_DATA: 'Bad product data',
}
</script>

<template>
  <div class="line" :class="{ excluded: !ok }">
    <ProductImage :src="line.image_url" :position="line.position" :alt="line.name || line.sku" />
    <div class="body">
      <div class="top">
        <div class="names">
          <div class="name">{{ line.name || 'Unknown product' }}</div>
          <div class="sku">SKU <span class="mono">{{ line.sku }}</span></div>
        </div>
        <span v-if="!ok" class="pill bad">{{ statusText[line.status] }}</span>
      </div>
      <div v-if="line.description && line.description !== line.name" class="desc">{{ line.description }}</div>
      <dl class="nums">
        <div><dt>RRP (incl. GST)</dt><dd>{{ aud(line.rrp) }}</dd></div>
        <div><dt>Unit price (ex GST)</dt><dd>{{ aud(line.unit_price_ex_gst) }}</dd></div>
        <div><dt>Quantity</dt><dd>{{ line.quantity }}</dd></div>
        <div class="total"><dt>Line subtotal (ex GST)</dt><dd>{{ ok ? aud(line.line_subtotal_ex_gst) : '—' }}</dd></div>
      </dl>
      <div v-if="!ok" class="msg">{{ line.message }}</div>
    </div>
  </div>
</template>

<style scoped>
.line {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.line:last-child { border-bottom: 0; }
.line.excluded .name { text-decoration: line-through; text-decoration-color: #c9a0a0; }
.body { flex: 1; min-width: 0; }
.top { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }
.names { min-width: 0; }
.name { font-weight: 700; color: var(--navy); }
.sku { font-size: 12px; color: var(--muted); }
.desc {
  margin-top: 2px;
  font-size: 12px;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.nums {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 6px 0 0;
}
.nums dt { font-size: 11px; color: var(--muted); }
.nums dd { margin: 0; font-variant-numeric: tabular-nums; }
.nums .total { text-align: right; }
.nums .total dd { font-weight: 700; }
.msg { margin-top: 4px; font-size: 13px; color: var(--red); }
</style>
