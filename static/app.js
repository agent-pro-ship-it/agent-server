// Antigravity Cloud Web Client & Engine Orchestrator
let SERVER_URL = localStorage.getItem("AGENT_SERVER_URL") || "https://agent-master-server.onrender.com";
if (SERVER_URL.endsWith("/")) SERVER_URL = SERVER_URL.slice(0, -1);

// Projects Data matching user's exact screenshot
const DEFAULT_PROJECTS = [
  { id: "agent", name: "Агент", task: "Бесплатный Сервер Для Антигравити", time: "2m", active: true },
  { id: "recruiter", name: "сайт Recruiter I Club", task: "Premium B2B SaaS Architecture", time: "53m", active: false },
  { id: "resume", name: "парсер и резюме", task: "Free AI Resume Optimizer", time: "1h", active: false },
  { id: "crm", name: "проект онлайн срм", task: "Разработка Полнофункциональной CRM", time: "7h", active: false },
  { id: "contract", name: "прога для договор...", task: "Автоматизация Заполнения Документов", time: "14d", active: false },
  { id: "recruiter_proj", name: "Recruiter проект", task: "Getting Vercel Access Token", time: "18d", active: false },
  { id: "site", name: "сайт", task: "Разработка Премиального Лендинга", time: "22d", active: false },
  { id: "bot", name: "telegram bot", task: "Создание Бота Для Сбора Заявок", time: "1mo", active: false },
  { id: "crm_debug", name: "отладка срм антиг...", task: "Фикс багов и деплой на сервер", time: "2mo", active: false }
];

let projects = JSON.parse(localStorage.getItem("ANTIGRAVITY_PROJECTS") || "null") || DEFAULT_PROJECTS;
let activeProject = projects.find(p => p.active) || projects[0];

// Conversation Store per project
let conversations = JSON.parse(localStorage.getItem("ANTIGRAVITY_CHATS") || "{}");

// DOM Elements
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const btnToggleSidebar = document.getElementById("btnToggleSidebar");
const projectsList = document.getElementById("projectsList");
const btnNewChat = document.getElementById("btnNewChat");
const crumbProject = document.getElementById("crumbProject");
const crumbTask = document.getElementById("crumbTask");
const chatFeed = document.getElementById("chatFeed");
const taskInput = document.getElementById("taskInput");
const btnSend = document.getElementById("btnSend");
const btnMic = document.getElementById("btnMic");
const btnSelectModel = document.getElementById("btnSelectModel");
const currentModelName = document.getElementById("currentModelName");
const modelDropdown = document.getElementById("modelDropdown");
const btnAttach = document.getElementById("btnAttach");
const attachDropdown = document.getElementById("attachDropdown");
const filePicker = document.getElementById("filePicker");

// Modals
const modalTerminal = document.getElementById("modalTerminal");
const btnOpenTerminal = document.getElementById("btnOpenTerminal");
const btnCloseTerminal = document.getElementById("btnCloseTerminal");
const modalSettings = document.getElementById("modalSettings");
const btnOpenSettings = document.getElementById("btnOpenSettings");
const btnCloseSettings = document.getElementById("btnCloseSettings");
const settingServerUrl = document.getElementById("settingServerUrl");
const btnSaveServerUrl = document.getElementById("btnSaveServerUrl");

// Speech Recognition
let isRecording = false;
let recognition = null;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// Render Projects List
function renderProjects() {
  projectsList.innerHTML = "";
  projects.forEach((proj) => {
    const item = document.createElement("div");
    item.className = `project-item ${proj.id === activeProject.id ? "active" : ""}`;
    item.onclick = () => selectProject(proj.id);

    item.innerHTML = `
      <div class="project-top-row">
        <span class="folder-icon">📁</span>
        <span class="project-name">${escapeHtml(proj.name)}</span>
      </div>
      <div class="project-sub-row">
        <span class="project-preview">${escapeHtml(proj.task)}</span>
        <span class="project-time">${escapeHtml(proj.time)}</span>
      </div>
    `;
    projectsList.appendChild(item);
  });
}

function selectProject(projId) {
  projects.forEach(p => p.active = (p.id === projId));
  activeProject = projects.find(p => p.id === projId) || projects[0];
  localStorage.setItem("ANTIGRAVITY_PROJECTS", JSON.stringify(projects));

  crumbProject.innerText = activeProject.name;
  crumbTask.innerText = activeProject.task;

  renderProjects();
  loadProjectConversation(activeProject.id);

  // Close mobile sidebar if open
  sidebar.classList.remove("open");
  sidebarBackdrop.classList.remove("active");
}

function loadProjectConversation(projId) {
  chatFeed.innerHTML = "";
  const history = conversations[projId] || [];

  if (history.length === 0) {
    // Initial welcome matching the screenshot
    appendAssistantMessage(`
<div class="antigravity-quote">
Привет! Я — настоящий агент Antigravity, запущенный на сервере Render. Я готов выполнять команды, редактировать код и решать любые поставленные задачи!
</div>

### 3. Как теперь этим пользоваться (3 способа)

1. **Через мобильный пульт Apple PWA (с телефона 24/7)**:
   - Откройте: <a href="https://agent-pro-ship-it.github.io/agent-mobile-apple/" target="_blank">https://agent-pro-ship-it.github.io/agent-mobile-apple/</a>
   - Любая задача, отправленная через чат или голос, теперь уходит напрямую в официальный движок Antigravity на сервере под вашей подпиской Google Pro (без ограничений бесплатных API-ключей).

2. **Через официальный пульт Google Antigravity (Remote Control)**:
   - Откройте: <a href="https://antigravity.google.com" target="_blank">https://antigravity.google.com</a> под вашим аккаунтом \`recruiterclub.bot@gmail.com\`.
   - В списке активных инстансов у вас отображается облачный агент \`AgentMasterCloud\`, запущенный на Render!

3. **Прямо через веб-терминал**:
   - Откройте: <a href="https://agent-master-server.onrender.com/terminal/" target="_blank">https://agent-master-server.onrender.com/terminal/</a>
   - Нажмите Enter — перед вами полноценный bash-терминал сервера, где доступна команда \`agy\` и все системные инструменты.
`);
  } else {
    history.forEach(msg => {
      if (msg.role === "user") appendUserMessage(msg.text, false);
      else appendAssistantMessage(msg.html, false);
    });
  }
}

