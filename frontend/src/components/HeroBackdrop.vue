<script setup lang="ts">
/**
 * HeroBackdrop - 奈飞官网桌面端 1:1 电影海报背景层
 *
 * 核心升级：
 * 1. 竖向排数由原先的 2 排调整为清晰可见的 3~4 排（网格行高精确适配视口）；
 * 2. 大小随机化：打破等大死板方块，采用真实官方影视瀑布流（包含标准海报、横版宽屏剧照、双倍重点大卡、竖向长卡）；
 * 3. 封面真随机化：深度整合 30+ 官方真实剧照 + 20+ 精选大片海报 + 用户动态片单，使用 Fisher-Yates 洗牌算法随机分布。
 */

import { onMounted, ref, watch } from 'vue'
import type { VodItem } from '@/api/types'

const props = withDefaults(
  defineProps<{
    items?: VodItem[]
  }>(),
  {
    items: () => [],
  },
)

// 奈飞官方原版提取之高画质海报剧照库 (涵盖横版 16:9 与竖版 2:3)
const officialNetflixPosters = [
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABchOs-1XieJMoyK3mNyWioi6yUn-js6rfSCYIK6Mutbxh9I9hiHFwXtxaPJ5P9GIP6lK2xLrcWl88F70-Zd-4fS8zSum3ZDe9yyIJAV7Xlpr8kfbZDeGskrJuVKvqhl3apbs.webp?r=35e',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABYtJ9rFHVd8YoHcPiepjGMHpK3gEU6BSBmuR6WVtlzJHUVlVFuevWd66lqq5L2iH93x4Av3L8IqYv8Iyhr4TV15B5vtDqh5dQlHq.webp?r=38b',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABWLunz798Q8P9bSiw5oN8KWCv_0yXPxoCCGBhQuUl_aod8-sWqFGi2sCoo9FdudMLfv9ufBppTskqk9aE4M406bk_udAjKhu_m5256Z6cceHeqTljQTf25ElyBQUr9Yyl5UH.webp?r=d48',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABRLs3licJG0Mj6F8LPxnpxeUQgoutXRD5Aq5BxN_i6MOhIXNdrYGfeOiedbbzgUCuLvlVmONpXzLE1kkzd4LV2MexXtdfUSjI2Vg.webp?r=5b2',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABQqJuyhZJCxJny-9qUSINKyR9SZcWkW2-PyYdirpftSasUwTmeKcdnHxrrRfzsarsdiNTEnnAB5wQMmKh03oLTltT01xCaKZFw.webp?r=6cd',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABYREREbjyo5fYJr_P89r3Ot1NbnY2DqMOyjIFAb3hQJ5Lkp-B9dmSzqArL4DS71Y4ahk7FFB5JuNP6M3DRgiKhMRpnHTBAYt43yo.webp?r=50e',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABYv53jhknxjcwbsI_L3Mejbt8c5Q-PCatXAIgERUUGOD59PxG_oWaxyBuAgsb-uEmSJ7o_Vlj-nfQKbt-IGAPhaQiPrCCgaF2F4.webp?r=17d',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABUvePr5DLeEf16P3YCvJliB0P9vmfxFNgQA4sP45LaqGLjpsXFSlm4fmRpM04dn8BSfbvQepugyqDMfnvtx2BhWuvFt5jpM5H2O5.webp?r=f8f',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABQIFB7F9xnugEgQ4tG-q1Hjrga4Doi6xPF2Z7QgNhdQyKkD1nHwTCnKyBV51sgHl1R--ibSmFHcFRpwEdT62P1D7iIK2H63DW9utNzv5GXCkyHI5YRH8oDMDo_Mkc30pYT59.webp?r=e8f',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABZ0zUb0lnewNxU6NHAuXsgIF2itIm5ek3jBEVGJsVsI6fdCwG7-WbEUR-nQMfAHaO9Qdne5QYfkj2aRwquxb36cjZY171k42Gi0.webp?r=bfd',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABXgvEdyOg8fAaIucE9LGFtb7ih9R31djnJokkl46JjSwFdjsHGAmhPgNlCpEO_ed-H9VV0OIIdGe7HUdzJUrtTO7xbBpFO9XbA1pAVnd5GKLmpObhH953jil2_JHrcoDTys0.webp?r=c04',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABeMqaY3vbvFVigshSmUtoWj9csHAgR6HWbQAy-9w9hsgXCahZfE3FCsXrLp5zzdAtcY3fTjHllPl8dPMPnZGQLIOK1m_J6zh9Q.webp?r=d5c',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABdPmRRuXiaOXCh4414YQ8j0gnTlP0b8guS_zNHd3Zk0fTX6zNdSnttcB-P5ZXzzan_AzQgm3o3Ri2W2emg5ReFzjYUZbZo0-mi3z.webp?r=9ee',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABeUvs8vMosqPug3rplnXDy-ouuMev7vfu20ytnzTfaf2FmRuHvqvQlITP2Y7kCHlnJIsHJ7EtuGVImcVLA9JuwtORYm9FzVTwKo.webp?r=2f3',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABcA0Y-9G8qkFO3pdedtwRaybHsXU3oDoXJpuJ1maUEqBuBtgvXkkkFI9bWMoU5j7TpFfHpABnDjRJ0QE_6LxyWQBx4VbV1E1LA.webp?r=d8d',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABa60udv_Ya2m_FELMcQUSYnaHL3iUMf6hMkJQ1VEFG_H93CAbKC1G2KuJW-cWFUevjVN0ZBY-rtmJW66zM5hAnf0PF-JjfnUtgrA.webp?r=f6d',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABdL5B4vHI_hwrD50RyibJ9B-7mCfOqSZzCbq1H2ZwMMxUixquAWg2892yJC41TbK-88T_VgpRJHeaYBSyXNpw6gi6Z7_PxuaOEIz.webp?r=f10',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABShm99JiluuQ_gecuSj3Tavf8uz2d07fywUjNspgXmVxM7PnB_yJiCDZK69WA6dTzNNMRPmAv7F-I1mUWQQnqth7R2nlQgjd1CuK4IqCUuTmE9E9bIIFv5IfjjMGZJBBzbbH.webp?r=a19',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABZqbuWHj62AimBgnCF0uFmYB40LnJpcNA9bRckQqvxvJfpUncLZuywvqaglIkM3KLibB0_RuYwxRid4AqqwUTlrpPT3inMzeQA.webp?r=7cc',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABfbZhP1GiEhpv3hTNeiNlS3Im5pCG5usk1AoHw1v3zDMlSfDHGSU3nkSMtHKnB0Wq3TXI09rV5MwJhunL9anJMIOI_MUy8MkcA.webp?r=68e',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABRNEavksAKBNr5xSeNbbDFP0gu_Xb-EUR4mhskSr177AfT7HjUeha8e5ZyIrUsSrWiV5TBHkb_1uyRWJ-M3EHA7ojPyzniEPPQ.webp?r=036',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABbkBdARQrhLI1QRXThYLUoO-t564ZnoTXjVMbz7J7i63Jlhwe8m-i8MNCZPJteZ_2n5cjsT1NT-EUCKd0h7cjN5HCI7mLRRtn9Q.webp?r=39f',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABWU7XO6V1jBBKE_KFSQl8dQcnlqt5jp5Omo_ug7php0yosWr-72mJhyZgiFYe4Ip8E9Pf3hJLEvKWSgB7Utc6s3z5h3_Y-HhSSjH.webp?r=772',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABUmUAF26YRhIGL9rN7KF_vsmUAfNP8omi8WHX-2EvI07yLGalwgNvKznqr1jWPk6G7bn0PaxRxQ1-APIPj3AYxRU0N_0DbC6svQ.webp?r=a2b',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABe3xKqWByUDStf2HHkq9P87RiI21Y41ES4b6-TWMlpfeKUsHeOWwhHz_eQiMdSUdqp_H1HgFIbojb4ysuc-eQlozb7fff4PuTA.webp?r=792',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/6AYY37jfdO6hpXcMjf9Yu5cnmO0/AAAABWRvsN2RFsgV_QbDTv_P-Q3A6jSIaZ3o_5jJinrfkAQEzN9uvLPzPeGwQ-cUIaaJqa1MxpePV4qRZBlpXBjdvUL3PhrszZhqMA0-.webp?r=52c',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABVFUdqopvpLfEtbDXmhjmEIPPWMFzvQqolFZu5Sz06I60TLJf6a2ql_qpXWUjr3P3lSFsEbt6oB_ayVndxurRQMhodilirmfsA.webp?r=3ed',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/S4oi7EPZbv2UEPaukW54OORa0S8/AAAABe2AVEd_9LIp34Q7RsWMR2gqUSWa96jzS31KqhJngO4wNkxGdISms6zwgUPmsed7Us9UottC9cZuOGXKSgVXv_7IQDughkOXBA.webp?r=311',
  'https://occ-0-325-395.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABSJJ-0dfWlsDeCpg-x0IoEOdgUVLEtn0UT64hC6eKS1WG_d2gJjNveUnLkAJ1BACQ_HG4a4zbH6Z7UJ-im66q9UsR5sPcKFJGz87MK3o8PD2H_cer2srRAuoVBuF1pg7shT4.webp?r=6b8',
]

