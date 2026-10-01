/// <reference types="vite/client" />

/** .vue 文件的类型声明：没有它 `import App from './App.vue'` 会报找不到模块 */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

interface ImportMetaEnv {
  /** 接口前缀，默认 /api/v1 */
  readonly VITE_API_BASE?: string
  /** 前端单请求超时（毫秒），默认 60000 */
  readonly VITE_REQUEST_TIMEOUT_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