// Append User Message Card
function appendUserMessage(text, save = true) {
  const div = document.createElement("div");
  div.className = "msg-user";
  div.innerText = text;
  chatFeed.appendChild(div);
  chatFeed.scrollTop = chatFeed.scrollHeight;

  if (save) {
    if (!conversations[activeProject.id]) conversations[activeProject.id] = [];
    conversations[activeProject.id].push({ role: "user", text: text });
    localStorage.setItem("ANTIGRAVITY_CHATS", JSON.stringify(conversations));
  }
  return div;
}

// Append Assistant Message with Markdown & Double Quote Support
function appendAssistantMessage(rawContent, save = true) {
  const div = document.createElement("div");
  div.className = "msg-assistant";
  div.innerHTML = formatMarkdown(rawContent);

  // Message Actions Footer (Copy, Thumb up, Thumb down)
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

  if (save) {
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

// Send Task to Server (delegates directly to Antigravity CLI Google Pro)
async function sendTask() {
  const text = taskInput.value.trim();
  if (!text) return;

  appendUserMessage(text);
  taskInput.value = "";
  taskInput.style.height = "auto";

  const loadingBubble = appendAssistantMessage("⏳ *Google Antigravity думает и выполняет задачу на сервере...*");

  try {
    const res = await fetch(`${SERVER_URL}/api/task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: text })
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

    appendAssistantMessage(outputHtml || "Задача завершена.");

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

// Auto-expand textarea
taskInput.addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = (this.scrollHeight) + "px";
});

// Voice Input (Web Speech API)
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = "ru-RU";
  recognition.continuous = false;
  recognition.interimResults = true;

  recognition.onstart = () => {
    isRecording = true;
    btnMic.classList.add("recording");
  };

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      transcript += event.results[i][0].transcript;
    }
    taskInput.value = transcript;
    taskInput.style.height = "auto";
    taskInput.style.height = (taskInput.scrollHeight) + "px";
  };

  recognition.onerror = () => {
    isRecording = false;
    btnMic.classList.remove("recording");
  };

  recognition.onend = () => {
    isRecording = false;
    btnMic.classList.remove("recording");
    if (taskInput.value.trim().length > 0) {
      sendTask();
    }
  };

  btnMic.addEventListener("click", () => {
    if (isRecording) {
      recognition.stop();
    } else {
      recognition.start();
    }
  });
} else {
  btnMic.addEventListener("click", () => {
    alert("Голосовой ввод не поддерживается вашим браузером. Используйте Chrome или Safari.");
  });
}

// Sidebar Toggle (Mobile & Desktop)
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

// New Conversation Button
btnNewChat.addEventListener("click", () => {
  const title = prompt("Название нового проекта / задачи:", "Новая задача");
  if (!title) return;
  const newId = "proj_" + Date.now();
  const newProj = { id: newId, name: title, task: "Новый диалог Antigravity", time: "just now", active: true };
  projects.forEach(p => p.active = false);
  projects.unshift(newProj);
  activeProject = newProj;
  localStorage.setItem("ANTIGRAVITY_PROJECTS", JSON.stringify(projects));
  renderProjects();
  selectProject(newId);
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
btnOpenTerminal.addEventListener("click", () => {
  modalTerminal.classList.add("active");
});
btnCloseTerminal.addEventListener("click", () => {
  modalTerminal.classList.remove("active");
});

// Settings Modal
btnOpenSettings.addEventListener("click", () => {
  settingServerUrl.value = SERVER_URL;
  modalSettings.classList.add("active");
});
btnCloseSettings.addEventListener("click", () => {
  modalSettings.classList.remove("active");
});
btnSaveServerUrl.addEventListener("click", () => {
  let val = settingServerUrl.value.trim();
  if (val.endsWith("/")) val = val.slice(0, -1);
  SERVER_URL = val;
  localStorage.setItem("AGENT_SERVER_URL", SERVER_URL);
  modalSettings.classList.remove("active");
  alert("Адрес сервера сохранен!");
});

// Close modals on background click
window.addEventListener("click", (e) => {
  if (e.target === modalTerminal) modalTerminal.classList.remove("active");
  if (e.target === modalSettings) modalSettings.classList.remove("active");
});

// Helper: Simple Markdown Formatter
function formatMarkdown(text) {
  if (!text) return "";
  let html = text;

  // Double quotes / box format: || text
  html = html.replace(/^\|\|\s*(.+)$/gm, '<div class="antigravity-quote">$1</div>');

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

  // Inline Code
  html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^\)]+)\)/gim, '<a href="$2" target="_blank">$1</a>');

  // Lists
  html = html.replace(/^\s*\* (.*$)/gim, '<ul><li>$1</li></ul>');
  html = html.replace(/^\s*\d+\.\s*(.*$)/gim, '<ol><li>$1</li></ol>');
  html = html.replace(/<\/ul>\s*<ul>/gim, '');
  html = html.replace(/<\/ol>\s*<ol>/gim, '');

  // Line breaks
  html = html.replace(/\n/gim, '<br>');
  return html;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Initialize
renderProjects();
selectProject(activeProject.id);

// PWA Service Worker
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
