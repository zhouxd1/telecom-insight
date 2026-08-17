import { createRouter, createWebHistory } from "vue-router";
import { getToken } from "../api";
import AppShell from "../layouts/AppShell.vue";
import LoginView from "../views/LoginView.vue";
import ChatView from "../views/ChatView.vue";
import DatasourcesView from "../views/admin/DatasourcesView.vue";
import WorkspacesView from "../views/admin/WorkspacesView.vue";
import UsersView from "../views/admin/UsersView.vue";
import ModelsView from "../views/admin/ModelsView.vue";
import TermsView from "../views/admin/TermsView.vue";
import ExamplesView from "../views/admin/ExamplesView.vue";
import BrandingView from "../views/admin/BrandingView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    {
      path: "/app",
      component: AppShell,
      children: [
        { path: "", redirect: { name: "chat" } },
        { path: "chat", name: "chat", component: ChatView },
        { path: "datasources", name: "datasources", component: DatasourcesView },
        { path: "workspaces", name: "workspaces", component: WorkspacesView },
        { path: "users", name: "users", component: UsersView },
        { path: "models", name: "models", component: ModelsView },
        { path: "terms", name: "terms", component: TermsView },
        { path: "examples", name: "examples", component: ExamplesView },
        { path: "branding", name: "branding", component: BrandingView },
      ],
    },
    {
      path: "/",
      redirect: () => (getToken() ? { name: "chat" } : { name: "login" }),
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach((to) => {
  const token = getToken();
  if (!to.meta.public && !token) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && token) {
    return { name: "chat" };
  }
  return true;
});

export default router;
