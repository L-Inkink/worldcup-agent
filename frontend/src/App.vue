<template>
  <header class="header">
    <div class="title-row">
      <h1>⚽ 2026 世界杯冠军预测 Agent</h1>
      <div v-if="data" class="meta">
        <span class="tag" :class="data.data_source.includes('snapshot') ? 'tag-gold' : 'tag-green'">
          数据源：{{ data.data_source.includes('snapshot') ? '本地快照' : '实时采集' }}
        </span>
        <span class="tag tag-blue">推理：{{ data.reasoning_source === 'qwen' ? 'Qwen 大模型' : '规则模板' }}</span>
        <span class="tag tag-blue" v-if="backtestAcc">回测命中率 {{ backtestAcc }}</span>
      </div>
    </div>
    <p v-if="data" class="champion-line">
      预测冠军：<b class="champ">{{ flag(data.champion.team) }} {{ data.teams[data.champion.team].name_zh }}</b>
      <span class="dim">（10000 次模拟夺冠概率 {{ (data.champion.probability * 100).toFixed(1) }}%）</span>
    </p>
    <nav class="tabs">
      <button v-for="t in tabs" :key="t.key"
              :class="{ active: tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>
  </header>

  <main v-if="data">
    <BracketTree v-if="tab === 'bracket'" :bracket="data.bracket" :teams="data.teams"
                 @select="openMatch" />
    <GroupTables v-if="tab === 'groups'" :groups="data.groups" :teams="data.teams"
                 :matches="data.group_matches" />
    <ChampionOdds v-if="tab === 'odds'" :mc="data.monte_carlo" :teams="data.teams"
                  :champion="data.champion.team" />
    <ChampionReport v-if="tab === 'report'" :champion="data.champion" :teams="data.teams"
                    :backtest="data.model_backtest" :mc="data.monte_carlo" />
  </main>
  <main v-else-if="error" class="center-note">
    <p>加载失败：{{ error }}</p>
    <button class="retry" @click="load">重试</button>
  </main>
  <main v-else class="center-note"><p>加载预测数据…</p></main>

  <MatchDetail v-if="selected" :match="selected" :teams="data.teams" :ratings="data.ratings"
               @close="selected = null" />
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import BracketTree from './components/BracketTree.vue'
import GroupTables from './components/GroupTables.vue'
import ChampionOdds from './components/ChampionOdds.vue'
import ChampionReport from './components/ChampionReport.vue'
import MatchDetail from './components/MatchDetail.vue'
import { flag } from './flags.js'

const tabs = [
  { key: 'bracket', label: '淘汰赛对阵树' },
  { key: 'groups', label: '小组赛回顾' },
  { key: 'odds', label: '夺冠概率' },
  { key: 'report', label: '冠军推理' },
]
const tab = ref('bracket')
const data = ref(null)
const error = ref(null)
const selected = ref(null)

const backtestAcc = computed(() => {
  const a = data.value?.model_backtest?.overall?.accuracy
  return a ? (a * 100).toFixed(0) + '%' : null
})

async function load() {
  error.value = null
  try {
    const resp = await fetch('/api/prediction')
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    data.value = await resp.json()
  } catch (e) {
    error.value = e.message
  }
}

function openMatch(match) {
  selected.value = match
}

onMounted(load)
</script>

<style scoped>
.header { padding: 24px 0 0; }
.title-row { display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }
h1 { font-size: 22px; letter-spacing: 0.5px; }
.meta { display: flex; gap: 8px; }
.champion-line { margin: 10px 0 16px; font-size: 15px; }
.champ { color: var(--gold); font-size: 17px; }
.dim { color: var(--text-dim); font-size: 13px; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); }
.tabs button {
  background: none; border: none; color: var(--text-dim);
  padding: 10px 18px; font-size: 14px; cursor: pointer;
  border-bottom: 2px solid transparent;
}
.tabs button.active { color: var(--gold); border-bottom-color: var(--gold); }
.tabs button:hover { color: var(--text); }
main { padding-top: 20px; }
.center-note { text-align: center; color: var(--text-dim); padding: 80px 0; }
.retry {
  margin-top: 12px; padding: 8px 24px; background: var(--bg-card);
  color: var(--text); border: 1px solid var(--border); border-radius: 6px; cursor: pointer;
}
</style>
