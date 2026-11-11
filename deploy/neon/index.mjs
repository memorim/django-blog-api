import { parseTriggerDelivery } from "@neon/functions/triggers";

export default {
  async fetch(request) {
    if (new URL(request.url).pathname !== "/cron")
      return new Response("Not found", { status: 404 });
    if (request.method !== "POST")
      return new Response("Method not allowed", { status: 405 });
    const parsed = await parseTriggerDelivery(request);
    if (!parsed.ok) return new Response("Unauthorized", { status: 401 });
    if (
      parsed.invocation.type !== "schedule" ||
      parsed.invocation.trigger.name !== "django-independent-backup"
    )
      return new Response("Unexpected trigger", { status: 403 });
    try {
      const origin = new URL(process.env.BACKUP_WORKER_ORIGIN);
      if (
        origin.protocol !== "https:" ||
        origin.username ||
        origin.password ||
        origin.search ||
        origin.hash ||
        origin.pathname !== "/"
      )
        throw new Error("Configure an exact HTTPS worker origin");
      const token = process.env.BACKUP_OPERATOR_TOKEN;
      if (!token || token.length < 40)
        throw new Error("Configure the private operator token");
      const response = await fetch(new URL("/backup", origin), {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
        redirect: "error",
        signal: AbortSignal.timeout(240000),
      });
      const summary = await response.json();
      if (
        !response.ok ||
        !Number.isSafeInteger(summary.snapshot) ||
        !/^[a-f0-9]{64}$/.test(summary.sha256)
      )
        throw new Error("Backup did not complete");
      console.log(
        JSON.stringify({
          event: "django_independent_backup",
          snapshot: summary.snapshot,
          sha256: summary.sha256,
        }),
      );
      return Response.json({
        status: "completed",
        snapshot: summary.snapshot,
        sha256: summary.sha256,
      });
    } catch {
      console.error(
        JSON.stringify({
          event: "django_independent_backup",
          status: "unavailable",
        }),
      );
      return Response.json({ status: "unavailable" }, { status: 503 });
    }
  },
};
