<script setup lang="ts">
/**
 * 根组件只做一件事：**处理\"被踢\"**。
 *
 * 为什么放在根上而不是播放页：被踢可能在**任何**接口上被发现
 * （心跳、首页、详情、播放都可能回 `SESSION_KICKED`），
 * 所以这是全局的横切关注点，不是某个页面的逻辑。
 *
 * 这里的按钮不是装饰，是设计的一部分：**不自动抢回**。
 * 自动抢 = 两台设备互相无限踢，用户只会看到画面疯狂中断。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useDeviceStore } from '@/stores/device'

const device = useDeviceStore()
const router = useRouter()
const route = useRoute()

/**
 * **后台不归用户端那套状态管。**
 *
 * 踩到过：这个根组件对**所有**路由生效，于是后台页面也会弹"已在别的设备上使用"——
 * 因为浏览器里那份设备令牌刚好被别人顶掉了。对运维来说这是个莫名其妙的弹窗，
 * 而且它带着用户语义的按钮（"在此设备继续"会去抢活跃位）。
 *
 * 后台用的是另一套凭证（`X-Admin-Token`），用户端的登录状态和它没有关系。
 */
const isAdminRoute = computed(() => route.path.startsWith('/admin'))

const show = computed({
  get: () => device.kicked && !isAdminRoute.value,
  set: (value: boolean) => {
    if (!value) device.dismissKicked()
  },
})

async function continueHere(): Promise<void> {
  const ok = await device.resume()
  if (!ok) {
    // 抢不回来通常意味着码过期或已被解绑，回激活页让用户重新输码
    device.forget()
    await router.push({ name: 'activate' })
  }
}

async function goActivate(): Promise<void> {
  device.forget()
  await router.push({ name: 'activate' })
}
</script>

<template>
  <router-view />

  <van-dialog
    v-model:show="show"
    title="已在别的设备上使用"
    confirm-button-text="在此设备继续"
    cancel-button-text="去激活页"
    show-cancel-button
    @confirm="continueHere"
    @cancel="goActivate"
  >
    <p style="padding: 16px; margin: 0; line-height: 1.6">
      这个激活码同一时间只能一台设备在线。你现在这台被另一台顶掉了。
      <br />
      <br />
      点「在此设备继续」会把在线的那台顶下来，那台会被提示。
    </p>
  </van-dialog>
</template>
