<script setup lang="ts">
/**
 * Plove Cloud Console - 全新现代管理后台外壳
 *
 * 现代化云原生设计：
 * 1. 左侧一体化高质感侧边栏：品牌徽标、四大业务维度分组导航、底部系统状态微卡；
 * 2. 顶部透明毛玻璃状态栏：层级面包屑、只读保护开关、巡检刷新器、暗黑模式切换器与安全退出；
 * 3. 严格禁止任何 emoji，采用正规书面中文与矢量图标。
 */
import {
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElButton,
  ElConfigProvider,
  ElIcon,
  ElMenu,
  ElMenuItem,
  ElMenuItemGroup,
  ElPopover,
  ElRadioButton,
  ElRadioGroup,
  ElSwitch,
  ElTooltip,
} from 'element-plus'
import {
  Aim,
  Bell,
  Connection,
  Expand,
  Fold,
  Grid,
  Lightning,
  Monitor,
  Moon,
  Odometer,
  Picture,
  RefreshRight,
  Sunny,
  SwitchButton,
  Tickets,
} from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './theme.css'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { clearAdminToken } from './token'
import { ADMIN_BASE_PATH, adminPath } from './config'
import { cycleTheme, enterAdminUi, leaveAdminUi, setAutoRefresh, setAutoRefreshSeconds, setReadOnly, themeLabel, ui } from './ui'

const route = useRoute()
const router = useRouter()

// ------------------------------------------------------------------ 移动端与侧栏折叠状态
const isMobile = ref(false)
const mobileOpen = ref(false)
const collapsed = ref(false)

const SIDEBAR_KEY = 'plove.admin.sidebar'

function updateMobileState(): void {
  isMobile.value = typeof window !== 'undefined' && window.innerWidth <= 768
}

function toggleSidebar(): void {
  if (isMobile.value) {
    mobileOpen.value = !mobileOpen.value
  } else {
    collapsed.value = !collapsed.value
    try {
      localStorage.setItem(SIDEBAR_KEY, collapsed.value ? '1' : '0')
    } catch {
      /* 忽略隐私模式异常 */
    }
  }
}

onMounted(() => {
  enterAdminUi()
  updateMobileState()
  window.addEventListener('resize', updateMobileState, { passive: true })
})

onUnmounted(() => {
  leaveAdminUi()
  window.removeEventListener('resize', updateMobileState)
})

watch(() => route.path, () => {
  if (isMobile.value) {
    mobileOpen.value = false
  }
})

const MENU_PREFIXES = computed(() => [
  adminPath('/playground'),
  adminPath('/cache'),
  adminPath('/proxy'),
  adminPath('/system'),
  adminPath('/codes'),
  adminPath('/sites'),
])

const activeMenu = computed(
  () => MENU_PREFIXES.value.find((prefix) => route.path.startsWith(prefix)) ?? ADMIN_BASE_PATH,
)

// ------------------------------------------------------------------ 面包屑导航

interface Crumb {
  label: string
  to?: string
}

const crumbs = computed<Crumb[]>(() => {
  const list: Crumb[] = [{ label: '控制台', to: ADMIN_BASE_PATH }]
  for (const record of route.matched) {
    const custom = record.meta.crumb as Crumb[] | undefined
    if (custom) list.push(...custom.map((item) => ({ ...item })))
    if (typeof record.meta.title === 'string' && record.meta.title !== '后台' && record.meta.title !== '控制台') {
      list.push({ label: record.meta.title })
    }
  }
  const last = list[list.length - 1]
  if (last) delete last.to
  return list
})

watch(
  () => route.path,
  () => {
    const current = [...crumbs.value].reverse().find((item) => !item.to)
    document.title = current ? `Plove 控制台 · ${current.label}` : 'Plove 控制台'
  },
  { immediate: true },
)

// ------------------------------------------------------------------ 顶栏操作

const themeIcon = computed(() => (ui.theme === 'dark' ? Moon : ui.theme === 'light' ? Sunny : Monitor))

