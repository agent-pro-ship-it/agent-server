// Antigravity Cloud Web Client & Engine Orchestrator
let SERVER_URL = localStorage.getItem("AGENT_SERVER_URL") || "https://agent-master-server.onrender.com";
if (SERVER_URL.endsWith("/")) SERVER_URL = SERVER_URL.slice(0, -1);

let activeProject = null;
let projects = [];
let conversations = JSON.parse(localStorage.getItem("ANTIGRAVITY_CHATS") || "{}");

// DOM Elements
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const btnToggleSidebar = document.getElementById("btnToggleSidebar");
const projectsList = document.getElementById("projectsList");
const btnNewChat = document.getElementById("btnNewChat");
const btnCreateProjectModal = document.getElementById("btnCreateProjectModal");
const btnRefreshProjects = document.getElementById("btnRefreshProjects");
const crumbProject = document.getElementById("crumbProject");
const crumbTask = document.getElementById("crumbTask");
const chatFeed = document.getElementById("chatFeed");
const taskInput = document.getElementById("taskInput");
const btnSend = document.getElementById("btnSend");
const btnMic = document.getElementById("btnMic");
const btnLiveChatToggle = document.getElementById("btnLiveChatToggle");
const btnOpenGeminiLive = document.getElementById("btnOpenGeminiLive");
const btnCloseGeminiLive = document.getElementById("btnCloseGeminiLive");
const voiceStatusBar = document.getElementById("voiceStatusBar");
const voiceStatusText = document.getElementById("voiceStatusText");
const micLevelFill = document.getElementById("micLevelFill");
const micDeviceSelect = document.getElementById("micDeviceSelect");
const btnSelectModel = document.getElementById("btnSelectModel");
const currentModelName = document.getElementById("currentModelName");
const modelDropdown = document.getElementById("modelDropdown");
const btnAttach = document.getElementById("btnAttach");
const attachDropdown = document.getElementById("attachDropdown");
const filePicker = document.getElementById("filePicker");
const btnHeaderTerminal = document.getElementById("btnHeaderTerminal");
const btnHeaderBrowser = document.getElementById("btnHeaderBrowser");
const btnToolOpenTerminal = document.getElementById("btnToolOpenTerminal");
const btnToolOpenBrowser = document.getElementById("btnToolOpenBrowser");
const modalBrowser = document.getElementById("modalBrowser");
const btnCloseBrowser = document.getElementById("btnCloseBrowser");
const browserUrlInput = document.getElementById("browserUrlInput");
const btnBrowserGo = document.getElementById("btnBrowserGo");
const browserIframe = document.getElementById("browserIframe");
const btnBrowserExternal = document.getElementById("btnBrowserExternal");
const btnBrowserReload = document.getElementById("btnBrowserReload");

// Files Drawer Elements
const btnToggleFiles = document.getElementById("btnToggleFiles");
const filesDrawer = document.getElementById("filesDrawer");
const btnCloseFiles = document.getElementById("btnCloseFiles");
const filesListContainer = document.getElementById("filesListContainer");
const filesCountBadge = document.getElementById("filesCountBadge");
const drawerProjectTitle = document.getElementById("drawerProjectTitle");

// Modals
const modalCreateProject = document.getElementById("modalCreateProject");
const btnCloseCreateProj = document.getElementById("btnCloseCreateProj");
const btnConfirmCreateProj = document.getElementById("btnConfirmCreateProj");
const newProjNameInput = document.getElementById("newProjNameInput");
const newProjTaskInput = document.getElementById("newProjTaskInput");

const modalFileViewer = document.getElementById("modalFileViewer");
const btnCloseFileViewer = document.getElementById("btnCloseFileViewer");
const fileViewerTitle = document.getElementById("fileViewerTitle");
const fileViewerCode = document.getElementById("fileEditorArea") || document.getElementById("fileViewerCode");

const modalTerminal = document.getElementById("modalTerminal");
const btnOpenTerminal = document.getElementById("btnOpenTerminal");
const btnCloseTerminal = document.getElementById("btnCloseTerminal");

const modalSettings = document.getElementById("modalSettings");
const btnOpenSettings = document.getElementById("btnOpenSettings");
const btnCloseSettings = document.getElementById("btnCloseSettings");
const settingServerUrl = document.getElementById("settingServerUrl");
const btnSaveServerUrl = document.getElementById("btnSaveServerUrl");

// Voice Recording State (Dual: MediaRecorder + Web Speech API)
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let recognition = null;
let webSpeechTranscript = "";

// 1. Fetch & Render Projects from Server
async function fetchProjects() {
  try {
    const res = await fetch(`${SERVER_URL}/api/projects`);
    if (res.ok) {
      const data = await res.json();
      projects = data.projects || [];
    }
  } catch (e) {
    console.warn("Could not fetch remote projects, using cache:", e);
  }

  const fallbackNames = {
    "agent": "Агент",
    "recruiter-club": "сайт Recruiter I Club",
    "resume-optimizer": "парсер и резюме",
    "online-crm": "проект онлайн срм",
    "doc-automation": "прога для договор...",
    "recruiter-project": "Recruiter проект",
    "site-landing": "сайт",
    "telegram-bot": "telegram bot",
    "crm-debug": "отладка срм антиг..."
  };
  if (projects && projects.length > 0) {
    projects.forEach(p => {
      if (fallbackNames[p.id] && (!p.name || p.name.includes("\ufffd") || p.name.includes("?") || p.name.length <= 1)) {
        p.name = fallbackNames[p.id];
      }
    });
  }

  if (!projects || projects.length === 0) {
    projects = [
      { id: "agent", name: "Агент", task: "Бесплатный Сервер Для Антигравити", time: "2m", active: true },
      { id: "recruiter-club", name: "сайт Recruiter I Club", task: "Premium B2B SaaS Architecture", time: "53m", active: false },
      { id: "resume-optimizer", name: "парсер и резюме", task: "Free AI Resume Optimizer", time: "1h", active: false },
      { id: "online-crm", name: "проект онлайн срм", task: "Разработка Полнофункциональной CRM", time: "7h", active: false }
    ];
  }

  const savedActiveId = localStorage.getItem("ACTIVE_PROJECT_ID");
  activeProject = projects.find(p => p.id === savedActiveId) || projects[0];
  renderProjects();
  selectProject(activeProject.id, false);
}

function renderProjects() {
  projectsList.innerHTML = "";
  projects.forEach((proj) => {
    const item = document.createElement("div");
    const isActive = activeProject && proj.id === activeProject.id;
    item.className = `project-item ${isActive ? "active" : ""}`;
    item.onclick = () => selectProject(proj.id);

    item.innerHTML = `
      <div class="project-top-row">
        <span class="folder-icon">📁</span>
        <span class="project-name">${escapeHtml(proj.name)}</span>
        <button class="btn-proj-rename" title="Переименовать проект" onclick="event.stopPropagation(); promptRenameProject('${proj.id}')">✏️</button>
      </div>
      <div class="project-sub-row">
        <span class="project-preview">${escapeHtml(proj.task || "Antigravity Project")}</span>
        <span class="project-time">${escapeHtml(proj.time || "")}</span>
      </div>
    `;
    projectsList.appendChild(item);
  });
}

async function promptRenameProject(projId) {
  const proj = projects.find(p => p.id === projId);
  if (!proj) return;
  const newName = prompt("Введите новое название проекта / папки:", proj.name);
  if (!newName || !newName.trim() || newName.trim() === proj.name) return;

  const trimmed = newName.trim();
  proj.name = trimmed;
  if (activeProject && activeProject.id === projId) {
    activeProject.name = trimmed;
    if (crumbProject) crumbProject.innerText = trimmed;
  }
  renderProjects();

  try {
    await fetch(`${SERVER_URL}/api/projects/${projId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: trimmed })
    });
  } catch (e) {
    console.warn("Error renaming project on server:", e);
  }
}

async function selectProject(projId, reloadFiles = true) {
  activeProject = projects.find(p => p.id === projId) || projects[0];
  localStorage.setItem("ACTIVE_PROJECT_ID", activeProject.id);

  crumbProject.innerText = activeProject.name;
  crumbTask.innerText = activeProject.task || "Папка проекта";
  drawerProjectTitle.innerText = `Файлы: ${activeProject.name}`;

  renderProjects();
  loadProjectConversation(activeProject.id);

  if (reloadFiles) {
    await loadProjectFiles(activeProject.id);
  }

  // Close mobile sidebar
  sidebar.classList.remove("open");
  sidebarBackdrop.classList.remove("active");
}

// 2. Load Project Files from Server
async function loadProjectFiles(projId) {
  try {
    const res = await fetch(`${SERVER_URL}/api/projects/${projId}/files`);
    if (res.ok) {
      const data = await res.json();
      const files = data.files || [];
      filesCountBadge.innerText = files.length;
      renderFilesList(files);
      return;
    }
  } catch (e) {
    console.warn("Could not load project files:", e);
  }
  filesCountBadge.innerText = "0";
  filesListContainer.innerHTML = '<p style="color:var(--text-muted); font-size:13px;">В папке проекта пока нет созданных файлов.</p>';
}

function renderFilesList(files) {
  filesListContainer.innerHTML = "";
  if (files.length === 0) {
    filesListContainer.innerHTML = '<p style="color:var(--text-muted); font-size:13px;">Папка пуста. Отправьте агенту задачу создать файл!</p>';
    return;
  }

  files.forEach(f => {
    const row = document.createElement("div");
    row.className = "file-row";
    row.onclick = () => openFileContent(activeProject.id, f.path);
    row.innerHTML = `
      <div class="file-info-left">
        <span>📄</span>
        <span class="file-name">${escapeHtml(f.path)}</span>
      </div>
      <span class="file-size">${formatBytes(f.size_bytes)}</span>
    `;
    filesListContainer.appendChild(row);
  });
}

async function openFileContent(projId, filePath) {
  if (typeof openFileInEditor === "function") {
    return openFileInEditor(filePath);
  }
}

// 3. Create New Project in Cloud
async function createNewProject(name, task) {
  try {
    const res = await fetch(`${SERVER_URL}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, task: task })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.project) {
        projects.unshift(data.project);
        renderProjects();
        selectProject(data.project.id);
        appendAssistantMessage(`✔ Создана новая облачная папка проекта **${name}** в \`/app/workspace/${data.project.id}/\` и синхронизирована с облаком Storj 25GB! Все задачи и скрипты теперь исполняются внутри этой папки.`);
        return;
      }
    }
  } catch (e) {
    alert("Ошибка связи с сервером при создании проекта.");
  }
}

btnConfirmCreateProj.addEventListener("click", () => {
  const name = newProjNameInput.value.trim();
  const task = newProjTaskInput.value.trim();
  if (!name) {
    alert("Введите название проекта.");
    return;
  }
  modalCreateProject.classList.remove("active");
  createNewProject(name, task);
  newProjNameInput.value = "";
  newProjTaskInput.value = "";
});

btnNewChat.addEventListener("click", () => {
  modalCreateProject.classList.add("active");
  newProjNameInput.focus();
});

btnCreateProjectModal.addEventListener("click", () => {
  modalCreateProject.classList.add("active");
  newProjNameInput.focus();
});

btnCloseCreateProj.addEventListener("click", () => {
  modalCreateProject.classList.remove("active");
});

btnRefreshProjects.addEventListener("click", fetchProjects);

// 4. Chat Feed Handling
function loadProjectConversation(projId) {
  chatFeed.innerHTML = "";
  const history = conversations[projId] || [];

  if (history.length === 0) {
    appendAssistantMessage(`
<div class="antigravity-quote">
Привет! Я — настоящий автономный агент Google Antigravity, работающий под вашей подпиской Google Pro на облачном сервере Render.
</div>

Вы находитесь в папке проекта: **${escapeHtml(activeProject.name)}**.

* Все создаваемые файлы сохраняются в рабочую папку проекта и в хранилище Storj 25GB.
* Доступен запуск терминальных команд, написание кода и полный цикл разработки.
* Вы можете надиктовать задачу голосом через красную кнопку микрофона внизу!
`);
  } else {
    history.forEach(msg => {
      if (msg.role === "user") appendUserMessage(msg.text, false);
      else appendAssistantMessage(msg.html, false);
    });
  }
}

function appendUserMessage(text, save = true) {
  const div = document.createElement("div");
  div.className = "msg-user";
  div.innerText = text;
  chatFeed.appendChild(div);
  chatFeed.scrollTop = chatFeed.scrollHeight;

  if (save && activeProject) {
    if (!conversations[activeProject.id]) conversations[activeProject.id] = [];
    conversations[activeProject.id].push({ role: "user", text: text });
    localStorage.setItem("ANTIGRAVITY_CHATS", JSON.stringify(conversations));
  }
  return div;
}

function appendAssistantMessage(rawContent, save = true) {
  const div = document.createElement("div");
  div.className = "msg-assistant";
  div.innerHTML = formatMarkdown(rawContent);

  const actions = document.createElement("div");
  actions.className = "msg-actions";
  actions.innerHTML = `
    <button class="action-icon-btn" title="Скопировать" onclick="copyText(this)">❐</button>
    <button class="action-icon-btn" title="Хороший ответ">👍</button>
    <button class="action-icon-btn" title="Плохой ответ">👎</button>
  `;
  div.appendChild(actions);

  chatFeed.appendChild(div);
  chatFeed.scrollTop = chatFeed.scrollHeight;

  if (save && activeProject) {
    if (!conversations[activeProject.id]) conversations[activeProject.id] = [];
    conversations[activeProject.id].push({ role: "assistant", html: rawContent });
    localStorage.setItem("ANTIGRAVITY_CHATS", JSON.stringify(conversations));
  }
  return div;
}

