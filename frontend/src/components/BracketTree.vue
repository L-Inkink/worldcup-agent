<template>
  <div class="bracket-wrap">
    <div class="legend">
      <span><i class="dot dot-green"></i>已赛（真实比分）</span>
      <span><i class="dot dot-blue"></i>预测（含晋级概率条）</span>
      <span class="dim">点击场次查看推理依据</span>
    </div>
    <div class="scroll">
      <svg :viewBox="`0 0 ${W} ${H}`" :style="{ minWidth: W * 0.75 + 'px' }">
        <!-- 轮次标签 -->
        <text v-for="lb in roundLabels" :key="lb.x" :x="lb.x" y="22"
              class="round-label" text-anchor="middle">{{ lb.text }}</text>

        <!-- 连接线 -->
        <path v-for="(d, i) in connectors" :key="'c' + i" :d="d" class="connector" />

        <!-- 冠军框 -->
        <g v-if="champion" :transform="`translate(${center.x}, ${champion.y})`">
          <text :x="CW / 2" y="0" text-anchor="middle" class="champ-emoji">🏆</text>
          <text :x="CW / 2" y="22" text-anchor="middle" class="champ-name">
            {{ flag(champion.code) }} {{ teams[champion.code].name_zh }}
          </text>
          <text :x="CW / 2" y="38" text-anchor="middle" class="champ-sub">预测冠军</text>
        </g>

        <!-- 比赛卡片 -->
        <g v-for="pm in positioned" :key="pm.m.id"
           :transform="`translate(${pm.x}, ${pm.y})`"
           class="match" @click="$emit('select', pm.m)">
          <rect :width="CW" :height="CH" rx="6"
                :class="pm.m.status === 'finished' ? 'box-finished' : 'box-scheduled'" />
          <line :x1="0" :y1="CH / 2" :x2="CW" :y2="CH / 2" class="divider" />
          <g v-for="(side, si) in ['home', 'away']" :key="si">
            <text :x="8" :y="si === 0 ? 17 : 17 + CH / 2"
                  :class="rowClass(pm.m, pm.m[side])">
              {{ teamLabel(pm.m[side]) }}
            </text>
            <text :x="CW - 8" :y="si === 0 ? 17 : 17 + CH / 2" text-anchor="end"
                  :class="rowClass(pm.m, pm.m[side])">
              {{ scoreLabel(pm.m, si) }}
            </text>
          </g>
          <!-- 预测晋级概率条 -->
          <g v-if="pm.m.status !== 'finished' && pm.m.prediction">
            <rect :x="0" :y="CH - 3" :width="CW * pm.m.prediction.p_advance" height="3"
                  class="pbar-home" />
            <rect :x="CW * pm.m.prediction.p_advance" :y="CH - 3"
                  :width="CW * (1 - pm.m.prediction.p_advance)" height="3" class="pbar-away" />
          </g>
          <text v-if="pm.m.date" :x="4" :y="CH + 13" class="date-label">{{ pm.m.date }} · {{ pm.m.venue }}</text>
        </g>
      </svg>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { flag } from '../flags.js'

const props = defineProps({
  bracket: { type: Object, required: true },
  teams: { type: Object, required: true },
})
defineEmits(['select'])

const CW = 172   // 卡片宽
const CH = 56    // 卡片高
const GAP = 30   // 列间距
const RH = 86    // R32 行高
const TOP = 44
const W = 9 * (CW + GAP) - GAP
const H = TOP + 8 * RH + 10

const colX = c => c * (CW + GAP)

const ROUND_TEXT = { round_of_32: '32强', round_of_16: '16强', quarter_finals: '8强', semi_finals: '半决赛', final: '决赛' }
const COLS = [
  { round: 'round_of_32', from: 0, to: 8, col: 0 },
  { round: 'round_of_16', from: 0, to: 4, col: 1 },
  { round: 'quarter_finals', from: 0, to: 2, col: 2 },
  { round: 'semi_finals', from: 0, to: 1, col: 3 },
  { round: 'final', from: 0, to: 1, col: 4 },
  { round: 'semi_finals', from: 1, to: 2, col: 5 },
  { round: 'quarter_finals', from: 2, to: 4, col: 6 },
  { round: 'round_of_16', from: 4, to: 8, col: 7 },
  { round: 'round_of_32', from: 8, to: 16, col: 8 },
]

const roundLabels = computed(() =>
  COLS.map(c => ({ x: colX(c.col) + CW / 2, text: ROUND_TEXT[c.round] })))