function logout(): void {
  clearAdminToken()
  void router.push({ name: 'admin-login' })
}
</script>

<template>
  <ElConfigProvider :locale="zhCn">
    <div class="admin-root shell">
      <!-- 移动端抽屉遮罩 -->
      <div v-if="isMobile && mobileOpen" class="mobile-sidebar-backdrop" @click="mobileOpen = false" />

      <!-- ---------------------------------------------------------- 现代侧边栏 -->
      <aside
        class="shell__side"
        :class="{
          'shell__side--collapsed': collapsed,
          'shell__side--mobile-hidden': isMobile && !mobileOpen,
        }"
      >
        <!-- 品牌标识区域 -->
        <div class="shell__brand">
          <div class="shell__logo-box">
            <span class="shell__logo-icon">P</span>
          </div>
          <div v-show="!collapsed" class="shell__brand-text">
            <div class="shell__logo-title">Plove Console</div>
            <div class="shell__logo-sub">
              <span class="online-indicator" />
              <span>控制中心</span>
            </div>
          </div>
          <ElTooltip :content="collapsed ? '展开侧栏' : '收起侧栏'" placement="right">
            <ElButton class="shell__collapse-btn" text size="small" @click="toggleSidebar">
              <ElIcon :size="15"><component :is="collapsed ? Expand : Fold" /></ElIcon>
            </ElButton>
          </ElTooltip>
        </div>

        <!-- 结构化业务菜单 -->
        <div class="shell__menu-wrapper">
          <ElMenu :default-active="activeMenu" :collapse="collapsed" :collapse-transition="false" router>
            <ElMenuItemGroup>
              <template #title><span class="shell__group-title">监控大屏</span></template>
              <ElMenuItem :index="adminPath('')">
                <ElIcon><Odometer /></ElIcon>
                <template #title>总览看板</template>
              </ElMenuItem>
            </ElMenuItemGroup>

            <ElMenuItemGroup>
              <template #title><span class="shell__group-title">内容与采集</span></template>
              <ElMenuItem :index="adminPath('/sites')">
                <ElIcon><Grid /></ElIcon>
                <template #title>内容源管理</template>
              </ElMenuItem>
              <ElMenuItem :index="adminPath('/proxy-nodes')">
                <ElIcon><Connection /></ElIcon>
                <template #title>代理节点池</template>
              </ElMenuItem>
              <ElMenuItem :index="adminPath('/playground')">
                <ElIcon><Aim /></ElIcon>
                <template #title>探针与试播台</template>
              </ElMenuItem>
            </ElMenuItemGroup>

            <ElMenuItemGroup>
              <template #title><span class="shell__group-title">缓存与加速</span></template>
              <ElMenuItem :index="adminPath('/cache')">
                <ElIcon><Lightning /></ElIcon>
                <template #title>全局缓存中心</template>
              </ElMenuItem>
              <ElMenuItem :index="adminPath('/proxy')">
                <ElIcon><Picture /></ElIcon>
                <template #title>图片防盗链代理</template>
              </ElMenuItem>
            </ElMenuItemGroup>

            <ElMenuItemGroup>
              <template #title><span class="shell__group-title">运营与授权</span></template>
              <ElMenuItem :index="adminPath('/system')">
                <ElIcon><Bell /></ElIcon>
                <template #title>公告与维护广播</template>
              </ElMenuItem>
              <ElMenuItem :index="adminPath('/codes')">
                <ElIcon><Tickets /></ElIcon>
                <template #title>激活码管理</template>
              </ElMenuItem>
            </ElMenuItemGroup>
          </ElMenu>
        </div>

        <!-- 侧栏底部状态微卡 -->
        <div v-show="!collapsed" class="shell__side-footer">
          <div class="footer-status-card">
            <div class="status-card-row">
              <span class="status-card-label">运行架构</span>
              <span class="status-card-val">分布式多源</span>
            </div>
            <div class="status-card-row">
              <span class="status-card-label">安全防护</span>
              <span class="status-card-tag">SingleFlight</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- ---------------------------------------------------------- 主体视窗 -->
      <div class="shell__main">
        <!-- 现代化毛玻璃顶栏 -->
        <header class="shell__top">
          <div class="shell__top-left">
            <button
              v-if="isMobile"
              class="mobile-menu-toggle"
              type="button"
              aria-label="切换侧栏"
              @click="toggleSidebar"
            >
              <ElIcon :size="18"><component :is="mobileOpen ? Fold : Expand" /></ElIcon>
            </button>
            <ElBreadcrumb separator="/">
              <ElBreadcrumbItem v-for="(crumb, index) in crumbs" :key="index" :to="crumb.to">
                {{ crumb.label }}
              </ElBreadcrumbItem>
            </ElBreadcrumb>
          </div>

          <div class="shell__top-actions">
            <!-- 运行状态指示微胶囊 -->
            <div class="status-pill">
              <span class="status-pill-dot" />
              <span class="status-pill-text">节点连接正常</span>
            </div>

            <!-- 只读防护开关 -->
            <ElTooltip content="开启后将禁用全站所有写操作（防止误触或误删）" placement="bottom">
              <div class="ctrl-capsule" :class="{ 'ctrl-capsule--warn': ui.readOnly }">
                <span class="ctrl-capsule-label">{{ ui.readOnly ? '只读保护生效' : '可写模式' }}</span>
                <ElSwitch
                  :model-value="ui.readOnly"
                  size="small"
                  @update:model-value="(value) => setReadOnly(Boolean(value))"
                />
              </div>
            </ElTooltip>

            <!-- 自动巡检刷新频率设置 -->
            <ElPopover :width="230" trigger="click" placement="bottom-end">
              <template #reference>
                <button class="top-action-btn" type="button">
                  <ElIcon :size="14"><RefreshRight /></ElIcon>
                  <span>{{ ui.autoRefreshEnabled ? `${ui.autoRefreshSeconds}s 巡检` : '自动刷新暂停' }}</span>
                </button>
              </template>
              <div class="popover-content">
                <div class="popover-row">
                  <span>后台自动刷新</span>
                  <ElSwitch
                    :model-value="ui.autoRefreshEnabled"
                    size="small"
                    @update:model-value="(value) => setAutoRefresh(Boolean(value))"
                  />
                </div>
                <div class="popover-row popover-row--col">
                  <span class="a-muted" style="font-size: 12px">刷新间隔</span>
                  <ElRadioGroup
                    :model-value="String(ui.autoRefreshSeconds)"
                    size="small"
                    @update:model-value="(value) => setAutoRefreshSeconds(Number(value))"
                  >
                    <ElRadioButton value="3">3秒</ElRadioButton>
                    <ElRadioButton value="5">5秒</ElRadioButton>
                    <ElRadioButton value="10">10秒</ElRadioButton>
                    <ElRadioButton value="30">30秒</ElRadioButton>
                  </ElRadioGroup>
                </div>
              </div>
            </ElPopover>

            <!-- 主题切换 -->
            <ElTooltip :content="`当前主题：${themeLabel()}（点击切换）`" placement="bottom">
              <button class="top-action-btn icon-only" type="button" @click="cycleTheme">
                <ElIcon :size="15"><component :is="themeIcon" /></ElIcon>
              </button>
            </ElTooltip>

            <!-- 退出登录 -->
            <ElTooltip content="退出管理员会话" placement="bottom">
              <button class="top-action-btn logout-btn" type="button" @click="logout">
                <ElIcon :size="15"><SwitchButton /></ElIcon>
                <span>退出</span>
              </button>
            </ElTooltip>
          </div>
        </header>

        <!-- 页面视图渲染区域 -->
        <main class="shell__content">
          <router-view />
        </main>
      </div>
    </div>
  </ElConfigProvider>
</template>

<style src="./admin-shell.css"></style>

