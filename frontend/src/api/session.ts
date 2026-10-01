/**
 * 会话状态里**最底层**的那一层：设备令牌，以及\"被踢\"这个事件的通道。
 *
 * 为什么不放在 pinia store 里：
 * `http.ts` 需要读令牌，`device` store 也需要读写它 —— 如果令牌住在 store 里，
 * HTTP 层就要 import store，而 store 又要 import client（去调接口），
 * 立刻变成一个循环依赖。这里用一个很小的模块来打断它：
 *
 *     http.ts ──读──> session.ts <──读写── stores/device.ts
 *
 * 它只管两件事：**令牌存哪**（localStorage，刷新和关掉再开都还在）
 * 和**被踢之后通知谁**（HTTP 层看到 `SESSION_KICKED` 时回调）。
 */

const TOKEN_KEY = 'plove.device_token'

let token: string | null = null

try {
  token = localStorage.getItem(TOKEN_KEY)
} catch {
  // 隐私模式 / 存储被禁用时 localStorage 会直接抛。令牌就只活在内存里，
  // 用户可以继续用，只是刷新后要重新激活 —— 比整个应用打不开好得多。
  token = null
}

export function getDeviceToken(): string | null {
  return token
}

export function setDeviceToken(value: string | null): void {
  token = value
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* 见上：存不进就算了 */
  }
}

type KickedHandler = () => void

let kickedHandler: KickedHandler | null = null

/** 由 device store 在初始化时注册。HTTP 层只负责\"喊一声\"。 */
export function onSessionKicked(handler: KickedHandler): void {
  kickedHandler = handler
}

/**
 * 任何请求拿到 `SESSION_KICKED` 都会走到这里。
 *
 * 注意**不要在这里自动抢回**：那正是我们要避免的无限互踢。
 * 这里只负责把状态标出来，让界面弹一个\"在此设备继续\"的按钮，
 * 由用户自己决定。
 */
export function notifySessionKicked(): void {
  kickedHandler?.()
}
