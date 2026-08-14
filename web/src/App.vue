<template>
  <div class="app-shell">
    <div class="atmosphere" aria-hidden="true" />
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { RouterView } from "vue-router";
</script>
