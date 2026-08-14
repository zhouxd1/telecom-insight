<template>
  <div class="app-root">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { RouterView } from "vue-router";
</script>

<style scoped>
.app-root {
  min-height: 100vh;
  background: var(--bg);
}
</style>
