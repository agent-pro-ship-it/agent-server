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
const voiceStatusBar = document.getElementById("voiceStatusBar");
const voiceStatusText = document.getElementById("voiceStatusText");
const btnSelectModel = document.getElementById("btnSelectModel");
const currentModelName = document.getElementById("currentModelName");
const modelDropdown = document.getElementById("modelDropdown");
const btnAttach = document.getElementById("btnAttach");
const attachDropdown = document.getElementById("attachDropdown");
const filePicker = document.getElementById("filePicker");

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
const fileViewerCode = document.getElementById("fileViewerCode");

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
  fileViewerTitle.innerText = `${filePath} (${projId})`;
  fileViewerCode.innerText = "Загрузка...";
  modalFileViewer.classList.add("active");

  try {
    const res = await fetch(`${SERVER_URL}/api/projects/${projId}/file?path=${encodeURIComponent(filePath)}`);
    if (res.ok) {
      const data = await res.json();
      fileViewerCode.innerText = data.content || "// Файл пуст";
      return;
    }
  } catch (e) {
    fileViewerCode.innerText = "Ошибка чтения файла: " + e.message;
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
async function sendTask() {
  const text = taskInput.value.trim();
  if (!text) return;

  appendUserMessage(text);
  taskInput.value = "";
  taskInput.style.height = "auto";

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
    const res = await fetch(`${SERVER_URL}/api/task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: text,
        project_id: activeProject ? activeProject.id : null
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
    // Only display terminal accordion if there's real command output different from explanation
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

    // Render clean process accordion + formatted explanation without duplication
    appendAssistantMessage(processAccordion + formatMarkdown(explanationText));
    if (activeProject) loadProjectFiles(activeProject.id);

  } catch (err) {
    loadingBubble.innerHTML = "❌ Ошибка соединения с сервером. Попробуйте еще раз.";
  }
}

btnSend.addEventListener("click", sendTask);
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
const btnAttach = document.getElementById("btnAttach");
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

// 6. Rock-Solid Dual Voice Capture (Hardware getUserMedia + Web Speech API + Gemini AI Server Transcribe)
let mediaStream = null;
let speechRecognizer = null;

async function startListening() {
  isRecording = true;
  btnMic.classList.add("recording");
  voiceStatusBar.style.display = "flex";
  voiceStatusText.innerText = "🔴 Запись... Говорите задачу (нажмите еще раз для завершения)";
  audioChunks = [];

  // Request audio hardware stream directly inside user gesture
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    let options = {};
    if (typeof MediaRecorder !== "undefined") {
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        options = { mimeType: 'audio/webm;codecs=opus' };
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        options = { mimeType: 'audio/webm' };
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        options = { mimeType: 'audio/mp4' };
      }
      mediaRecorder = new MediaRecorder(mediaStream, options);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunks.push(e.data);
      };
      mediaRecorder.start(200);
    }
  } catch (err) {
    console.warn("Microphone access denied or error:", err);
    isRecording = false;
    btnMic.classList.remove("recording");
    voiceStatusBar.style.display = "none";
    alert("Доступ к микрофону заблокирован в браузере.\nПожалуйста, нажмите на значок настроек/замочка слева в адресной строке и включите «Микрофон».");
    return;
  }

  // Parallel Web Speech API for real-time live preview typing
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
          taskInput.value = text;
          taskInput.style.height = "auto";
          taskInput.style.height = (taskInput.scrollHeight) + "px";
          voiceStatusText.innerText = "🎙 " + text;
        }
      };

      speechRecognizer.onerror = (e) => {
        console.warn("SpeechRecognition preview error (MediaRecorder still active):", e.error);
      };

      speechRecognizer.start();
    } catch (e) {
      console.warn("SpeechRecognition start exception:", e);
    }
  }
}

async function stopListening() {
  isRecording = false;
  btnMic.classList.remove("recording");
  voiceStatusText.innerText = "⏳ Распознавание речи...";

  if (speechRecognizer) {
    try { speechRecognizer.stop(); } catch(e) {}
    speechRecognizer = null;
  }

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
    mediaStream = null;
  }

  await new Promise(r => setTimeout(r, 400));

  // If live recognition already filled taskInput, we are done
  if (taskInput.value.trim().length > 0) {
    voiceStatusBar.style.display = "none";
    taskInput.focus();
    return;
  }

  // Otherwise fallback to cloud transcription via Gemini AI
  if (audioChunks.length > 0) {
    const mime = (mediaRecorder && mediaRecorder.mimeType) || "audio/webm";
    const audioBlob = new Blob(audioChunks, { type: mime });

    if (audioBlob.size > 500) {
      try {
        const formData = new FormData();
        formData.append("file", audioBlob, "voice.webm");
        const resp = await fetch(`${SERVER_URL}/api/voice-transcribe`, {
          method: "POST",
          body: formData
        });
        if (resp.ok) {
          const resJson = await resp.json();
          if (resJson.success && resJson.text && resJson.text !== "NONE") {
            taskInput.value = resJson.text;
            taskInput.style.height = "auto";
            taskInput.style.height = (taskInput.scrollHeight) + "px";
            taskInput.focus();
          }
        }
      } catch (err) {
        console.warn("Cloud transcribe error:", err);
      }
    }
  }

  voiceStatusBar.style.display = "none";
}

btnMic.addEventListener("click", (e) => {
  e.preventDefault();
  if (isRecording) {
    stopListening();
  } else {
    startListening();
  }
});


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

const btnOpenGeminiLive = document.getElementById("btnOpenGeminiLive");
const btnCloseGeminiLive = document.getElementById("btnCloseGeminiLive");
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

// 5. Open / Close Live Session
async function openGeminiLiveModal() {
  initNaturalVoices();
  const m = document.getElementById("modalGeminiLive");
  if (m) m.classList.add("active");
  await startLiveSession();
}

function closeGeminiLiveModal() {
  stopLiveSession();
  const m = document.getElementById("modalGeminiLive");
  if (m) m.classList.remove("active");
}

if (btnOpenGeminiLive) {
  btnOpenGeminiLive.addEventListener("click", openGeminiLiveModal);
}

if (btnCloseGeminiLive) {
  btnCloseGeminiLive.addEventListener("click", closeGeminiLiveModal);
}

// Global delegated clicks
document.addEventListener("click", (e) => {
  if (e.target && e.target.closest("#btnOpenGeminiLive")) {
    openGeminiLiveModal();
  }
  if (e.target && e.target.closest("#btnCloseGeminiLive")) {
    closeGeminiLiveModal();
  }
});

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
