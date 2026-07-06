<template>
  <div class="layout">
    <div class="card hero">
      <div class="trophy">🏆</div>
      <div class="big">{{ flag(champion.team) }} {{ teams[champion.team].name_zh }}</div>
      <div class="prob">夺冠概率 {{ (champion.probability * 100).toFixed(1) }}%</div>
      <div class="podium">
        <div v-for="(row, i) in top3" :key="row.code" class="podium-row">
          <span class="rank">{{ i + 1 }}</span>
          <span>{{ flag(row.code) }} {{ teams[row.code].name_zh }}</span>
          <span class="p">{{ (row.p * 100).toFixed(1) }}%</span>
        </div>
      </div>
      <div v-if="modelParams" class="backtest">
        <div class="section-label">模型档案</div>
        <div class="bt-row"><span>参数来源</span>
          <b :class="{ calibrated: modelParams.source === 'calibrated' }">
            {{ modelParams.source === 'calibrated' ? '回测自动校准' : '经验默认值' }}</b></div>
        <template v-if="modelParams.source === 'calibrated'">
          <div class="bt-row"><span>校准样本</span><b>{{ modelParams.matches_used }} 场已赛</b></div>
          <div class="bt-row"><span>对数损失</span>
            <b>{{ modelParams.baseline_log_loss }} → {{ modelParams.log_loss }}</b></div>
          <p class="bt-note">吸收新赛果时自动重校准（改善超阈值才生效）</p>
        </template>
      </div>

      <div class="backtest">
        <div class="section-label">模型可信度（回测）</div>
        <div class="bt-row"><span>已赛场次方向命中</span>
          <b>{{ backtest.overall.hits }}/{{ backtest.overall.matches }}
            （{{ (backtest.overall.accuracy * 100).toFixed(0) }}%）</b></div>
        <div class="bt-row"><span>淘汰赛命中</span>
          <b>{{ backtest.knockout.hits }}/{{ backtest.knockout.matches }}
            （{{ (backtest.knockout.accuracy * 100).toFixed(0) }}%）</b></div>
        <p class="bt-note">{{ backtest.note }}</p>
      </div>
    </div>

    <div class="card report">
      <h3>冠军推理报告
        <span class="tag" :class="champion.report.source === 'qwen' ? 'tag-gold' : 'tag-blue'">
          {{ champion.report.source === 'qwen' ? 'Qwen (qwen-max) 生成' : '规则模板生成' }}
        </span>
      </h3>
      <p class="text">{{ champion.report.text }}</p>
      <details>
        <summary>查看输入给模型的量化事实</summary>
        <pre>{{ champion.report.facts }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { flag } from '../flags.js'

const props = defineProps({
  champion: { type: Object, required: true },
  teams: { type: Object, required: true },
  backtest: { type: Object, required: true },
  mc: { type: Object, required: true },
  modelParams: { type: Object, default: null },
})

const top3 = computed(() =>
  Object.entries(props.mc.p_champion).slice(0, 3).map(([code, p]) => ({ code, p })))
</script>

<style scoped>
.layout { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
@media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
.hero { text-align: center; align-self: start; }
.trophy { font-size: 54px; margin: 10px 0; }
.big { font-size: 24px; font-weight: 700; color: var(--gold); }
.prob { color: var(--text-dim); margin: 6px 0 18px; }
.podium { border-top: 1px solid var(--border); padding-top: 12px; }
.podium-row { display: flex; gap: 10px; padding: 5px 12px; font-size: 14px; align-items: center; }
.rank { width: 20px; height: 20px; border-radius: 50%; background: #24355480; font-size: 11px;
        display: flex; align-items: center; justify-content: center; color: var(--text-dim); }
.podium-row .p { margin-left: auto; color: var(--text-dim); }
.backtest { border-top: 1px solid var(--border); margin-top: 14px; padding-top: 12px; text-align: left; }
.section-label { font-size: 12px; color: var(--text-dim); letter-spacing: 1px; margin-bottom: 8px; }
.bt-row { display: flex; justify-content: space-between; font-size: 13px; padding: 3px 0; }
.bt-row b { color: var(--green); }
.bt-row b.calibrated { color: var(--gold); }
.bt-note { font-size: 11.5px; color: var(--text-dim); margin-top: 8px; }
.report h3 { font-size: 15px; margin-bottom: 14px; }
.text { line-height: 2; font-size: 14px; white-space: pre-wrap; }
details { margin-top: 16px; font-size: 12px; color: var(--text-dim); }
pre { margin-top: 8px; background: #0b1320; padding: 12px; border-radius: 6px;
      white-space: pre-wrap; font-size: 11.5px; line-height: 1.7; }
</style>
