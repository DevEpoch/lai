<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import {
  CloudProvider, DownloadItem, GateRow, Overview, PortRow,
  Project, ServiceStatus, get, post,
} from "./api";
import { Lang, lang, t } from "./i18n";

type ViewId = "home" | "overview" | "plan" | "projects" | "cloud" | "system" | "logs";
const NAV: { id: ViewId; ico: string; label: string }[] = [
  { id: "home", ico: "⌂", label: "nav.home" },
  { id: "overview", ico: "◉", label: "nav.overview" },
  { id: "plan", ico: "▦", label: "nav.plan" },
  { id: "projects", ico: "❖", label: "nav.projects" },
  { id: "cloud", ico: "☁", label: "nav.cloud" },
  { id: "system", ico: "⚙", label: "nav.system" },
  { id: "logs", ico: "≡", label: "nav.logs" },
];
const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "fa", label: "فارسی" },
  { id: "ar", label: "العربية" },
];

const ICON = "/icon.svg"; // served by lai at runtime - not a bundled asset
const view = ref<ViewId>("home");
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
  if (!ch || !hw.value) return t("up.to.date");
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

// ---- Home (simple mode) ----
interface ChatMsg { role: "user" | "assistant"; content: string }
const chatMsgs = ref<ChatMsg[]>([]);
const chatInput = ref("");
const chatBusy = ref(false);
const swapUp = computed(() => services.value.some(s => s.name.startsWith("llama-swap") && s.up));
const allModelsDone = computed(() => downloads.value.length > 0 && downloads.value.every(d => d.done));
const homeState = computed<"setup" | "downloading" | "starting" | "ready">(() => {
  if (!o.value?.choices || (!downloads.value.length && !o.value.running.setup)) return "setup";
  if (o.value.running.download || o.value.running.setup || !allModelsDone.value) return "downloading";
  return swapUp.value ? "ready" : "starting";
});
const homePct = computed(() => dlTotal.value ? Math.min(99, Math.round(dlHave.value / dlTotal.value * 100)) : 0);
const HOME_KEY: Record<string, string> = {
  setup: "setup", downloading: "down", starting: "start", ready: "ready",
};

async function easySetup(): Promise<void> {
  await act("easy", () => post("/api/easy"), "Setting everything up — watch the progress here!");
}

