<script setup>
import { onMounted, ref } from 'vue'
import { fetchOrders } from './api'
import OrderList from './components/OrderList.vue'
import OrderDetail from './components/OrderDetail.vue'

const orders = ref([])
const dataWarnings = ref([])
const selected = ref(null)
const error = ref('')
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchOrders()
    orders.value = data.orders
    dataWarnings.value = data.data_warnings
    if (!selected.value && orders.value.length) selected.value = orders.value[0].order_no
  } catch (e) {
    error.value = `Could not load orders (${e.message}). Is the backend running on port 8000?`
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <h1>Orders</h1>
        <button class="refresh" @click="load" :disabled="loading">Refresh</button>
      </div>
      <OrderList :orders="orders" :selected="selected" @select="selected = $event" />
      <div v-if="dataWarnings.length" class="banner warn small">
        <strong>Data file warnings</strong>
        <ul><li v-for="w in dataWarnings" :key="w">{{ w }}</li></ul>
      </div>
    </aside>

    <main class="content">
      <div v-if="error" class="banner bad">{{ error }}</div>
      <p v-else-if="loading && !orders.length" class="muted">Loading orders…</p>
      <OrderDetail v-else-if="selected" :key="selected" :order-no="selected" />
      <p v-else class="muted">No orders in the data files.</p>
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 100vh;
}
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px 14px;
  background: var(--navy);
  color: #fff;
}
.brand { display: flex; align-items: center; justify-content: space-between; padding: 0 6px; }
.brand h1 { color: #fff; font-size: 18px; }
.refresh {
  border: 1px solid rgba(255,255,255,.35);
  background: transparent;
  color: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
}
.refresh:disabled { opacity: .5; cursor: default; }
.content { padding: 24px; min-width: 0; }

@media (max-width: 860px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar { padding: 14px 16px; }
  .content { padding: 16px; }
}
</style>
