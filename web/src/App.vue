<template>
  <div class="app-root">
    <div v-if="showAtmosphere" class="atmosphere" aria-hidden="true" />
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

const route = useRoute();
const showAtmosphere = computed(() => route.name !== "login");
</script>

<style scoped>
.app-root {
  position: relative;
  min-height: 100vh;
}
</style>