window.copyText = function(btn) {
  const msgDiv = btn.closest(".msg-assistant");
  const clone = msgDiv.cloneNode(true);
  const acts = clone.querySelector(".msg-actions");
  if (acts) acts.remove();
  navigator.clipboard.writeText(clone.innerText.trim());
  btn.innerText = "✓";
  setTimeout(() => { btn.innerText = "❐"; }, 1500);
};

// 5. Send Task to Antigravity Engine
async function sendTask(customText = null, isVoice = false) {
  const text = (typeof customText === "string" ? customText : taskInput.value).trim();
  if (!text) return;

  if (typeof customText !== "string") {
    taskInput.value = "";
    taskInput.style.height = "auto";
  }

  // Direct Terminal Command Interception from Chat ($ command, ! command, /sh command)
  if (text.startsWith("$") || text.startsWith("!") || text.startsWith("/sh ") || text.startsWith("cmd:")) {
    let cmd = text;
    if (cmd.startsWith("$") || cmd.startsWith("!")) cmd = cmd.slice(1).trim();
    else if (cmd.startsWith("/sh ")) cmd = cmd.slice(4).trim();
    else if (cmd.startsWith("cmd:")) cmd = cmd.slice(4).trim();

    appendUserMessage(text);
    await runTerminalCommandInChat(cmd);
    return;
  }

  // Direct Browser Interception from Chat (/browser, открой браузер, можешь открыть браузер, etc.)
  const lower = text.toLowerCase();
  if (lower === "/browser" || lower.startsWith("/browser ") ||
      lower.includes("открой браузер") || lower.includes("открыть браузер") ||
      lower.includes("запусти браузер") || lower.includes("покажи браузер") ||
      lower.includes("можешь открыть браузер") || lower.includes("открой сайт")) {
    appendUserMessage(text);
    let targetUrl = "https://accounts.google.com";
    const urlMatch = text.match(/https?:\/\/[^\s]+/i);
    if (urlMatch) targetUrl = urlMatch[0];
    else if (lower.includes("github")) targetUrl = "https://github.com/login";
    else if (lower.includes("telegram")) targetUrl = "https://web.telegram.org";
    else if (lower.includes("render")) targetUrl = "https://dashboard.render.com";
    else if (lower.includes("google")) targetUrl = "https://accounts.google.com";
    else if (lower.startsWith("/browser ")) {
      const param = text.slice(9).trim();
      if (param) targetUrl = param.startsWith("http") ? param : "https://" + param;
    }

    openBrowserModal(targetUrl);
    appendAssistantMessage(`
      <div class="terminal-chat-card success">
        <div class="terminal-chat-header">
          <span class="terminal-chat-title">🌐 Встроенный браузер Antigravity: <code>${escapeHtml(targetUrl)}</code></span>
          <span class="terminal-badge badge-ok">Браузер запущен</span>
        </div>
        <div class="terminal-chat-output" style="color:#e2e8f0;">
          Окно браузера открыто прямо на экране! Вы можете войти в аккаунт (Google OAuth, GitHub, Telegram), ввести данные или поручить мне веб-автоматизацию на странице.
        </div>
        <div class="terminal-chat-actions">
          <button class="msg-action-btn" onclick="openBrowserModal('${escapeHtml(targetUrl)}')">🔍 Развернуть окно браузера</button>
        </div>
      </div>
    `);
    return;
  }

  appendUserMessage(text);

  // Live Antigravity Process Card with Animated Steps
  const loadingBubble = appendAssistantMessage(`
    <div class="antigravity-process-card">
      <div class="process-header">
        <span class="process-spinner">✦</span>
        <span class="process-title">Google Antigravity выполняет задачу...</span>
      </div>
      <div class="process-steps">
        <div class="process-step active">
          <span class="step-icon">💭</span>
          <span>Анализ контекста и планирование действий</span>
          <span class="step-status">Выполняется...</span>
        </div>
        <div class="process-step">
          <span class="step-icon">⚡</span>
          <span>Выполнение в рабочей среде проекта</span>
          <span class="step-status">Ожидание...</span>
        </div>
        <div class="process-step">
          <span class="step-icon">☁️</span>
          <span>Синхронизация файлов в Storj 25GB</span>
          <span class="step-status">Ожидание...</span>
        </div>
      </div>
    </div>
  `, false);

  try {
    const historyList = (activeProject && conversations[activeProject.id]) ?
      conversations[activeProject.id].slice(-6).map(m => ({
        role: m.role,
        text: m.text || (m.html ? m.html.replace(/<[^>]*>/g, '').trim() : '')
      })) : [];

    const res = await fetch(`${SERVER_URL}/api/task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: text,
        project_id: activeProject ? activeProject.id : null,
        voice_mode: isVoice || isContinuousLiveVoiceActive,
        history: historyList
      })
    });

    if (!res.ok) {
      loadingBubble.innerHTML = "❌ Ошибка сервера Render. Проверьте статус подключения в Settings.";
      return;
    }

    const data = await res.json();
    loadingBubble.remove();

    const explanationText = data.explanation || "Задача выполнена.";
    const terminalOutput = (data.terminal_log || data.stdout || "").trim();
    const hasTerminalOutput = terminalOutput.length > 0 && terminalOutput !== explanationText.trim();

    const processAccordion = `
    <details class="antigravity-process-accordion" open>
      <summary>
        <span class="sparkle" style="color:#2563eb;">✦</span>
        <span>Ход выполнения Antigravity</span>
        <span class="process-summary-badge">✓ Завершено</span>
      </summary>
      <div class="process-details-body">
        <div class="process-step done">
          <span class="step-icon">💭</span>
          <span>Анализ задачи и планирование</span>
          <span class="step-status" style="background:#dcfce7;color:#15803d;">✓ Готово</span>
        </div>
        <div class="process-step done">
          <span class="step-icon">⚡</span>
          <span>Выполнение в рабочей среде</span>
          <span class="step-status" style="background:#dcfce7;color:#15803d;">✓ Готово</span>
        </div>
        ${data.cloud_synced_files && data.cloud_synced_files.length > 0 ? `
        <div class="process-step done">
          <span class="step-icon">☁️</span>
          <span>Синхронизировано в Storj 25GB: ${data.cloud_synced_files.length} файлов</span>
          <span class="step-status" style="background:#dcfce7;color:#15803d;">✓ Загружено</span>
        </div>
        ` : ''}
        ${hasTerminalOutput ? `
        <details class="terminal-drawer">
          <summary>▸ Вывод терминала (${terminalOutput.split('\n').length} строк)</summary>
          <pre><code>${escapeHtml(terminalOutput)}</code></pre>
        </details>
        ` : ''}
      </div>
    </details>
    `;

    // Check if the assistant requested to open the browser
    const browserTagMatch = explanationText.match(/\[OPEN_BROWSER(?::\s*([^\]]+))?\]/i);
    let browserCardHtml = "";
    if (browserTagMatch) {
      const targetUrl = browserTagMatch[1] ? browserTagMatch[1].trim() : "https://accounts.google.com";
      explanationText = explanationText.replace(/\[OPEN_BROWSER(?::\s*[^\]]+)?\]/gi, '').trim();
      browserCardHtml = `
        <div class="terminal-chat-card success" style="margin-top:10px;">
          <div class="terminal-chat-header">
            <span class="terminal-chat-title">🌐 Встроенный браузер: <code>${escapeHtml(targetUrl)}</code></span>
            <span class="terminal-badge badge-ok">Браузер открыт</span>
          </div>
          <div class="terminal-chat-output" style="color:#e2e8f0;">
            Окно встроенного браузера открыто. Вы можете войти в аккаунт или поручить агенту веб-автоматизацию.
          </div>
          <div class="terminal-chat-actions">
            <button class="msg-action-btn" onclick="openBrowserModal('${escapeHtml(targetUrl)}')">🔍 Развернуть окно браузера</button>
          </div>
        </div>
      `;
      openBrowserModal(targetUrl);
    }

    appendAssistantMessage(processAccordion + formatMarkdown(explanationText) + browserCardHtml);
    if (activeProject) loadProjectFiles(activeProject.id);

    // If voice reply was returned, play it directly
    if (data.voice_audio_base64) {
      playBotVoiceAudio(data.voice_audio_base64);
    }

  } catch (err) {
    loadingBubble.innerHTML = "❌ Ошибка соединения с сервером. Попробуйте еще раз.";
  }
}

async function runTerminalCommandInChat(cmd) {
  const loadingBubble = appendAssistantMessage(`
    <div class="terminal-chat-card">
      <div class="terminal-chat-header">
        <span class="terminal-chat-title">⚡ Терминал: <code>${escapeHtml(cmd)}</code></span>
        <span class="terminal-badge" style="background:#3b82f6; color:#fff;">Выполняется...</span>
      </div>
      <div class="terminal-chat-output" style="color:#94a3b8;"><span class="process-spinner">✦</span> Запуск команды на сервере в каталоге проекта...</div>
    </div>
  `, false);

  try {
    const res = await fetch(`${SERVER_URL}/api/terminal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command: cmd,
        project_id: activeProject ? activeProject.id : null
      })
    });

    const data = await res.json();
    const isSuccess = data.exit_code === 0;
    const output = (data.stdout || "") + (data.stderr ? (data.stdout ? "\n" : "") + data.stderr : "");
    const safeOutput = escapeHtml(output.trim() || "(Команда завершилась без текстового вывода)");

    loadingBubble.innerHTML = `
      <div class="terminal-chat-card ${isSuccess ? 'success' : 'error'}">
        <div class="terminal-chat-header">
          <span class="terminal-chat-title">⚡ Терминал: <code>${escapeHtml(cmd)}</code></span>
          <span class="terminal-badge ${isSuccess ? 'badge-ok' : 'badge-err'}">Код: ${data.exit_code}</span>
        </div>
        <pre class="terminal-chat-output">${safeOutput}</pre>
        <div class="terminal-chat-actions">
          <button class="msg-action-btn" onclick="navigator.clipboard.writeText(this.closest('.terminal-chat-card').querySelector('pre').innerText); this.innerText='✓ Скопировано'; setTimeout(()=>this.innerText='❐ Копировать', 1500)">❐ Копировать вывод</button>
        </div>
      </div>
    `;

    if (activeProject) loadProjectFiles(activeProject.id);

  } catch (err) {
    loadingBubble.innerHTML = `
      <div class="terminal-chat-card error">
        <div class="terminal-chat-header">
          <span class="terminal-chat-title">❌ Ошибка выполнения: <code>${escapeHtml(cmd)}</code></span>
          <span class="terminal-badge badge-err">Ошибка сети</span>
        </div>
        <div class="terminal-chat-output" style="color:#f87171;">${escapeHtml(err.message || String(err))}</div>
      </div>
    `;
  }
}

btnSend.addEventListener("click", () => sendTask());
taskInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendTask();
  }
});

taskInput.addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = (this.scrollHeight) + "px";
});

// Tools (+) Popup Menu Toggle & Actions
const toolsPopup = document.getElementById("toolsPopup");

if (btnAttach && toolsPopup) {
  btnAttach.addEventListener("click", (e) => {
    e.stopPropagation();
    const isHidden = toolsPopup.style.display === "none" || !toolsPopup.style.display;
    toolsPopup.style.display = isHidden ? "block" : "none";
  });

  document.addEventListener("click", (e) => {
    if (toolsPopup && !toolsPopup.contains(e.target) && e.target !== btnAttach) {
      toolsPopup.style.display = "none";
    }
  });

  toolsPopup.querySelectorAll(".tool-popup-item[data-cmd]").forEach(item => {
    item.addEventListener("click", () => {
      const cmd = item.getAttribute("data-cmd");
      if (cmd && taskInput) {
        taskInput.value = cmd;
        taskInput.focus();
        toolsPopup.style.display = "none";
      }
    });
  });

  const btnToolAttachFile = document.getElementById("btnToolAttachFile");
  if (btnToolAttachFile && filePicker) {
    btnToolAttachFile.addEventListener("click", () => {
      toolsPopup.style.display = "none";
      filePicker.click();
    });
  }
}

// Project Renaming Handlers (Breadcrumb & Header)
const btnRenameProject = document.getElementById("btnRenameProject");
if (btnRenameProject) {
  btnRenameProject.addEventListener("click", (e) => {
    e.stopPropagation();
    if (activeProject) promptRenameProject(activeProject.id);
  });
}
if (crumbProject) {
  crumbProject.style.cursor = "pointer";
  crumbProject.addEventListener("click", () => {
    if (activeProject) promptRenameProject(activeProject.id);
  });
}

// 6. Robust Hardware Voice Engine with Live VU Level Meter & Multi-Mic Selection
// (micLevelFill and micDeviceSelect declared at top of file)

let currentBotAudio = null;
let isContinuousLiveVoiceActive = false;
let mediaStream = null;
let speechRecognizer = null;
let audioCtx = null;
let analyserNode = null;
let micSourceNode = null;
let vuAnimationFrameId = null;

let isUserSpeakingNow = false;
let speechStartMs = 0;
let silenceStartMs = 0;
let liveTranscribedText = "";

function stopBotVoiceAudio() {
  if (currentBotAudio) {
    try {
      currentBotAudio.pause();
      currentBotAudio.currentTime = 0;
    } catch(e) {}
    currentBotAudio = null;
  }
}

function playBotVoiceAudio(base64Mp3) {
  stopBotVoiceAudio();
  try {
    currentBotAudio = new Audio("data:audio/mp3;base64," + base64Mp3);
    currentBotAudio.onended = () => {
      currentBotAudio = null;
      if (isContinuousLiveVoiceActive) {
        updateVoiceStatusUI("🎙 Слушаю вас... Говорите в микрофон");
      }
    };
    currentBotAudio.play().catch(err => {
      console.warn("Audio autoplay blocked:", err);
    });
    updateVoiceStatusUI("🔊 Antigravity говорит (Dmitry Studio)...");
  } catch (err) {
    console.warn("Could not play voice audio:", err);
  }
}

