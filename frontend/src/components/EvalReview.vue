<template>
  <div v-if="report">
    <div class="card summary">
      <h3>预测复盘 <span class="dim">（Eval Agent：赛前预测 vs 实际赛果）</span></h3>
      <div v-if="report.n_cases === 0" class="dim">账本中暂无可复盘场次（需赛前预测过且已完赛）。</div>
      <div v-else class="metrics">
        <div class="metric"><b>{{ (s.winner_accuracy * 100).toFixed(0) }}%</b><span>晋级方命中<br>{{ s.winner_hits }}/{{ s.cases }}</span></div>
        <div class="metric"><b>{{ s.avg_gd_error }}</b><span>平均净胜球<br>误差</span></div>
        <div class="metric"><b>{{ s.avg_log_loss }}</b><span>平均对数<br>损失</span></div>
        <div class="metric"><b>{{ s.avg_brier }}</b><span>平均 Brier<br>分</span></div>
      </div>
      <div v-if="s.goal_bias" class="bias" :class="{ warn: s.goal_bias.verdict !== '无明显偏差' }">
        进球偏差诊断：<b>{{ s.goal_bias.verdict }}</b>
        （实际−预测总进球均值 {{ s.goal_bias.avg_actual_minus_predicted > 0 ? '+' : '' }}{{ s.goal_bias.avg_actual_minus_predicted }}）
        <span class="dim">— 交由 Evolution Agent 分析（下方进化时间线）</span>
      </div>
    </div>

    <div v-if="evolution.length" class="card">
      <h3>进化时间线 <span class="dim">（Evolution Agent：可回放的模型自我改进史）</span></h3>
      <div class="evo" v-for="(e, i) in evolution" :key="i">
        <div class="evo-head">
          <span class="evo-tag" :class="e.recalibration && e.recalibration.applied ? 'applied' : 'noop'">
            {{ e.trigger === 'goal_bias_proposal' ? '偏差提案' : '标准重校准' }}
          </span>
          <span class="dim">{{ fmtTime(e.at) }} · 样本 {{ e.matches_used }} 场</span>
        </div>
        <div class="evo-body">
          <div v-if="e.recalibration">
            重校准：log loss {{ e.recalibration.log_loss.baseline }} → {{ e.recalibration.log_loss.best }}，
            <b :class="e.recalibration.applied ? 'ok' : 'dim'">
              {{ e.recalibration.applied ? '已生效' : '改善不足，未落盘' }}</b>
            <span v-if="Object.keys(e.params_changed || {}).length" class="dim">
              （{{ Object.keys(e.params_changed).join('、') }} 变更）</span>
          </div>
          <div v-if="e.proposal" class="evo-proposal">
            <b>提案（交人工决策）：</b>{{ e.proposal.observation }}
            <div class="proposal-rec">{{ e.proposal.recommendation }}</div>
            <span v-if="e.proposal.conflict" class="tag-conflict">方向冲突，未自动执行</span>
          </div>
          <div v-if="e.champion_delta && e.champion_delta.champion_change" class="dim">
            冠军预测变化：{{ e.champion_delta.champion_change.from }} → {{ e.champion_delta.champion_change.to }}
          </div>
        </div>
      </div>
      <p class="dim small">进化日志只追加不可改，保证审计完整性。参数变更一律经校准门禁，偏差提案不自动执行。</p>
    </div>

    <div v-if="report.calibration.length" class="card">
      <h3>置信度校准表 <span class="dim">（理想：预测均值 ≈ 实际命中率）</span></h3>
      <table>
        <tr><th>置信度桶</th><th>场次</th><th>预测均值</th><th>实际命中率</th><th>校准</th></tr>
        <tr v-for="b in report.calibration" :key="b.bucket">
          <td>{{ b.bucket }}</td><td>{{ b.n }}</td>
          <td>{{ (b.avg_predicted_conf * 100).toFixed(0) }}%</td>
          <td>{{ (b.actual_hit_rate * 100).toFixed(0) }}%</td>
          <td><span class="cal-dot" :style="calStyle(b)"></span></td>
        </tr>
      </table>
      <p class="dim small">样本量小时单桶波动大，随赛事推进收敛。</p>
    </div>

    <div class="card">
      <h3>逐场对照</h3>
      <div class="case" v-for="c in report.cases" :key="c.match_id">
        <div class="case-head">
          <span :class="{ hit: c.winner_hit, miss: !c.winner_hit }">{{ c.winner_hit ? '✓' : '✗' }}</span>
          <b>{{ c.home_zh }} vs {{ c.away_zh }}</b>
          <span class="dim">{{ c.date }} · {{ roundZh(c.round) }}</span>
        </div>
        <div class="case-body">
          <span>预测 <b>{{ fmtScore(c.predicted_score) }}</b>（{{ zh(c.predicted_winner, c) }}晋级，赛前 {{ pct(c) }}）</span>
          <span class="arrow">→</span>
          <span>实际 <b>{{ fmtScore(c.actual_score) }}</b>（{{ zh(c.actual_winner, c) }}晋级）</span>
        </div>
        <p v-if="c.reasoning" class="case-reason">{{ c.reasoning }}</p>
      </div>
    </div>
  </div>
  <div v-else class="dim center">加载复盘数据…</div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const report = ref(null)
