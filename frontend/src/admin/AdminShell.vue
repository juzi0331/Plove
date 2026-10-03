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
import { cycleTheme, enterAdminUi, leaveAdminUi, setAutoRefresh, setAutoRefreshSeconds, setReadOnly, themeLabel, ui } from './ui'
import { ADMIN_BASE_PATH, adminPath } from './config'

const route = useRoute()
const router = useRouter()

onMounted(enterAdminUi)
onUnmounted(leaveAdminUi)

// ------------------------------------------------------------------ 侧栏折叠状态

const SIDEBAR_KEY = 'plove.admin.sidebar'

const collapsed = ref(false) // 默认展开

function toggleSidebar(): void {
  collapsed.value = !collapsed.value
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed.value ? '1' : '0')
  } catch {
    /* 忽略隐私模式异常 */
  }
}

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
      <!-- ---------------------------------------------------------- 现代侧边栏 -->
      <aside class="shell__side" :class="{ 'shell__side--collapsed': collapsed }">
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

<style scoped>
.shell {
  display: flex;
  height: 100vh;
  width: 100vw;
  background: var(--a-bg);
  overflow: hidden;
}

/* ---------------------------------------------------------- 侧边栏 */

.shell__side {
  flex: 0 0 auto;
  width: 248px;
  display: flex;
  flex-direction: column;
  background: #0f172a;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  transition: width 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
  z-index: 20;
}

.shell__side--collapsed {
  width: 68px;
}

.shell__side--collapsed :deep(.el-menu-item-group__title) {
  display: none !important;
}

.shell__side--collapsed .shell__side-footer {
  display: none !important;
}

html.dark .shell__side {
  background: #090d16;
  border-right-color: rgba(255, 255, 255, 0.06);
}

.shell__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 64px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.shell__side--collapsed .shell__brand {
  justify-content: center;
  padding: 0;
}

.shell__logo-box {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.4);
  flex-shrink: 0;
}

.shell__logo-icon {
  font-size: 18px;
  font-weight: 800;
  color: #ffffff;
  line-height: 1;
}

.shell__brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.shell__logo-title {
  font-size: 14.5px;
  font-weight: 750;
  color: #f8fafc;
  letter-spacing: -0.01em;
}

.shell__logo-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #94a3b8;
}

.online-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.shell__collapse-btn {
  margin-left: auto;
  color: #64748b !important;
  transition: color 0.2s ease;
}

.shell__collapse-btn:hover {
  color: #f8fafc !important;
}

.shell__side--collapsed .shell__collapse-btn {
  display: none;
}

.shell__menu-wrapper {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 0;
}

.shell__menu-wrapper::-webkit-scrollbar {
  width: 4px;
}
.shell__menu-wrapper::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.shell__group-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #475569;
  padding: 0 4px;
}

.shell__side :deep(.el-menu) {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #94a3b8;
  --el-menu-active-color: #ffffff;
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.05);
  --el-menu-item-height: 42px;
  --el-menu-base-level-padding: 16px;
  border-right: none;
  padding: 0 10px;
}

.shell__side :deep(.el-menu-item) {
  border-radius: 8px;
  margin-bottom: 4px;
  font-weight: 500;
  font-size: 13.5px;
  transition: all 0.2s ease;
}

.shell__side :deep(.el-menu-item:hover) {
  color: #f1f5f9;
}

.shell__side :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(79, 70, 229, 0.2) 0%, rgba(79, 70, 229, 0.06) 100%);
  color: #ffffff;
  font-weight: 600;
  border-left: 3px solid #6366f1;
}

.shell__side :deep(.el-menu-item-group__title) {
  padding: 18px 12px 6px;
}

.shell__side-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.footer-status-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
}

.status-card-label {
  color: #64748b;
}

.status-card-val {
  color: #cbd5e1;
  font-weight: 500;
}

.status-card-tag {
  color: #818cf8;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

/* ---------------------------------------------------------- 顶栏与主视窗 */

.shell__main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.shell__top {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 64px;
  padding: 0 32px;
  background: color-mix(in srgb, var(--a-card) 88%, transparent);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--a-border);
  flex-shrink: 0;
}

.shell__top-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  background: var(--a-success-bg);
  border: 1px solid var(--a-success-border);
}

.status-pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-success);
}

.status-pill-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--a-success-text);
}

.ctrl-capsule {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: var(--a-bg-subtle);
  border: 1px solid var(--a-border);
  border-radius: 20px;
  transition: all 0.2s ease;
}

.ctrl-capsule--warn {
  background: var(--a-warn-bg);
  border-color: var(--a-warn-border);
}

.ctrl-capsule-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--a-text-2);
}

.top-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--a-border);
  background: var(--a-card);
  color: var(--a-text-2);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.top-action-btn:hover {
  background: var(--a-bg-subtle);
  color: var(--a-text);
  border-color: var(--a-border-strong);
}

.top-action-btn.icon-only {
  padding: 0;
  width: 32px;
  justify-content: center;
}

.logout-btn:hover {
  background: var(--a-danger-bg);
  color: var(--el-color-danger);
  border-color: var(--a-danger-border);
}

.shell__content {
  flex: 1 1 auto;
  overflow-y: auto;
  background: var(--a-bg);
}

.popover-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px;
}

.popover-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.popover-row--col {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
</style>
