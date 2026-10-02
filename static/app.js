// Configuration & State
let SERVER_URL = localStorage.getItem(AGENT_SERVER_URL) || window.location.origin;
if (SERVER_URL.endsWith(/)) SERVER_URL = SERVER_URL.slice(0, -1);

let chatHistory = [];
let isRecording = false;
let recognition = null;
let ws = null;

// DOM Elements
const chatContainer = document.getElementById(chatContainer);
const messageInput = document.getElementById(messageInput);
const btnSend = document.getElementById(btnSend);
const btnMic = document.getElementById(btnMic);
const waveform = document.getElementById(waveform);
const statusDot = document.getElementById(statusDot);
const currentAccountLabel = document.getElementById(currentAccountLabel);

// Modals
const modalAccount = document.getElementById(modalAccount);
const modalSkills = document.getElementById(modalSkills);
const modalStorage = document.getElementById(modalStorage);
const modalSettings = document.getElementById(modalSettings);

// Register PWA Service Worker
if (serviceWorker in navigator) {
  navigator.serviceWorker.register(/sw.js).catch(() => {});
}

// Check Backend Connection
async function checkHealth() {
  try {
    const res = await fetch(${SERVER_URL}/health);
    if (res.ok) {
      const data = await res.json();
      statusDot.style.background = #30d158;
      statusDot.title = Connected to Render Server;
      if (data.current_account && data.current_account.name) {
        currentAccountLabel.innerText = data.current_account.name;
      }
    } else {
      statusDot.style.background = #ff9f0a;
    }
  } catch (e) {
    statusDot.style.background = #ff453a;
    statusDot.title = Offline or waking up...;
  }
}
setInterval(checkHealth, 25000);
checkHealth();

// Append message to UI
function appendMessage(role, text) {
  const div = document.createElement(div);
  div.className = message ;
  div.innerText = text;
  chatContainer.appendChild(div);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return div;
}

// Send Message Flow
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  appendMessage(user, text);
  messageInput.value = ";
 chatHistory.push({ role: user, content: text });

 const assistantBubble = appendMessage(assistant, ...);

 try {
 const res = await fetch(${SERVER_URL}/api/chat, {
 method: POST,
 headers: { Content-Type: application/json },
 body: JSON.stringify({ message: text, history: chatHistory.slice(-10) })
 });

 if (!res.ok) {
 assistantBubble.innerText = Ошибка сервера. Проверьте адрес бэкенда в настройках.;
 return;
 }

 const reader = res.body.getReader();
 const decoder = new TextDecoder();
 let fullText = ;
 assistantBubble.innerText = ;

 while (true) {
 const { done, value } = await reader.read();
 if (done) break;

 const chunk = decoder.decode(value);
 const lines = chunk.split(\n);
 for (const line of lines) {
 if (line.startsWith(data: )) {
 try {
 const data = JSON.parse(line.slice(6));
 if (data.type === chunk) {
 fullText += data.text;
 assistantBubble.innerText = fullText;
 chatContainer.scrollTop = chatContainer.scrollHeight;
 } else if (data.type === account_switch) {
 const notice = document.createElement(div);
 notice.style.fontSize = 12px;
 notice.style.color = var(--apple-orange);
 notice.style.margin = 4px 0;
 notice.innerText = ⚡  + data.notice;
 chatContainer.appendChild(notice);
 checkHealth();
 } else if (data.type === error) {
 assistantBubble.innerText = data.text;
 }
 } catch (e) {}
 }
 }
 }

 chatHistory.push({ role: assistant, content: fullText });

 } catch (err) {
 assistantBubble.innerText = Не удалось подключиться к серверу Render. Проверьте соединение.;
 }
}

btnSend.addEventListener(click, sendMessage);
messageInput.addEventListener(keydown, (e) => {
 if (e.key === Enter) sendMessage();
});

// Voice Input (Web Speech API)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
 recognition = new SpeechRecognition();
 recognition.lang = ru-RU;
 recognition.continuous = false;
 recognition.interimResults = true;

 recognition.onstart = () => {
 isRecording = true;
 btnMic.classList.add(recording);
 waveform.classList.add(active);
 };

 recognition.onresult = (event) => {
 let transcript = ;
 for (let i = event.resultIndex; i < event.results.length; ++i) {
 transcript += event.results[i][0].transcript;
 }
 messageInput.value = transcript;
 };

 recognition.onend = () => {
 isRecording = false;
 btnMic.classList.remove(recording);
 waveform.classList.remove(active);
 if (messageInput.value.trim().length > 0) {
 sendMessage();
 }
 };

 recognition.onerror = () => {
 isRecording = false;
 btnMic.classList.remove(recording);
 waveform.classList.remove(active);
 };

 btnMic.addEventListener(click, () => {
 if (isRecording) {
 recognition.stop();
 } else {
 recognition.start();
 }
 });
} else {
 btnMic.style.opacity = 0.4;
 btnMic.title = Голосовой ввод не поддерживается браузером;
}

