<template>
  <main class="login-page">
    <div class="login-atmosphere" aria-hidden="true">
      <div class="orb orb-a" />
      <div class="orb orb-b" />
      <div class="grid-fade" />
    </div>

    <section class="login-stage">
      <div class="hero-brand">
        <img src="/logo.svg" alt="元景.智数" class="hero-logo" />
        <h1>元景.智数</h1>
        <p>电信域数据问答与经营洞察</p>
      </div>

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
  padding: 2rem 1.25rem;
  overflow: hidden;
  background: #061018;
}

.login-atmosphere {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(8px);
}

.orb-a {
  width: 52vw;
  height: 52vw;
  left: -12vw;
  top: -18vw;
  background: radial-gradient(circle, rgba(20, 184, 166, 0.38), transparent 68%);
  animation: drift 14s ease-in-out infinite alternate;
}

.orb-b {
  width: 42vw;
  height: 42vw;
  right: -10vw;
  bottom: -16vw;
  background: radial-gradient(circle, rgba(11, 31, 42, 0.95), rgba(15, 118, 110, 0.28) 45%, transparent 70%);
  animation: drift 18s ease-in-out infinite alternate-reverse;
}

.grid-fade {
  position: absolute;
  inset: 0;
  opacity: 0.28;
  background-image:
    linear-gradient(rgba(232, 245, 242, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(232, 245, 242, 0.05) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(circle at 50% 40%, #000 20%, transparent 72%);
}

.login-stage {
  position: relative;
  width: min(440px, 100%);
  padding: 2.4rem 2rem 1.7rem;
  border-radius: 22px;
  border: 1px solid rgba(232, 245, 242, 0.14);
  background: rgba(244, 250, 249, 0.92);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(14px);
  animation: rise 480ms ease-out;
}

.hero-brand {
  text-align: center;
  margin-bottom: 1.7rem;
}

.hero-logo {
  width: 72px;
  height: 72px;
  margin-bottom: 0.85rem;
  filter: drop-shadow(0 10px 24px rgba(15, 118, 110, 0.35));
}

.hero-brand h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 2.45rem);
  letter-spacing: 0.06em;
  color: var(--ink);
  font-weight: 700;
}

.hero-brand p {
  margin: 0.45rem 0 0;
  color: var(--muted);
  font-size: 0.95rem;
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
  padding: 0.75rem 0.9rem;
  border: 1px solid var(--line);
  border-radius: 12px;
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
  margin-top: 0.35rem;
  border: 0;
  border-radius: 12px;
  padding: 0.82rem 1rem;
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
  text-align: center;
  color: var(--muted);
  font-size: 0.82rem;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes drift {
  from {
    transform: translate3d(0, 0, 0) scale(1);
  }
  to {
    transform: translate3d(24px, -18px, 0) scale(1.06);
  }
}
</style>
