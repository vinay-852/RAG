const userSelect = document.querySelector("#userSelect");
const selectedUserName = document.querySelector("#selectedUserName");
const selectedUserDept = document.querySelector("#selectedUserDept");
const selectedUserRoles = document.querySelector("#selectedUserRoles");
const form = document.querySelector("#queryForm");
const question = document.querySelector("#question");
const answer = document.querySelector("#answer");
const routeBadge = document.querySelector("#routeBadge");
const confidence = document.querySelector("#confidence");
const traceUser = document.querySelector("#traceUser");
const traceRoles = document.querySelector("#traceRoles");
const traceRoute = document.querySelector("#traceRoute");
const sourceCount = document.querySelector("#sourceCount");
const sources = document.querySelector("#sources");
const askButton = document.querySelector("#askButton");

const DEFAULT_API_BASE_URL = "https://humble-rotary-phone-7gwx6j7qvr5h45x-8000.app.github.dev";
const API_BASE_URL = (window.API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");

let users = [];

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function routeClass(route = "") {
  return route.toLowerCase().replace(/[^a-z0-9_-]/g, "");
}

function setRouteBadge(label, kind = "") {
  routeBadge.className = `metric-pill ${routeClass(kind || label)}`;
  routeBadge.textContent = label;
}

function setSelectedUser() {
  const user = users.find((item) => item.id === userSelect.value);
  if (!user) return;

  selectedUserName.textContent = user.display_name;
  selectedUserDept.textContent = user.department;
  selectedUserRoles.innerHTML = user.roles
    .map((role) => `<span class="role-chip">${escapeHtml(role)}</span>`)
    .join("");
}

async function loadUsers() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/users`);
    if (!response.ok) throw new Error("Seed data is not available");
    users = await response.json();
    userSelect.innerHTML = users
      .map((user) => `<option value="${escapeHtml(user.id)}">${escapeHtml(user.display_name)} - ${escapeHtml(user.department)}</option>`)
      .join("");
    setSelectedUser();
  } catch (error) {
    userSelect.innerHTML = '<option value="u_eli">Seed data not ingested</option>';
    selectedUserName.textContent = "Seed data unavailable";
    selectedUserDept.textContent = error.message;
    selectedUserRoles.innerHTML = '<span class="role-chip">offline</span>';
  }
}

function renderSources(items) {
  sourceCount.textContent = String(items.length);
  sources.classList.toggle("empty-sources", items.length === 0);
  if (!items.length) {
    sources.innerHTML = '<div class="empty-card">No authorized sources returned.</div>';
    return;
  }

  sources.innerHTML = items
    .map((source, index) => {
      const type = escapeHtml(source.type);
      const cls = routeClass(type);
      return `
        <article class="source">
          <div class="source-top">
            <strong>[${index + 1}] ${escapeHtml(source.title)}</strong>
            <span class="source-type ${cls}">${type}</span>
          </div>
          <p>${escapeHtml(source.preview)}</p>
          <footer>
            <span>Confidence</span>
            <span>${Number(source.score).toFixed(3)}</span>
          </footer>
        </article>
      `;
    })
    .join("");
}

function setLoading(isLoading) {
  askButton.disabled = isLoading;
  askButton.classList.toggle("loading", isLoading);
  answer.classList.toggle("loading", isLoading);
  if (isLoading) {
    answer.textContent = "Retrieving authorized context and preparing a grounded response...";
    setRouteBadge("routing");
    confidence.textContent = "0.00";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) return;

  setLoading(true);
  try {
    const response = await fetch(`${API_BASE_URL}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text, user_id: userSelect.value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Query failed");

    answer.textContent = payload.answer;
    setRouteBadge(payload.route, payload.route);
    confidence.textContent = Number(payload.confidence).toFixed(2);
    traceUser.textContent = `${payload.user.display_name} (${payload.user.department})`;
    traceRoles.textContent = payload.user.roles.join(", ");
    traceRoute.textContent = payload.route_reason;
    renderSources(payload.sources);
  } catch (error) {
    answer.textContent = error.message;
    setRouteBadge("error", "error");
    confidence.textContent = "0.00";
    traceRoute.textContent = "Request failed";
    renderSources([]);
  } finally {
    setLoading(false);
  }
});

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    question.value = button.dataset.example;
    question.focus();
  });
});

userSelect.addEventListener("change", setSelectedUser);

loadUsers();
