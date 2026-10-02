// Configuration & State
let SERVER_URL = localStorage.getItem("AGENT_SERVER_URL") || "https://agent-master-server.onrender.com";
if (SERVER_URL.endsWith("/")) SERVER_URL = SERVER_URL.slice(0, -1);

let isRecording = false;
let recognition = null;

// DOM Elements
const chatContainer = document.getElementById("chatContainer");
const messageInput = document.getElementById("messageInput");
const btnSend = document.getElementById("btnSend");
const btnMic = document.getElementById("btnMic");
const waveform = document.getElementById("waveform");
const statusDot = document.getElementById("statusDot");

// Modals
const modalStorage = document.getElementById("modalStorage");
const modalSettings = document.getElementById("modalSettings");

// Register PWA Service Worker
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

// Check Backend Connection & Status
async function checkHealth() {
  try {
    const res = await fetch(`${SERVER_URL}/api/status`);
    if (res.ok) {
      const data = await res.json();
      statusDot.style.background = "#30d158";
      statusDot.title = `Исполнитель онлайн: RAM ${data.system?.ram_used_mb}MB, Storj 25GB: ${data.storage?.storj_connected ? 'Подключен' : 'Ожидание'}`;
    } else {
      statusDot.style.background = "#ff9f0a";
    }
  } catch (e) {
    statusDot.style.background = "#ff453a";
    statusDot.title = "Сервер просыпается или оффлайн...";
  }
}
setInterval(checkHealth, 20000);
checkHealth();

// Append message to UI
function appendMessage(role, text, codeBlock = null, files = null) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerText = text;

  if (codeBlock) {
    const pre = document.createElement("pre");
    pre.innerText = codeBlock;
    div.appendChild(pre);
  }

  if (files && files.length > 0) {
    const filesDiv = document.createElement("div");
    filesDiv.style.fontSize = "12px";
    filesDiv.style.color = "var(--apple-green)";
    filesDiv.style.marginTop = "6px";
    filesDiv.innerText = "☁️ Сохранено в Storj 25GB: " + files.join(", ");
    div.appendChild(filesDiv);
  }

  chatContainer.appendChild(div);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return div;
}

// Send Message / Task to Server Executor
async function sendTask() {
  const text = messageInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  messageInput.value = "";

  const assistantBubble = appendMessage("assistant", "Исполняю задачу на сервере Render...");

  try {
    const res = await fetch(`${SERVER_URL}/api/task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: text })
    });

    if (!res.ok) {
      assistantBubble.innerText = "Ошибка сервера. Проверьте адрес бэкенда в настройках.";
      return;
    }

    const data = await res.json();
    assistantBubble.innerText = "";

    const explanation = data.explanation || (data.success ? "Задача успешно выполнена на сервере." : "Ошибка выполнения.");
    const output = data.stdout || data.stderr || (data.error ? data.error : "");
    const synced = data.cloud_synced_files || [];

    assistantBubble.innerText = explanation;

    if (output) {
      const pre = document.createElement("pre");
      pre.innerText = output;
      assistantBubble.appendChild(pre);
    }

    if (synced.length > 0) {
      const fInfo = document.createElement("div");
      fInfo.style.fontSize = "12px";
      fInfo.style.color = "var(--apple-green)";
      fInfo.style.marginTop = "6px";
      fInfo.innerText = "☁️ Сохранено в облако Storj 25GB: " + synced.join(", ");
      assistantBubble.appendChild(fInfo);
    }

    chatContainer.scrollTop = chatContainer.scrollHeight;

  } catch (err) {
    assistantBubble.innerText = "Не удалось подключиться к серверу Render. Он просыпается, попробуйте через минуту.";
  }
}

btnSend.addEventListener("click", sendTask);
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendTask();
});

// Voice Input (Web Speech API)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = "ru-RU";
  recognition.continuous = false;
  recognition.interimResults = true;

  recognition.onstart = () => {
    isRecording = true;
    btnMic.classList.add("recording");
    waveform.classList.add("active");
  };

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      transcript += event.results[i][0].transcript;
    }
    messageInput.value = transcript;
  };

  recognition.onend = () => {
    isRecording = false;
    btnMic.classList.remove("recording");
    waveform.classList.remove("active");
    if (messageInput.value.trim().length > 0) {
      sendTask();
    }
  };

  recognition.onerror = () => {
    isRecording = false;
    btnMic.classList.remove("recording");
    waveform.classList.remove("active");
  };

  btnMic.addEventListener("click", () => {
    if (isRecording) {
      recognition.stop();
    } else {
      recognition.start();
    }
  });
} else {
  btnMic.style.opacity = "0.4";
  btnMic.title = "Голосовой ввод не поддерживается";
}

// Modal Handlers
function setupModal(triggerId, modalEl, onOpen) {
  const trigger = document.getElementById(triggerId);
  if (!trigger || !modalEl) return;
  trigger.addEventListener("click", () => {
    modalEl.classList.add("open");
    if (onOpen) onOpen();
  });
  modalEl.addEventListener("click", (e) => {
    if (e.target === modalEl) modalEl.classList.remove("open");
  });
}

// Storage Modal
setupModal("btnStorageModal", modalStorage, async () => {
  const listEl = document.getElementById("storageFilesList");
  listEl.innerHTML = "Загрузка файлов из Storj 25GB...";
  try {
    const res = await fetch(`${SERVER_URL}/api/files`);
    const data = await res.json();
    listEl.innerHTML = "";
    const cloud = data.storj_cloud_25gb || [];
    const local = data.local_workspace || [];

    if (cloud.length === 0 && local.length === 0) {
      listEl.innerHTML = "<div style='opacity:0.6; font-size:13px;'>Файлы пока отсутствуют. Дайте агенту задачу создать проект!</div>";
      return;
    }

    cloud.forEach(f => {
      const item = document.createElement("div");
      item.className = "apple-pill";
      item.style.display = "flex";
      item.style.justifyContent = "space-between";
      item.innerHTML = `
        <span>☁️ ${f.name}</span>
        <span style="opacity:0.6; font-size:11px;">${Math.round(f.size / 1024)} KB (Storj)</span>
      `;
      listEl.appendChild(item);
    });

    local.forEach(f => {
      const item = document.createElement("div");
      item.className = "apple-pill";
      item.style.display = "flex";
      item.style.justifyContent = "space-between";
      item.innerHTML = `
        <span>📄 ${f.name}</span>
        <span style="opacity:0.6; font-size:11px;">Workspace</span>
      `;
      listEl.appendChild(item);
    });

  } catch (e) {
    listEl.innerHTML = "Ошибка загрузки файлов.";
  }
});

// Settings Modal
setupModal("btnSettingsModal", modalSettings, () => {
  document.getElementById("serverUrlInput").value = SERVER_URL;
});

document.getElementById("btnSaveServerUrl").addEventListener("click", () => {
  const url = document.getElementById("serverUrlInput").value.trim();
  if (url) {
    localStorage.setItem("AGENT_SERVER_URL", url);
    SERVER_URL = url;
    modalSettings.classList.remove("open");
    checkHealth();
  }
});
