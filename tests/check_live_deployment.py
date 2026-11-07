"""Explicit HTTPS deployment probe; --write uses synthetic records only."""
import argparse
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


parser = argparse.ArgumentParser()
parser.add_argument("--write", action="store_true")
args = parser.parse_args()
base = os.environ["SMOKE_URL"].rstrip("/")
url = urllib.parse.urlsplit(base)
if url.scheme != "https" or url.username or url.password or url.query or url.fragment or url.path:
    raise ValueError("SMOKE_URL must be a fixed HTTPS origin without credentials")
opener = urllib.request.build_opener(NoRedirect)


def call(path, expected, method="GET", body=None, headers=None):
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers=request_headers,
    )
    try:
        response = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        payload = response.read(200_000)
        if response.status != expected:
            raise RuntimeError(f"{method} {path}: unexpected HTTP {response.status}")
        if "max-age=31536000" not in response.headers.get("Strict-Transport-Security", ""):
            raise RuntimeError("Missing production HSTS")
        return (json.loads(payload) if payload and "application/json" in response.headers.get("Content-Type", "") else None), response.headers


articles, _ = call("/api/articles", 200)
assert isinstance(articles, list)
call("/api/docs", 404)
call("/api/articles", 401, "POST", {"title": "fixture", "content": "fixture"})
summary = {"https": True, "hsts": True, "private_docs": True, "anonymous_write_denied": True}

state_path = Path(os.environ["SMOKE_STATE_FILE"]) if os.getenv("SMOKE_STATE_FILE") else None
state = json.loads(state_path.read_text()) if state_path and state_path.exists() else {}


def save():
    state_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        json.dump(state, file)


if args.write:
    if state_path is None:
        raise ValueError("Set SMOKE_STATE_FILE to a private path outside the repository")
    if not state:
        state.update(username="deployment_" + secrets.token_hex(6), password=secrets.token_urlsafe(32))
        save()
        auth, _ = call("/api/auth/register", 201, "POST", state)
    else:
        auth, _ = call("/api/auth/login", 200, "POST", {"username": state["username"], "password": state["password"]})
    token = {"X-API-Token": auth["token"]}
    body = {"title": "Deployment verification fixture", "content": "Synthetic HTTPS and persistent database check."}
    if not state.get("article_id"):
        article, _ = call("/api/articles", 201, "POST", body, token)
        state["article_id"] = article["id"]
        save()
    article_path = "/api/articles/" + str(state["article_id"])
    _, headers = call(article_path, 200)
    call(article_path, 428, "PUT", body, token)
    call(article_path, 412, "PUT", body, {**token, "If-Match": '"stale"'})
    body["title"] = "Deployment verification fixture updated"
    marker = headers.get("X-Resource-Version", headers["ETag"])
    assert marker.startswith('"') and not marker.startswith("W/")
    call(article_path, 200, "PUT", body, {**token, "If-Match": marker})
    state["expected_title"] = body["title"]
    save()
    call("/api/auth/logout", 204, "POST", headers=token)
    call(article_path, 401, "PUT", body, {**token, "If-Match": headers["ETag"]})
    summary.update(authenticated_writes=True, version_preconditions=True, logout_revocation=True)
elif state.get("article_id"):
    article, _ = call("/api/articles/" + str(state["article_id"]), 200)
    assert article["title"] == state["expected_title"]
    summary["persistent_record"] = True

print(json.dumps({"check": "live_deployment", "status": "ok", **summary}))
