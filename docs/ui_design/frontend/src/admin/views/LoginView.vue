<script setup lang="ts">
/**
 * 后台登录：输入 `X-Admin-Token`。
 *
 * 它**验证的方式就是真发一个请求** —— 不自己比对任何东西。
 * 令牌对不对只有服务器知道，前端猜不得。
 *
 * 视觉：与主壳共用同一套 token（theme.css），卡片居中、品牌点用用户端那个红 ——
 * 它是后台唯一"看起来像 Plove"的地方。
 */
import { ElButton, ElInput } from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './../theme.css'
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { describeError } from '@/api/http'

import * as api from '../api'
import { setAdminToken } from '../token'
import { enterAdminUi, leaveAdminUi } from '../ui'

const router = useRouter()
const value = ref('')
const busy = ref(false)
const error = ref<string | null>(null)

onMounted(() => {
  enterAdminUi()
  document.title = 'Plove 后台 · 登录'
})
onUnmounted(leaveAdminUi)

async function submit(): Promise<void> {
  const token = value.value.trim()
  if (!token || busy.value) return

  busy.value = true
  error.value = null
  // 先临时存上，让下面的请求能带上它
  setAdminToken(token)
  try {
    await api.status()
    await router.push({ name: 'admin' })
  } catch (err) {
    setAdminToken('')
    error.value = describeError(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="admin-root login">
    <div class="login__card">
      <div class="login__brand">
        <span class="login__dot" />
        <span class="login__logo">Plove</span>
        <span class="login__badge">后台</span>
      </div>

      <p class="login__hint">
        输入后台令牌（<span class="a-mono">PLOVE_ADMIN_TOKEN</span>）。它与激活码是两套凭证，互不相干。
      </p>

      <ElInput
        v-model="value"
        type="password"
        show-password
        size="large"
        placeholder="后台令牌"
        @keyup.enter="submit"
      />

      <ElButton type="primary" size="large" :loading="busy" class="login__submit" @click="submit">
        进入
      </ElButton>

      <div v-if="error" class="login__error">{{ error }}</div>

      <p class="login__note">
        令牌只存在这个标签页里（<span class="a-mono">sessionStorage</span>），关掉就没了 ——
        它不该在别人也能碰的电脑上留着。
      </p>
    </div>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(1100px 420px at 50% -80px, color-mix(in srgb, var(--a-brand) 9%, transparent), transparent),
    var(--a-bg);
}

.login__card {
  width: 100%;
  max-width: 400px;
  padding: 30px 28px 24px;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: 14px;
  box-shadow: var(--a-shadow-2);
}

.login__brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.login__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--a-brand);
}

.login__logo {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.4px;
}

.login__badge {
  padding: 1px 7px;
  border: 1px solid var(--a-border-strong);
  border-radius: 999px;
  color: var(--a-text-3);
  font-size: 11px;
}

.login__hint {
  margin: 14px 0 16px;
  color: var(--a-text-2);
  font-size: 12.5px;
  line-height: 1.8;
}

.login__submit {
  width: 100%;
  margin-top: 16px;
}

.login__error {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid var(--a-danger-border);
  border-radius: 8px;
  background: var(--a-danger-bg);
  color: var(--el-color-danger);
  font-size: 12.5px;
}

.login__note {
  margin: 16px 0 0;
  color: var(--a-text-3);
  font-size: 12px;
  line-height: 1.8;
}
</style>