// 每场比赛的中心 y：R32 均布，后续轮次取两个 feeder 的中点
const centerY = computed(() => {
  const map = {}
  const b = props.bracket
  b.round_of_32.forEach((m, i) => {
    const row = i % 8
    map[m.id] = TOP + row * RH + RH / 2
  })
  for (const rn of ['round_of_16', 'quarter_finals', 'semi_finals', 'final']) {
    b[rn].forEach(m => {
      const [f1, f2] = m.feeders
      map[m.id] = (map[f1] + map[f2]) / 2
    })
  }
  return map
})

const positioned = computed(() => {
  const out = []
  for (const c of COLS) {
    props.bracket[c.round].slice(c.from, c.to).forEach(m => {
      out.push({ m, x: colX(c.col), y: centerY.value[m.id] - CH / 2, col: c.col })
    })
  }
  return out
})

// 连接线：左半区从卡片右侧连出，右半区镜像
const connectors = computed(() => {
  const paths = []
  const pos = {}
  positioned.value.forEach(pm => { pos[pm.m.id] = pm })
  for (const pm of positioned.value) {
    const feeders = pm.m.feeders
    if (!feeders) continue
    for (const fid of feeders) {
      const f = pos[fid]
      if (!f) continue
      const fy = centerY.value[fid]
      const my = centerY.value[pm.m.id]
      let x1, x2
      if (f.col < pm.col) {          // 左半区：feeder 右边 → 本场左边
        x1 = f.x + CW; x2 = pm.x
      } else {                        // 右半区：feeder 左边 → 本场右边
        x1 = f.x; x2 = pm.x + CW
      }
      const xm = (x1 + x2) / 2
      paths.push(`M ${x1} ${fy} H ${xm} V ${my} H ${x2}`)
    }
  }
  return paths
})

const champion = computed(() => {
  const f = props.bracket.final[0]
  const code = f.winner || f.predicted_winner
  if (!code) return null
  return { code, y: centerY.value[f.id] - 62 }
})

const center = { x: colX(4) }

function teamLabel(code) {
  if (!code) return '待定'
  return `${flag(code)} ${props.teams[code].name_zh}`
}

function winnerOf(m) {
  return m.winner || m.predicted_winner
}

function rowClass(m, code) {
  if (!code) return 'row row-dim'
  const w = winnerOf(m)
  if (!w) return 'row'
  return w === code ? (m.status === 'finished' ? 'row row-won' : 'row row-pred') : 'row row-dim'
}

function scoreLabel(m, sideIndex) {
  if (m.status === 'finished' && m.score) {
    const g = m.score[sideIndex]
    const p = m.pens ? ` (${m.pens[sideIndex]})` : ''
    return `${g}${p}`
  }
  if (m.predicted_score) return m.predicted_score[sideIndex]
  return ''
}
</script>

<style scoped>
.bracket-wrap { width: 100%; }
.legend { display: flex; gap: 20px; font-size: 12px; color: var(--text-dim); margin-bottom: 12px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px; }
.dot-green { background: var(--green); }
.dot-blue { background: var(--blue); }
.scroll { overflow-x: auto; padding-bottom: 8px; }
svg { width: 100%; height: auto; display: block; }

.round-label { fill: var(--text-dim); font-size: 12px; letter-spacing: 2px; }
.connector { stroke: #2a3b5c; stroke-width: 1.2; fill: none; }

.match { cursor: pointer; }
.box-finished { fill: var(--bg-card); stroke: #14532d; stroke-width: 1.4; }
.box-scheduled { fill: var(--bg-card); stroke: #1e3a5f; stroke-width: 1.4; }
.match:hover rect:first-of-type { fill: var(--bg-card-hover); }
.divider { stroke: #24355480; stroke-width: 1; }

.row { fill: var(--text); font-size: 12.5px; }
.row-won { fill: var(--green); font-weight: 700; }
.row-pred { fill: var(--blue); font-weight: 700; }
.row-dim { fill: var(--text-dim); }

.pbar-home { fill: var(--blue); opacity: 0.9; }
.pbar-away { fill: #3b4a68; }
.date-label { fill: #5a6b8c; font-size: 9.5px; }

.champ-emoji { font-size: 26px; }
.champ-name { fill: var(--gold); font-size: 15px; font-weight: 700; }
.champ-sub { fill: var(--text-dim); font-size: 10px; letter-spacing: 3px; }
</style>
