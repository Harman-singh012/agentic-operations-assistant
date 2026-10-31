const messages = document.getElementById("messages");
const input = document.getElementById("q");
const sendBtn = document.getElementById("send");
const chatList = document.getElementById("chat-list");
const sidebar = document.getElementById("sidebar");
const menuBtn = document.getElementById("menu-btn");

const streamUrl = messages.dataset.streamUrl;
const homeUrl = messages.dataset.homeUrl;
const csrf = document.querySelector('meta[name="csrf-token"]').content;
let cid = messages.dataset.cid || "";

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function scrollDown() { messages.scrollTop = messages.scrollHeight; }
scrollDown();

function addUser(text) {
  const row = el("div", "msg user");
  row.append(el("div", "bubble", text));
  messages.append(row);
}

function addBot() {
  const row = el("div", "msg bot");
  const box = el("div", "bot-box");
  const dots = el("button", "dots");
  dots.type = "button";
  dots.innerHTML = "&#8942;";
  dots.setAttribute("aria-label", "Show steps");
  const bubble = el("div", "bubble thinking", "Thinking...");
  const panel = el("div", "steps-panel");
  box.append(dots, bubble, panel);
  row.append(box);
  messages.append(row);
  return { bubble, panel };
}

function addStep(panel, type, text) {
  const s = el("div", "step " + type);
  s.append(el("b", "", type.toUpperCase()), document.createTextNode(text));
  panel.append(s);
}

/* ---------- sidebar ---------- */
function addSidebarItem(id, title) {
  chatList.querySelectorAll(".chat-item.active").forEach((i) => i.classList.remove("active"));
  const item = el("div", "chat-item active");
  item.dataset.id = id;
  const a = el("a", "chat-link", title);
  a.href = chatList.dataset.chatBase.replace("/0/", "/" + id + "/");
  const del = el("button", "chat-del", "\u00d7");
  del.type = "button";
  del.title = "Delete chat";
  item.append(a, del);
  chatList.prepend(item);
}

function onMeta(d) {
  const id = String(d.cid);
  if (!cid) {
    cid = id;
    history.replaceState(null, "", chatList.dataset.chatBase.replace("/0/", "/" + id + "/"));
    addSidebarItem(id, d.title);
  } else {
    const item = chatList.querySelector('.chat-item[data-id="' + id + '"]');
    if (item) chatList.prepend(item);
  }
}

chatList.addEventListener("click", async (e) => {
  const del = e.target.closest(".chat-del");
  if (!del) return;
  const item = del.closest(".chat-item");
  if (!confirm("Delete this chat?")) return;
  const url = chatList.dataset.deleteBase.replace("/0/", "/" + item.dataset.id + "/");
  const r = await fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf } });
  if (r.ok) {
    const wasCurrent = String(item.dataset.id) === String(cid);
    item.remove();
    if (wasCurrent) window.location.href = homeUrl;
  }
});

/* ---------- three-dot steps panel ---------- */
document.addEventListener("click", (e) => {
  if (e.target.closest(".steps-panel")) return;
  const dots = e.target.closest(".dots");
  const target = dots ? dots.parentElement.querySelector(".steps-panel") : null;
  document.querySelectorAll(".steps-panel.open").forEach((p) => {
    if (p !== target) p.classList.remove("open");
  });
  if (target) target.classList.toggle("open");
});

/* ---------- asking ---------- */
function ask(text) {
  const q = (text || input.value).trim();
  if (!q || sendBtn.disabled) return;

  const welcome = messages.querySelector(".welcome");
  if (welcome) welcome.remove();

  input.value = "";
  sendBtn.disabled = true;
  addUser(q);
  const bot = addBot();
  addStep(bot.panel, "question", q);
  scrollDown();

  let finished = false;
  const es = new EventSource(
    streamUrl + "?cid=" + encodeURIComponent(cid) + "&q=" + encodeURIComponent(q)
  );

  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.type === "meta") { onMeta(d); return; }
    if (d.type === "done") {
      finished = true;
      es.close();
      sendBtn.disabled = false;
      input.focus();
      return;
    }
    if (d.type === "final") {
      bot.bubble.classList.remove("thinking");
      bot.bubble.textContent = d.text;
      addStep(bot.panel, "final", d.text);
    } else {
      addStep(bot.panel, d.type, d.text);
      if (d.type === "error") bot.bubble.classList.add("error");
    }
    scrollDown();
  };

  es.onerror = () => {
    es.close();
    sendBtn.disabled = false;
    if (!finished) {
      bot.bubble.classList.remove("thinking");
      bot.bubble.classList.add("error");
      bot.bubble.textContent = "Connection lost. Make sure the server is running and try again.";
    }
  };
}

sendBtn.addEventListener("click", () => ask());
input.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
messages.addEventListener("click", (e) => {
  const ex = e.target.closest(".example");
  if (ex) ask(ex.textContent);
});
if (menuBtn) menuBtn.addEventListener("click", () => sidebar.classList.toggle("open"));