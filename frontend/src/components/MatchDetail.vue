<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal card">
      <button class="close" @click="$emit('close')">✕</button>
      <h2>
        {{ flag(match.home) }} {{ name(match.home) }}
        <span class="vs">{{ scoreText }}</span>
        {{ name(match.away) }} {{ flag(match.away) }}
      </h2>
      <p class="sub">{{ match.date }} · {{ match.venue }}
        <span class="tag" :class="match.status === 'finished' ? 'tag-green' : 'tag-blue'">
          {{ match.status === 'finished' ? '✓ 已赛' : '预测' }}
        </span>
      </p>

      <template v-if="pred">
        <!-- 胜平负概率条 -->
        <div class="section-title">90 分钟胜平负概率</div>
        <div class="prob-bar">
          <div class="seg seg-home" :style="{ width: pct(pred.p_win) }">{{ pct(pred.p_win) }}</div>
          <div class="seg seg-draw" :style="{ width: pct(pred.p_draw) }">{{ pct(pred.p_draw) }}</div>
          <div class="seg seg-away" :style="{ width: pct(pred.p_loss) }">{{ pct(pred.p_loss) }}</div>
        </div>
        <div class="prob-legend">
          <span>{{ name(match.home) }}胜</span><span>平局</span><span>{{ name(match.away) }}胜</span>
        </div>

        <div v-if="pred.p_advance != null" class="advance">
          晋级概率：{{ name(match.home) }} <b>{{ pct(pred.p_advance) }}</b>
          / {{ name(match.away) }} <b>{{ pct(1 - pred.p_advance) }}</b>
          <span v-if="pred.decided_in_extra" class="dim">（最可能进入加时/点球）</span>
        </div>

        <!-- 比分概率热力矩阵 -->
        <div class="section-title">比分概率矩阵（行：{{ name(match.home) }}，列：{{ name(match.away) }}）</div>
        <table class="matrix">
          <tr>
            <th></th>
            <th v-for="j in 6" :key="j">{{ j - 1 }}</th>
          </tr>
          <tr v-for="i in 6" :key="i">
            <th>{{ i - 1 }}</th>
            <td v-for="j in 6" :key="j"
                :style="cellStyle(i - 1, j - 1)"
                :class="{ ml: isML(i - 1, j - 1) }">
              {{ (matrixAt(i - 1, j - 1) * 100).toFixed(1) }}
            </td>
          </tr>
        </table>
        <p class="dim small">最可能比分 {{ pred.most_likely_score[0] }}:{{ pred.most_likely_score[1] }}
          （单元格为该比分概率%，金框为最大值；期望进球 {{ pred.expected_goals[0] }} vs {{ pred.expected_goals[1] }}）</p>
      </template>

      <!-- 双方实力对比 -->
      <div class="section-title">量化依据</div>
      <table class="facts">
        <tr><th></th><th>{{ name(match.home) }}</th><th>{{ name(match.away) }}</th></tr>
        <tr v-for="row in factRows" :key="row.label">
          <td>{{ row.label }}</td><td>{{ row.h }}</td><td>{{ row.a }}</td>
        </tr>
      </table>

      <!-- 推理文本 -->
      <template v-if="match.reasoning?.text">
        <div class="section-title">
          推理分析
          <span class="tag" :class="match.reasoning.source === 'qwen' ? 'tag-gold' : 'tag-blue'">
            {{ match.reasoning.source === 'qwen' ? 'Qwen 生成' : '规则模板' }}
          </span>
        </div>
        <p class="reasoning">{{ match.reasoning.text }}</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { flag } from '../flags.js'

const props = defineProps({
  match: { type: Object, required: true },
  teams: { type: Object, required: true },
  ratings: { type: Object, required: true },
})
defineEmits(['close'])

const pred = computed(() => props.match.prediction)

