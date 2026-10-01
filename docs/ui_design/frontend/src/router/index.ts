import { createRouter, createWebHistory } from 'vue-router'

import { getDeviceToken } from '@/api/session'
import { hasAdminToken } from '@/admin/token'

/**
 * 路由表刻意很浅：**没有\"我的\"、\"设置\"这类页面**。
 * 用户端只有五件事：激活 → 选源 → 首页 → 分类/详情 → 播放。
 *
 * 用 `createWebHistory`（真实路径）而不是 hash：
 * 日后封 ipa 时 WKWebView 里 hash 路由的返回手势会很难受，
 * 而 `history` 模式需要 nginx 把未知路径回落到 `index.html`（部署时记得配）。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [    {
      path: '/activate',
      name: 'activate',
      component: () => import('@/views/ActivationView.vue'),
      meta: { public: true },
    },
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/sites', name: 'sites', component: () => import('@/views/SitesView.vue') },
    {
      path: '/category/:tid',
      name: 'category',
      component: () => import('@/views/CategoryView.vue'),
      props: true,
    },
    {
      path: '/detail/:vodId',
      name: 'detail',
      component: () => import('@/views/DetailView.vue'),
      props: true,
    },
    {
      path: '/play/:vodId/:ep',
      name: 'play',
      component: () => import('@/views/PlayerView.vue'),
      props: true,
    },
    // ---------------------------------------------------------- 后台（阶段 7）
    // 它和用户端共用一套 `http.ts` 与生成的契约类型，但**凭证完全不同**：
    // 后台用 X-Admin-Token，不需要"先给自己发个激活码"。
    // 路由整体懒加载 —— Element Plus 与这几个页面都不会进用户端的首屏包。
    {
      path: '/admin/login',
      name: 'admin-login',
      component: () => import('@/admin/views/LoginView.vue'),
      meta: { admin: true, public: true, title: '登录' },
    },
    {
      path: '/admin',
      component: () => import('@/admin/AdminShell.vue'),
      children: [
        {
          path: '',
          name: 'admin',
          component: () => import('@/admin/views/DashboardView.vue'),
          meta: { admin: true, title: '总览' },
        },
        {
          path: 'codes',
          name: 'admin-codes',
          component: () => import('@/admin/views/CodesView.vue'),
          meta: { admin: true, title: '激活码' },
        },
        {
          path: 'sites',
          name: 'admin-sites',
          component: () => import('@/admin/views/SitesView.vue'),
          meta: { admin: true, title: '站点管理' },
        },
        {
          path: 'codes/:codeId/devices',
          name: 'admin-devices',
          component: () => import('@/admin/views/DevicesView.vue'),
          props: true,
          meta: { admin: true, title: '设备', crumb: [{ label: '激活码', to: '/admin/codes' }] },
        },
      ],
    },

    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  },
})

/**
 * 守卫读的是 `session.ts` 里的令牌，**不是 store**。
 * 原因见 session.ts 顶部的说明：守卫可能在 pinia 装好之前就被调用，
 * 直接读一个不依赖框架的模块最稳。
 */
router.beforeEach((to) => {
  // 后台是**另一套凭证**，不能拿用户端那条"必须先激活"的规则去拦它 ——
  // 否则运维会被赶去激活页，而运维根本不需要激活码。
  if (to.path.startsWith('/admin')) {
    if (to.meta.public) return true
    if (!hasAdminToken()) return { name: 'admin-login' }
    return true
  }

  const activated = getDeviceToken() !== null
  if (!activated && to.name !== 'activate') return { name: 'activate' }
  if (activated && to.name === 'activate') return { name: 'home' }
  return true
})

export default router
