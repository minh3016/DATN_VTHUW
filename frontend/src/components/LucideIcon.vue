<template>
  <i ref="el" :data-lucide="name" :style="iconStyle"></i>
</template>

<script setup>
import { ref, onMounted, onUpdated, computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 20 },
  strokeWidth: { type: [Number, String], default: 2 },
})

const el = ref(null)
const iconStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
}))

function renderIcon() {
  if (window.lucide && el.value) {
    window.lucide.createIcons({ nodes: [el.value] })
  }
}

onMounted(renderIcon)
onUpdated(renderIcon)
</script>
