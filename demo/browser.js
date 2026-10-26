// Browser-only adapter, loaded exclusively by scripts/build_demo.py.
// ponytail: state lasts for one page session; use the documented server for shared, durable data.
(() => {
  const state = structuredClone(globalThis.DEMO_SEED);
  const fail = (message, status = 400) => {
    throw Object.assign(new Error(message), { status });
  };
  const text = (value, min = 1, max = 200) => {
    if (
      typeof value !== "string" ||
      value.trim().length < min ||
      value.trim().length > max
    )
      fail("Проверьте введённые данные");
    return value.trim();
  };
  const json = (value, status = 200) =>
    new Response(JSON.stringify(value), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const originalFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (input, options = {}) => {
    const url = new URL(input, globalThis.location.href);
    if (
      url.origin !== globalThis.location.origin ||
      !url.pathname.startsWith("/api/")
    )
      return originalFetch(input, options);
    if (options.signal?.aborted)
      throw new DOMException("Aborted", "AbortError");
    try {
      return await handle(
        url,
        options.method || "GET",
        options.body ? JSON.parse(options.body) : {},
        new Headers(options.headers),
      );
    } catch (error) {
      return json(
        { message: error.message, detail: error.message },
        error.status || 400,
      );
    }
  };
  globalThis.PORTFOLIO_DEMO = true;
  async function handle(url, method, body) {
    const articles = state["/api/articles"],
      comments = state["/api/comments"];
    if (url.pathname === "/api/articles" && method === "GET")
      return json(articles);
    if (url.pathname === "/api/comments" && method === "GET")
      return json(comments);
    if (url.pathname === "/api/articles" && method === "POST") {
      const row = {
        id: Math.max(0, ...articles.map((x) => x.id)) + 1,
        title: text(body.title, 1, 200),
        content: text(body.content, 1, 50000),
        author_id: 1,
        version: 1,
      };
      if (articles.length >= 30) fail("До 30 статей на сессию");
      articles.unshift(row);
      return json(row, 201);
    }
    const match = url.pathname.match(/^\/api\/articles\/(\d+)$/);
    if (match) {
      const index = articles.findIndex((x) => x.id === Number(match[1]));
      if (index < 0) fail("Не найдено", 404);
      if (method === "DELETE") {
        articles.splice(index, 1);
        state["/api/comments"] = comments.filter(
          (x) => x.article_id !== Number(match[1]),
        );
        return json({ deleted: true });
      }
      if (method === "PUT") {
        if (body.version !== articles[index].version)
          fail("Статья уже изменена", 409);
        articles[index] = {
          ...articles[index],
          title: text(body.title, 1, 200),
          content: text(body.content, 1, 50000),
          version: articles[index].version + 1,
        };
        return json(articles[index]);
      }
    }
    if (url.pathname === "/api/comments" && method === "POST") {
      if (!articles.some((x) => x.id === body.article_id))
        fail("Статья не найдена", 404);
      const row = {
        id: comments.length + 1,
        article_id: body.article_id,
        content: text(body.content, 1, 5000),
        author_id: 1,
      };
      comments.push(row);
      return json(row, 201);
    }
    fail("Не найдено", 404);
  }
})();
