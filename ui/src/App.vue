<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import {
  Choices, CloudProvider, DownloadItem, GateRow, Overview, PortRow,
  Project, ServiceStatus, get, post,
} from "./api";

type ViewId = "overview" | "plan" | "projects" | "cloud" | "system" | "logs";
const NAV: { id: ViewId; ico: string; label: string }[] = [
  { id: "overview", ico: "◉", label: "Overview" },
  { id: "plan", ico: "▦", label: "Models & Plan" },
  { id: "projects", ico: "❖", label: "Projects" },
  { id: "cloud", ico: "☁", label: "Cloud" },
  { id: "system", ico: "⚙", label: "System" },
  { id: "logs", ico: "≡", label: "Logs" },
];

const ICON = "/icon.svg"; // served by lai at runtime - not a bundled asset
const view = ref<ViewId>("overview");
const o = ref<Overview | null>(null);
const services = ref<ServiceStatus[]>([]);
const downloads = ref<DownloadItem[]>([]);
const ports = ref<PortRow[]>([]);
const cloud = ref<CloudProvider[]>([]);
const projects = ref<Project[]>([]);
const candidates = ref<Record<string, string[]>>({});
const gateOut = ref<GateRow[]>([]);
const logText = ref("");
const logName = ref("");
const newStack = ref("");
const newPath = ref("");
const busy = reactive<Record<string, boolean>>({});
const toasts = ref<{ id: number; text: string; err: boolean }[]>([]);
let tid = 0;
let timer: number | undefined;

function toast(text: string, err = false): void {
  const id = ++tid;
  toasts.value.push({ id, text, err });
  setTimeout(() => (toasts.value = toasts.value.filter(t => t.id !== id)), 6000);
}

async function act(key: string, fn: () => Promise<unknown>, okMsg?: string): Promise<void> {
  busy[key] = true;
  try {
    await fn();
    if (okMsg) toast(okMsg);
    await refresh();
  } catch (e) {
    toast((e as { error?: string }).error ?? "failed", true);
  } finally {
    busy[key] = false;
  }
}

async function refresh(): Promise<void> {
  try {
    o.value = await get<Overview>("/api/overview");
    services.value = await get<ServiceStatus[]>("/api/status");
    downloads.value = (await get<{ items: DownloadItem[] }>("/api/downloads")).items;
    if (view.value === "system") ports.value = (await get<{ ports: PortRow[] }>("/api/ports")).ports;
    if (view.value === "cloud") cloud.value = (await get<{ providers: CloudProvider[] }>("/api/cloudcfg")).providers;
    if (view.value === "projects" || view.value === "overview")
      projects.value = (await get<{ projects: Project[] }>("/api/projects")).projects;
  } catch { /* server briefly busy - next tick catches up */ }
}

async function loadCandidates(): Promise<void> {
  candidates.value = (await get<{ candidates: Record<string, string[]> }>("/api/candidates")).candidates;
}

const hw = computed(() => o.value?.choices?.hardware);
const hwLine = computed(() => {
  const ch = o.value?.choices;
  if (!ch || !hw.value) return "no plan yet — pick a use case in Models & Plan";
  return `${ch.tier} · ${hw.value.gpus.map(g => g.name).join(", ") || "no GPU"} · ` +
    `${hw.value.vram_gb} GB VRAM · ${hw.value.ram_gb} GB RAM · ${ch.engine}` +
    (o.value?.remote ? ` · ⇄ ${o.value.remote.host}:${o.value.remote.port}` : "");
});
const upCount = computed(() => services.value.filter(s => s.up).length);
const dlTotal = computed(() => downloads.value.reduce((a, d) => a + d.expected_gb, 0));
const dlHave = computed(() =>
  downloads.value.reduce((a, d) => a + (d.done ? d.expected_gb : Math.min(d.have_gb, d.expected_gb)), 0));

const usecase = ref("general");
const ROLE_ORDER = ["coder", "thinker", "vision", "autocomplete", "embeddings"];