async function sendChat(): Promise<void> {
  const text = chatInput.value.trim();
  if (!text || chatBusy.value) return;
  chatMsgs.value.push({ role: "user", content: text });
  chatInput.value = "";
  chatBusy.value = true;
  try {
    const r = await post<{ reply: string }>("/api/chat", {
      messages: chatMsgs.value.map(m => ({ role: m.role, content: m.content })).slice(-12),
    });
    chatMsgs.value.push({ role: "assistant", content: r.reply });
  } catch (e) {
    toast((e as { error?: string }).error ?? "chat failed", true);
  } finally {
    chatBusy.value = false;
  }
}

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
        <span class="ico">{{ n.ico }}</span><span class="nav-label">{{ t(n.label) }}</span>
      </div>
      <div class="side-foot">
        <select v-model="lang" style="margin-bottom:8px;width:100%">
          <option v-for="l in LANGS" :key="l.id" :value="l.id">{{ l.label }}</option>
        </select>
        <span class="mono">lai {{ o?.lai_version }} · {{ o?.choices?.catalog_version ?? "—" }}</span><br />
        {{ t("foot.local") }}
      </div>
    </aside>

    <main class="main">
      <div class="topbar">
        <span>{{ hwLine }}</span>
        <span style="flex:1"></span>
        <span class="pill" :class="{ ok: upCount > 0 }">{{ upCount }}/{{ services.length }} {{ t("top.services") }}</span>
        <span class="pill" :class="{ busy: o?.running.download }">{{ o?.running.download ? t("top.downloading") : t("top.dlidle") }}</span>
        <span class="pill" :class="{ busy: o?.running.bench }">{{ o?.running.bench ? t("top.bench") : t("top.benchidle") }}</span>
      </div>

      <div class="content" style="position:relative">
        <Transition name="view" mode="out-in">

          <!-- ============ HOME (simple mode) ============ -->
          <div v-if="view === 'home'" key="home" class="grid">
            <div class="card wide hero">
              <div class="hero-light" :class="homeState"></div>
              <div>
                <div class="hero-big">{{ t(`home.${HOME_KEY[homeState]}.big`) }}</div>
                <div class="dim">{{ t(`home.${HOME_KEY[homeState]}.small`) }}</div>
              </div>
              <div style="flex:1"></div>
              <button v-if="homeState === 'setup'" class="primary hero-btn" :disabled="busy.easy"
                      @click="easySetup()">{{ t("home.btn.setup") }}</button>
              <button v-else-if="homeState === 'starting'" class="primary hero-btn" :disabled="busy.start"
                      @click="act('start', () => post('/api/start'), '…')">{{ t("home.btn.start") }}</button>
            </div>

            <div v-if="homeState === 'downloading'" class="card wide">
              <h3>{{ t("home.progress") }} · {{ homePct }}%</h3>
              <div class="bar big"><i :style="{ width: homePct + '%' }"></i></div>
              <div class="dim mt">{{ dlHave.toFixed(1) }} {{ t("home.progress.note") }} {{ dlTotal.toFixed(1) }} {{ t("home.progress.note2") }}</div>
            </div>

            <div class="card wide">
              <h3>{{ t("home.chat.title") }}</h3>
              <div class="chatbox" v-if="chatMsgs.length">
                <div v-for="(m, i) in chatMsgs" :key="i" class="msg" :class="m.role">
                  <pre>{{ m.content }}</pre>
                </div>
                <div v-if="chatBusy" class="msg assistant dim">{{ t("home.chat.thinking") }}</div>
              </div>
              <div class="row mt">
                <input v-model="chatInput" :disabled="homeState !== 'ready'" style="flex:1"
                       :placeholder="homeState === 'ready' ? t('home.chat.ph.ready') : t('home.chat.ph.wait')"
                       @keydown.enter="sendChat()" />
                <button class="primary" :disabled="homeState !== 'ready' || chatBusy" @click="sendChat()">{{ t("btn.send") }}</button>
              </div>
              <div class="dim mt">{{ t("home.chat.note") }} <a :href="svcUrl('open-webui :3001') ?? 'http://localhost:3001'" target="_blank">Open WebUI ↗</a></div>
            </div>

            <div v-if="o?.updates && (o.updates.new_models.length || o.updates.catalog_newer)" class="card wide">
              <h3>{{ t("updates.title") }} ({{ o.updates.when.slice(0, 10) }})</h3>
              <div class="dim" v-if="o.updates.catalog_newer">{{ t("updates.catalog") }} <span class="mono">lai catalog --update</span></div>
              <table v-if="o.updates.new_models.length"><tbody>
                <tr v-for="m in o.updates.new_models.slice(0, 5)" :key="m.id">
                  <td class="mono">{{ m.id }}</td>
                  <td class="dim num">{{ m.downloads.toLocaleString() }} {{ t("updates.dl") }}</td>
                </tr>
              </tbody></table>
              <div class="dim mt">{{ t("updates.note") }} <span class="mono">lai refresh</span></div>
            </div>

            <div class="card">
              <h3>{{ t("home.what.title") }}</h3>
              <div class="dim">
                · {{ t("home.what.1") }}<br />
                · {{ t("home.what.2") }} <span class="mono">lai chat</span><br />
                · {{ t("home.what.3") }}<br />
                · {{ t("home.what.4") }}
              </div>
            </div>
            <div class="card">
              <h3>{{ t("home.priv.title") }}</h3>
              <div class="dim">{{ t("home.priv.body") }}</div>
            </div>
          </div>

          <!-- ============ OVERVIEW ============ -->
          <div v-else-if="view === 'overview'" key="overview" class="grid">
            <div class="card">
              <h3>{{ t("card.services") }}</h3>
              <table><tbody>
                <tr v-for="s in services" :key="s.name">
                  <td><span class="dot" :class="{ up: s.up }"></span>{{ s.name }}</td>
                  <td class="dim">{{ s.up ? t("svc.up") : t("svc.down") }}</td>
                  <td style="text-align:right"><a v-if="s.up && svcUrl(s.name)" :href="svcUrl(s.name)!" target="_blank">{{ t("open") }}</a></td>
                </tr>
              </tbody></table>
              <div class="row mt">
                <button class="primary" :disabled="busy.start" @click="act('start', () => post('/api/start'), 'stack started')">{{ t("btn.start") }}</button>
                <button :disabled="busy.restart" @click="act('restart', () => post('/api/restart'), 'restarted')">{{ t("btn.restart") }}</button>
                <button class="danger" :disabled="busy.stop" @click="act('stop', () => post('/api/stop'), 'stopped')">{{ t("btn.stop") }}</button>
              </div>
            </div>

            <div class="card">
              <h3>{{ t("card.downloads") }} · {{ dlHave.toFixed(1) }} / {{ dlTotal.toFixed(1) }} GB</h3>
              <table><tbody>
                <tr v-for="d in downloads" :key="d.id">
                  <td style="width:42%">{{ d.id }}</td>
                  <td><div class="bar"><i :class="{ indet: !d.done && o?.running.download && d.have_gb < 0.05 }"
                      :style="{ width: (d.done ? 100 : Math.min(99, d.have_gb / d.expected_gb * 100)) + '%' }"></i></div></td>
                  <td class="dim" style="width:104px;text-align:right">
                    {{ d.done ? t("dl.done") : `${Math.min(99, Math.round(d.have_gb / d.expected_gb * 100))}% · ${d.expected_gb} GB` }}
                  </td>
                </tr>
              </tbody></table>
              <div class="row mt">
                <button class="primary" :disabled="o?.running.download" @click="act('dl', () => post('/api/download', { action: 'start' }), 'download started')">{{ t("btn.dlstart") }}</button>
                <button :disabled="!o?.running.download" @click="act('dlp', () => post('/api/download', { action: 'pause' }), 'paused (resumable)')">{{ t("btn.dlpause") }}</button>
              </div>
              <div class="dim mt">{{ t("dl.resume") }}</div>
            </div>

            <div class="card">
              <h3>{{ t("card.models") }}</h3>
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
              <h3>{{ t("card.bench") }}</h3>
              <div class="row">
                <button :disabled="o?.running.bench" @click="act('b1', () => post('/api/bench', { quality: false }), 'speed bench running')">{{ t("btn.speed") }}</button>
                <button :disabled="o?.running.bench" @click="act('b2', () => post('/api/bench', { quality: true }), 'quality bench running')">{{ t("btn.quality") }}</button>
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
              <h3>{{ t("card.usecase") }} · tier {{ o?.choices?.tier ?? "—" }}</h3>
              <div class="row">
                <select v-model="usecase">
                  <option v-for="(d, id) in o?.usecases" :key="id" :value="id">{{ id }} — {{ d.label }}</option>
                </select>
                <button :disabled="busy.plan" @click="act('plan', async () => { await post('/api/plan', { usecase }); await loadCandidates(); }, 're-planned')">{{ t("btn.replan") }}</button>
                <button class="primary" :disabled="busy.cfg" @click="act('cfg', () => post('/api/config'), 'config regenerated — restart to apply')">{{ t("btn.apply") }}</button>
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
              <h3>{{ t("card.newproject") }}</h3>
              <div class="row">
                <select v-model="newStack">
                  <option v-for="(d, id) in o?.stacks" :key="id" :value="id">{{ id }} — {{ d.label }}</option>
                </select>
                <input v-model="newPath" :placeholder="t('ph.path')" style="flex:1;min-width:200px" />
                <button class="primary" :disabled="busy.new" @click="act('new', () => post('/api/new', { stack: newStack, path: newPath }), 'project created — open it in VS Code')">{{ t("btn.create") }}</button>
              </div>
            </div>
            <div class="card wide">
              <h3>{{ t("card.projects") }}</h3>
              <table><tbody>
                <tr v-for="p in projects" :key="p.path">
                  <td>{{ p.name }}</td>
                  <td class="dim">{{ p.stack }}</td>
                  <td>
                    <span v-if="p.last_gate" class="pill" :class="p.last_gate.fail ? 'bad' : 'ok'">
                      {{ p.last_gate.fail ? p.last_gate.fail + " fail" : "gate ok" }}{{ p.last_gate.warn ? " · " + p.last_gate.warn + " warn" : "" }}
                    </span>
                  </td>
                  <td style="text-align:right" class="row">
                    <button @click="gate(p.path, false)">{{ t("btn.gate") }}</button>
                    <button @click="gate(p.path, true)">{{ t("btn.fix") }}</button>
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
              {{ t("cloud.note") }}
            </div>
            <div class="card" v-for="p in cloud" :key="p.id">
              <h3>{{ p.id }} <span class="pill" :class="p.has_key ? 'ok' : ''">{{ p.has_key ? "key configured" : "no key" }}</span></h3>
              <div class="row">
                <input :placeholder="p.has_key ? 'replace API key…' : 'paste API key…'" type="password"
                       :id="'key-' + p.id" style="flex:1" />
                <button @click="act('ck', () => post('/api/cloudcfg', { action: 'add', provider: p.id, key: (document.getElementById('key-' + p.id) as HTMLInputElement).value }), 'key stored (gitignored)')">{{ t("btn.savekey") }}</button>
                <button class="danger" v-if="p.has_key" @click="act('cr', () => post('/api/cloudcfg', { action: 'remove', provider: p.id }), 'key removed')">{{ t("btn.remove") }}</button>
              </div>
              <div class="row mt">
                <input v-model="useModel[p.id]" :placeholder="p.default_model || 'default model id…'" style="flex:1" />
                <button @click="act('cu', () => post('/api/cloudcfg', { action: 'use', provider: p.id, model: useModel[p.id] || p.default_model }), 'default model saved')">{{ t("btn.setdefault") }}</button>
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
              <h3>{{ t("card.ports") }} <span class="dim">{{ t("ports.note") }}</span></h3>
              <div class="row" style="margin-bottom:8px">
                <button class="primary" :disabled="busy.pfix" @click="act('pfix', async () => { const r = await post<{ moved: Record<string, number> }>('/api/ports', { action: 'fix' }); toast(Object.keys(r.moved).length ? 'moved: ' + JSON.stringify(r.moved) + ' — restart + lai docker to apply' : 'no conflicts'); })">{{ t("btn.fixconf") }}</button>
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
              <h3>{{ t("card.maint") }}</h3>
              <div class="row">
                <button @click="act('verify', async () => { const r = await post<{ results: { id: string; status: string }[] }>('/api/verify'); toast(r.results.filter(x => x.status !== 'ok').length === 0 ? 'all catalog repos resolve ✓' : 'issues: ' + r.results.filter(x => x.status !== 'ok').map(x => x.id + '=' + x.status).join(', '), r.results.some(x => x.status === 'missing')); })">{{ t("btn.verify") }}</button>
              </div>
              <div class="dim mt">engines: {{ Object.entries(o?.versions ?? {}).map(([k, v]) => `${k} ${v}`).join(" · ") || "not installed" }}</div>
              <div class="dim mt">update check: <span class="mono">lai upgrade</span> · catalog: <span class="mono">lai catalog --update</span></div>
            </div>
          </div>

          <!-- ============ LOGS ============ -->
          <div v-else key="logs" class="grid">
            <div class="card wide">
              <h3>{{ t("card.logs") }}</h3>
              <div class="row" style="margin-bottom:10px">
                <select v-model="logName" @change="loadLog()">
                  <option v-for="l in o?.logs" :key="l" :value="l">{{ l }}</option>
                </select>
                <button @click="loadLog()">{{ t("btn.refresh") }}</button>
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
