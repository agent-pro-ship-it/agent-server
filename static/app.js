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
      </div>
      <div class="project-sub-row">
        <span class="project-preview">${escapeHtml(proj.task || "Antigravity Project")}</span>
        <span class="project-time">${escapeHtml(proj.time || "")}</span>
      </div>
    `;
    projectsList.appendChild(item);
  });
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

  const loadingBubble = appendAssistantMessage("⏳ *Google Antigravity выполняет задачу в папке проекта...*");

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

    let outputHtml = "";
    if (data.explanation) {
      outputHtml += formatMarkdown(data.explanation);
    }
    if (data.stdout || data.stderr) {
      const code = data.stdout || data.stderr;
      outputHtml += `<pre><code>${escapeHtml(code)}</code></pre>`;
    }
    if (data.cloud_synced_files && data.cloud_synced_files.length > 0) {
      outputHtml += `<p style="font-size:12px; color:#16a34a; margin-top:8px;">☁️ Синхронизировано в Storj 25GB: <code>${data.cloud_synced_files.join(", ")}</code></p>`;
    }

    appendAssistantMessage(outputHtml || "Задача выполнена.");
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

// 6. Direct Fresh Speech Recognition on every tap (Fixes Safari Single-Use Instance Bug)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let activeRecognition = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

function startListening() {
  if (SpeechRecognition) {
    try {
      activeRecognition = new SpeechRecognition();
      activeRecognition.lang = "ru-RU";
      activeRecognition.continuous = true;
      activeRecognition.interimResults = true;
      activeRecognition.maxAlternatives = 1;

      activeRecognition.onstart = () => {
        isRecording = true;
        btnMic.classList.add("recording");
        voiceStatusBar.style.display = "flex";
        voiceStatusText.innerText = "🔴 Говорите задачу... (микрофон активен)";
      };

      activeRecognition.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let i = 0; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript + " ";
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        const current = (final + interim).trim();
        if (current) {
          taskInput.value = current;
          taskInput.style.height = "auto";
          taskInput.style.height = (taskInput.scrollHeight) + "px";
          voiceStatusText.innerText = "🎙 " + current;
        }
      };

      activeRecognition.onerror = (e) => {
        console.warn("SpeechRecognition error:", e.error);
        if (e.error === "not-allowed" || e.error === "service-not-allowed") {
          isRecording = false;
          btnMic.classList.remove("recording");
          voiceStatusBar.style.display = "none";
          alert("Доступ к микрофону заблокирован в настройках браузера. Разрешите микрофон для этого сайта.");
        } else if (e.error === "no-speech") {
          // ignore silence
        } else {
          stopListening();
          startMediaRecorderFallback();
        }
      };

      activeRecognition.onend = () => {
        isRecording = false;
        btnMic.classList.remove("recording");
        voiceStatusBar.style.display = "none";
        if (taskInput.value.trim()) {
          taskInput.focus();
        }
      };

      // Direct synchronous start inside the user click!
      activeRecognition.start();
      return;
    } catch (err) {
      console.warn("SpeechRecognition start exception, using fallback:", err);
    }
  }

  startMediaRecorderFallback();
}

function stopListening() {
  isRecording = false;
  btnMic.classList.remove("recording");
  voiceStatusBar.style.display = "none";

  if (activeRecognition) {
    try { activeRecognition.stop(); } catch(e) {}
    activeRecognition = null;
  }

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    stopMediaRecorderFallback();
  }
}

async function startMediaRecorderFallback() {
  audioChunks = [];
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    let options = {};
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      options = { mimeType: 'audio/webm;codecs=opus' };
    } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
      options = { mimeType: 'audio/mp4' };
    }
    mediaRecorder = new MediaRecorder(stream, options);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(250);
    isRecording = true;
    btnMic.classList.add("recording");
    voiceStatusBar.style.display = "flex";
    voiceStatusText.innerText = "🔴 Запись аудио... Говорите";
  } catch (err) {
    alert("Не удалось включить микрофон: разрешите доступ к микрофону в браузере.");
    btnMic.classList.remove("recording");
    voiceStatusBar.style.display = "none";
  }
}

async function stopMediaRecorderFallback() {
  isRecording = false;
  btnMic.classList.remove("recording");
  voiceStatusText.innerText = "Расшифровка через сервер...";

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(track => track.stop());

    await new Promise(r => setTimeout(r, 400));
    const mime = mediaRecorder.mimeType || "audio/webm";
    const audioBlob = new Blob(audioChunks, { type: mime });

    if (audioBlob.size > 1000) {
      try {
        const formData = new FormData();
        formData.append("file", audioBlob, "voice.webm");
        const resp = await fetch(`${SERVER_URL}/api/voice-transcribe`, {
          method: "POST",
          body: formData
        });
        if (resp.ok) {
          const resJson = await resp.json();
          if (resJson.success && resJson.text) {
            taskInput.value = resJson.text;
            taskInput.style.height = "auto";
            taskInput.style.height = (taskInput.scrollHeight) + "px";
          }
        }
      } catch (e) {
        console.warn("Fallback transcribe error:", e);
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