const scoreText = computed(() => {
  const m = props.match
  if (m.status === 'finished' && m.score) {
    let t = `${m.score[0]} : ${m.score[1]}`
    if (m.pens) t += `（点球 ${m.pens[0]}:${m.pens[1]}）`
    else if (m.aet) t += '（加时）'
    return t
  }
  if (m.predicted_score) return `预测 ${m.predicted_score[0]} : ${m.predicted_score[1]}`
  return 'vs'
})

function name(code) {
  return code ? props.teams[code].name_zh : '待定'
}
function pct(v) {
  return (v * 100).toFixed(0) + '%'
}
function matrixAt(i, j) {
  return pred.value?.score_matrix?.[i]?.[j] ?? 0
}
function isML(i, j) {
  const s = pred.value?.most_likely_score
  return s && s[0] === i && s[1] === j
}
function cellStyle(i, j) {
  const p = matrixAt(i, j)
  const alpha = Math.min(1, p * 6)
  return { background: `rgba(96, 165, 250, ${alpha.toFixed(2)})` }
}

const factRows = computed(() => {
  const rh = props.ratings[props.match.home]
  const ra = props.ratings[props.match.away]
  if (!rh || !ra) return []
  return [
    { label: '综合实力分', h: rh.strength, a: ra.strength },
    { label: 'Elo 评分', h: rh.elo, a: ra.elo },
    { label: 'FIFA 排名', h: `第${rh.fifa_rank}`, a: `第${ra.fifa_rank}` },
    { label: '近一年 Elo 变化', h: signed(rh.form_1y), a: signed(ra.form_1y) },
    { label: '本届净胜球', h: `${signed(rh.wc_gd)}（${rh.wc_played}场）`, a: `${signed(ra.wc_gd)}（${ra.wc_played}场）` },
  ]
})
function signed(v) {
  return v > 0 ? `+${v}` : `${v}`
}
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.65);
  display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px;
}
.modal {
  max-width: 620px; width: 100%; max-height: 88vh; overflow-y: auto; position: relative;
  padding: 24px 28px;
}
.close {
  position: absolute; top: 14px; right: 16px; background: none; border: none;
  color: var(--text-dim); font-size: 16px; cursor: pointer;
}
h2 { font-size: 18px; text-align: center; margin-bottom: 4px; }
.vs { color: var(--gold); margin: 0 10px; }
.sub { text-align: center; color: var(--text-dim); font-size: 12.5px; margin-bottom: 18px; }
.section-title {
  font-size: 13px; color: var(--text-dim); letter-spacing: 1px;
  margin: 18px 0 8px; border-left: 3px solid var(--gold); padding-left: 8px;
}
.prob-bar { display: flex; height: 26px; border-radius: 5px; overflow: hidden; font-size: 11.5px; }
.seg { display: flex; align-items: center; justify-content: center; min-width: 34px; color: #0b1320; font-weight: 700; }
.seg-home { background: var(--blue); }
.seg-draw { background: #94a3b8; }
.seg-away { background: var(--red); }
.prob-legend { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--text-dim); margin-top: 4px; }
.advance { margin-top: 12px; font-size: 13.5px; }
.advance b { color: var(--gold); }
.matrix { border-collapse: collapse; font-size: 11px; width: 100%; }
.matrix th { color: var(--text-dim); font-weight: 400; padding: 3px; }
.matrix td { text-align: center; padding: 4px 3px; border: 1px solid #0b1320; }
.matrix td.ml { outline: 2px solid var(--gold); font-weight: 700; }
.facts { width: 100%; border-collapse: collapse; font-size: 13px; }
.facts th { color: var(--text-dim); font-weight: 600; padding: 5px; text-align: center; }
.facts td { padding: 5px; text-align: center; border-top: 1px solid var(--border); }
.facts td:first-child { color: var(--text-dim); text-align: left; }
.reasoning { font-size: 13.5px; line-height: 1.8; white-space: pre-wrap; }
.dim { color: var(--text-dim); }
.small { font-size: 11.5px; margin-top: 6px; }
</style>