function updateVoiceStatusUI(text, isRec = false) {
  if (voiceStatusText) voiceStatusText.innerText = text;
  if (voiceStatusBar) voiceStatusBar.style.display = isContinuousLiveVoiceActive ? "flex" : "none";
  if (btnMic) {
    if (isRec) btnMic.classList.add("recording");
    else btnMic.classList.remove("recording");
  }
}

async function populateMicDevices() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter(d => d.kind === "audioinput");
    if (micDeviceSelect) {
      const currentVal = micDeviceSelect.value;
      micDeviceSelect.innerHTML = "";
      if (audioInputs.length > 1) {
        micDeviceSelect.style.display = "inline-block";
        audioInputs.forEach((dev, idx) => {
          const opt = document.createElement("option");
          opt.value = dev.deviceId;
          opt.innerText = dev.label || `Микрофон ${idx + 1}`;
          if (dev.deviceId === currentVal) opt.selected = true;
          micDeviceSelect.appendChild(opt);
        });
      } else {
        micDeviceSelect.style.display = "none";
      }
    }
  } catch(e) {
    console.warn("Device enumeration error:", e);
  }
}

if (micDeviceSelect) {
  micDeviceSelect.addEventListener("change", async () => {
    if (isContinuousLiveVoiceActive) {
      await stopLiveVoiceMode();
      await startLiveVoiceMode();
    }
  });
}

function handleMicError(err) {
  let msg = "Не удалось получить доступ к микрофону:\n\n";
  if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
    msg += "1. В браузере (Chrome/Edge): нажмите на значок замочка слева в адресной строке и включите 'Микрофон'.\n" +
           "2. В Windows: откройте «Параметры Windows» -> «Конфиденциальность» -> «Микрофон» и убедитесь, что включен доступ для браузера.";
  } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
    msg += "Микрофон не обнаружен на ноутбуке. Подключите гарнитуру или проверьте подключение в диспетчере звука.";
  } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
    msg += "Микрофон занят другой программой (Zoom, Discord, Telegram, Skype). Закройте их и повторите попытку.";
  } else {
    msg += (err.message || err.name);
  }
  alert(msg);
  updateVoiceStatusUI("❌ Микрофон недоступен");
}

async function toggleLiveVoiceMode() {
  if (isContinuousLiveVoiceActive) {
    stopLiveVoiceMode();
  } else {
    await startLiveVoiceMode();
  }
}

async function startLiveVoiceMode() {
  if (isDictating) {
    await stopDictationMode();
  }
  stopBotVoiceAudio();
  isContinuousLiveVoiceActive = true;

  if (btnOpenGeminiLive) {
    btnOpenGeminiLive.classList.add("active");
    btnOpenGeminiLive.title = "Выключить живой голосовой диалог";
  }
  if (btnLiveChatToggle) {
    btnLiveChatToggle.classList.add("active");
    btnLiveChatToggle.title = "Выключить живой голосовой диалог";
  }
  updateVoiceStatusUI("🔴 Подключение к микрофону...");

  // 1. Request hardware microphone stream
  try {
    const selectedDeviceId = (micDeviceSelect && micDeviceSelect.value) ? micDeviceSelect.value : null;
    const audioConstraints = {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    };
    if (selectedDeviceId) {
      audioConstraints.deviceId = { exact: selectedDeviceId };
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
    } catch(primaryErr) {
      console.warn("Primary mic constraints failed, trying basic audio:true", primaryErr);
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    
    // Refresh device list with granted labels
    await populateMicDevices();

  } catch(err) {
    console.error("Microphone getUserMedia failed completely:", err);
    stopLiveVoiceMode();
    handleMicError(err);
    return;
  }

  // 2. Real-time Web Audio API Hardware Volume Meter & Speech Energy Detector
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!audioCtx || audioCtx.state === "closed") {
      audioCtx = new AudioContextClass();
    }
    if (audioCtx.state === "suspended") {
      await audioCtx.resume();
    }

    analyserNode = audioCtx.createAnalyser();
    analyserNode.fftSize = 512;
    analyserNode.smoothingTimeConstant = 0.25;

    micSourceNode = audioCtx.createMediaStreamSource(mediaStream);
    micSourceNode.connect(analyserNode);

    runAudioMeterLoop();
  } catch(audioCtxErr) {
    console.warn("Web Audio VU meter init error (recording still works):", audioCtxErr);
  }

  // 3. Start MediaRecorder
  audioChunks = [];
  try {
    let options = {};
    if (typeof MediaRecorder !== "undefined") {
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) options = { mimeType: 'audio/webm;codecs=opus' };
      else if (MediaRecorder.isTypeSupported('audio/webm')) options = { mimeType: 'audio/webm' };
      else if (MediaRecorder.isTypeSupported('audio/mp4')) options = { mimeType: 'audio/mp4' };
    }
    mediaRecorder = new MediaRecorder(mediaStream, options);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(250);
  } catch(recErr) {
    console.warn("MediaRecorder start error:", recErr);
  }

  // 4. Parallel Web Speech API for real-time live preview typing
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    try {
      speechRecognizer = new SpeechRecognition();
      speechRecognizer.lang = "ru-RU";
      speechRecognizer.continuous = true;
      speechRecognizer.interimResults = true;

      speechRecognizer.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let i = 0; i < event.results.length; ++i) {
          if (event.results[i].isFinal) final += event.results[i][0].transcript + " ";
          else interim += event.results[i][0].transcript;
        }
        const text = (final + interim).trim();
        if (text) {
          liveTranscribedText = text;
          taskInput.value = text;
          taskInput.style.height = "auto";
          taskInput.style.height = (taskInput.scrollHeight) + "px";
          updateVoiceStatusUI("🎙 " + text, true);
        }
      };

      speechRecognizer.onerror = (e) => {
        console.warn("SpeechRecognition preview notice:", e.error);
      };

      speechRecognizer.onend = () => {
        if (isContinuousLiveVoiceActive && speechRecognizer) {
          try { speechRecognizer.start(); } catch(e) {}
        }
      };

      speechRecognizer.start();
    } catch(e) {
      console.warn("Web Speech start exception:", e);
    }
  }

  updateVoiceStatusUI("🎙 Слушаю вас... Говорите в микрофон");
}

function runAudioMeterLoop() {
  if (!isContinuousLiveVoiceActive || !analyserNode) return;

  const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
  analyserNode.getByteFrequencyData(dataArray);

  let sum = 0;
  for (let i = 0; i < dataArray.length; i++) {
    sum += dataArray[i];
  }
  const avgVolume = sum / dataArray.length;
  const percent = Math.min(100, Math.round((avgVolume / 120) * 100));

  // Update hardware VU meter visually
  if (micLevelFill) {
    micLevelFill.style.width = percent + "%";
    if (percent > 15) micLevelFill.style.background = "#10b981"; // Active green
    else micLevelFill.style.background = "#9ca3af"; // Idle gray
  }

  // Voice Activity Detection (VAD) via real audio energy
  const now = Date.now();
  if (avgVolume > 16) {
    // BARGE-IN: User is speaking! Immediately silence any bot audio!
    stopBotVoiceAudio();

    if (!isUserSpeakingNow) {
      isUserSpeakingNow = true;
      speechStartMs = now;
      silenceStartMs = 0;
      updateVoiceStatusUI("🎙 Слышу ваш голос...", true);
    } else {
      silenceStartMs = 0;
    }
  } else {
    // Below threshold (silence)
    if (isUserSpeakingNow) {
      if (silenceStartMs === 0) {
        silenceStartMs = now;
      } else if (now - silenceStartMs > 900) {
        // 900ms silence detected after speech -> User finished speaking!
        isUserSpeakingNow = false;
        silenceStartMs = 0;
        onUserFinishedUtterance();
      }
    }
  }

  vuAnimationFrameId = requestAnimationFrame(runAudioMeterLoop);
}

async function onUserFinishedUtterance() {
  updateVoiceStatusUI("⏳ Обрабатываю речь...", false);

  const capturedText = liveTranscribedText.trim();
  liveTranscribedText = "";

  if (capturedText.length > 1) {
    taskInput.value = "";
    taskInput.style.height = "auto";
    updateVoiceStatusUI("💭 Antigravity думает...", false);
    await sendTask(capturedText, true);
    return;
  }

  // If live Web Speech transcript was empty, fallback to recorded chunks via Gemini STT
  if (audioChunks.length > 0 && mediaRecorder) {
    const currentChunks = [...audioChunks];
    audioChunks = [];
    const mime = mediaRecorder.mimeType || "audio/webm";
    const audioBlob = new Blob(currentChunks, { type: mime });

    if (audioBlob.size > 800) {
      try {
        const formData = new FormData();
        formData.append("file", audioBlob, "speech.webm");
        const resp = await fetch(`${SERVER_URL}/api/voice-transcribe`, {
          method: "POST",
          body: formData
        });
        if (resp.ok) {
          const resJson = await resp.json();
          const text = (resJson.text || "").trim();
          if (text && text !== "NONE") {
            taskInput.value = "";
            taskInput.style.height = "auto";
            updateVoiceStatusUI("💭 Antigravity думает...", false);
            await sendTask(text, true);
            return;
          }
        }
      } catch(err) {
        console.warn("Cloud transcribe fallback error:", err);
      }
    }
  }

  if (isContinuousLiveVoiceActive) {
    updateVoiceStatusUI("🎙 Слушаю вас... Говорите в микрофон");
  }
}

function stopLiveVoiceMode() {
  isContinuousLiveVoiceActive = false;
  isUserSpeakingNow = false;
  stopBotVoiceAudio();

  if (vuAnimationFrameId) {
    cancelAnimationFrame(vuAnimationFrameId);
    vuAnimationFrameId = null;
  }

  if (micSourceNode) {
    try { micSourceNode.disconnect(); } catch(e) {}
    micSourceNode = null;
  }

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try { mediaRecorder.stop(); } catch(e) {}
  }

  if (mediaStream) {
    try { mediaStream.getTracks().forEach(t => t.stop()); } catch(e) {}
    mediaStream = null;
  }

  if (speechRecognizer) {
    try { speechRecognizer.stop(); } catch(e) {}
    speechRecognizer = null;
  }

  if (btnOpenGeminiLive) {
    btnOpenGeminiLive.classList.remove("active");
    btnOpenGeminiLive.title = "Включить живой голосовой диалог";
  }
  if (btnLiveChatToggle) {
    btnLiveChatToggle.classList.remove("active");
    btnLiveChatToggle.title = "Живой голосовой диалог с Antigravity (Live-режим)";
  }
  if (!isDictating) {
    if (btnMic) {
      btnMic.classList.remove("recording");
      btnMic.classList.remove("live-active");
    }
    if (voiceStatusBar) {
      voiceStatusBar.style.display = "none";
    }
    if (micLevelFill) {
      micLevelFill.style.width = "0%";
    }
  }
}

// ========================================================
// SINGLE-TURN VOICE DICTATION CONTROLLER (INTO CHAT INPUT)
// ========================================================
let isDictating = false;
let dictationStream = null;
let dictationAudioCtx = null;
let dictationAnalyser = null;
let dictationMicSource = null;
let dictationVuAnimId = null;
let dictationSpeechRec = null;
let dictationMediaRec = null;
let dictationChunks = [];
let dictationBaseText = "";
let dictationLastCaptured = "";
let dictationTimerInterval = null;
let dictationSeconds = 0;

async function toggleDictationMode() {
  if (isContinuousLiveVoiceActive) {
    stopLiveVoiceMode();
  }
  if (isDictating) {
    await stopDictationMode();
  } else {
    await startDictationMode();
  }
}

