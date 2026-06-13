const examples = [
  "Có bao nhiêu tin bất động sản ở Hà Nội?",
  "Mỗi danh mục gốc có bao nhiêu tin đăng?",
  "Top 10 khu vực có nhiều tin xe nhất là gì?",
  "Giá trung bình theo từng nhóm danh mục là bao nhiêu?"
];

const healthStatus = document.querySelector("#healthStatus");
const askForm = document.querySelector("#askForm");
const questionInput = document.querySelector("#questionInput");
const roundInput = document.querySelector("#roundInput");
const messages = document.querySelector("#messages");
const sqlBox = document.querySelector("#sqlBox code");
const roundCount = document.querySelector("#roundCount");
const suggestions = document.querySelector("#suggestions");
const loadSchemaButton = document.querySelector("#loadSchemaButton");
const schemaBox = document.querySelector("#schemaBox");
const detailsPanel = document.querySelector("#detailsPanel");
const toggleSqlButton = document.querySelector("#toggleSqlButton");
const closeSqlButton = document.querySelector("#closeSqlButton");
const sqlPanel = document.querySelector("#sqlPanel");
const runSqlButton = document.querySelector("#runSqlButton");
const sqlInput = document.querySelector("#sqlInput");
const queryResult = document.querySelector("#queryResult");
const newChatButton = document.querySelector("#newChatButton");

function setBusy(button, busy, busyText) {
  button.disabled = busy;
  if (busyText) {
    button.dataset.idleText = button.dataset.idleText || button.textContent;
    button.textContent = busy ? busyText : button.dataset.idleText;
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Yêu cầu thất bại: ${response.status}`);
  }
  return payload;
}

function addMessage(role, text, options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "Bạn" : "AI";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (options.error) {
    bubble.classList.add("error-text");
  }
  bubble.textContent = text;

  article.append(avatar, bubble);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function renderRows(container, rows) {
  if (!rows || rows.length === 0) {
    container.innerHTML = "<div class=\"bubble\">Không có dòng kết quả.</div>";
    return;
  }

  const columns = Object.keys(rows[0]);
  const head = columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns.map((column) => `<td>${escapeHtml(row[column] ?? "")}</td>`).join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function autoGrowTextarea() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 160)}px`;
}

async function loadHealth() {
  try {
    const health = await requestJson("/health");
    healthStatus.textContent = "Đã kết nối";
  } catch (error) {
    healthStatus.textContent = "API chưa sẵn sàng";
  }
}

async function loadSchema() {
  setBusy(loadSchemaButton, true, "Đang tải...");
  detailsPanel.classList.add("open");
  try {
    const payload = await requestJson("/schema");
    schemaBox.textContent = payload.schema;
  } catch (error) {
    schemaBox.textContent = error.message;
  } finally {
    setBusy(loadSchemaButton, false, "Đang tải...");
  }
}

async function runSql() {
  setBusy(runSqlButton, true, "Đang chạy...");
  queryResult.innerHTML = "";
  try {
    const payload = await requestJson("/query", {
      method: "POST",
      body: JSON.stringify({ sql: sqlInput.value, row_limit: 100 })
    });
    if (!payload.ok) {
      queryResult.innerHTML = `<div class="bubble error-text">${escapeHtml(payload.error || payload.content)}</div>`;
      return;
    }
    renderRows(queryResult, payload.rows);
  } catch (error) {
    queryResult.innerHTML = `<div class="bubble error-text">${escapeHtml(error.message)}</div>`;
  } finally {
    setBusy(runSqlButton, false, "Đang chạy...");
  }
}

async function askQuestion(event) {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    return;
  }

  const submitButton = askForm.querySelector("button[type='submit']");
  addMessage("user", question);
  questionInput.value = "";
  autoGrowTextarea();

  const pendingBubble = addMessage("assistant", "Đang tạo SQL và truy vấn cơ sở dữ liệu...");
  setBusy(submitButton, true, "...");
  sqlBox.textContent = "";
  roundCount.textContent = "";

  try {
    const payload = await requestJson("/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        max_rounds: Number(roundInput.value) || 10
      })
    });

    pendingBubble.textContent = payload.answer || "Không có câu trả lời.";
    sqlBox.textContent = payload.sql || "";
    sqlInput.value = payload.sql || sqlInput.value;
    roundCount.textContent = payload.rounds ? `${payload.rounds} vòng xử lý` : "";
    detailsPanel.classList.add("open");
  } catch (error) {
    pendingBubble.textContent = error.message;
    pendingBubble.classList.add("error-text");
  } finally {
    setBusy(submitButton, false, "...");
  }
}

function resetChat() {
  messages.innerHTML = "";
  addMessage(
    "assistant",
    "Xin chào. Bạn có thể hỏi về dữ liệu tin đăng, danh mục, khu vực, giá, bất động sản, xe, việc làm hoặc dịch vụ.\n\nVí dụ: “Mỗi danh mục gốc có bao nhiêu tin đăng?”"
  );
  sqlBox.textContent = "";
  roundCount.textContent = "";
  detailsPanel.classList.remove("open");
  questionInput.focus();
}

examples.forEach((example) => {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = example;
  button.addEventListener("click", () => {
    questionInput.value = example;
    autoGrowTextarea();
    questionInput.focus();
  });
  suggestions.appendChild(button);
});

askForm.addEventListener("submit", askQuestion);
loadSchemaButton.addEventListener("click", loadSchema);
runSqlButton.addEventListener("click", runSql);
newChatButton.addEventListener("click", resetChat);
toggleSqlButton.addEventListener("click", () => sqlPanel.classList.add("open"));
closeSqlButton.addEventListener("click", () => sqlPanel.classList.remove("open"));
questionInput.addEventListener("input", autoGrowTextarea);
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    askForm.requestSubmit();
  }
});

loadHealth();
