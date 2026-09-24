<script setup>
import { ref } from 'vue'

const props = defineProps({ src: String, position: Number, alt: String })
const failed = ref(false)
</script>

<template>
  <img v-if="props.src && !failed" :src="props.src" :alt="props.alt" class="img" @error="failed = true" />
  <div v-else class="placeholder" :title="`Placeholder image — Product ${position}`">
    <svg viewBox="0 0 40 52" width="28" height="36" aria-hidden="true">
      <rect x="11" y="2" width="18" height="8" rx="2" fill="#b9d4df" stroke="#34647c" stroke-width="2" />
      <rect x="4" y="10" width="32" height="40" rx="6" fill="#e6f3f7" stroke="#34647c" stroke-width="2" />
      <rect x="9" y="22" width="22" height="14" rx="1" fill="#fff" />
      <text x="20" y="32.5" text-anchor="middle" font-size="9" font-weight="800" fill="#1f6570" font-family="Arial">Rx</text>
    </svg>
    <span>Product {{ position }}</span>
  </div>
</template>

<style scoped>
.img, .placeholder {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  flex: none;
}
.img { object-fit: cover; border: 1px solid var(--line); }
.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  background: var(--blue-soft);
  border: 1px dashed #b8d3e0;
  color: #34647c;
  font-size: 9px;
  font-weight: 700;
}
</style>