// Modal Sheet Handlers
function setupModal(triggerId, modalEl, onOpen) {
 document.getElementById(triggerId).addEventListener(click, () => {
 modalEl.classList.add(open);
 if (onOpen) onOpen();
 });
 modalEl.addEventListener(click, (e) => {
 if (e.target === modalEl) modalEl.classList.remove(open);
 });
}

// 1. Account Switcher Modal
setupModal(btnAccountModal, modalAccount, async () => {
 const listEl = document.getElementById(accountsList);
 listEl.innerHTML = Загрузка...;
 try {
 const res = await fetch(${SERVER_URL}/api/accounts);
 const data = await res.json();
 listEl.innerHTML = ;
 data.accounts.forEach((acc, index) => {
 const card = document.createElement(div);
 card.className = apple-pill;
 card.style.display = flex;
 card.style.justifyContent = space-between;
 card.style.padding = 10px 14px;
 card.innerHTML = 
 <div>
 <b></b> <span style=opacity:0.6; font-size:12px;>()</span>
 </div>
 <span style=color:;>
 
 </span>
 ;
 card.addEventListener(click, async () => {
 await fetch(${SERVER_URL}/api/accounts/switch, {
 method: POST,
 headers: { Content-Type: application/json },
 body: JSON.stringify({ index })
 });
 modalAccount.classList.remove(open);
 checkHealth();
 });
 listEl.appendChild(card);
 });
 } catch (e) {
 listEl.innerHTML = Ошибка загрузки списка аккаунтов.;
 }
});

// Add Account
document.getElementById(btnAddAccount).addEventListener(click, async () => {
 const name = document.getElementById(newAccountName).value.trim();
 const key = document.getElementById(newAccountKey).value.trim();
 if (!name || !key) return;
 await fetch(${SERVER_URL}/api/accounts/add, {
 method: POST,
 headers: { Content-Type: application/json },
 body: JSON.stringify({ name, key })
 });
 document.getElementById(newAccountName).value = ;
 document.getElementById(newAccountKey).value = ;
 modalAccount.classList.remove(open);
 checkHealth();
});

// 2. Skills Modal
setupModal(btnSkillsModal, modalSkills, async () => {
 const listEl = document.getElementById(skillsList);
 listEl.innerHTML = Загрузка навыков...;
 try {
 const res = await fetch(${SERVER_URL}/api/skills);
 const data = await res.json();
 listEl.innerHTML = ;
 data.skills.forEach(skill => {
 const item = document.createElement(div);
 item.style.background = rgba(255,255,255,0.06);
 item.style.padding = 10px 14px;
 item.style.borderRadius = 14px;
 item.innerHTML = 
 <div style=font-weight:600; font-size:14px; margin-bottom:4px;>⚡ </div>
 <div style=font-size:12px; color:var(--text-secondary); max-height:60px; overflow:hidden;>...</div>
 ;
 listEl.appendChild(item);
 });
 } catch (e) {
 listEl.innerHTML = Ошибка загрузки навыков.;
 }
});

// 3. Storage Modal
setupModal(btnStorageModal, modalStorage, async () => {
 const listEl = document.getElementById(storageFilesList);
 listEl.innerHTML = Загрузка файлов...;
 try {
 const res = await fetch(${SERVER_URL}/api/files);
 const data = await res.json();
 listEl.innerHTML = ;
 if (!data.files || data.files.length === 0) {
 listEl.innerHTML = <div style='opacity:0.6; font-size:13px;'>Файлы пока отсутствуют.</div>;
 return;
 }
 data.files.forEach(f => {
 const item = document.createElement(div);
 item.className = apple-pill;
 item.style.display = flex;
 item.style.justifyContent = space-between;
 item.innerHTML = 
 <span>📄 </span>
 <span style=opacity:0.6; font-size:11px;></span>
 ;
 listEl.appendChild(item);
 });
 } catch (e) {
 listEl.innerHTML = Ошибка загрузки файлов.;
 }
});

// 4. Settings Modal
setupModal(btnSettingsModal, modalSettings, () => {
 document.getElementById(serverUrlInput).value = SERVER_URL;
});

document.getElementById(btnSaveServerUrl).addEventListener(click, () => {
 const url = document.getElementById(serverUrlInput).value.trim();
 if (url) {
 localStorage.setItem(AGENT_SERVER_URL, url);
 SERVER_URL = url;
 modalSettings.classList.remove(open);
 checkHealth();
 }
});
