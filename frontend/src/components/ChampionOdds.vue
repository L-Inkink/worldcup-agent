<template>
  <div class="card">
    <h3>夺冠概率分布 <span class="dim">（蒙特卡洛 {{ mc.n_sims }} 次模拟 · 固定种子可复现）</span></h3>
    <div class="bars">
      <div v-for="row in rows" :key="row.code" class="bar-row">
        <span class="team" :class="{ champ: row.code === champion }">
          {{ flag(row.code) }} {{ teams[row.code].name_zh }}
        </span>
        <div class="track">
          <div class="fill" :class="{ 'fill-champ': row.code === champion }"
               :style="{ width: Math.max(1.5, row.p * 100 / maxP * 100) + '%' }"></div>
        </div>
        <span class="val">{{ (row.p * 100).toFixed(1) }}%</span>
      </div>
    </div>
  </div>

  <div class="card table-card">
    <h3>各轮晋级概率 <span class="dim">（Top 12）</span></h3>
    <table>
      <tr><th class="tl">球队</th><th>进四强</th><th>进决赛</th><th>夺冠</th></tr>
      <tr v-for="row in rows.slice(0, 12)" :key="row.code">
        <td class="tl" :class="{ champ: row.code === champion }">
          {{ flag(row.code) }} {{ teams[row.code].name_zh }}
        </td>
        <td>{{ fmt(mc.p_semi[row.code]) }}</td>
        <td>{{ fmt(mc.p_final[row.code]) }}</td>
        <td class="bold">{{ fmt(row.p) }}</td>
      </tr>
    </table>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { flag } from '../flags.js'

const props = defineProps({
  mc: { type: Object, required: true },
  teams: { type: Object, required: true },
  champion: { type: String, required: true },
})

const rows = computed(() =>
  Object.entries(props.mc.p_champion).slice(0, 16)
    .map(([code, p]) => ({ code, p })))

const maxP = computed(() => Math.max(...rows.value.map(r => r.p)) * 100)

function fmt(v) {
  return v == null ? '—' : (v * 100).toFixed(1) + '%'
}
</script>

<style scoped>
.card { margin-bottom: 16px; }
h3 { font-size: 15px; margin-bottom: 16px; }
.dim { color: var(--text-dim); font-size: 12px; font-weight: 400; }
.bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.team { width: 130px; font-size: 13px; text-align: right; flex-shrink: 0; }
.team.champ { color: var(--gold); font-weight: 700; }
.track { flex: 1; height: 18px; background: #0b1320; border-radius: 4px; overflow: hidden; }
.fill { height: 100%; background: var(--blue); border-radius: 4px; transition: width 0.6s; }
.fill-champ { background: linear-gradient(90deg, var(--gold), #d4a63f); }
.val { width: 52px; font-size: 12.5px; color: var(--text-dim); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { color: var(--text-dim); font-weight: 400; padding: 6px; text-align: center; }
td { padding: 6px; text-align: center; border-top: 1px solid var(--border); }
.tl { text-align: left; }
.champ { color: var(--gold); font-weight: 700; }
.bold { font-weight: 700; }
</style>