const evolution = ref([])
const s = computed(() => report.value?.summary || {})

function fmtTime(iso) {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}

const ROUND_ZH = {
  round_of_32: '32强', round_of_16: '16强', quarter_finals: '8强',
  semi_finals: '半决赛', final: '决赛', third_place: '季军赛',
}
function roundZh(r) { return ROUND_ZH[r] || r }
function fmtScore(sc) { return sc ? `${sc[0]}:${sc[1]}` : '—' }
function zh(code, c) { return code === c.home ? c.home_zh : c.away_zh }
function pct(c) {
  return c.pred_confidence != null
    ? (c.pred_confidence * 100).toFixed(0) + '%' : '—'
}
function calStyle(b) {
  const gap = Math.abs(b.avg_predicted_conf - b.actual_hit_rate)
  const hue = gap < 0.1 ? 140 : gap < 0.25 ? 45 : 0
  return { background: `hsl(${hue}, 60%, 55%)` }
}

onMounted(async () => {
  try {
    const r = await fetch('/api/eval')
    report.value = await r.json()
  } catch (e) {
    report.value = { n_cases: 0, summary: {}, calibration: [], cases: [] }
  }
  try {
    const r = await fetch('/api/evolution')
    evolution.value = (await r.json()).log.slice().reverse()
  } catch (e) { /* 进化日志可选 */ }
})
</script>

<style scoped>
.card { margin-bottom: 16px; }
h3 { font-size: 15px; margin-bottom: 14px; }
.dim { color: var(--text-dim); font-size: 12px; font-weight: 400; }
.metrics { display: flex; gap: 12px; flex-wrap: wrap; }
.metric {
  flex: 1; min-width: 100px; background: #0b1320; border-radius: 8px;
  padding: 14px; text-align: center;
}
.metric b { display: block; font-size: 26px; color: var(--gold); }
.metric span { font-size: 12px; color: var(--text-dim); }
.bias { margin-top: 14px; padding: 10px 14px; border-radius: 6px; background: #0b1320; font-size: 13.5px; }
.bias.warn { border-left: 3px solid var(--gold); }
.bias b { color: var(--gold); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { color: var(--text-dim); font-weight: 400; padding: 6px; text-align: center; }
td { padding: 6px; text-align: center; border-top: 1px solid var(--border); }
.cal-dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; }
.small { font-size: 11.5px; margin-top: 8px; }
.case { padding: 12px 0; border-top: 1px solid var(--border); }
.case-head { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.case-head .hit { color: var(--green); font-weight: 700; }
.case-head .miss { color: var(--red); font-weight: 700; }
.case-body { display: flex; align-items: center; gap: 12px; margin-top: 6px; font-size: 13px; }
.case-body b { color: var(--text); }
.arrow { color: var(--text-dim); }
.case-reason { margin-top: 6px; font-size: 12px; color: var(--text-dim); line-height: 1.7; }
.center { text-align: center; padding: 60px 0; }
.evo { padding: 12px 0; border-top: 1px solid var(--border); }
.evo:first-of-type { border-top: none; }
.evo-head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.evo-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; }
.evo-tag.applied { background: #14532d; color: var(--green); }
.evo-tag.noop { background: #1e3a5f; color: var(--blue); }
.evo-body { font-size: 13px; line-height: 1.8; }
.evo-body .ok { color: var(--green); }
.evo-proposal { margin-top: 6px; padding: 8px 12px; background: #0b1320; border-radius: 6px;
  border-left: 3px solid var(--gold); }
.proposal-rec { margin-top: 4px; font-size: 12.5px; color: var(--text-dim); line-height: 1.7; }
.tag-conflict { display: inline-block; margin-top: 4px; font-size: 11px; color: var(--gold); }
</style>
