const events = [];
function showError(error) {
  document.querySelector("#feedback").textContent = error.message;
}
async function call(path, method = "GET", body) {
  const headers = {
    "Content-Type": "application/json",
    "X-User-Id": document.querySelector("#actor")?.value || "author",
  };
  const response = await fetch(path, {
    method,
    headers,
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const payload = await response.json();
  if (method !== "GET") {
    document.querySelector("#request").textContent =
      method + " " + path + "\n" + JSON.stringify(body || {}, null, 2);
    document.querySelector("#response").textContent =
      response.status + "\n" + JSON.stringify(payload, null, 2);
    events.unshift({
      path,
      method,
      status: response.status,
      time: new Date().toLocaleTimeString("ru-RU"),
    });
    const history = document.querySelector("#history");
    history.replaceChildren();
    for (const event of events.slice(0, 10)) {
      const row = document.createElement("div");
      row.className = "event";
      row.textContent =
        event.time + " · " + event.method + " · " + event.status;
      history.append(row);
    }
    document.querySelector("#feedback").textContent = response.ok
      ? "Изменения сохранены в текущей вкладке."
      : "";
  }
  if (!response.ok) throw Error(payload.message || payload.detail);
  return payload;
}
let records = [],
  comments = [],
  editing = null;
async function render() {
  records = await call("/api/articles");
  comments = await call("/api/comments");
  const root = document.querySelector("#records");
  root.replaceChildren();
  for (const row of records) {
    const article = document.createElement("article");
    const title = document.createElement("h3");
    title.textContent = row.title;
    const copy = document.createElement("p");
    copy.className = "article-copy";
    copy.textContent = row.content;
    article.append(title, copy);
    const actions = document.createElement("div");
    actions.className = "actions";
    for (const [label, action] of [
      [
        "Изменить",
        () => {
          editing = row;
          const form = document.querySelector("#editor");
          form.elements.title.value = row.title;
          form.elements.content.value = row.content;
          form.scrollIntoView({ behavior: "smooth" });
          form.elements.title.focus();
        },
      ],
      [
        "Удалить",
        async () => {
          if (!confirm("Удалить статью и её комментарии?")) return;
          await call("/api/articles/" + row.id, "DELETE");
          await render();
        },
      ],
    ]) {
      const b = document.createElement("button");
      b.textContent = label;
      b.className = "secondary";
      b.onclick = () => Promise.resolve().then(action).catch(showError);
      actions.append(b);
    }
    article.append(actions);
    for (const comment of comments.filter((x) => x.article_id === row.id)) {
      const p = document.createElement("p");
      p.textContent = "Комментарий: " + comment.content;
      article.append(p);
    }
    const form = document.createElement("form");
    form.className = "actions";
    const label = document.createElement("label");
    label.textContent = "Комментарий";
    const input = document.createElement("input");
    input.required = true;
    input.maxLength = 5000;
    label.append(input);
    const button = document.createElement("button");
    button.textContent = "Добавить";
    form.append(label, button);
    form.onsubmit = async (e) => {
      e.preventDefault();
      try {
        await call("/api/comments", "POST", {
          article_id: row.id,
          content: input.value,
        });
        await render();
      } catch (error) {
        showError(error);
      }
    };
    article.append(form);
    root.append(article);
  }
}
document.querySelector("#editor").onsubmit = async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const payload = {
      title: form.elements.title.value,
      content: form.elements.content.value,
      ...(editing ? { version: editing.version } : {}),
    };
    await call(
      "/api/articles" + (editing ? "/" + editing.id : ""),
      editing ? "PUT" : "POST",
      payload,
    );
    editing = null;
    form.reset();
    await render();
  } catch (error) {
    showError(error);
  }
};
render().catch(showError);