function svcUrl(name: string): string | null {
  const map: [string, (p: number) => string][] = [
    ["llama-swap", p => `http://localhost:${p}/ui`],
    ["qdrant", p => `http://localhost:${p}/dashboard`],
    ["openhands", p => `http://localhost:${p}`],
    ["open-webui", p => `http://localhost:${p}`],
    ["searxng", p => `http://localhost:${p}`],
  ];
  const m = name.match(/:(\d+)/);
  if (!m) return null;
  const port = Number(m[1]);
  const hit = map.find(([k]) => name.startsWith(k));
  return hit ? hit[1](port) : null;
}

async function setRole(role: string, model: string): Promise<void> {
  await act(`set-${role}`, async () => {
    try {
      await post("/api/set", { role, model });
    } catch (e) {
      const err = e as { error?: string; needs_force?: boolean };
      if (err.needs_force && confirm(`${err.error}\n\nForce it anyway?`)) {
        await post("/api/set", { role, model, force: true });
      } else throw e;
    }
  }, `${role} → ${model} (Apply regenerates the config)`);
}

async function gate(path: string, fix: boolean): Promise<void> {
  await act("gate", async () => {
    gateOut.value = (await post<{ results: GateRow[] }>("/api/gate", { path, fix })).results;
  });
}

async function loadLog(): Promise<void> {
  if (!logName.value && o.value?.logs.length) logName.value = o.value.logs[0];
  if (!logName.value) return;
  logText.value = (await get<{ text: string }>(`/api/logs?name=${logName.value}`)).text || "(empty)";
}

const useModel = reactive<Record<string, string>>({});

