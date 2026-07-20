<template>
  <div v-if="frame" class="vc-preview">
    <img :src="'data:image/jpeg;base64,' + frame" alt="Preview" class="vc-preview-img" />
  </div>
</template>

<script setup>
// Component riêng cho ảnh preview realtime (base64, cập nhật liên tục qua WebSocket).
// Tách khỏi card cha để mỗi lần đổi frame chỉ re-render đúng <img> này, không kéo theo
// diff lại toàn bộ card (progress bar, nút bấm, badge...) — giảm giật lag khi có nhiều
// video/camera cùng cập nhật preview đồng thời.
defineProps({
  frame: { type: String, default: '' },
})
</script>

<style scoped>
.vc-preview { margin-top: 16px; border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--border-color); max-height: 420px; }
.vc-preview-img { width: 100%; display: block; object-fit: contain; max-height: 420px; }
</style>
