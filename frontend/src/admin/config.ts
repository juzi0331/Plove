/**
 * 管理后台安全路径与隐蔽配置。
 *
 * 安全防御机制：
 * 1. 杜绝硬编码 /admin：/admin 是全网扫描器与爆破脚本的头号探测目标。
 * 2. 支持通过 VITE_ADMIN_PATH 自定义隐秘入口（默认为 /_manage）。
 * 3. 访问旧的 /admin 路径将直接被路由蜜罐拦截，静默回落至前台首页。
 */

export const ADMIN_BASE_PATH: string = (
  (import.meta.env.VITE_ADMIN_PATH as string | undefined) || '/_manage'
).replace(/\/+$/, '')

export function adminPath(subPath = ''): string {
  if (!subPath || subPath === '/') {
    return ADMIN_BASE_PATH
  }
  const clean = subPath.startsWith('/') ? subPath : `/${subPath}`
  return `${ADMIN_BASE_PATH}${clean}`
}