async function startDictationMode() {
  if (isContinuousLiveVoiceActive) {
    stopLiveVoiceMode();
  }
  stopBotVoiceAudio();
  isDictating = true;

  if (btnMic) {
    btnMic.classList.add("recording");
    btnMic.title = "Остановить запись и вставить текст";
  }

  // Pre-fill base text if user already typed something
  dictationBaseText = (taskInput.value || "").trim();
  if (dictationBaseText.length > 0) dictationBaseText += " ";
  dictationLastCaptured = "";
  dictationChunks = [];
  dictationSeconds = 0;

  updateVoiceStatusUI("🔴 Запись 0:00 | Говорите в микрофон...", true);
  if (voiceStatusBar) voiceStatusBar.style.display = "flex";

  // Start visual timer for clear recording awareness
  clearInterval(dictationTimerInterval);
  dictationTimerInterval = setInterval(() => {
    dictationSeconds++;
    const m = Math.floor(dictationSeconds / 60);
    const s = String(dictationSeconds % 60).padStart(2, "0");
    const prefix = `🔴 Запись ${m}:${s} | `;
    if (voiceStatusText) {
      voiceStatusText.innerText = prefix + (dictationLastCaptured ? "🎙 " + dictationLastCaptured : "Говорите в микрофон...");
    }
  }, 1000);

  // 1. Hardware Microphone Stream
  try {
    const selectedDeviceId = (micDeviceSelect && micDeviceSelect.value) ? micDeviceSelect.value : null;
    const constraints = {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    };
    if (selectedDeviceId) constraints.deviceId = { exact: selectedDeviceId };

    try {
      dictationStream = await navigator.mediaDevices.getUserMedia({ audio: constraints });
    } catch (e1) {
      console.warn("Dictation constraints fallback to audio:true", e1);
      dictationStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    await populateMicDevices();
  } catch (err) {
    console.error("Dictation getUserMedia failed:", err);
    await stopDictationMode();
    handleMicError(err);
    return;
  }

  // 2. Hardware VU Meter for visual feedback
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!dictationAudioCtx || dictationAudioCtx.state === "closed") {
      dictationAudioCtx = new AudioContextClass();
    }
    if (dictationAudioCtx.state === "suspended") {
      await dictationAudioCtx.resume();
    }
    dictationAnalyser = dictationAudioCtx.createAnalyser();
    dictationAnalyser.fftSize = 256;
    dictationMicSource = dictationAudioCtx.createMediaStreamSource(dictationStream);
    dictationMicSource.connect(dictationAnalyser);

    function runDictationMeter() {
      if (!isDictating || !dictationAnalyser) return;
      const dataArr = new Uint8Array(dictationAnalyser.frequencyBinCount);
      dictationAnalyser.getByteFrequencyData(dataArr);
      let sum = 0;
      for (let i = 0; i < dataArr.length; i++) sum += dataArr[i];
      const avg = sum / dataArr.length;
      const pct = Math.min(100, Math.round((avg / 110) * 100));
      if (micLevelFill) {
        micLevelFill.style.width = pct + "%";
        micLevelFill.style.background = pct > 12 ? "#10b981" : "#9ca3af";
      }
      dictationVuAnimId = requestAnimationFrame(runDictationMeter);
    }
    runDictationMeter();
  } catch (vuErr) {
    console.warn("Dictation VU init error:", vuErr);
  }

  // 3. Web Speech Recognition for instant live streaming transcription
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    try {
      dictationSpeechRec = new SpeechRecognition();
      dictationSpeechRec.lang = "ru-RU";
      dictationSpeechRec.continuous = true;
      dictationSpeechRec.interimResults = true;

      dictationSpeechRec.onresult = (evt) => {
        let interim = "";
        let final = "";
        for (let i = 0; i < evt.results.length; i++) {
          if (evt.results[i].isFinal) final += evt.results[i][0].transcript + " ";
          else interim += evt.results[i][0].transcript;
        }
        const spoken = (final + interim).trim();
        if (spoken) {
          dictationLastCaptured = spoken;
          taskInput.value = dictationBaseText + spoken;
          taskInput.style.height = "auto";
          taskInput.style.height = taskInput.scrollHeight + "px";
          const m = Math.floor(dictationSeconds / 60);
          const s = String(dictationSeconds % 60).padStart(2, "0");
          if (voiceStatusText) voiceStatusText.innerText = `🔴 ${m}:${s} | 🎙 ` + spoken;
        }
      };

      dictationSpeechRec.onerror = (e) => {
        console.warn("Dictation speechRec error:", e.error);
      };

      // Auto-rearm on speech pauses so long dictations don't break
      dictationSpeechRec.onend = () => {
        if (isDictating && dictationSpeechRec) {
          try { dictationSpeechRec.start(); } catch(e) {}
        }
      };

      dictationSpeechRec.start();
    } catch (recErr) {
      console.warn("Dictation SpeechRec start error:", recErr);
    }
  }

  // 4. MediaRecorder audio backup for Gemini cloud transcribe
  try {
    let opts = {};
    if (typeof MediaRecorder !== "undefined") {
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) opts = { mimeType: 'audio/webm;codecs=opus' };
      else if (MediaRecorder.isTypeSupported('audio/webm')) opts = { mimeType: 'audio/webm' };
      else if (MediaRecorder.isTypeSupported('audio/mp4')) opts = { mimeType: 'audio/mp4' };
    }
    dictationMediaRec = new MediaRecorder(dictationStream, opts);
    dictationMediaRec.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) dictationChunks.push(e.data);
    };
    dictationMediaRec.start(250);
  } catch (mErr) {
    console.warn("Dictation MediaRecorder error:", mErr);
  }
}

async function stopDictationMode() {
  if (!isDictating) return;
  isDictating = false;

  clearInterval(dictationTimerInterval);
  dictationTimerInterval = null;

  if (btnMic) {
    btnMic.classList.remove("recording");
    btnMic.title = "Голосовой ввод (нажмите для диктовки)";
  }

  if (dictationVuAnimId) {
    cancelAnimationFrame(dictationVuAnimId);
    dictationVuAnimId = null;
  }

  if (dictationMicSource) {
    try { dictationMicSource.disconnect(); } catch(e) {}
    dictationMicSource = null;
  }

  if (dictationSpeechRec) {
    try { dictationSpeechRec.stop(); } catch(e) {}
    dictationSpeechRec = null;
  }

  const chunksToTranscribe = [...dictationChunks];
  dictationChunks = [];

  if (dictationMediaRec && dictationMediaRec.state !== "inactive") {
    try { dictationMediaRec.stop(); } catch(e) {}
  }

  if (dictationStream) {
    try { dictationStream.getTracks().forEach(t => t.stop()); } catch(e) {}
    dictationStream = null;
  }

  if (micLevelFill) micLevelFill.style.width = "0%";

  // Explicit processing indicator
  updateVoiceStatusUI("⏳ Обработка аудио... Расшифровка нейросетью Gemini Flash-Lite...", false);
  if (voiceStatusBar) voiceStatusBar.style.display = "flex";

  // If Web Speech API didn't produce text, fallback to Gemini Cloud Transcribe
  if (!dictationLastCaptured && chunksToTranscribe.length > 0) {
    const mime = (dictationMediaRec && dictationMediaRec.mimeType) || "audio/webm";
    const audioBlob = new Blob(chunksToTranscribe, { type: mime });
    if (audioBlob.size > 500) {
      try {
        const formData = new FormData();
        formData.append("file", audioBlob, "dictation.webm");
        const resp = await fetch(`${SERVER_URL}/api/voice-transcribe`, {
          method: "POST",
          body: formData
        });
        if (resp.ok) {
          const resJson = await resp.json();
          const cloudText = (resJson.text || "").trim();
          if (cloudText && cloudText !== "NONE") {
            taskInput.value = dictationBaseText + cloudText;
            taskInput.style.height = "auto";
            taskInput.style.height = taskInput.scrollHeight + "px";
          }
        }
      } catch (err) {
        console.warn("Cloud transcribe fallback error:", err);
      }
    }
  }

  updateVoiceStatusUI("✅ Текст готов!", false);
  setTimeout(() => {
    if (!isContinuousLiveVoiceActive && !isDictating) {
      if (voiceStatusBar) voiceStatusBar.style.display = "none";
    }
  }, 1600);

  taskInput.focus();
}

// Wire Voice and Live Buttons
if (btnMic) {
  btnMic.addEventListener("click", (e) => {
    e.preventDefault();
    toggleDictationMode();
  });
}

if (btnLiveChatToggle) {
  btnLiveChatToggle.addEventListener("click", (e) => {
    e.preventDefault();
    toggleLiveVoiceMode();
  });
}

if (btnOpenGeminiLive) {
  btnOpenGeminiLive.addEventListener("click", (e) => {
    e.preventDefault();
    toggleLiveVoiceMode();
  });
}

// ========================================================
// TERMINAL & CLOUD BROWSER MODAL HANDLERS
// ========================================================
function openTerminalModal() {
  if (modalTerminal) {
    const frame = document.getElementById("terminalFrame");
    if (frame && (!frame.src || frame.src === "about:blank")) {
      frame.src = `${SERVER_URL}/terminal/`;
    }
    modalTerminal.classList.add("active");
  }
}

if (btnHeaderTerminal) btnHeaderTerminal.addEventListener("click", openTerminalModal);
if (btnToolOpenTerminal) btnToolOpenTerminal.addEventListener("click", () => {
  if (toolsPopup) toolsPopup.style.display = "none";
  openTerminalModal();
});
if (btnOpenTerminal) btnOpenTerminal.addEventListener("click", openTerminalModal);

let browserWs = null;
const browserCanvas = document.getElementById("browserStreamCanvas");
const browserLoader = document.getElementById("browserStreamLoader");
const browserStatusText = document.getElementById("browserStreamStatusText");
const btnBrowserPopup = document.getElementById("btnBrowserPopup");
const btnBrowserAgentView = document.getElementById("btnBrowserAgentView");
const btnBannerOpenAuth = document.getElementById("btnBannerOpenAuth");
const browserSecurityBanner = document.getElementById("browserSecurityBanner");
const browserScreenshotView = document.getElementById("browserScreenshotView");
const browserScreenshotImg = document.getElementById("browserScreenshotImg");
const browserAgentOverlay = document.getElementById("browserAgentOverlay");
const browserAgentText = document.getElementById("browserAgentText");
const btnBrowserBack = document.getElementById("btnBrowserBack");
const btnBrowserForward = document.getElementById("btnBrowserForward");

function openBrowserModal(rawUrl = null) {
  if (modalBrowser) {
    modalBrowser.classList.add("active");
    const targetUrl = rawUrl || (browserUrlInput ? browserUrlInput.value : "") || "https://www.google.com";
    if (browserUrlInput) browserUrlInput.value = targetUrl;
    connectBrowserStream(targetUrl);
  }
}

function connectBrowserStream(initialUrl = null) {
  if (browserWs && browserWs.readyState === WebSocket.OPEN) {
    if (initialUrl) {
      sendBrowserAction({ type: "navigate", url: initialUrl });
    }
    return;
  }

  if (browserLoader) browserLoader.style.display = "flex";
  if (browserStatusText) browserStatusText.innerText = "Подключение к облачному Chromium...";

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = SERVER_URL.replace(/^https?:\/\//, "");
  const wsUrl = `${protocol}//${host}/browser/ws`;

  try {
    browserWs = new WebSocket(wsUrl);
  } catch(e) {
    console.warn("WebSocket init error:", e);
    if (browserStatusText) browserStatusText.innerText = "Ошибка соединения";
    return;
  }

  browserWs.onopen = () => {
    if (browserStatusText) browserStatusText.innerText = "Инициализация сессии Chromium...";
    if (initialUrl) {
      sendBrowserAction({ type: "navigate", url: initialUrl });
    }
  };

  browserWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "frame" && data.data && browserCanvas) {
        if (browserLoader && browserLoader.style.display !== "none") {
          browserLoader.style.display = "none";
        }
        const img = new Image();
        img.onload = () => {
          const ctx = browserCanvas.getContext("2d");
          ctx.drawImage(img, 0, 0, browserCanvas.width, browserCanvas.height);
        };
        img.src = "data:image/jpeg;base64," + data.data;

        if (data.url && browserUrlInput && document.activeElement !== browserUrlInput) {
          browserUrlInput.value = data.url;
        }
        if (data.url && (data.url.includes("accounts.google.com") || data.url.includes("signin/rejected"))) {
          if (browserSecurityBanner) browserSecurityBanner.style.display = "flex";
        } else {
          if (browserSecurityBanner) browserSecurityBanner.style.display = "none";
        }
      } else if (data.type === "navigated") {
        if (data.url && browserUrlInput && document.activeElement !== browserUrlInput) {
          browserUrlInput.value = data.url;
        }
        if (data.url && (data.url.includes("accounts.google.com") || data.url.includes("signin/rejected"))) {
          if (browserSecurityBanner) browserSecurityBanner.style.display = "flex";
        } else {
          if (browserSecurityBanner) browserSecurityBanner.style.display = "none";
        }
      } else if (data.type === "error") {
        if (browserStatusText) browserStatusText.innerText = `Ошибка: ${data.message}`;
      }
    } catch(err) {
      console.warn("Browser WS message error:", err);
    }
  };

  browserWs.onclose = () => {
    if (browserLoader) {
      browserLoader.style.display = "flex";
      if (browserStatusText) browserStatusText.innerText = "Сессия браузера закрыта. Нажмите ↻ для перезапуска.";
    }
  };

  browserWs.onerror = (e) => {
    console.warn("Browser WS error:", e);
    if (browserStatusText) browserStatusText.innerText = "Не удалось подключиться к Chromium на сервере";
  };
}

function sendBrowserAction(actionObj) {
  if (browserWs && browserWs.readyState === WebSocket.OPEN) {
    browserWs.send(JSON.stringify(actionObj));
  }
}

// Canvas user input
if (browserCanvas) {
  function handleCanvasClick(clientX, clientY) {
    const rect = browserCanvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const scaleX = browserCanvas.width / rect.width;
    const scaleY = browserCanvas.height / rect.height;
    const x = Math.round((clientX - rect.left) * scaleX);
    const y = Math.round((clientY - rect.top) * scaleY);
    sendBrowserAction({ type: "click", x, y });
  }

  browserCanvas.addEventListener("mousedown", (e) => {
    e.preventDefault();
    handleCanvasClick(e.clientX, e.clientY);
  });

  browserCanvas.addEventListener("touchstart", (e) => {
    if (e.touches && e.touches.length > 0) {
      e.preventDefault();
      const touch = e.touches[0];
      handleCanvasClick(touch.clientX, touch.clientY);
    }
  }, { passive: false });

  browserCanvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    sendBrowserAction({ type: "scroll", deltaX: Math.round(e.deltaX), deltaY: Math.round(e.deltaY) });
  }, { passive: false });
}

// Keyboard typing into remote Chromium
window.addEventListener("keydown", (e) => {
  if (!modalBrowser || !modalBrowser.classList.contains("active")) return;
  if (document.activeElement === browserUrlInput) return; // Allow URL bar editing

  if (e.key === "Backspace" || e.key === "Enter" || e.key === "Tab" || e.key === "Escape" || e.key.startsWith("Arrow")) {
    e.preventDefault();
    sendBrowserAction({ type: "press", key: e.key });
  } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    sendBrowserAction({ type: "type", text: e.key });
  }
});

