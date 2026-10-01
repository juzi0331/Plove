<script setup lang="ts">
/**
 * 后台外壳：深色侧栏（分组菜单、可折叠）+ 顶栏（面包屑 + 全局开关）。
 *
 * 三件全局的东西放在这里，因为**它们不属于任何一个页面**：
 *
 * 1. **主题**（浅色 / 深色 / 跟随系统）—— Element 的暗色变量挂在 `html.dark`，
 *    由 `ui.ts` 在进入后台时挂上、离开时摘掉（计数式，登录页切主壳不会闪）；
 * 2. **只读模式** —— 一键禁用所有写操作（防手滑）。`api.ts` 里也有一道兜底；
 * 3. **自动刷新** —— 间隔在这里配，总览页照它执行。
 *
 * 面包屑与浏览器标题都来自路由 `meta` —— 新增页面时**只改路由表**，
 * 不用回来改这个文件。
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
import { Expand, Fold, Link, Monitor, Moon, Odometer, Setting, Sunny, Tickets } from '@element-plus/icons-vue'
// Element 默认是英文（分页会显示 "Total 6" / "20/page"），这里统一成中文
import zhCn from 'element-plus/es/locale/lang/zh-cn'
// 样式只在这里与登录页引入 —— 会进**后台自己的 chunk**，用户端首屏不会变重
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './theme.css'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { clearAdminToken } from './token'
import { cycleTheme, enterAdminUi, leaveAdminUi, setAutoRefresh, setAutoRefreshSeconds, setReadOnly, themeLabel, ui } from './ui'

const route = useRoute()
const router = useRouter()

onMounted(enterAdminUi)
onUnmounted(leaveAdminUi)

// ------------------------------------------------------------------ 侧栏

const SIDEBAR_KEY = 'plove.admin.sidebar'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === '1'
  } catch {
    return false
  }
}

const collapsed = ref(readCollapsed())

function toggleSidebar(): void {
  collapsed.value = !collapsed.value
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed.value ? '1' : '0')
  } catch {
    /* 隐私模式：这次会话仍然可用，只是不记忆 */
  }
}

// 子路由（码的设备页）也应该让它的父项亮着：**前缀最长者优先**，
// 这样新增页面时不用回来改这里的 if
const MENU_PREFIXES = ['/admin/codes', '/admin/sites'] as const

const activeMenu = computed(
  () => MENU_PREFIXES.find((prefix) => route.path.startsWith(prefix)) ?? '/admin',
)

// ------------------------------------------------------------------ 面包屑 / 标题

interface Crumb {
  label: string
  to?: string
}

const crumbs = computed<Crumb[]>(() => {
  const list: Crumb[] = [{ label: '后台', to: '/admin' }]
  for (const record of route.matched) {
    const custom = record.meta.crumb as Crumb[] | undefined
    // 自定义 crumb 是"父级路径"，自己的标题仍然要接在后面（设备页就是这种）
    if (custom) list.push(...custom.map((item) => ({ ...item })))
    if (typeof record.meta.title === 'string' && record.meta.title !== '后台') {
      list.push({ label: record.meta.title })
    }
  }
  // 最后一项是当前页：它是"你在哪"，不是一个可点的链接
  const last = list[list.length - 1]
  if (last) delete last.to
  return list
})

watch(
  () => route.path,
  () => {
    const current = [...crumbs.value].reverse().find((item) => !item.to)
    document.title = current ? `Plove 后台 · ${current.label}` : 'Plove 后台'
  },
  { immediate: true },
)

// ------------------------------------------------------------------ 顶栏动作

const themeIcon = computed(() => (ui.theme === 'dark' ? Moon : ui.theme === 'light' ? Sunny : Monitor))

function logout(): void {
  clearAdminToken()
  void router.push({ name: 'admin-login' })
}
</script>