// 高清电影质感壁纸库补足
const cinemaWallPosters = [
  'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=450&q=80',
  'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=450&q=80',
  'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=450&q=80',
  'https://images.unsplash.com/photo-1635805737707-575885ab0820?w=450&q=80',
  'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=450&q=80',
  'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=450&q=80',
  'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=450&q=80',
  'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=450&q=80',
  'https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=450&q=80',
  'https://images.unsplash.com/photo-1534447677768-be436bb09401?w=450&q=80',
  'https://images.unsplash.com/photo-1509281373149-e957c6296406?w=450&q=80',
  'https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=450&q=80',
  'https://images.unsplash.com/photo-1563089145-599997674d42?w=450&q=80',
  'https://images.unsplash.com/photo-1574375927938-d5a98e8ffe85?w=450&q=80',
  'https://images.unsplash.com/photo-1512070679279-8986d2040638?w=450&q=80',
  'https://images.unsplash.com/photo-1616530940355-351fabd9524b?w=450&q=80',
  'https://images.unsplash.com/photo-1585951237318-9ea5e175b891?w=450&q=80',
  'https://images.unsplash.com/photo-1542204165-65bf26472b9b?w=450&q=80',
  'https://images.unsplash.com/photo-1568876694728-451bbf694b83?w=450&q=80',
  'https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=450&q=80',
]