function openSecureAuthPopup(rawUrl = null) {
  let targetUrl = rawUrl || (browserUrlInput ? browserUrlInput.value : "") || "https://accounts.google.com";
  if (targetUrl.includes("signin/rejected") || targetUrl.includes("rejected?")) {
    targetUrl = "https://accounts.google.com";
  }
  const w = 620;
  const h = 720;
  const left = Math.max(0, Math.round((window.screen.width - w) / 2));
  const top = Math.max(0, Math.round((window.screen.height - h) / 2));
  window.open(targetUrl, "AntigravitySecureAuth", `width=${w},height=${h},top=${top},left=${left},resizable=yes,scrollbars=yes`);
}

function navigateToBrowserUrl(rawUrl = null) {
  let url = (rawUrl || (browserUrlInput ? browserUrlInput.value : "")).trim();
  if (!url) return;
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    url = "https://" + url;
  }
  if (browserUrlInput) browserUrlInput.value = url;
  if (browserWs && browserWs.readyState === WebSocket.OPEN) {
    sendBrowserAction({ type: "navigate", url: url });
  } else {
    connectBrowserStream(url);
  }
}

async function loadAgentBrowserScreenshot(targetUrl = null) {
  const url = targetUrl || (browserUrlInput ? browserUrlInput.value : "");
  if (!url) return;

  if (browserAgentOverlay) {
    browserAgentOverlay.style.display = "flex";
    if (browserAgentText) browserAgentText.innerText = "Серверный агент загружает страницу...";
  }

  try {
    const res = await fetch(`${SERVER_URL}/api/browser/navigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();
    if (data.screenshot_base64 && browserScreenshotImg && browserScreenshotView) {
      browserScreenshotImg.src = "data:image/jpeg;base64," + data.screenshot_base64;
      browserScreenshotView.style.display = "flex";
      if (browserCanvas) browserCanvas.style.display = "none";
      if (data.url && browserUrlInput) browserUrlInput.value = data.url;
    }
  } catch(e) {
    console.warn("Agent browser error:", e);
  } finally {
    if (browserAgentOverlay) browserAgentOverlay.style.display = "none";
  }
}

if (btnHeaderBrowser) btnHeaderBrowser.addEventListener("click", () => openBrowserModal());
if (btnToolOpenBrowser) btnToolOpenBrowser.addEventListener("click", () => {
  if (toolsPopup) toolsPopup.style.display = "none";
  openBrowserModal();
});
if (btnCloseBrowser) btnCloseBrowser.addEventListener("click", () => {
  modalBrowser.classList.remove("active");
  if (browserWs) {
    try { browserWs.close(); } catch(e) {}
    browserWs = null;
  }
});
if (btnBrowserGo) btnBrowserGo.addEventListener("click", () => navigateToBrowserUrl());
if (btnBrowserPopup) btnBrowserPopup.addEventListener("click", () => openSecureAuthPopup());
if (btnBannerOpenAuth) btnBannerOpenAuth.addEventListener("click", () => openSecureAuthPopup());
if (btnBrowserAgentView) btnBrowserAgentView.addEventListener("click", () => loadAgentBrowserScreenshot());

if (btnBrowserBack) {
  btnBrowserBack.addEventListener("click", () => {
    sendBrowserAction({ type: "back" });
  });
}

if (btnBrowserForward) {
  btnBrowserForward.addEventListener("click", () => {
    sendBrowserAction({ type: "forward" });
  });
}

if (btnBrowserReload) {
  btnBrowserReload.addEventListener("click", () => {
    if (!browserWs || browserWs.readyState !== WebSocket.OPEN) {
      connectBrowserStream(browserUrlInput ? browserUrlInput.value : null);
    } else {
      sendBrowserAction({ type: "reload" });
    }
  });
}

if (btnBrowserExternal) {
  btnBrowserExternal.addEventListener("click", () => {
    let u = (browserUrlInput && browserUrlInput.value) || "https://www.google.com";
    if (u.includes("signin/rejected") || u.includes("rejected?")) {
      u = "https://accounts.google.com";
    }
    window.open(u, "_blank");
  });
}

// Browser Quick Link Chips
document.querySelectorAll(".quick-link-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const targetUrl = chip.getAttribute("data-url");
    if (targetUrl === "https://accounts.google.com") {
      openSecureAuthPopup("https://accounts.google.com");
    } else if (targetUrl) {
      navigateToBrowserUrl(targetUrl);
    }
  });
});

if (browserUrlInput) {
  browserUrlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      navigateToBrowserUrl();
    }
  });
}


// 7. Files Drawer & Modals Handlers
btnToggleFiles.addEventListener("click", () => {
  filesDrawer.classList.toggle("open");
  if (filesDrawer.classList.contains("open") && activeProject) {
    loadProjectFiles(activeProject.id);
  }
});
btnCloseFiles.addEventListener("click", () => filesDrawer.classList.remove("open"));
btnCloseFileViewer.addEventListener("click", () => modalFileViewer.classList.remove("active"));

// Sidebar Toggle
btnToggleSidebar.addEventListener("click", () => {
  if (window.innerWidth <= 768) {
    sidebar.classList.toggle("open");
    sidebarBackdrop.classList.toggle("active");
  } else {
    sidebar.classList.toggle("collapsed");
  }
});

sidebarBackdrop.addEventListener("click", () => {
  sidebar.classList.remove("open");
  sidebarBackdrop.classList.remove("active");
});

// Model Dropdown
btnSelectModel.addEventListener("click", (e) => {
  e.stopPropagation();
  attachDropdown.classList.remove("active");
  const rect = btnSelectModel.getBoundingClientRect();
  modelDropdown.style.left = `${rect.left}px`;
  modelDropdown.style.bottom = `${window.innerHeight - rect.top + 8}px`;
  modelDropdown.classList.toggle("active");
});

document.querySelectorAll("#modelDropdown .dropdown-item").forEach(item => {
  item.addEventListener("click", () => {
    document.querySelectorAll("#modelDropdown .dropdown-item").forEach(i => i.classList.remove("active"));
    item.classList.add("active");
    const m = item.getAttribute("data-model");
    currentModelName.innerText = m;
    modelDropdown.classList.remove("active");
  });
});

// Attach Button Dropdown
btnAttach.addEventListener("click", (e) => {
  e.stopPropagation();
  modelDropdown.classList.remove("active");
  const rect = btnAttach.getBoundingClientRect();
  attachDropdown.style.left = `${rect.left}px`;
  attachDropdown.style.bottom = `${window.innerHeight - rect.top + 8}px`;
  attachDropdown.classList.toggle("active");
});

document.getElementById("actInsertBash").addEventListener("click", () => {
  taskInput.value = "$ ";
  taskInput.focus();
  attachDropdown.classList.remove("active");
});

document.getElementById("actUploadFile").addEventListener("click", () => {
  filePicker.click();
  attachDropdown.classList.remove("active");
});

document.getElementById("actClearChat").addEventListener("click", () => {
  if (confirm("Очистить историю диалога этого проекта?")) {
    conversations[activeProject.id] = [];
    localStorage.setItem("ANTIGRAVITY_CHATS", JSON.stringify(conversations));
    loadProjectConversation(activeProject.id);
  }
  attachDropdown.classList.remove("active");
});

document.addEventListener("click", () => {
  modelDropdown.classList.remove("active");
  attachDropdown.classList.remove("active");
});

// Terminal Modal
btnOpenTerminal.addEventListener("click", () => modalTerminal.classList.add("active"));
btnCloseTerminal.addEventListener("click", () => modalTerminal.classList.remove("active"));

// Settings Modal
btnOpenSettings.addEventListener("click", () => {
  settingServerUrl.value = SERVER_URL;
  modalSettings.classList.add("active");
});
btnCloseSettings.addEventListener("click", () => modalSettings.classList.remove("active"));
btnSaveServerUrl.addEventListener("click", () => {
  let val = settingServerUrl.value.trim();
  if (val.endsWith("/")) val = val.slice(0, -1);
  SERVER_URL = val;
  localStorage.setItem("AGENT_SERVER_URL", SERVER_URL);
  modalSettings.classList.remove("active");
  alert("Адрес сервера сохранен!");
  fetchProjects();
});

// Close modals on background click
window.addEventListener("click", (e) => {
  if (e.target === modalTerminal) modalTerminal.classList.remove("active");
  if (e.target === modalBrowser) modalBrowser.classList.remove("active");
  if (e.target === modalSettings) modalSettings.classList.remove("active");
  if (e.target === modalCreateProject) modalCreateProject.classList.remove("active");
  if (e.target === modalFileViewer) modalFileViewer.classList.remove("active");
});

// Formatters
function formatMarkdown(text) {
  if (!text) return "";
  let html = text;
  html = html.replace(/^\|\|\s*(.+)$/gm, '<div class="antigravity-quote">$1</div>');
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
  // GitHub alerts
  html = html.replace(/^> \[!NOTE\]\s*(.+)$/gm, '<div class="antigravity-alert"><strong>Note:</strong> $1</div>');
  html = html.replace(/^> \[!IMPORTANT\]\s*(.+)$/gm, '<div class="antigravity-alert important"><strong>Important:</strong> $1</div>');
  html = html.replace(/^> \[!WARNING\]\s*(.+)$/gm, '<div class="antigravity-alert warning"><strong>Warning:</strong> $1</div>');
  html = html.replace(/^> \[!TIP\]\s*(.+)$/gm, '<div class="antigravity-alert tip"><strong>Tip:</strong> $1</div>');
  html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');
  html = html.replace(/\[([^\]]+)\]\(([^\)]+)\)/gim, '<a href="$2" target="_blank">$1</a>');
  html = html.replace(/^\s*\* (.*$)/gim, '<ul><li>$1</li></ul>');
  html = html.replace(/^\s*\d+\.\s*(.*$)/gim, '<ol><li>$1</li></ol>');
  html = html.replace(/<\/ul>\s*<ul>/gim, '');
  html = html.replace(/<\/ol>\s*<ol>/gim, '');
  html = html.replace(/\n/gim, '<br>');
  return html;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Initial Launch
fetchProjects();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}


// ========================================================
// ENHANCEMENTS: GOOGLE ACCOUNTS HUB & 10 ADVANCED FEATURES
// ========================================================

// Elements
const modalAccounts = document.getElementById("modalAccounts");
const btnCloseAccounts = document.getElementById("btnCloseAccounts");
const accountsListContainer = document.getElementById("accountsListContainer");
const googleProBadge = document.getElementById("googleProBadge");
const badgeAccount = document.getElementById("badgeAccount");
const btnStartGoogleOAuth = document.getElementById("btnStartGoogleOAuth");
const btnSubmitGoogleCode = document.getElementById("btnSubmitGoogleCode");
const oauthCodeInputModal = document.getElementById("oauthCodeInputModal");
const oauthModalStatus = document.getElementById("oauthModalStatus");
const btnToggleManualToken = document.getElementById("btnToggleManualToken");
const manualTokenBox = document.getElementById("manualTokenBox");
const manualTokenJsonInput = document.getElementById("manualTokenJsonInput");
const btnSaveManualToken = document.getElementById("btnSaveManualToken");
const btnLogoutActiveAccount = document.getElementById("btnLogoutActiveAccount");

const modalHistoryViewer = document.getElementById("modalHistoryViewer");
const btnCloseHistoryViewer = document.getElementById("btnCloseHistoryViewer");
const historyListContainer = document.getElementById("historyListContainer");
const btnHistory = document.getElementById("btnHistory");

const btnThemeToggle = document.getElementById("btnThemeToggle");
const btnBackupProject = document.getElementById("btnBackupProject");
const gitStatusBadge = document.getElementById("gitStatusBadge");
const gitBranchName = document.getElementById("gitBranchName");
const gitChangesBadge = document.getElementById("gitChangesBadge");

const fileEditorArea = document.getElementById("fileEditorArea");
const fileEditorPath = document.getElementById("fileEditorPath");
const btnSaveEditedFile = document.getElementById("btnSaveEditedFile");

let currentEditingPath = "";

// 1. Google Accounts Hub
async function fetchAccounts() {
  try {
    const res = await fetch(`${SERVER_URL}/api/auth/accounts`);
    if (res.ok) {
      const data = await res.json();
      renderAccountsList(data.accounts || [], data.active);
      if (data.active && data.active.email) {
        badgeAccount.innerText = data.active.email;
      }
    }
  } catch (err) {
    console.warn("Could not fetch accounts:", err);
  }
}

function renderAccountsList(accounts, activeAccount) {
  if (!accountsListContainer) return;
  if (!accounts || accounts.length === 0) {
    accountsListContainer.innerHTML = '<div style="color:var(--text-muted); font-size:13px; padding:10px;">Нет сохраненных аккаунтов. Подключите аккаунт Google ниже.</div>';
    return;
  }

  accountsListContainer.innerHTML = accounts.map(acc => {
    const isActive = activeAccount && (acc.id === activeAccount.id || acc.active);
    const isExhausted = acc.status === "quota_exhausted";
    const initial = (acc.email || "G").charAt(0).toUpperCase();

    return `
      <div class="account-item-card ${isActive ? 'is-active' : ''}">
        <div class="account-item-left">
          <div class="account-avatar">${initial}</div>
          <div class="account-meta">
            <span class="account-email">${escapeHtml(acc.email)}</span>
            <span class="account-tier">${escapeHtml(acc.tier || "Google Pro")} ${isExhausted ? '⚠️ Лимит исчерпан' : '• Готов'}</span>
          </div>
        </div>
        <div class="account-actions">
          ${isActive 
            ? '<span class="badge-active-pill">АКТИВЕН</span>' 
            : `<button class="btn-switch-account" onclick="switchAccount('${acc.id}')">Переключить ⚡</button>`
          }
        </div>
      </div>
    `;
  }).join('');
}

window.switchAccount = async function(accountId) {
  try {
    const res = await fetch(`${SERVER_URL}/api/auth/switch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_id: accountId })
    });
    const data = await res.json();
    if (data.success) {
      alert(`✔ Переключено на аккаунт: ${data.active_account.email}`);
      fetchAccounts();
    } else {
      alert("Ошибка переключения: " + (data.error || "Неизвестная ошибка"));
    }
  } catch (e) {
    alert("Ошибка связи с сервером при смене аккаунта: " + e.message);
  }
};

