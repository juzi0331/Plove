#!/usr/bin/env node
/**
 * 契约 → TypeScript 类型。**类型不手写。**
 *
 *     node tools/gen-types.mjs            # 写出 src/api/types.ts
 *     node tools/gen-types.mjs --check    # 只比对不写；过期就退出码 1（可以塞进部署脚本）
 *
 * 为什么要有这个脚本，而不是让前端手写 interface：
 * 后端改字段时**手写的类型不会报错** —— 它只会安静地和实际响应不一致，
 * 等到线上出现 `undefined` 才发现。这里的类型直接长在
 * `contracts/schemas/*.json` 上（那是后端 Pydantic 模型的生成物），
 * 所以整条链是：**Pydantic 模型 → JSON Schema → TS 类型**，每一段都能校验。
 *
 * 只实现我们契约里真的用到的 JSON Schema 子集：
 * `type` / `properties` / `required` / `enum` / `const` / `array.items` /
 * `anyOf` / `$ref` / `$defs` / `additionalProperties`。
 * **遇到不认识的形状会显式报错并退出**（而不是悄悄生成一个 `any`）——
 * 悄悄降级成 any 正是这个脚本要防的那种失败。
 */

import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const FRONTEND_DIR = resolve(HERE, '..')
const REPO_DIR = resolve(FRONTEND_DIR, '..')

const DEFAULT_SCHEMA_DIR = existsSync(join(REPO_DIR, 'backend', 'contracts', 'schemas'))
  ? join(REPO_DIR, 'backend', 'contracts', 'schemas')
  : join(REPO_DIR, 'contracts', 'schemas')

const SCHEMA_DIR = process.env.PLOVE_CONTRACTS_DIR
  ? join(process.env.PLOVE_CONTRACTS_DIR, 'schemas')
  : DEFAULT_SCHEMA_DIR
const OUT_FILE = join(FRONTEND_DIR, 'src', 'api', 'types.ts')

// ---------------------------------------------------------------- 命名
/** `Envelope[Any]` 这种带方括号的 title 不能直接当 TS 名字 */
function typeName(raw) {
  const cleaned = String(raw).replace(/[^A-Za-z0-9_$]/g, '')
  return /^[0-9]/.test(cleaned) ? `T${cleaned}` : cleaned
}

/** `#/$defs/VodItem` → `VodItem`；只解析 `#/$defs/<name>` 这一种形式 */
function refName(ref) {
  const m = /^#\/\$defs\/(.+)$/.exec(ref)
  if (!m) {
    throw new Error(`不认识的 $ref: ${ref}（只支持 #/$defs/<name>）`)
  }
  return typeName(m[1])
}

const IDENT = /^[A-Za-z_$][A-Za-z0-9_$]*$/
const propName = (key) => (IDENT.test(key) ? key : JSON.stringify(key))
const literal = (value) => JSON.stringify(value)

// ---------------------------------------------------------------- 收集定义
/** 同一个类型可能出现多次：名字 → 各个来源里的那份 */
const definitions = new Map()

function collect(rawName, schema, source) {
  const name = typeName(rawName)
  const variants = definitions.get(name) ?? []
  variants.push({ schema, source })
  definitions.set(name, variants)

  for (const [nestedName, nested] of Object.entries(schema.$defs ?? {})) {
    collect(nestedName, nested, source)
  }
}

/** `VodItem` → `vod-item`，用来挑"最该代表这个类型的那份定义" */
function kebab(name) {
  return name
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1-$2')
    .toLowerCase()
}

/**
 * 同一个类型在多个契约里各定义了一份（`VodItem` 出现在 5 个文件里）：
 * 独立文件那份带 `description`，被嵌进别人 `$defs` 的那份没有。
 *
 * 所以**比较生成的 TS 文本**，而不是比较原始 JSON —— 我们真正关心的是
 * "它们会不会产生不同的类型"，注释和 `title` 的差异不影响这一点。
 * 生成结果不一致才是真问题（那是后端契约自相矛盾），那时宁可报错也不替它选。
 */
function pickDefinition(name, variants) {
  const rendered = variants.map((v) => ({ ...v, ts: tsType(v.schema) }))
  const distinct = new Set(rendered.map((r) => r.ts))
  if (distinct.size > 1) {
    const detail = rendered.map((r) => `      ${r.source}`).join('\n')
    throw new Error(
      `${name} 在不同契约里的形状不一致，前端的类型没法只写一个：\n${detail}\n` +
        '  先把后端的契约改成一致，再重新生成。',
    )
  }
  // 优先用"和类型同名那个文件"，它带 description，能生成注释
  return rendered.find((r) => r.source === `${kebab(name)}.json`) ?? rendered[0]
}

for (const file of readdirSync(SCHEMA_DIR).sort()) {
  if (!file.endsWith('.json')) continue
  const schema = JSON.parse(readFileSync(join(SCHEMA_DIR, file), 'utf8'))
  const title = schema.title
  if (!title) throw new Error(`${file} 没有 title，没法给类型起名`)
  collect(title, schema, file)
}