export interface PosterCardItem {
  id: string
  pic: string
  sizeVariant: 'standard' | 'wide' | 'tall' | 'featured'
}

/** 随机洗牌算法 (Fisher-Yates) */
function shuffleArray<T>(arr: T[]): T[] {
  const result = [...arr]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

// 响应式卡片列表（避免 SSR/客户端 hydration 不一致，并在挂载时执行真正随机化）
const cardList = ref<PosterCardItem[]>([])

import { formatPosterUrl } from '@/utils/format'

function buildPosterWall(): void {
  // 1. 汇集所有素材
  const livePics = props.items
    .filter((it) => it.vod_pic && it.vod_pic.startsWith('http'))
    .map((it) => formatPosterUrl(it.vod_pic))

  const allPics = shuffleArray([...officialNetflixPosters, ...cinemaWallPosters, ...livePics])

  // 2. 构造具有自然错落大小比例的卡片池 (竖向 3~4 排需约 60~72 张卡片密集平铺)
  const result: PosterCardItem[] = []
  const count = 72

  for (let i = 0; i < count; i++) {
    const pic = allPics[i % allPics.length]

    // 随机大小分布规律：
    // - 约 60% 标准卡片 (1x1)
    // - 约 22% 横版宽屏剧照 (2x1 wide)
    // - 约 10% 竖向加长海报 (1x2 tall)
    // - 约 8% 大画幅双倍焦点卡片 (2x2 featured)
    const rand = Math.random()
    let sizeVariant: PosterCardItem['sizeVariant'] = 'standard'
    if (rand < 0.22) {
      sizeVariant = 'wide'
    } else if (rand < 0.32) {
      sizeVariant = 'tall'
    } else if (rand < 0.40) {
      sizeVariant = 'featured'
    }

    result.push({
      id: `poster-${i}-${Math.random().toString(36).substring(2, 7)}`,
      pic,
      sizeVariant,
    })
  }

  cardList.value = result
}

onMounted(() => {
  buildPosterWall()
})

watch(() => props.items, () => {
  if (props.items && props.items.length > 0) {
    buildPosterWall()
  }
}, { deep: true })
</script>

<template>
  <div class="nf-backdrop" aria-hidden="true">
    <!-- 真实清晰电影海报墙 (超广角斜向错落矩阵，竖向完整呈现 3~4 排) -->
    <div class="nf-poster-wall">
      <div class="nf-poster-grid">
        <div
          v-for="card in cardList"
          :key="card.id"
          class="nf-poster-card"
          :class="`is-${card.sizeVariant}`"
        >
          <img
            :src="card.pic"
            alt="poster"
            class="nf-poster-img"
            referrerpolicy="no-referrer"
            crossorigin="anonymous"
            @error="($event.target as HTMLElement).style.display = 'none'"
          />
        </div>
      </div>
    </div>

    <!-- 奈飞官方经典多层通透遮罩 (保证海报清晰，绝不黑死) -->
    <div class="nf-vignette-overlay" />

    <!-- 官方 1:1 原生 CSS 椭圆地平线弧光与渐隐系统 (The Official Netflix Curve Container) -->
    <div class="nf-curve-container">
      <div class="nf-curve" />
    </div>
  </div>
</template>

<style scoped>
.nf-backdrop {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background: #000000;
}

/* 电影海报墙：高可见度、微倾斜、密集、色彩丰富清晰 */
.nf-poster-wall {
  position: absolute;
  top: -18%;
  left: -12%;
  right: -12%;
  bottom: -18%;
  transform: rotate(-3.5deg) scale(1.06);
  opacity: 0.92;
  filter: contrast(1.05) brightness(0.88);
}

/* 密集紧凑自适应错落网格 (grid-auto-flow: dense 保证大小随机无缝拼贴)
   行高设为 165px，在 700~900px 首屏视口内刚好呈现 3~4 排真实海报！ */
.nf-poster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  grid-auto-rows: 165px;
  grid-auto-flow: dense;
  gap: 12px;
  width: 100%;
  height: 100%;
}

