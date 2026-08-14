<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>模型配置</h1>
        <p>管理问数引擎使用的大模型接入。</p>
      </div>
    </header>
    <div class="placeholder-card">页面加载中… 请稍后在管理功能中完善。</div>
  </section>
</template>

<style scoped>
.admin-page {
  padding: 1.25rem 1.5rem 2rem;
}

.page-head h1 {
  margin: 0;
  font-size: 1.35rem;
  color: var(--ink);
}

.page-head p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.placeholder-card {
  margin-top: 1.25rem;
  padding: 1.25rem;
  border: 1px dashed var(--line);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.7);
  color: var(--muted);
}
</style>