// ---------------------------------------------------------------- 转类型
function tsType(node) {
  if (node === null || typeof node !== 'object') return 'unknown'
  // 空的 `{}` 在 JSON Schema 里就是"任何值"（如 ErrorInfo.detail）
  if (Object.keys(node).length === 0) return 'unknown'
  if (node.$ref) return refName(node.$ref)
  if ('const' in node) return literal(node.const)
  if (Array.isArray(node.enum)) return unique(node.enum.map(literal)).join(' | ')

  for (const key of ['anyOf', 'oneOf']) {
    if (Array.isArray(node[key])) {
      return unique(node[key].map(tsType)).join(' | ')
    }
  }

  if (node.type === 'array') return `${parenthesize(tsType(node.items ?? {}))}[]`

  if (node.properties || node.additionalProperties || node.type === 'object') {
    return objectType(node)
  }

  switch (node.type) {
    case 'string':
      return 'string'
    case 'integer':
    case 'number':
      return 'number'
    case 'boolean':
      return 'boolean'
    case 'null':
      return 'null'
    default:
      if (!node.type) return 'unknown'
      throw new Error(`不认识的 schema 形状：${JSON.stringify(node).slice(0, 120)}`)
  }
}

/** 联合类型当数组元素时要加括号：`(A | B)[]` 而不是 `A | B[]` */
function parenthesize(ts) {
  return ts.includes('|') || ts.includes('&') ? `(${ts})` : ts
}

function objectType(node) {
  const props = node.properties ?? {}
  const required = new Set(node.required ?? [])

  if (Object.keys(props).length === 0) {
    // 纯字典，如播放用的 headers: { [k: string]: string }
    if (node.additionalProperties) {
      return `Record<string, ${tsType(node.additionalProperties)}>`
    }
    return 'Record<string, unknown>'
  }

  const lines = Object.entries(props).map(([key, value]) => {
    const optional = required.has(key) ? '' : '?'
    return `  ${propName(key)}${optional}: ${tsType(value)}`
  })
  return `{\n${lines.join('\n')}\n}`
}

function unique(items) {
  return [...new Set(items)]
}

// ---------------------------------------------------------------- 手写的两处
/**
 * 信封是**泛型**的：契约里 `Envelope[Any]` 的 `data` 是任意值，
 * 直接生成出来是 `unknown`，用起来要到处断言。这里给它一个类型参数。
 * 这是唯一一处\"不生成、手写\"的地方，所以放在最显眼的位置。
 */
const HAND_WRITTEN = {
  EnvelopeAny: `/** 统一响应信封。**每个**接口都是这个形状，包括错误。 */
export interface ApiEnvelope<T = unknown> {
  ok: boolean
  data?: T | null
  error?: ErrorInfo | null
  /** 请求 id，排查问题时拿它串日志 */
  request_id: string
}`,
}

// ---------------------------------------------------------------- 输出
function render() {
  const banner = [
    '// ┌─────────────────────────────────────────────────────────────────┐',
    '// │  这个文件是生成物，**不要手改** —— 手改的部分下次生成就没了。    │',
    '// └─────────────────────────────────────────────────────────────────┘',
    '//',
    '// 来源：contracts/schemas/*.json（后端 Pydantic 模型的生成物）',
    '// 重新生成：cd frontend && npm run gen:types',
    '// 检查是否过期：npm run check:types（退出码非 0 = 契约改过但没重新生成）',
    '//',
    `// 契约指纹：${fingerprint()}`,
    '',
  ].join('\n')

  const chunks = []
  for (const name of [...definitions.keys()].sort((a, b) => a.localeCompare(b))) {
    if (HAND_WRITTEN[name]) {
      chunks.push(HAND_WRITTEN[name])
      continue
    }

    const { schema, ts } = pickDefinition(name, definitions.get(name))
    const doc = schema.description ? `/** ${docComment(schema.description)} */\n` : ''
    const properties = Object.keys(schema.properties ?? {})

    // 有具名字段的才写成 interface（报错信息里能看出缺了哪个字段）；
    // 枚举 / 字典 / 联合这些写成 type
    if ((schema.type === 'object' || schema.properties) && properties.length > 0) {
      chunks.push(`${doc}export interface ${name} ${ts}`)
    } else {
      chunks.push(`${doc}export type ${name} = ${ts}`)
    }
  }

  return `${banner}${chunks.join('\n\n')}\n`
}

/** 把 schema 的 description 压成能放进 /** *\/ 的形式 */
function docComment(text) {
  const oneLine = String(text).replace(/\s+/g, ' ').trim()
  return oneLine.replace(/\*\//g, '*\\/').slice(0, 300)
}

function fingerprint() {
  const hash = createHash('sha256')
  for (const file of readdirSync(SCHEMA_DIR).sort()) {
    if (!file.endsWith('.json')) continue
    hash.update(file)
    hash.update(readFileSync(join(SCHEMA_DIR, file)))
  }
  return hash.digest('hex').slice(0, 12)
}

const output = render()

if (process.argv.includes('--check')) {
  const current = (() => {
    try {
      return readFileSync(OUT_FILE, 'utf8')
    } catch {
      return ''
    }
  })()
  if (current !== output) {
    console.error('src/api/types.ts 已过期，请重新生成：')
    console.error('  cd frontend && npm run gen:types')
    process.exit(1)
  }
  console.log(`类型是最新的（契约指纹 ${fingerprint()}）`)
  process.exit(0)
}

mkdirSync(dirname(OUT_FILE), { recursive: true })
writeFileSync(OUT_FILE, output, 'utf8')
console.log(`已生成 ${OUT_FILE}`)
console.log(`  ${definitions.size} 个类型 ← ${readdirSync(SCHEMA_DIR).filter((f) => f.endsWith('.json')).length} 个契约`)
console.log(`  契约指纹 ${fingerprint()}`)