if (googleProBadge) {
  googleProBadge.addEventListener("click", () => {
    fetchAccounts();
    modalAccounts.classList.add("active");
  });
}
if (btnCloseAccounts) {
  btnCloseAccounts.addEventListener("click", () => modalAccounts.classList.remove("active"));
}

if (btnStartGoogleOAuth) {
  btnStartGoogleOAuth.addEventListener("click", async () => {
    oauthModalStatus.style.display = "block";
    oauthModalStatus.style.color = "#0a84ff";
    oauthModalStatus.innerText = "Генерирую ссылку для входа в Google...";
    try {
      const res = await fetch(`${SERVER_URL}/api/antigravity/oauth-url`);
      const data = await res.json();
      if (data.url) {
        window.open(data.url, "_blank");
        oauthModalStatus.innerText = "Ссылка открыта в новой вкладке. Войдите в Google аккаунт, скопируйте код и вставьте в поле ниже.";
      } else {
        oauthModalStatus.innerText = "Ошибка: " + (data.message || "Попробуйте снова.");
      }
    } catch (e) {
      oauthModalStatus.innerText = "Ошибка связи с сервером.";
    }
  });
}

if (btnSubmitGoogleCode) {
  btnSubmitGoogleCode.addEventListener("click", async () => {
    const code = oauthCodeInputModal.value.trim();
    if (!code) {
      alert("Пожалуйста, вставьте код авторизации от Google.");
      return;
    }
    oauthModalStatus.style.display = "block";
    oauthModalStatus.style.color = "#ff9f0a";
    oauthModalStatus.innerText = "Подтверждение токена в Antigravity...";
    try {
      const res = await fetch(`${SERVER_URL}/api/antigravity/submit-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code })
      });
      const data = await res.json();
      if (data.success) {
        oauthModalStatus.style.color = "#30d158";
        oauthModalStatus.innerText = "✔ Аккаунт успешно добавлен в пул и сохранен в Storj S3!";
        oauthCodeInputModal.value = "";
        fetchAccounts();
      } else {
        oauthModalStatus.style.color = "#ff453a";
        oauthModalStatus.innerText = "Ошибка: " + (data.error || "Неверный код.");
      }
    } catch (e) {
      oauthModalStatus.innerText = "Ошибка отправки кода.";
    }
  });
}

if (btnToggleManualToken) {
  btnToggleManualToken.addEventListener("click", () => {
    manualTokenBox.style.display = manualTokenBox.style.display === "none" ? "block" : "none";
  });
}

if (btnSaveManualToken) {
  btnSaveManualToken.addEventListener("click", async () => {
    const raw = manualTokenJsonInput.value.trim();
    if (!raw) return;
    try {
      const res = await fetch(`${SERVER_URL}/api/auth/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token_json: raw })
      });
      const data = await res.json();
      if (data.success) {
        alert("✔ Токен успешно сохранен в пул аккаунтов!");
        manualTokenJsonInput.value = "";
        manualTokenBox.style.display = "none";
        fetchAccounts();
      } else {
        alert("Ошибка: " + (data.detail || "Неверный формат"));
      }
    } catch (e) {
      alert("Ошибка отправки: " + e.message);
    }
  });
}

if (btnLogoutActiveAccount) {
  btnLogoutActiveAccount.addEventListener("click", async () => {
    if (confirm("Вы действительно хотите выйти из текущего активного Google аккаунта?")) {
      try {
        await fetch(`${SERVER_URL}/api/auth/logout`, { method: "POST" });
        alert("Вы вышли из активного аккаунта.");
        fetchAccounts();
      } catch (e) {
        console.warn("Logout error:", e);
      }
    }
  });
}

// 2. Interactive Code Editor Save
async function openFileInEditor(filePath) {
  if (!activeProject) return;
  currentEditingPath = filePath;
  modalFileViewer.classList.add("active");
  if (fileEditorPath) fileEditorPath.innerText = filePath;
  if (fileEditorArea) fileEditorArea.value = "Загрузка содержимого файла...";

  try {
    const res = await fetch(`${SERVER_URL}/api/projects/${activeProject.id}/file?path=${encodeURIComponent(filePath)}`);
    if (res.ok) {
      const data = await res.json();
      if (fileEditorArea) fileEditorArea.value = data.content || "";
    }
  } catch (e) {
    if (fileEditorArea) fileEditorArea.value = "Ошибка загрузки файла: " + e.message;
  }
}

