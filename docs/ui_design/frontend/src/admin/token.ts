/**
 * 后台令牌的存放。
 *
 * ### 为什么用 `sessionStorage` 而不是 `localStorage`
 *
 * 它是**整台机器的钥匙**：能发码、封码、踢设备、看所有用户。
 * 放在 `localStorage` 里意味着它会一直留在那台电脑上，
 * 而\"面板\"经常会开在别人也能碰到的机器上（网吧、公司电脑、朋友的电脑）。
 * `sessionStorage` 关掉标签页就没了 —— 每次重新输入一次密码，代价极小。
 *
 * ### 为什么它不是打包时注入的环境变量
 *
 * 任何 `VITE_*` 变量都会被**打进产物**。令牌一旦进产物，任何打开页面的人
 * 都能在 JS 里搜到它 —— 那不是\"密钥\"，那是公开信息。
 * 所以它只能**运行时由人输入**。
 *
 * ### 为什么单独一个模块（不在 store 里）
 *
 * 和 `api/session.ts` 同一个理由：`api` 层要读它，而要打断
 * `http → store → client → http` 这个循环。
 */

const KEY = 'plove.admin_token'

function read(): string | null {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    // 隐私模式会直接抛。令牌只活在内存里，仍然可用，只是刷新要重新输。
    return null
  }
}

let token: string | null = read()

export function getAdminToken(): string | null {
  return token
}

export function hasAdminToken(): boolean {
  return token !== null && token !== ''
}

export function setAdminToken(value: string): void {
  token = value
  try {
    sessionStorage.setItem(KEY, value)
  } catch {
    /* 见上 */
  }
}

/** 退出登录 / 令牌失效时调它。清干净再回登录页，别留下半截状态。 */
export function clearAdminToken(): void {
  token = null
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* 见上 */
  }
}
