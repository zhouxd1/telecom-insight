<template>
  <main class="login-page">
    <section class="login-panel">
      <header class="brand">
        <img src="/logo.svg" alt="元景.智数" class="logo" />
        <div>
          <h1>元景.智数</h1>
          <p>电信域数据问答与洞察</p>
        </div>
      </header>

      <form class="login-form" @submit.prevent="onSubmit">
        <label>
          <span>账号</span>
          <input v-model="username" type="text" autocomplete="username" placeholder="demo" />
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="demo123"
          />
        </label>

        <p v-if="error" class="error" role="alert">{{ error }}</p>

        <button type="submit" :disabled="loading">
          {{ loading ? "登录中…" : "进入工作台" }}
        </button>
      </form>

      <p class="hint">演示账号：demo / demo123</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { friendlyError, login } from "../api";

const router = useRouter();
const username = ref("demo");
const password = ref("demo123");
const loading = ref(false);
const error = ref("");

async function onSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await login(username.value.trim(), password.value);
    await router.replace({ name: "chat" });
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem;
}

.login-panel {
  width: min(420px, 100%);
  padding: 2rem 2rem 1.5rem;
  border: 1px solid var(--line);
  border-radius: calc(var(--radius) + 4px);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--shadow);
  backdrop-filter: blur(10px);
  animation: rise 420ms ease-out;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  margin-bottom: 1.6rem;
}

.logo {
  width: 52px;
  height: 52px;
}

.brand h1 {
  margin: 0;
  font-size: 1.55rem;
  letter-spacing: 0.02em;
  color: var(--ink);
}

.brand p {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.92rem;
}

.login-form {
  display: grid;
  gap: 0.9rem;
}

label {
  display: grid;
  gap: 0.35rem;
}

label span {
  font-size: 0.85rem;
  color: var(--muted);
}

input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  color: var(--text);
  outline: none;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

input:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px var(--teal-mist);
}

button[type="submit"] {
  margin-top: 0.3rem;
  border: 0;
  border-radius: 10px;
  padding: 0.78rem 1rem;
  background: linear-gradient(135deg, var(--ink) 0%, var(--teal) 100%);
  color: #f4fffc;
  font-weight: 600;
  transition: transform 140ms ease, opacity 140ms ease;
}

button[type="submit"]:hover:not(:disabled) {
  transform: translateY(-1px);
}

button[type="submit"]:disabled {
  opacity: 0.7;
  cursor: wait;
}

.error {
  margin: 0;
  color: var(--danger);
  font-size: 0.9rem;
}

.hint {
  margin: 1rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