if (btnSaveEditedFile) {
  btnSaveEditedFile.addEventListener("click", async () => {
    if (!activeProject || !currentEditingPath) return;
    const content = fileEditorArea.value;
    btnSaveEditedFile.innerText = "Сохранение...";
    try {
      const res = await fetch(`${SERVER_URL}/api/projects/save-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: activeProject.id,
          path: currentEditingPath,
          content: content
        })
      });
      if (res.ok) {
        btnSaveEditedFile.innerText = "✔ Сохранено!";
        setTimeout(() => { btnSaveEditedFile.innerText = "💾 Сохранить (Ctrl+S)"; }, 1500);
        loadProjectFiles(activeProject.id);
      } else {
        btnSaveEditedFile.innerText = "Ошибка!";
      }
    } catch (e) {
      alert("Ошибка сохранения: " + e.message);
      btnSaveEditedFile.innerText = "💾 Сохранить (Ctrl+S)";
    }
  });
}

window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "s") {
    if (modalFileViewer && modalFileViewer.classList.contains("active")) {
      e.preventDefault();
      if (btnSaveEditedFile) btnSaveEditedFile.click();
    }
  }
});

// 3. One-Click Full Project Backup to Storj S3
if (btnBackupProject) {
  btnBackupProject.addEventListener("click", async () => {
    if (!activeProject) return;
    btnBackupProject.innerHTML = "<span>⏳ Бэкап...</span>";
    try {
      const res = await fetch(`${SERVER_URL}/api/projects/${activeProject.id}/backup`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        alert(`✔ Снапшот проекта сохранен в Storj S3 25GB!\nКлюч: ${data.key}\nРазмер: ${formatBytes(data.size_bytes)}`);
      } else {
        alert("Ошибка создания бэкапа: " + (data.error || "Неизвестно"));
      }
    } catch (e) {
      alert("Ошибка бэкапа: " + e.message);
    } finally {
      btnBackupProject.innerHTML = "<span>💾 Бэкап в S3</span>";
    }
  });
}

// 4. Git Status in Toolbar
async function fetchGitStatus() {
  try {
    const res = await fetch(`${SERVER_URL}/api/git/status`);
    if (res.ok) {
      const data = await res.json();
      if (gitBranchName) gitBranchName.innerText = data.branch || "main";
      if (gitChangesBadge) {
        gitChangesBadge.innerText = data.modified_count || "0";
        gitChangesBadge.style.display = data.modified_count > 0 ? "inline-block" : "none";
      }
    }
  } catch (e) {}
}

// 5. Quick Action Chips
document.querySelectorAll(".quick-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const cmd = chip.getAttribute("data-cmd");
    if (cmd) {
      taskInput.value = cmd;
      taskInput.focus();
      taskInput.style.height = "auto";
      taskInput.style.height = (taskInput.scrollHeight) + "px";
    }
  });
});

// 6. Task History Modal
if (btnHistory) {
  btnHistory.addEventListener("click", async (e) => {
    e.preventDefault();
    modalHistoryViewer.classList.add("active");
    try {
      const res = await fetch(`${SERVER_URL}/api/history`);
      if (res.ok) {
        const data = await res.json();
        const list = data.history || [];
        if (list.length === 0) {
          historyListContainer.innerHTML = '<div style="color:var(--text-muted); font-size:13px; padding:10px;">История пуста. Выполните первую задачу!</div>';
        } else {
          historyListContainer.innerHTML = list.map(item => `
            <div class="history-item-card" onclick="replayTask('${escapeHtml(item.task || '')}')">
              <div class="history-task-text">${escapeHtml(item.task || '')}</div>
              <div class="history-meta">${escapeHtml(item.time || '')} • ${escapeHtml(item.engine || 'Antigravity')}</div>
            </div>
          `).join('');
        }
      }
    } catch (err) {}
  });
}

window.replayTask = function(taskText) {
  taskInput.value = taskText;
  modalHistoryViewer.classList.remove("active");
  taskInput.focus();
};

if (btnCloseHistoryViewer) {
  btnCloseHistoryViewer.addEventListener("click", () => modalHistoryViewer.classList.remove("active"));
}

// 7. Theme Toggle
if (btnThemeToggle) {
  const savedTheme = localStorage.getItem("ANTIGRAVITY_THEME") || "dark";
  if (savedTheme === "light") document.body.classList.add("light-theme");

  btnThemeToggle.addEventListener("click", () => {
    document.body.classList.toggle("light-theme");
    const isLight = document.body.classList.contains("light-theme");
    localStorage.setItem("ANTIGRAVITY_THEME", isLight ? "light" : "dark");
  });
}

// Close extra modals on background click
window.addEventListener("click", (e) => {
  if (e.target === modalAccounts) modalAccounts.classList.remove("active");
  if (e.target === modalHistoryViewer) modalHistoryViewer.classList.remove("active");
});

// Hook into file click to use interactive editor
window.openProjectFile = function(filePath) {
  openFileInEditor(filePath);
};

// Periodic background sync
fetchAccounts();
fetchGitStatus();
setInterval(fetchGitStatus, 15000);


// ========================================================
// AUXILIARY PANE, SLASH COMMANDS & THINKING PARITY LOGIC
// ========================================================

const auxiliaryPane = document.getElementById("auxiliaryPane");
const btnToggleLayout = document.getElementById("btnToggleLayout");
const btnCloseAuxPane = document.getElementById("btnCloseAuxPane");
const artifactsListContainer = document.getElementById("artifactsListContainer");
const diffViewerContainer = document.getElementById("diffViewerContainer");
const btnRefreshDiff = document.getElementById("btnRefreshDiff");
const slashPopup = document.getElementById("slashPopup");

// 1. Auxiliary Pane Toggle & Tabs
if (btnToggleLayout) {
  btnToggleLayout.addEventListener("click", () => {
    auxiliaryPane.classList.toggle("open");
    if (auxiliaryPane.classList.contains("open")) {
      const activeTab = document.querySelector(".aux-tab-btn.active");
      const tabName = activeTab ? activeTab.getAttribute("data-tab") : "subagents";
      switchAuxTab(tabName);
    }
  });
}

if (btnCloseAuxPane) {
  btnCloseAuxPane.addEventListener("click", () => auxiliaryPane.classList.remove("open"));
}

document.querySelectorAll(".aux-tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const tabName = btn.getAttribute("data-tab");
    switchAuxTab(tabName);
  });
});

function switchAuxTab(tabName) {
  document.querySelectorAll(".aux-tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".aux-tab-content").forEach(c => c.classList.remove("active"));

  const targetBtn = document.querySelector(`.aux-tab-btn[data-tab="${tabName}"]`);
  if (targetBtn) targetBtn.classList.add("active");

  if (tabName === "subagents") {
    const el = document.getElementById("tabContentSubagents");
    if (el) el.classList.add("active");
  } else if (tabName === "artifacts") {
    const el = document.getElementById("tabContentArtifacts");
    if (el) el.classList.add("active");
    fetchArtifacts();
  } else if (tabName === "files-changed") {
    const el = document.getElementById("tabContentFilesChanged");
    if (el) el.classList.add("active");
    fetchGitDiff();
  } else if (tabName === "terminal") {
    const el = document.getElementById("tabContentTerminal");
    if (el) el.classList.add("active");
  }
}

// 2. Fetch Artifacts
async function fetchArtifacts() {
  if (!artifactsListContainer) return;
  artifactsListContainer.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:8px;">Загрузка артефактов...</div>';
  try {
    const res = await fetch(`${SERVER_URL}/api/artifacts`);
    if (res.ok) {
      const data = await res.json();
      const list = data.artifacts || [];
      if (list.length === 0) {
        artifactsListContainer.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:8px;">Нет артефактов в проекте.</div>';
        return;
      }
      artifactsListContainer.innerHTML = list.map(art => `
        <div class="artifact-card" onclick="openProjectFile('${escapeHtml(art.path)}')">
          <div class="artifact-title">📄 ${escapeHtml(art.name)}</div>
          <div class="artifact-preview">${escapeHtml(art.preview || '')}</div>
        </div>
      `).join('');
    }
  } catch (e) {
    artifactsListContainer.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:8px;">Не удалось загрузить артефакты.</div>';
  }
}

// 3. Fetch Git Diff
async function fetchGitDiff() {
  if (!diffViewerContainer) return;
  diffViewerContainer.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:8px;">Загрузка diff...</div>';
  try {
    const res = await fetch(`${SERVER_URL}/api/git/diff`);
    if (res.ok) {
      const data = await res.json();
      if (!data.has_changes || !data.files || data.files.length === 0) {
        diffViewerContainer.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:8px;">✔ Рабочая директория чиста. Нет несохраненных изменений.</div>';
        return;
      }
      diffViewerContainer.innerHTML = data.files.map(f => {
        const linesHtml = f.diff.split('\n').map(l => {
          let cls = 'diff-line';
          if (l.startsWith('+') && !l.startsWith('+++')) cls += ' added';
          else if (l.startsWith('-') && !l.startsWith('---')) cls += ' removed';
          else if (l.startsWith('@@')) cls += ' info';
          return `<div class="${cls}">${escapeHtml(l)}</div>`;
        }).join('');
        return `
          <div class="diff-file-block">
            <div class="diff-file-header">📄 ${escapeHtml(f.file)}</div>
            <pre class="diff-code-body">${linesHtml}</pre>
          </div>
        `;
      }).join('');
    }
  } catch (e) {
    diffViewerContainer.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:8px;">Ошибка получения diff.</div>';
  }
}

if (btnRefreshDiff) {
  btnRefreshDiff.addEventListener("click", () => fetchGitDiff());
}

// 4. Slash Commands Autocomplete
if (taskInput && slashPopup) {
  taskInput.addEventListener("input", () => {
    const val = taskInput.value;
    if (val.startsWith("/") && val.length < 15 && !val.includes(" ")) {
      slashPopup.style.display = "block";
      const filter = val.toLowerCase();
      document.querySelectorAll(".slash-item").forEach(item => {
        const cmd = item.getAttribute("data-cmd").toLowerCase();
        item.style.display = cmd.includes(filter) ? "flex" : "none";
      });
    } else {
      slashPopup.style.display = "none";
    }
  });

  taskInput.addEventListener("keydown", (e) => {
    if (slashPopup.style.display === "block") {
      const visibleItems = Array.from(document.querySelectorAll(".slash-item")).filter(i => i.style.display !== "none");
      if (visibleItems.length === 0) return;

      let currentIndex = visibleItems.findIndex(i => i.classList.contains("active"));

      if (e.key === "ArrowDown") {
        e.preventDefault();
        visibleItems.forEach(i => i.classList.remove("active"));
        const nextIndex = (currentIndex + 1) % visibleItems.length;
        visibleItems[nextIndex].classList.add("active");
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        visibleItems.forEach(i => i.classList.remove("active"));
        const prevIndex = (currentIndex - 1 + visibleItems.length) % visibleItems.length;
        visibleItems[prevIndex].classList.add("active");
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const activeItem = visibleItems[currentIndex] || visibleItems[0];
        if (activeItem) {
          selectSlashCommand(activeItem.getAttribute("data-cmd"));
        }
      } else if (e.key === "Escape") {
        slashPopup.style.display = "none";
      }
    }
  });

  document.querySelectorAll(".slash-item").forEach(item => {
    item.addEventListener("click", () => {
      selectSlashCommand(item.getAttribute("data-cmd"));
    });
  });
}

function selectSlashCommand(cmd) {
  if (!taskInput || !cmd) return;
  taskInput.value = cmd + " ";
  slashPopup.style.display = "none";
  taskInput.focus();
}

// 5. Rich Markdown Enhancements (Alerts, Code Copy)
window.copyCodeSnippet = function(btn) {
  const pre = btn.closest(".code-wrapper").querySelector("pre code");
  if (pre) {
    navigator.clipboard.writeText(pre.innerText).then(() => {
      btn.innerText = "Copied!";
      setTimeout(() => { btn.innerText = "Copy"; }, 1500);
    });
  }
};


// ========================================================
// GEMINI LIVE VOICE BRAINSTORM CONTROLLER (EDGE STUDIO TTS & DUAL-ENGINE VAD)
// ========================================================

// (btnOpenGeminiLive and btnCloseGeminiLive declared at top of file)
const liveOrb = document.getElementById("liveOrb");
const liveStatusText = document.getElementById("liveStatusText");
const liveDialogBox = document.getElementById("liveDialogBox");
const btnLiveMicToggle = document.getElementById("btnLiveMicToggle");
const btnLiveStopAudio = document.getElementById("btnLiveStopAudio");
const btnTransferPrompt = document.getElementById("btnTransferPrompt");
const liveVoiceName = document.getElementById("liveVoiceName");
const liveActiveModelBadge = document.getElementById("liveActiveModelBadge");
const liveVolumeBar = document.getElementById("liveVolumeBar");
const liveTextInput = document.getElementById("liveTextInput");
const btnLiveSendText = document.getElementById("btnLiveSendText");

let liveHistory = [];
let liveIsListening = false;
let liveIsThinking = false;
let liveSpeechRecognizer = null;
let liveBestVoice = null;
let liveSilenceTimer = null;
let liveCurrentSpeechText = "";
let liveRestartTimeout = null;

// Hardware Audio & VAD variables
let liveAudioStream = null;
let liveAudioContext = null;
let liveAnalyser = null;
let liveAnimFrameId = null;
let liveMediaRecorder = null;
let liveRollingBuffer = [];
let liveActiveSpeechChunks = [];
let liveUserSpokeSound = false;

// 1. Voice Detection (Microsoft Edge Natural Studio Voice prioritized)
function initNaturalVoices() {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return;

  let selected = voices.find(v => v.name.includes("Natural") && (v.name.includes("Dmitry") || v.name.includes("Svetlana")));
  if (!selected) selected = voices.find(v => v.name.includes("Natural") && (v.lang.startsWith("ru") || v.name.includes("Russian")));
  if (!selected) selected = voices.find(v => v.name.includes("Google") && v.lang.startsWith("ru"));
  if (!selected) selected = voices.find(v => v.lang.startsWith("ru") || v.lang === "ru-RU");

  if (selected) {
    liveBestVoice = selected;
    const voiceBadge = document.getElementById("liveVoiceName");
    if (voiceBadge) {
      voiceBadge.innerText = `🎙 ${selected.name.replace("Microsoft ", "").replace(" Online (Natural) - Russian (Russia)", " (Edge Natural Studio)")}`;
    }
  }
}

if (typeof window !== "undefined" && "speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = initNaturalVoices;
  initNaturalVoices();
}

// 2. Hardware Audio & Volume Visualizer Setup
async function initLiveAudioHardware() {
  try {
    if (liveAudioStream && liveAudioStream.active) {
      return true;
    }

    liveAudioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {
      if (!liveAudioContext || liveAudioContext.state === "closed") {
        liveAudioContext = new AudioCtx();
      }
      if (liveAudioContext.state === "suspended") {
        await liveAudioContext.resume();
      }
      const source = liveAudioContext.createMediaStreamSource(liveAudioStream);
      liveAnalyser = liveAudioContext.createAnalyser();
      liveAnalyser.fftSize = 256;
      liveAnalyser.smoothingTimeConstant = 0.4;
      source.connect(liveAnalyser);

      startVolumeVisualizer();
    }
    return true;
  } catch (err) {
    console.warn("Live getUserMedia hardware access denied or failed:", err);
    const status = document.getElementById("liveStatusText");
    if (status) {
      status.innerText = "⚠️ Доступ к микрофону заблокирован. Разрешите его в браузере (значок замочка слева от адреса).";
    }
    return false;
  }
}

function startVolumeVisualizer() {
  if (liveAnimFrameId) cancelAnimationFrame(liveAnimFrameId);

  const dataArray = new Uint8Array(liveAnalyser.frequencyBinCount);

  function loop() {
    if (!liveAudioStream || !liveAudioStream.active) return;
    liveAnimFrameId = requestAnimationFrame(loop);

    const modal = document.getElementById("modalGeminiLive");
    if (!modal || !modal.classList.contains("active")) return;

    if (window.speechSynthesis && window.speechSynthesis.speaking) {
      const vBar = document.getElementById("liveVolumeBar");
      if (vBar) vBar.style.width = "0%";
      return;
    }

    liveAnalyser.getByteFrequencyData(dataArray);
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const avg = sum / dataArray.length;
    const normalized = Math.min(100, Math.round((avg / 50) * 100));

    const vBar = document.getElementById("liveVolumeBar");
    if (vBar) {
      vBar.style.width = `${normalized}%`;
      if (normalized > 20) {
        vBar.style.background = "linear-gradient(90deg, #10b981, #06b6d4, #8b5cf6)";
      } else {
        vBar.style.background = "#3b82f6";
      }
    }

    const orb = document.getElementById("liveOrb");
    if (orb && liveIsListening && !liveIsThinking) {
      if (normalized > 12) {
        const scale = 1 + (normalized / 220);
        orb.style.transform = `scale(${scale})`;
      } else {
        orb.style.transform = "";
      }
    }

    // Voice Activity Detection (VAD)
    const isAudioPlaying = liveAudioPlayer && !liveAudioPlayer.paused;
    if (normalized > 14 && liveIsListening && !liveIsThinking && !isAudioPlaying) {
      liveUserSpokeSound = true;

      // Reset speech silence timer (1.4s of silence after speech)
      if (liveSilenceTimer) clearTimeout(liveSilenceTimer);
      liveSilenceTimer = setTimeout(() => {
        handleSilenceTimeout();
      }, 1400);
    }
  }

  loop();
}

function startLiveMediaRecorder() {
  if (!liveAudioStream || typeof MediaRecorder === "undefined") return;

  // Never stop or recreate if already recording - avoids Android InvalidStateError
  if (liveMediaRecorder && liveMediaRecorder.state === "recording") {
    liveActiveSpeechChunks = [];
    return;
  }

  try {
    let options = {};
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      options = { mimeType: 'audio/webm;codecs=opus' };
    } else if (MediaRecorder.isTypeSupported('audio/webm')) {
      options = { mimeType: 'audio/webm' };
    } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
      options = { mimeType: 'audio/mp4' };
    }
    liveMediaRecorder = new MediaRecorder(liveAudioStream, options);
    liveActiveSpeechChunks = [];
    liveRollingBuffer = [];

    liveMediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        const isAudioPlaying = liveAudioPlayer && !liveAudioPlayer.paused;
        if (liveIsThinking || isAudioPlaying) {
          // Assistant is speaking or thinking: clear incoming voice
          liveRollingBuffer = [];
          liveActiveSpeechChunks = [];
          return;
        }

        if (liveUserSpokeSound) {
          // User is actively speaking: record speech chunks
          liveActiveSpeechChunks.push(e.data);
          if (liveActiveSpeechChunks.length > 70) {
            liveActiveSpeechChunks.shift();
          }
        } else {
          // Ambient silence: keep rolling pre-roll buffer of 3 chunks (~600ms)
          liveRollingBuffer.push(e.data);
          if (liveRollingBuffer.length > 3) {
            liveRollingBuffer.shift();
          }
        }
      }
    };

    liveMediaRecorder.start(200);
  } catch (e) {
    console.warn("Live MediaRecorder start failed:", e);
  }
}

// 3. Web Speech Recognition Loop (Disabled on Android to eliminate system chimes)
function startLiveSpeechRecognition() {
  const isAndroid = /android/i.test(navigator.userAgent);
  if (isAndroid) {
    // Avoid Android system chime sound ('тулюлюн') on repeated SpeechRecognition starts.
    // Pure Hardware VAD + Gemini Transcribe handles Android seamlessly and quietly.
    return;
  }

  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) {
    console.log("WebSpeech not available, running hardware VAD + Gemini Transcribe");
    return;
  }

  try {
    if (liveSpeechRecognizer) {
      try { liveSpeechRecognizer.abort(); } catch(e) {}
    }

    liveSpeechRecognizer = new SpeechRec();
    liveSpeechRecognizer.lang = "ru-RU";
    liveSpeechRecognizer.continuous = true;
    liveSpeechRecognizer.interimResults = true;

    liveSpeechRecognizer.onstart = () => {
      liveIsListening = true;
      const status = document.getElementById("liveStatusText");
      if (status && !liveIsThinking) {
        status.innerText = "🟢 Слушаю вас... Говорите";
      }
      const btn = document.getElementById("btnLiveMicToggle");
      if (btn) btn.classList.add("active");
    };

    liveSpeechRecognizer.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = 0; i < event.results.length; ++i) {
        if (event.results[i].isFinal) final += event.results[i][0].transcript + " ";
        else interim += event.results[i][0].transcript;
      }

      const text = (final + interim).trim();
      if (text) {
        liveCurrentSpeechText = text;
        liveUserSpokeSound = true;
        const status = document.getElementById("liveStatusText");
        if (status) {
          status.innerText = `🎙 «${text}»`;
        }

        if (liveSilenceTimer) clearTimeout(liveSilenceTimer);
        liveSilenceTimer = setTimeout(() => {
          handleSilenceTimeout();
        }, 1400);
      }
    };

    liveSpeechRecognizer.onerror = (e) => {
      console.log("Speech recognition error:", e.error);
      if (e.error === "not-allowed") {
        const status = document.getElementById("liveStatusText");
        if (status) status.innerText = "⚠️ Доступ к микрофону заблокирован в браузере";
      }
    };

    liveSpeechRecognizer.onend = () => {
      const isPlaying = liveAudioPlayer && !liveAudioPlayer.paused;
      const modal = document.getElementById("modalGeminiLive");
      if (modal && modal.classList.contains("active") && liveIsListening && !liveIsThinking && !isPlaying) {
        clearTimeout(liveRestartTimeout);
        liveRestartTimeout = setTimeout(() => {
          const playingNow = liveAudioPlayer && !liveAudioPlayer.paused;
          const m = document.getElementById("modalGeminiLive");
          if (m && m.classList.contains("active") && liveIsListening && !liveIsThinking && !playingNow) {
            try { liveSpeechRecognizer.start(); } catch(err) {}
          }
        }, 800);
      }
    };

    liveSpeechRecognizer.start();
  } catch (err) {
    console.warn("SpeechRec start error:", err);
  }
}

// 4. Silence Timeout Handler (Dual-Engine: WebSpeech or Gemini Transcribe)
async function handleSilenceTimeout() {
  if (liveIsThinking || !liveUserSpokeSound) return;
  const isAudioPlaying = liveAudioPlayer && !liveAudioPlayer.paused;
  if (isAudioPlaying) return;

  liveUserSpokeSound = false;

  const captured = liveCurrentSpeechText.trim();
  if (captured.length > 1) {
    liveCurrentSpeechText = "";
    handleUserLiveUtterance(captured);
    return;
  }

  // Dual-Engine: Transcribe recorded hardware audio with Gemini AI
  const combinedChunks = [...liveRollingBuffer, ...liveActiveSpeechChunks];
  liveActiveSpeechChunks = [];
  liveRollingBuffer = [];

  if (combinedChunks.length > 0 && liveMediaRecorder) {
    const status = document.getElementById("liveStatusText");
    if (status) status.innerText = "⏳ Распознаю речь через Gemini...";

    const mime = liveMediaRecorder.mimeType || "audio/webm";
    const blob = new Blob(combinedChunks, { type: mime });

    if (blob.size > 350) {
      liveIsThinking = true;
      try {
        const formData = new FormData();
        formData.append("file", blob, "live_mic.webm");
        const resp = await fetch(`${SERVER_URL}/api/voice-transcribe`, {
          method: "POST",
          body: formData
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data.success && data.text && data.text !== "NONE" && data.text.trim().length > 1) {
            handleUserLiveUtterance(data.text.trim());
            return;
          }
        }
      } catch (err) {
        console.warn("Gemini transcribe error:", err);
      }
      liveIsThinking = false;
    }
  }

  const status = document.getElementById("liveStatusText");
  if (status && !liveIsThinking && !(liveAudioPlayer && !liveAudioPlayer.paused)) {
    status.innerText = "🟢 Слушаю вас... Говорите";
  }
}

// 5. Open / Close Live Session (Redirected to Unified In-Chat Live Voice)
async function openGeminiLiveModal() {
  toggleLiveVoiceMode();
}

function closeGeminiLiveModal() {
  stopLiveVoiceMode();
}

async function startLiveSession() {
  liveHistory = [];
  liveCurrentSpeechText = "";
  liveIsThinking = false;
  liveUserSpokeSound = false;

  const dialog = document.getElementById("liveDialogBox");
  if (dialog) {
    dialog.innerHTML = `
      <div class="live-msg-bubble assistant">
        👋 Привет! Я слушаю. Расскажите идею для проекта своими словами — я отвечу кратко и по делу!
      </div>
    `;
  }
  const status = document.getElementById("liveStatusText");
  if (status) status.innerText = "Инициализация микрофона...";
  const orb = document.getElementById("liveOrb");
  if (orb) orb.className = "live-orb listening";

  const hasHardware = await initLiveAudioHardware();
  liveIsListening = true;
  if (hasHardware) {
    startLiveMediaRecorder();
  }
  startLiveSpeechRecognition();

  if (status) {
    status.innerText = "🟢 Слушаю вас... Говорите";
  }
}

function stopLiveSession() {
  liveIsListening = false;
  liveIsThinking = false;
  liveUserSpokeSound = false;
  liveActiveSpeechChunks = [];
  liveRollingBuffer = [];

  if (liveAudioPlayer) {
    try {
      liveAudioPlayer.pause();
      liveAudioPlayer.currentTime = 0;
    } catch(e) {}
    liveAudioPlayer = null;
  }
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  if (liveSpeechRecognizer) {
    try { liveSpeechRecognizer.abort(); } catch(e) {}
    liveSpeechRecognizer = null;
  }
  if (liveSilenceTimer) clearTimeout(liveSilenceTimer);
  if (liveRestartTimeout) clearTimeout(liveRestartTimeout);

  if (liveMediaRecorder && liveMediaRecorder.state !== "inactive") {
    try { liveMediaRecorder.stop(); } catch(e) {}
  }
  liveMediaRecorder = null;
  if (liveAudioStream) {
    liveAudioStream.getTracks().forEach(track => track.stop());
    liveAudioStream = null;
  }
  if (liveAnimFrameId) {
    cancelAnimationFrame(liveAnimFrameId);
    liveAnimFrameId = null;
  }
  const vBar = document.getElementById("liveVolumeBar");
  if (vBar) vBar.style.width = "0%";
}

// 6. Handle User Utterance -> Send to Gemini Cascade
async function handleUserLiveUtterance(userText) {
  if (!userText || !userText.trim()) return;

  liveIsThinking = true;
  appendLiveBubble("user", userText);
  liveHistory.push({ role: "user", text: userText });

  const orb = document.getElementById("liveOrb");
  if (orb) {
    orb.className = "live-orb";
    orb.style.transform = "";
  }
  const status = document.getElementById("liveStatusText");
  if (status) status.innerText = "⏳ Gemini думает...";

  // Pause recognition while speaking
  if (liveSpeechRecognizer) {
    try { liveSpeechRecognizer.abort(); } catch(e) {}
  }

  try {
    const res = await fetch(`${SERVER_URL}/api/gemini/cascade-chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userText,
        history: liveHistory
      })
    });

    if (res.ok) {
      const data = await res.json();
      const reply = data.reply || "Понял вас! Развиваем эту мысль дальше.";
      const badge = document.getElementById("liveActiveModelBadge");
      if (badge) {
        const modelStr = data.model_used || "Gemini 3.1 Flash";
        badge.innerText = `Каскад: ${modelStr} • Edge Dmitry Studio`;
      }
      appendLiveBubble("assistant", reply);
      liveHistory.push({ role: "model", text: reply });

      let audioB64 = data.audio_base64;
      if (!audioB64) {
        try {
          const ttsRes = await fetch(`${SERVER_URL}/api/edge-tts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: reply, voice: "ru-RU-DmitryNeural" })
          });
          if (ttsRes.ok) {
            const ttsData = await ttsRes.json();
            audioB64 = ttsData.audio_base64;
          }
        } catch (e) {
          console.warn("Direct Edge TTS fetch fallback error:", e);
        }
      }

      // Speak reply with TRUE studio quality Microsoft Edge Neural Voice
      speakNaturalReply(reply, audioB64, () => {
        setTimeout(() => {
          liveIsThinking = false;
          liveUserSpokeSound = false;
          liveActiveSpeechChunks = [];
          liveRollingBuffer = [];
          liveCurrentSpeechText = "";

          // Resume audio context and ensure mic track active
          if (liveAudioContext && liveAudioContext.state === "suspended") {
            try { liveAudioContext.resume(); } catch(e) {}
          }
          if (liveAudioStream) {
            try {
              liveAudioStream.getAudioTracks().forEach(t => t.enabled = true);
            } catch(e) {}
          }

          const modal = document.getElementById("modalGeminiLive");
          if (modal && modal.classList.contains("active") && liveIsListening) {
            const liveOrbEl = document.getElementById("liveOrb");
            if (liveOrbEl) liveOrbEl.className = "live-orb listening";
            const statusEl = document.getElementById("liveStatusText");
            if (statusEl) statusEl.innerText = "🟢 Слушаю вас... Говорите дальше";

            if (!/android/i.test(navigator.userAgent)) {
              startLiveSpeechRecognition();
            }
          }
        }, 250);
      });
    } else {
      liveIsThinking = false;
      if (status) status.innerText = "Ошибка ответа от Gemini.";
      startLiveSpeechRecognition();
    }
  } catch (err) {
    liveIsThinking = false;
    if (status) status.innerText = "Ошибка соединения: " + err.message;
    startLiveSpeechRecognition();
  }
}

function appendLiveBubble(role, text) {
  const dialog = document.getElementById("liveDialogBox");
  if (!dialog) return;
  const bubble = document.createElement("div");
  bubble.className = `live-msg-bubble ${role}`;
  bubble.innerText = text;
  dialog.appendChild(bubble);
  dialog.scrollTop = dialog.scrollHeight;
}

let liveAudioPlayer = null;

// 7. Speech Synthesis with TRUE Microsoft Edge Studio Neural Voice (Audio Element)
async function speakNaturalReply(text, audioBase64, onComplete) {
  // Stop any previous speech / audio
  if (liveAudioPlayer) {
    try {
      liveAudioPlayer.pause();
      liveAudioPlayer.currentTime = 0;
    } catch(e) {}
    liveAudioPlayer = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  if (liveSpeechRecognizer) {
    try { liveSpeechRecognizer.abort(); } catch(e) {}
  }

  const orb = document.getElementById("liveOrb");
  if (orb) orb.className = "live-orb speaking";
  const status = document.getElementById("liveStatusText");
  if (status) status.innerText = "🔊 Gemini говорит (Edge Studio Voice)...";

  // If audioBase64 was not provided, fetch from backend /api/edge-tts
  if (!audioBase64) {
    try {
      const resp = await fetch(`${SERVER_URL}/api/edge-tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, voice: "ru-RU-DmitryNeural" })
      });
      if (resp.ok) {
        const d = await resp.json();
        audioBase64 = d.audio_base64;
      }
    } catch (e) {
      console.warn("Direct Edge TTS fetch failed:", e);
    }
  }

  // Priority 1: True Microsoft Edge Studio Neural MP3 Audio from Backend
  if (audioBase64) {
    try {
      const audioUrl = "data:audio/mp3;base64," + audioBase64;
      liveAudioPlayer = new Audio(audioUrl);

      liveAudioPlayer.onended = () => {
        liveAudioPlayer = null;
        if (onComplete) onComplete();
      };

      liveAudioPlayer.onerror = (e) => {
        console.warn("Studio audio playback error, falling back to WebSpeech:", e);
        fallbackSpeechSynthesis(text, onComplete);
      };

      liveAudioPlayer.play().catch(err => {
        console.warn("Studio audio play() blocked or failed:", err);
        fallbackSpeechSynthesis(text, onComplete);
      });
      return;
    } catch (e) {
      console.warn("Audio element exception:", e);
    }
  }

  // Priority 2: Fallback to browser speechSynthesis
  fallbackSpeechSynthesis(text, onComplete);
}

