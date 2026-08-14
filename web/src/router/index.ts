import { createRouter, createWebHistory } from "vue-router";
import LoginView from "../views/LoginView.vue";
import ChatView from "../views/ChatView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/", name: "chat", component: ChatView },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach((to) => {
  const token = localStorage.getItem("ti_token");
  if (to.name !== "login" && !token) {
    return { name: "login" };
  }
  if (to.name === "login" && token) {
    return { name: "chat" };
  }
  return true;
});

export default router;
