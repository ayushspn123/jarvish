// JARVIS web app — continuous voice with WebRTC echo-cancelled mic + barge-in.

const $ = (id) => document.getElementById(id);
const orb = $("orb"), orbLabel = $("orbLabel"), statusEl = $("status"), logEl = $("log");
const talkBtn = $("talk"), newChatBtn = $("newChat");
const typeForm = $("typeForm"), typeInput = $("typeInput");

let ws, recognition, audio = null;
let sessionActive = false;
let speaking = false;     // JARVIS audio is playing
let booted = false;

// ---------- WebSocket ----------
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === "ready") { booted = true; setStatus("Ready — tap to talk"); }
    else if (m.type === "filler") { setStatus(m.text); }   // transient "thinking" line
    else if (m.type === "reply") { addMsg("jarvis", m.text); }
    else if (m.type === "audio") { playAudio(m.b64); }
  };
  ws.onclose = () => { setStatus("Disconnected — reconnecting…"); setTimeout(connect, 1500); };
}
connect();

// ---------- UI helpers ----------
function setState(s, label) {
  orb.className = "orb " + s;
  if (label) orbLabel.textContent = label;
}
function setStatus(t) { statusEl.textContent = t; }
function addMsg(who, text) {
  const d = document.createElement("div");
  d.className = "msg " + who;
  d.textContent = text;
  logEl.appendChild(d);
  logEl.scrollTop = logEl.scrollHeight;
}

// ---------- Audio playback (with barge-in) ----------
function playAudio(b64) {
  stopAudio();
  audio = new Audio("data:audio/mpeg;base64," + b64);
  speaking = true;
  setState("speaking", "Speaking…");
  setStatus("Speaking — just talk to interrupt");
  audio.onended = () => { speaking = false; if (sessionActive) listeningState(); };
  audio.play().catch(() => { speaking = false; });
}
function stopAudio() {
  if (audio) { try { audio.pause(); } catch (e) {} audio = null; }
  speaking = false;
}

function listeningState() { setState("listening", "Listening…"); setStatus("Listening — go ahead"); }

// ---------- Speech recognition ----------
function makeRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { setStatus("This browser has no speech recognition — use Chrome."); return null; }
  const r = new SR();
  r.continuous = true;
  r.interimResults = true;
  r.lang = "en-IN";
  r.onresult = (e) => {
    const res = e.results[e.results.length - 1];
    const text = res[0].transcript.trim();
    // Any speech while JARVIS is talking = barge-in: cut it off immediately.
    if (speaking && text.length > 0) { stopAudio(); listeningState(); }
    if (res.isFinal && text) {
      addMsg("user", text);
      setState("thinking", "Thinking…");
      setStatus("Thinking…");
      ws.send(JSON.stringify({ type: "message", text }));
    }
  };
  r.onend = () => { if (sessionActive) { try { r.start(); } catch (e) {} } };
  r.onerror = (e) => { if (e.error === "not-allowed") { setStatus("Mic blocked — allow microphone access."); stopSession(); } };
  return r;
}

async function startSession() {
  // Request the mic with echo cancellation so JARVIS doesn't hear itself (enables barge-in).
  try {
    await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (e) { setStatus("Microphone permission needed."); return; }

  recognition = makeRecognition();
  if (!recognition) return;
  sessionActive = true;
  try { recognition.start(); } catch (e) {}
  talkBtn.textContent = "Stop";
  talkBtn.classList.add("active");
  listeningState();
}

function stopSession() {
  sessionActive = false;
  if (recognition) { try { recognition.stop(); } catch (e) {} }
  stopAudio();
  talkBtn.textContent = "Start talking";
  talkBtn.classList.remove("active");
  setState("idle", "Tap to talk");
  setStatus("Idle");
}

// ---------- Text input (type commands, e.g. from your phone) ----------
function sendText(text) {
  text = text.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  stopAudio();
  addMsg("user", text);
  setState("thinking", "Thinking…");
  setStatus("Thinking…");
  ws.send(JSON.stringify({ type: "message", text }));
}
typeForm.onsubmit = (e) => { e.preventDefault(); sendText(typeInput.value); typeInput.value = ""; };

// ---------- Buttons ----------
talkBtn.onclick = () => { sessionActive ? stopSession() : startSession(); };
orb.onclick = () => { if (!sessionActive) startSession(); };
newChatBtn.onclick = () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "reset" }));
  logEl.innerHTML = "";
  setStatus("New chat started");
};

// ---------- PWA service worker ----------
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