function fallbackSpeechSynthesis(text, onComplete) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    if (onComplete) onComplete();
    return;
  }

  window.speechSynthesis.cancel();
  const cleanText = text.replace(/[*#`_]/g, "").trim();
  const utter = new SpeechSynthesisUtterance(cleanText);
  utter.rate = 1.05;
  utter.pitch = 1.0;

  if (liveBestVoice) {
    utter.voice = liveBestVoice;
  }

  utter.onend = () => {
    if (onComplete) onComplete();
  };
  utter.onerror = () => {
    if (onComplete) onComplete();
  };

  window.speechSynthesis.speak(utter);
}

// 8. Stop Speaking Button
if (btnLiveStopAudio) {
  btnLiveStopAudio.addEventListener("click", () => {
    if (liveAudioPlayer) {
      try {
        liveAudioPlayer.pause();
        liveAudioPlayer.currentTime = 0;
      } catch(e) {}
      liveAudioPlayer = null;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    liveIsThinking = false;
    const orb = document.getElementById("liveOrb");
    if (orb) orb.className = "live-orb listening";
    const status = document.getElementById("liveStatusText");
    if (status) status.innerText = "🟢 Слушаю вас... Говорите";
    startLiveSpeechRecognition();
  });
}

// 9. Toggle Mic in Live
if (btnLiveMicToggle) {
  btnLiveMicToggle.addEventListener("click", async () => {
    if (liveIsListening) {
      if (liveSpeechRecognizer) {
        try { liveSpeechRecognizer.abort(); } catch(e) {}
      }
      liveIsListening = false;
      btnLiveMicToggle.classList.remove("active");
      const status = document.getElementById("liveStatusText");
      if (status) status.innerText = "Микрофон отключен (нажмите для включения)";
      const orb = document.getElementById("liveOrb");
      if (orb) orb.className = "live-orb";
    } else {
      await initLiveAudioHardware();
      liveIsListening = true;
      btnLiveMicToggle.classList.add("active");
      startLiveMediaRecorder();
      startLiveSpeechRecognition();
      const status = document.getElementById("liveStatusText");
      if (status) status.innerText = "🟢 Слушаю вас... Говорите";
    }
  });
}

// 10. Quick Text Input Handlers
function sendLiveTextInput() {
  const input = document.getElementById("liveTextInput");
  if (!input) return;
  const val = input.value.trim();
  if (!val) return;
  input.value = "";
  handleUserLiveUtterance(val);
}

if (btnLiveSendText) {
  btnLiveSendText.addEventListener("click", sendLiveTextInput);
}
if (liveTextInput) {
  liveTextInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendLiveTextInput();
    }
  });
}

// 11. Transfer Finalized Prompt to Antigravity
if (btnTransferPrompt) {
  btnTransferPrompt.addEventListener("click", async () => {
    if (liveHistory.length === 0) {
      alert("Сначала обсудите идею голосом, чтобы сформировать задачу.");
      return;
    }

    btnTransferPrompt.innerText = "⏳ Формирую задачу...";
    const status = document.getElementById("liveStatusText");
    if (status) status.innerText = "✨ Создаю структурированный промпт для Antigravity...";

    try {
      const res = await fetch(`${SERVER_URL}/api/gemini/summarize-task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ history: liveHistory })
      });

      if (res.ok) {
        const data = await res.json();
        const promptText = data.prompt || "";

        closeGeminiLiveModal();

        taskInput.value = promptText;
        taskInput.style.height = "auto";
        taskInput.style.height = (taskInput.scrollHeight) + "px";
        taskInput.focus();

        alert("✔ Готовая задача сформирована и перенесена в окно Antigravity! Можете запускать проект.");
      } else {
        alert("Не удалось сформировать промпт. Попробуйте еще раз.");
      }
    } catch (e) {
      alert("Ошибка: " + e.message);
    } finally {
      btnTransferPrompt.innerHTML = "<span>🚀 Сформировать промпт в Antigravity</span>";
    }
  });
}

// Close Live modal on background click
window.addEventListener("click", (e) => {
  const m = document.getElementById("modalGeminiLive");
  if (m && e.target === m) {
    closeGeminiLiveModal();
  }
});