/* 基础卡片 */
.nf-poster-card {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.7);
  background-color: #1a1a1a;
  transform: translateZ(0);
}

/* 1. 标准卡片 (1x1) */
.nf-poster-card.is-standard {
  grid-column: span 1;
  grid-row: span 1;
}

/* 2. 横版宽幅剧照 (2x1) - 奈飞原版特色 */
.nf-poster-card.is-wide {
  grid-column: span 2;
  grid-row: span 1;
}

/* 3. 竖向纵长海报 (1x2) */
.nf-poster-card.is-tall {
  grid-column: span 1;
  grid-row: span 2;
}

/* 4. 双倍焦点大卡片 (2x2) */
.nf-poster-card.is-featured {
  grid-column: span 2;
  grid-row: span 2;
}

.nf-poster-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 官方轻量遮罩：中心只做温和暗角，使标题和输入框清晰可读，四周海报生动丰富 */
.nf-vignette-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  background-image:
    linear-gradient(
      180deg,
      rgba(0, 0, 0, 0.85) 0%,
      rgba(0, 0, 0, 0.25) 35%,
      rgba(0, 0, 0, 0.3) 65%,
      rgba(0, 0, 0, 0.9) 100%
    ),
    radial-gradient(
      60% 55% at 50% 50%,
      rgba(0, 0, 0, 0.75) 0%,
      rgba(0, 0, 0, 0.5) 55%,
      rgba(0, 0, 0, 0.15) 100%
    );
}

/* ====================================================================
   官方 1:1 纯 CSS 椭圆地平线弧光与渐隐系统 (Netflix Official Pure CSS Curve)
==================================================================== */
.nf-curve-container {
  box-sizing: border-box;
  overflow-x: hidden;
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 6.25rem;
  z-index: 3;
  pointer-events: none;
}

.nf-curve {
  box-sizing: border-box;
  position: absolute;
  height: 100%;
  top: 0;
  margin: auto;
  display: flex;
  align-items: center;
  border: solid 0.25rem transparent;
  border-top-left-radius: 50% 100%;
  border-top-right-radius: 50% 100%;
  border-bottom: none;
  background: radial-gradient(
    50% 500% at 50% -420%,
    rgba(64, 97, 231, 0.4) 80%,
    rgba(0, 0, 0, 0.1) 100%
  ), black;
  -webkit-background-clip: padding-box;
  background-clip: padding-box;
  width: 200%;
  left: -50%;
}

@media all and (min-width: 600px) {
  .nf-curve {
    width: 180%;
    left: -40%;
  }
}

@media all and (min-width: 960px) {
  .nf-curve {
    width: 150%;
    left: -25%;
  }
}

@media all and (min-width: 1280px) {
  .nf-curve {
    width: 130%;
    left: -15%;
  }
}

@media all and (min-width: 1920px) {
  .nf-curve {
    width: 120%;
    left: -10%;
  }
}

/* 官方核心渐变线：两翼精准渐隐消融！ */
.nf-curve:before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: -1;
  margin-top: -0.25rem;
  border-radius: inherit;
  background: linear-gradient(
    to right,
    rgba(33, 13, 22, 1) 16%,
    rgba(184, 40, 105, 1),
    rgba(229, 9, 20, 1),
    rgba(184, 40, 105, 1),
    rgba(33, 13, 22, 1) 84%
  );
}

@media (max-width: 768px) {
  .nf-curve-container {
    height: 4.5rem;
  }

  .nf-poster-grid {
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 10px;
  }
}
</style>
