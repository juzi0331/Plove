/**
 * "没有海报时用什么颜色" —— 一个地方算，两个地方用。
 *
 * 为什么需要它：实测 `ncat21` 的海报**一张都拿不到**（图片路径被源站 WAF 拦），
 * 所以"缺图"不是异常而是常态。缺图时如果只留一块灰底，整个界面会看起来像坏了；
 * 给它一个**由片名算出来的颜色**，它就会看起来像一种设计。
 *
 * 两个关键点：
 *
 * 1. **是算出来的，不是随机的。** 同一部片每次都是同一个颜色，
 *    用户第二次看到会认得出来；随机会让界面每次都在"闪颜色"，看起来像故障。
 * 2. **色相分散 + 明度压低。** 分散才不至于一排全是同色；明度压低是因为
 *    底是纯黑的，亮色块会刺眼、也会和海报抢注意力。
 *
 * 放在 `utils` 而不是组件里：海报卡、头图、详情头图都要用，
 * 而它们各自算一遍迟早会算出不一致的颜色。
 */

/** 片名 → 0~359 的稳定色相 */
export function titleHue(text: string): number {
  let acc = 0
  for (const ch of text || 'plove') {
    acc = (acc * 31 + (ch.codePointAt(0) ?? 0)) % 360
  }
  return acc
}

/**
 * 片名的"专属渐变"。
 *
 * 用 155 度是因为它和竖版海报的对角线方向接近，铺在 2:3 的格子里比纯竖直更活。
 * 第二个色相 +32 度，让渐变有明显走向但不会变成"彩虹"。
 */
export function titleGradient(text: string): string {
  const hue = titleHue(text)
  const to = (hue + 32) % 360
  return `linear-gradient(155deg, hsl(${hue} 38% 24%), hsl(${to} 44% 9%))`
}


/**
 * Third-party poster URL -> same-origin image proxy.
 *
 * 2048's image CDN is already browser-friendly and is intentionally left
 * direct to avoid an unnecessary hop. Other upstreams often require
 * anti-hotlink headers / WAF handling and must go through the backend proxy.
 */
export function proxiedImageUrl(url: string | null | undefined): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw

  try {
    const parsed = new URL(raw)
    const host = parsed.hostname.toLowerCase()
    if (host === '2048ai.vip' || host.endsWith('.2048ai.vip')) return raw
    if (typeof window !== 'undefined' && host === window.location.hostname) return raw
  } catch {
    return raw
  }

  return `/api/v1/proxy/image?url=${encodeURIComponent(raw)}`
}
