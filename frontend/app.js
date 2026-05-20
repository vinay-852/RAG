const userSelect = document.querySelector("#userSelect");
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

async function loadUsers() {
  const response = await fetch("/api/users");
  if (!response.ok) {
    userSelect.innerHTML = '<option value="u_eli">Seed data not ingested</option>';
    return;
  }
  const users = await response.json();
  userSelect.innerHTML = users
    .map((user) => `<option value="${user.id}">${user.display_name} - ${user.department}</option>`)
    .join("");
}

function renderSources(items) {
  sourceCount.textContent = String(items.length);
  sources.innerHTML = items
    .map(
      (source, index) => `
        <article class="source">
          <strong>[${index + 1}] ${source.title}</strong>
          <p>${source.preview}</p>
          <footer>
            <span>${source.type}</span>
            <span>${Number(source.score).toFixed(3)}</span>
          </footer>
        </article>
      `,
    )
    .join("");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) return;

  askButton.disabled = true;
  answer.textContent = "Retrieving authorized context...";
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text, user_id: userSelect.value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Query failed");

    answer.textContent = payload.answer;
    routeBadge.textContent = payload.route;
    confidence.textContent = Number(payload.confidence).toFixed(2);
    traceUser.textContent = `${payload.user.display_name} (${payload.user.department})`;
    traceRoles.textContent = payload.user.roles.join(", ");
    traceRoute.textContent = payload.route_reason;
    renderSources(payload.sources);
  } catch (error) {
    answer.textContent = error.message;
    routeBadge.textContent = "error";
    confidence.textContent = "0.00";
    renderSources([]);
  } finally {
    askButton.disabled = false;
  }
});

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    question.value = button.dataset.example;
    question.focus();
  });
});

loadUsers();
