import { createRouter, createWebHashHistory } from 'vue-router';
import userRoutes from './modules/user';

function buildRoutes() {
  const routes = [...userRoutes];
  routes.push({
    path: '/:pathMatch(.*)*',
    redirect: '/app/home'
  });
  return routes;
}

const router = createRouter({
  history: createWebHashHistory(),
  routes: buildRoutes()
});

export default router;
