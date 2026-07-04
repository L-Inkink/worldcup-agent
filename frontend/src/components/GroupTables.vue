<template>
  <div class="grid">
    <div v-for="(rows, g) in groups" :key="g" class="card group">
      <h3>{{ g }} 组</h3>
      <table>
        <tr><th class="tl">球队</th><th>赛</th><th>胜</th><th>平</th><th>负</th><th>净</th><th>分</th></tr>
        <tr v-for="r in rows" :key="r.code" :class="stateClass(r)">
          <td class="tl">{{ flag(r.code) }} {{ teams[r.code].name_zh }}</td>
          <td>{{ r.played }}</td><td>{{ r.won }}</td><td>{{ r.drawn }}</td>
          <td>{{ r.lost }}</td><td>{{ r.gd > 0 ? '+' + r.gd : r.gd }}</td>
          <td class="pts">{{ r.points }}</td>
        </tr>
      </table>
      <div class="mini-matches">
        <span v-for="m in matchesOf(g)" :key="m.id" class="mini">
          {{ flag(m.home) }} {{ m.score[0] }}:{{ m.score[1] }} {{ flag(m.away) }}
        </span>
      </div>
    </div>
  </div>
  <p class="note">前两名直接晋级 32 强（高亮绿色）；成绩最好的 8 个第三名同样晋级（高亮蓝色）。</p>
</template>

<script setup>
import { flag } from '../flags.js'

const props = defineProps({
  groups: { type: Object, required: true },
  teams: { type: Object, required: true },
  matches: { type: Array, required: true },
})

// 晋级的 8 个第三名（来自淘汰赛名单：B/D/E/F/I/J/K/L 组）
const THIRD_ADVANCED = new Set(['BIH', 'PAR', 'ECU', 'SWE', 'SEN', 'ALG', 'COD', 'GHA'])

function stateClass(r) {
  if (r.pos <= 2) return 'adv-direct'
  if (r.pos === 3 && THIRD_ADVANCED.has(r.code)) return 'adv-third'
  return 'out'
}

function matchesOf(g) {
  return props.matches.filter(m => m.group === g)
}
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}
h3 { font-size: 14px; color: var(--gold); margin-bottom: 10px; letter-spacing: 1px; }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th { color: var(--text-dim); font-weight: 400; padding: 3px 4px; text-align: center; font-size: 11px; }
td { padding: 4px; text-align: center; border-top: 1px solid var(--border); }
.tl { text-align: left; }
.pts { font-weight: 700; color: var(--gold); }
.adv-direct td:first-child { color: var(--green); }
.adv-third td:first-child { color: var(--blue); }
.out td:first-child { color: var(--text-dim); }
.mini-matches { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.mini {
  font-size: 11px; background: #0b1320; padding: 2px 7px; border-radius: 4px;
  color: var(--text-dim);
}
.note { margin-top: 14px; font-size: 12px; color: var(--text-dim); }
</style>
