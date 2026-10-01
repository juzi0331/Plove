import { createPinia } from 'pinia'
import Vant from 'vant'
import { createApp } from 'vue'

import 'vant/lib/index.css'
import '@/styles/app.css'

import App from '@/App.vue'
import router from '@/router'
import { useDeviceStore } from '@/stores/device'

const app = createApp(App)

app.use(createPinia())
app.use(router)
// 整包注册 Vant：骨架阶段先要\"能写\"，包体积留到后面按需引入（见 README 的待办）。
app.use(Vant)

app.mount('#app')

// 刷新页面之后 store 是新的，但令牌还在 localStorage 里。
// 心跳必须跟着恢复 —— 否则用户以为自己还在线，实际已经不在活跃位上了。
const device = useDeviceStore()
if (device.activated) device.startHeartbeat()
