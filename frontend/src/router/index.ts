import { createRouter, createWebHistory } from 'vue-router'

import { getDeviceToken } from '@/api/session'
import { hasAdminToken } from '@/admin/token'
import { ADMIN_BASE_PATH } from '@/admin/config'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/activate',
      name: 'activate',
      component: () => import('@/views/ActivationView.vue'),
      meta: { public: true },
    },
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    {
      path: '/category/:tid(.*)',
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
    // 安全隐蔽入口：杜绝死写 /admin 防止扫描爆破。通过 ADMIN_BASE_PATH 动态挂载。
    {
      path: `${ADMIN_BASE_PATH}/login`,
      name: 'admin-login',
      component: () => import('@/admin/views/LoginView.vue'),
      meta: { admin: true, public: true, title: '登录' },
    },
    {
      path: ADMIN_BASE_PATH,
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
          meta: { admin: true, title: '内容源' },
        },
        {
          path: 'webhooks',
          name: 'admin-webhooks',
          component: () => import('@/admin/views/WebhooksView.vue'),
          meta: { admin: true, title: 'Telegram 机器人' },
        },

        {
          path: 'cache',
          name: 'admin-cache',
          component: () => import('@/admin/views/CacheCenterView.vue'),
          meta: { admin: true, title: '缓存中心' },
        },
        {
          path: 'proxy',
          name: 'admin-proxy',
          component: () => import('@/admin/views/ImageProxyView.vue'),
          meta: { admin: true, title: '图片代理' },
        },
        {
          path: 'proxy-nodes',
          name: 'admin-proxy-nodes',
          component: () => import('@/admin/views/ProxyNodesView.vue'),
          meta: { admin: true, title: '代理节点池' },
        },
        {
          path: 'system',
          name: 'admin-system',
          component: () => import('@/admin/views/SystemNoticeView.vue'),
          meta: { admin: true, title: '公告与维护' },
        },
        {
          path: 'experience',
          name: 'admin-experience',
          component: () => import('@/admin/views/ExperienceCenterView.vue'),
          meta: { admin: true, title: '体验发布中心' },
        },
        {
          path: 'codes/:codeId/devices',
          name: 'admin-devices',
          component: () => import('@/admin/views/DevicesView.vue'),
          props: true,
          meta: { admin: true, title: '设备', crumb: [{ label: '激活码', to: `${ADMIN_BASE_PATH}/codes` }] },
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

router.beforeEach((to) => {
  // 安全蜜罐：如果外部直接探测常见的 /admin 且自定义了安全路径，直接静默回落到首页
  if (ADMIN_BASE_PATH !== '/admin' && to.path.startsWith('/admin')) {
    return { name: 'home' }
  }

  // 后台安全入口认证
  if (to.path.startsWith(ADMIN_BASE_PATH)) {
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