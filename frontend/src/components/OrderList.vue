<script setup>
import { aud, auDate } from '../format'

defineProps({ orders: Array, selected: String })
defineEmits(['select'])
</script>

<template>
  <nav class="list">
    <button
      v-for="o in orders" :key="o.order_no"
      class="item" :class="{ active: o.order_no === selected }"
      @click="$emit('select', o.order_no)"
    >
      <span class="row">
        <span class="no mono">{{ o.order_no }}</span>
        <span v-if="o.is_test" class="tag">TEST</span>
      </span>
      <span class="row sub">
        <span>{{ o.customer }} · {{ auDate(o.order_date) }}</span>
      </span>
      <span class="row sub">
        <span>{{ o.status }}</span>
        <strong>{{ aud(o.total) }}</strong>
      </span>
      <span v-if="o.warning_count" class="warn">⚠ {{ o.warning_count }} warning{{ o.warning_count > 1 ? 's' : '' }}</span>
    </button>
  </nav>
</template>

<style scoped>
.list { display: flex; flex-direction: column; gap: 6px; }
.item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: rgba(255,255,255,.06);
  color: #dce9f1;
  text-align: left;
  font: inherit;
  cursor: pointer;
}
.item:hover { background: rgba(255,255,255,.12); }
.item.active { background: #fff; color: var(--ink); border-color: #fff; }
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.no { font-size: 13px; font-weight: 700; }
.sub { font-size: 12px; opacity: .85; }
.tag {
  font-size: 10px; font-weight: 800; letter-spacing: .05em;
  padding: 1px 6px; border-radius: 4px; background: #ffe6ae; color: #784900;
}
.warn { font-size: 11px; color: #f3c46b; }
.item.active .warn { color: var(--amber); }
</style>