onMounted(async () => {
  await refresh();
  await loadCandidates();
  usecase.value = o.value?.choices?.usecase ?? "general";
  timer = window.setInterval(refresh, 3000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <div class="layout">
    <aside class="side">
      <div class="brand"><img :src="ICON" alt="" /><b>lai</b></div>
      <div v-for="n in NAV" :key="n.id" class="nav-item"
           :class="{ active: view === n.id }"
           @click="view = n.id; refresh(); if (n.id === 'logs') loadLog();">
        <span class="ico">{{ n.ico }}</span><span class="nav-label">{{ n.label }}</span>
      </div>
      <div class="side-foot">
        lai {{ o?.lai_version }}<br />catalog {{ o?.choices?.catalog_version ?? "—" }}<br />
        100% local · no telemetry
      </div>
    </aside>

    <main class="main">
      <div class="topbar">
        <span>{{ hwLine }}</span>
        <span style="flex:1"></span>
        <span class="pill" :class="{ ok: upCount > 0 }">{{ upCount }}/{{ services.length }} services</span>
        <span class="pill" :class="{ busy: o?.running.download }">{{ o?.running.download ? "downloading" : "downloads idle" }}</span>
        <span class="pill" :class="{ busy: o?.running.bench }">{{ o?.running.bench ? "benchmarking" : "bench idle" }}</span>
      </div>

      <div class="content" style="position:relative">
        <Transition name="view" mode="out-in">

          <!-- ============ OVERVIEW ============ -->
          <div v-if="view === 'overview'" key="overview" class="grid">
            <div class="card">
              <h3>Services</h3>
              <table><tbody>
                <tr v-for="s in services" :key="s.name">
                  <td><span class="dot" :class="{ up: s.up }"></span>{{ s.name }}</td>
                  <td class="dim">{{ s.up ? "up" : "down" }}</td>
                  <td style="text-align:right"><a v-if="s.up && svcUrl(s.name)" :href="svcUrl(s.name)!" target="_blank">open ↗</a></td>
                </tr>
              </tbody></table>
              <div class="row mt">
                <button class="primary" :disabled="busy.start" @click="act('start', () => post('/api/start'), 'stack started')">▶ Start</button>
                <button :disabled="busy.restart" @click="act('restart', () => post('/api/restart'), 'restarted')">↻ Restart</button>
                <button class="danger" :disabled="busy.stop" @click="act('stop', () => post('/api/stop'), 'stopped')">■ Stop</button>
              </div>
            </div>

            <div class="card">
              <h3>Model downloads · {{ dlHave.toFixed(1) }} / {{ dlTotal.toFixed(1) }} GB</h3>
              <table><tbody>
                <tr v-for="d in downloads" :key="d.id">
                  <td style="width:42%">{{ d.id }}</td>
                  <td><div class="bar"><i :class="{ indet: !d.done && o?.running.download && d.have_gb < 0.05 }"
                      :style="{ width: (d.done ? 100 : Math.min(99, d.have_gb / d.expected_gb * 100)) + '%' }"></i></div></td>
                  <td class="dim" style="width:104px;text-align:right">
                    {{ d.done ? "✓ done" : `${Math.min(99, Math.round(d.have_gb / d.expected_gb * 100))}% · ${d.expected_gb} GB` }}
                  </td>
                </tr>
              </tbody></table>
              <div class="row mt">
                <button class="primary" :disabled="o?.running.download" @click="act('dl', () => post('/api/download', { action: 'start' }), 'download started')">⇣ Start</button>
                <button :disabled="!o?.running.download" @click="act('dlp', () => post('/api/download', { action: 'pause' }), 'paused (resumable)')">⏸ Pause</button>
              </div>
              <div class="dim mt">Resumable across pauses, crashes, and reboots.</div>
            </div>

            <div class="card">
              <h3>Active models</h3>
              <table><tbody>
                <tr v-for="r in ROLE_ORDER" :key="r">
                  <td class="dim">{{ r }}</td>
                  <td>{{ o?.choices?.roles[r]?.model ?? "—" }}</td>
                  <td class="dim" style="text-align:right">{{ o?.choices?.roles[r]?.mode ?? "" }}</td>
                </tr>
              </tbody></table>
              <div class="dim mt" v-if="o?.last_quality">
                last quality run: {{ o.last_quality.model }} — {{ o.last_quality.score }}/{{ o.last_quality.total }}
              </div>
            </div>

            <div class="card">
              <h3>Benchmarks & terminal</h3>
              <div class="row">
                <button :disabled="o?.running.bench" @click="act('b1', () => post('/api/bench', { quality: false }), 'speed bench running')">Speed bench</button>
                <button :disabled="o?.running.bench" @click="act('b2', () => post('/api/bench', { quality: true }), 'quality bench running')">Quality bench</button>
              </div>
              <pre class="mt" style="max-height:130px">lai chat            # streaming terminal assistant
lai git review      # AI code review of your diff
lai docs search "q" # project documentation RAG
lai info            # one-screen status</pre>
            </div>
          </div>

          <!-- ============ PLAN ============ -->
          <div v-else-if="view === 'plan'" key="plan" class="grid">
            <div class="card wide">
              <h3>Use case & roles · tier {{ o?.choices?.tier ?? "—" }}</h3>
              <div class="row">
                <select v-model="usecase">
                  <option v-for="(d, id) in o?.usecases" :key="id" :value="id">{{ id }} — {{ d.label }}</option>
                </select>
                <button :disabled="busy.plan" @click="act('plan', async () => { await post('/api/plan', { usecase }); await loadCandidates(); }, 're-planned')">Re-plan</button>
                <button class="primary" :disabled="busy.cfg" @click="act('cfg', () => post('/api/config'), 'config regenerated — restart to apply')">Apply config</button>
              </div>
              <table class="mt">
                <thead><tr><th>role</th><th>model</th><th>runs as</th><th>ctx</th><th>size</th></tr></thead>
                <tbody>
                  <tr v-for="r in ROLE_ORDER" :key="r">
                    <td class="dim">{{ r }}</td>
                    <td>
                      <select :value="o?.choices?.roles[r]?.model ?? 'none'"
                              @change="setRole(r, ($event.target as HTMLSelectElement).value)">
                        <option value="none">(disabled)</option>
                        <option v-for="m in candidates[r] ?? []" :key="m" :value="m">{{ m }}</option>
                      </select>
                    </td>
                    <td class="dim">{{ o?.choices?.roles[r]?.mode ?? "—" }}</td>
                    <td class="dim">{{ o?.choices?.roles[r]?.ctx ?? "—" }}</td>
                    <td class="dim">{{ o?.choices?.roles[r] ? (o?.models_meta[o!.choices!.roles[r]!.model]?.disk_gb + " GB") : "" }}</td>
                  </tr>
                </tbody>
              </table>
              <div class="dim mt" v-if="o?.choices?.targets">
                healthy targets: prompt ≥ {{ o.choices.targets.pp }} t/s · generation ≥ {{ o.choices.targets.tg }} t/s
              </div>
            </div>
          </div>

          <!-- ============ PROJECTS ============ -->
          <div v-else-if="view === 'projects'" key="projects" class="grid">
            <div class="card wide">
              <h3>New project</h3>
              <div class="row">
                <select v-model="newStack">
                  <option v-for="(d, id) in o?.stacks" :key="id" :value="id">{{ id }} — {{ d.label }}</option>
                </select>
                <input v-model="newPath" placeholder="path, e.g. D:\projects\mytool" style="flex:1;min-width:200px" />
                <button class="primary" :disabled="busy.new" @click="act('new', () => post('/api/new', { stack: newStack, path: newPath }), 'project created — open it in VS Code')">Create</button>
              </div>
            </div>
            <div class="card wide">
              <h3>Projects</h3>
              <table><tbody>
                <tr v-for="p in projects" :key="p.path">
                  <td>{{ p.name }}</td>
                  <td class="dim">{{ p.stack }}</td>
                  <td>
                    <span v-if="p.last_gate" class="pill" :class="p.last_gate.fail ? 'bad' : 'ok'">
                      {{ p.last_gate.fail ? p.last_gate.fail + " fail" : "gate ok" }}{{ p.last_gate.warn ? " · " + p.last_gate.warn + " warn" : "" }}
                    </span>
                  </td>
                  <td style="text-align:right" class="row" >
                    <button @click="gate(p.path, false)">Gate</button>
                    <button @click="gate(p.path, true)">Fix</button>
                    <select :id="'sk-' + p.name" style="max-width:130px">
                      <option v-for="(d, s) in o?.skills" :key="s" :value="s" :title="d">{{ s }}</option>
                    </select>
                    <button @click="act('sk', () => post('/api/skill', { name: (document.getElementById('sk-' + p.name) as HTMLSelectElement).value, path: p.path }), 'skill installed')">+Skill</button>
                  </td>
                </tr>
                <tr v-if="!projects.length"><td class="dim">no projects yet — create one above (team config travels in the repo)</td></tr>
              </tbody></table>
              <table class="mt" v-if="gateOut.length"><tbody>
                <tr v-for="(g, i) in gateOut" :key="i">
                  <td style="width:80px"><span class="pill" :class="g.status === 'FAIL' ? 'bad' : g.status === 'WARN' ? '' : 'ok'">{{ g.status }}</span></td>
                  <td class="mono">{{ g.item }}</td>
                  <td class="dim">{{ g.detail }}</td>
                </tr>
              </tbody></table>
            </div>
          </div>

          <!-- ============ CLOUD ============ -->
          <div v-else-if="view === 'cloud'" key="cloud" class="grid">
            <div class="card wide dim">
              Local models are <b>always</b> the default. Cloud runs only when you explicitly pick a prefixed
              model (<span class="mono">or: / oa: / an:</span>) — and with the defaults below it stays token-lean
              (max_tokens 1024). Set a default per provider, then a bare prefix uses it.
            </div>
            <div class="card" v-for="p in cloud" :key="p.id">
              <h3>{{ p.id }} <span class="pill" :class="p.has_key ? 'ok' : ''">{{ p.has_key ? "key configured" : "no key" }}</span></h3>
              <div class="row">
                <input :placeholder="p.has_key ? 'replace API key…' : 'paste API key…'" type="password"
                       :id="'key-' + p.id" style="flex:1" />
                <button @click="act('ck', () => post('/api/cloudcfg', { action: 'add', provider: p.id, key: (document.getElementById('key-' + p.id) as HTMLInputElement).value }), 'key stored (gitignored)')">Save key</button>
                <button class="danger" v-if="p.has_key" @click="act('cr', () => post('/api/cloudcfg', { action: 'remove', provider: p.id }), 'key removed')">Remove</button>
              </div>
              <div class="row mt">
                <input v-model="useModel[p.id]" :placeholder="p.default_model || 'default model id…'" style="flex:1" />
                <button @click="act('cu', () => post('/api/cloudcfg', { action: 'use', provider: p.id, model: useModel[p.id] || p.default_model }), 'default model saved')">Set default</button>
              </div>
              <div class="dim mt" v-if="p.default_model">default: <span class="mono">{{ p.prefix }}: → {{ p.default_model }}</span> · {{ p.params }}</div>
              <table class="mt"><tbody>
                <tr v-for="r in p.recommended" :key="r.id" style="cursor:pointer" :title="'click to set as default'"
                    @click="useModel[p.id] = r.id">
                  <td class="mono">{{ r.id }}</td><td class="dim">{{ r.why }}</td>
                </tr>
              </tbody></table>
              <div class="dim mt">all models + live prices: <span class="mono">lai cloud models {{ p.id }}</span></div>
            </div>
          </div>

          <!-- ============ SYSTEM ============ -->
          <div v-else-if="view === 'system'" key="system" class="grid">
            <div class="card wide">
              <h3>Ports <span class="dim">(another app on a port? fix moves lai, never your app)</span></h3>
              <div class="row" style="margin-bottom:8px">
                <button class="primary" :disabled="busy.pfix" @click="act('pfix', async () => { const r = await post<{ moved: Record<string, number> }>('/api/ports', { action: 'fix' }); toast(Object.keys(r.moved).length ? 'moved: ' + JSON.stringify(r.moved) + ' — restart + lai docker to apply' : 'no conflicts'); })">Fix conflicts</button>
              </div>
              <table>
                <thead><tr><th>service</th><th>default</th><th>current</th><th>status</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="pr in ports" :key="pr.name">
                    <td class="mono">{{ pr.name }}</td>
                    <td class="dim">{{ pr.default }}</td>
                    <td><input :id="'port-' + pr.name" :value="pr.current" style="width:84px" /></td>
                    <td><span class="pill" :class="pr.status.includes('CONFLICT') ? 'bad' : pr.status.includes('lai') ? 'ok' : ''">{{ pr.status }}</span></td>
                    <td style="text-align:right"><button @click="act('ps', () => post('/api/ports', { action: 'set', name: pr.name, port: Number((document.getElementById('port-' + pr.name) as HTMLInputElement).value) }), pr.name + ' moved — restart/docker/ide to apply')">Set</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="card">
              <h3>Maintenance</h3>
              <div class="row">
                <button @click="act('verify', async () => { const r = await post<{ results: { id: string; status: string }[] }>('/api/verify'); toast(r.results.filter(x => x.status !== 'ok').length === 0 ? 'all catalog repos resolve ✓' : 'issues: ' + r.results.filter(x => x.status !== 'ok').map(x => x.id + '=' + x.status).join(', '), r.results.some(x => x.status === 'missing')); })">Verify catalog</button>
              </div>
              <div class="dim mt">engines: {{ Object.entries(o?.versions ?? {}).map(([k, v]) => `${k} ${v}`).join(" · ") || "not installed" }}</div>
              <div class="dim mt">update check: <span class="mono">lai upgrade</span> · catalog: <span class="mono">lai catalog --update</span></div>
            </div>
          </div>

          <!-- ============ LOGS ============ -->
          <div v-else key="logs" class="grid">
            <div class="card wide">
              <h3>Logs</h3>
              <div class="row" style="margin-bottom:10px">
                <select v-model="logName" @change="loadLog()">
                  <option v-for="l in o?.logs" :key="l" :value="l">{{ l }}</option>
                </select>
                <button @click="loadLog()">Refresh</button>
              </div>
              <pre style="max-height:460px">{{ logText || "select a log…" }}</pre>
            </div>
          </div>

        </Transition>
      </div>
    </main>

    <div class="toasts">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="{ err: t.err }">{{ t.text }}</div>
    </div>
  </div>
</template>