<template>
  <ElConfigProvider :locale="zhCn">
    <div class="admin-root shell">
    <!-- ---------------------------------------------------------- 侧栏 -->
    <aside class="shell__side" :class="{ 'shell__side--collapsed': collapsed }">
      <div class="shell__brand">
        <span class="shell__dot" />
        <span v-show="!collapsed" class="shell__logo">Plove</span>
        <span v-show="!collapsed" class="shell__badge">后台</span>
        <ElTooltip :content="collapsed ? '展开侧栏' : '收起侧栏'" placement="right">
          <ElButton class="shell__collapse" text size="small" @click="toggleSidebar">
            <ElIcon><component :is="collapsed ? Expand : Fold" /></ElIcon>
          </ElButton>
        </ElTooltip>
      </div>

      <ElMenu :default-active="activeMenu" :collapse="collapsed" :collapse-transition="false" router>
        <ElMenuItemGroup>
          <template #title><span class="shell__group">概览</span></template>
          <ElMenuItem index="/admin">
            <ElIcon><Odometer /></ElIcon>
            <template #title>总览</template>
          </ElMenuItem>
        </ElMenuItemGroup>

        <ElMenuItemGroup>
          <template #title><span class="shell__group">运营</span></template>
          <ElMenuItem index="/admin/codes">
            <ElIcon><Tickets /></ElIcon>
            <template #title>激活码</template>
          </ElMenuItem>
        </ElMenuItemGroup>

        <ElMenuItemGroup>
          <template #title><span class="shell__group">内容源</span></template>
          <ElMenuItem index="/admin/sites">
            <ElIcon><Link /></ElIcon>
            <template #title>站点管理</template>
          </ElMenuItem>
        </ElMenuItemGroup>
      </ElMenu>
    </aside>

    <!-- ---------------------------------------------------------- 主区 -->
    <div class="shell__main">
      <header class="shell__top">
        <ElBreadcrumb separator="/">
          <ElBreadcrumbItem v-for="(crumb, index) in crumbs" :key="index" :to="crumb.to">
            {{ crumb.label }}
          </ElBreadcrumbItem>
        </ElBreadcrumb>

        <div class="shell__controls">
          <!-- 只读模式：防手滑。写按钮会全部禁用，api 层也兜底 -->
          <ElTooltip content="只读模式：禁用所有写操作（发码 / 停用 / 踢设备）" placement="bottom">
            <label class="shell__ctrl">
              <span class="shell__ctrl-label">只读</span>
              <ElSwitch
                :model-value="ui.readOnly"
                size="small"
                @update:model-value="(value) => setReadOnly(Boolean(value))"
              />
            </label>
          </ElTooltip>

          <!-- 自动刷新：总览页照这个跑 -->
          <ElPopover :width="220" trigger="click" placement="bottom-end">
            <template #reference>
              <ElButton text size="small" class="shell__ctrl-button">
                <ElIcon><Setting /></ElIcon>
                <span class="shell__ctrl-label">
                  {{ ui.autoRefreshEnabled ? `自动刷新 ${ui.autoRefreshSeconds}s` : '自动刷新已暂停' }}
                </span>
              </ElButton>
            </template>
            <div class="popover">
              <label class="popover__row">
                <span>开启自动刷新</span>
                <ElSwitch
                  :model-value="ui.autoRefreshEnabled"
                  size="small"
                  @update:model-value="(value) => setAutoRefresh(Boolean(value))"
                />
              </label>
              <div class="popover__row popover__row--col">
                <span class="a-muted">间隔</span>
                <ElRadioGroup
                  :model-value="String(ui.autoRefreshSeconds)"
                  size="small"
                  @update:model-value="(value) => setAutoRefreshSeconds(Number(value))"
                >
                  <ElRadioButton value="3">3s</ElRadioButton>
                  <ElRadioButton value="5">5s</ElRadioButton>
                  <ElRadioButton value="10">10s</ElRadioButton>
                  <ElRadioButton value="30">30s</ElRadioButton>
                </ElRadioGroup>
              </div>
            </div>
          </ElPopover>

          <ElTooltip :content="`主题：${themeLabel()}（点击切换）`" placement="bottom">
            <ElButton text size="small" class="shell__ctrl-button" @click="cycleTheme">
              <ElIcon><component :is="themeIcon" /></ElIcon>
            </ElButton>
          </ElTooltip>

          <ElButton text size="small" @click="logout">退出</ElButton>
        </div>
      </header>

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
  background: var(--a-bg);
}

/* ---------------------------------------------------------- 侧栏 */

.shell__side {
  flex: 0 0 auto;
  width: 214px;
  display: flex;
  flex-direction: column;
  background: #1c212c;
  transition: width 0.18s ease;
  overflow: hidden;
}

.shell__side--collapsed {
  width: 64px;
}

html.dark .shell__side {
  background: #16181d;
}

.shell__brand {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 56px;
  padding: 0 12px 0 16px;
  color: #fff;
}

.shell__side--collapsed .shell__brand {
  justify-content: center;
  padding: 0 8px;
}

.shell__dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--a-brand);
  flex: 0 0 auto;
}

.shell__logo {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.4px;
}

.shell__badge {
  padding: 1px 6px;
  border: 1px solid rgb(255 255 255 / 25%);
  border-radius: 999px;
  color: rgb(255 255 255 / 65%);
  font-size: 11px;
}

.shell__collapse {
  margin-left: auto;
  color: rgb(255 255 255 / 55%) !important;
}

.shell__side--collapsed .shell__collapse {
  margin-left: 0;
}

.shell__group {
  font-size: 11px;
  letter-spacing: 1px;
  color: rgb(255 255 255 / 35%);
}

.shell__side :deep(.el-menu) {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #aab2c0;
  --el-menu-active-color: #fff;
  --el-menu-hover-bg-color: rgb(255 255 255 / 6%);
  --el-menu-item-height: 40px;
  --el-menu-base-level-padding: 16px;
  border-right: none;
  padding: 4px 8px;
}

.shell__side :deep(.el-menu-item) {
  border-radius: 8px;
  margin-bottom: 2px;
}

.shell__side :deep(.el-menu-item.is-active) {
  background: rgb(255 255 255 / 10%);
  position: relative;
}

.shell__side :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 2px;
  background: var(--a-brand);
}

.shell__side :deep(.el-menu-item-group__title) {
  padding: 14px 12px 4px;
}

/* ---------------------------------------------------------- 主区 */

.shell__main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
}

.shell__top {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 56px;
  padding: 0 22px;
  background: color-mix(in srgb, var(--a-card) 86%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--a-border);
}

.shell__controls {
  display: flex;
  align-items: center;
  gap: 14px;
}

.shell__ctrl {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.shell__ctrl-label {
  color: var(--a-text-2);
  font-size: 12.5px;
}

.shell__ctrl-button {
  gap: 6px;
}

.shell__content {
  flex: 1 1 auto;
}

.popover {
  display: grid;
  gap: 12px;
}

.popover__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.popover__row--col {
  flex-direction: column;
  align-items: flex-start;
}
</style>
