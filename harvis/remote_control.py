from __future__ import annotations

import ipaddress
import json
import secrets
import socket
import threading
import time
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DEFAULT_REMOTE_PORT = 8765
MAX_REMOTE_BODY_BYTES = 16 * 1024
PAIR_FAILURE_LIMIT = 8
PAIR_FAILURE_WINDOW_SECONDS = 60.0

CommandHandler = Callable[[str], None]
StatusProvider = Callable[[], dict[str, Any]]
MicrophoneToggleHandler = Callable[[], bool]


_MOBILE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#00072B">
  <title>Harvis Remote</title>
  <style>
    :root{color-scheme:dark;--primary:#00072B;--secondary:#85B1FF;--tertiary:#53EEFC;--text:#F5F8FF;--muted:#AEB8D7;}
    *{box-sizing:border-box} body{margin:0;min-height:100vh;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 20% 0%,rgba(133,177,255,.25),transparent 38%),radial-gradient(circle at 100% 100%,rgba(83,238,252,.16),transparent 34%),var(--primary);color:var(--text);padding:max(24px,env(safe-area-inset-top)) 18px max(28px,env(safe-area-inset-bottom));}
    .shell{max-width:680px;margin:0 auto}.brand{display:flex;align-items:center;gap:12px;margin-bottom:22px}.orb{width:42px;height:42px;border-radius:50%;background:radial-gradient(circle at 34% 28%,#fff 0 4%,var(--tertiary) 18%,var(--secondary) 48%,#24488f 76%,transparent 78%);box-shadow:0 0 34px rgba(83,238,252,.38)}
    h1{font-size:28px;margin:0} .sub{color:var(--muted);margin-top:3px}.card{background:linear-gradient(145deg,rgba(255,255,255,.105),rgba(255,255,255,.04));border:1px solid rgba(255,255,255,.14);border-radius:24px;padding:20px;box-shadow:0 18px 60px rgba(0,0,0,.28);backdrop-filter:blur(20px);margin-bottom:16px}
    .row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.status{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:8px 12px;background:rgba(133,177,255,.12);color:#dfe9ff;font-size:13px}.dot{width:8px;height:8px;border-radius:50%;background:var(--tertiary);box-shadow:0 0 12px rgba(83,238,252,.8)}
    label{display:block;color:var(--muted);font-size:13px;margin:0 0 8px} input,textarea{width:100%;border:1px solid rgba(255,255,255,.14);background:rgba(0,7,43,.55);color:var(--text);border-radius:16px;padding:14px 15px;font:inherit;outline:none} input:focus,textarea:focus{border-color:rgba(83,238,252,.7);box-shadow:0 0 0 3px rgba(83,238,252,.1)} textarea{min-height:108px;resize:vertical}
    button{border:0;border-radius:16px;padding:13px 16px;font:600 15px inherit;cursor:pointer}.primary{background:linear-gradient(135deg,var(--secondary),var(--tertiary));color:#00123a;box-shadow:0 8px 28px rgba(83,238,252,.2)}.secondary{background:rgba(255,255,255,.09);color:var(--text);border:1px solid rgba(255,255,255,.12)} button:disabled{opacity:.5;cursor:default}.actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.full{grid-column:1/-1}
    .response{white-space:pre-wrap;word-break:break-word;min-height:70px;color:#eaf0ff}.meta{font-size:12px;color:var(--muted);margin-top:12px}.hidden{display:none}.error{color:#ffb7c4;margin-top:10px;font-size:13px}
  </style>
</head>
<body>
  <main class="shell">
    <div class="brand"><div class="orb"></div><div><h1>Harvis Remote</h1><div class="sub">Local mobile control</div></div></div>

    <section id="pairCard" class="card hidden">
      <h2>Pair this phone</h2>
      <p class="sub">Enter the six-digit code shown in Harvis Settings on the computer.</p>
      <label for="pairCode">Pairing code</label>
      <input id="pairCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000">
      <div class="actions"><button id="pairButton" class="primary full">Pair phone</button></div>
      <div id="pairError" class="error"></div>
    </section>

    <section id="remoteCard" class="hidden">
      <div class="card">
        <div class="row"><div class="status"><span class="dot"></span><span id="statusText">Connecting...</span></div><div class="status" id="modeText">Mode</div></div>
        <div class="meta">This connection works only while the phone can reach the Harvis computer on the local network.</div>
      </div>

      <div class="card">
        <label for="command">Command</label>
        <textarea id="command" placeholder="Open Spotify and play the next song"></textarea>
        <div class="actions">
          <button id="sendButton" class="primary full">Send to Harvis</button>
          <button id="muteButton" class="secondary">Toggle microphone</button>
          <button id="refreshButton" class="secondary">Refresh status</button>
        </div>
        <div id="commandError" class="error"></div>
      </div>

      <div class="card">
        <label>Latest Harvis response</label>
        <div id="responseText" class="response">No response yet.</div>
      </div>
    </section>
  </main>

  <script>
    const TOKEN_KEY = "harvisRemoteToken";
    const pairCard = document.getElementById("pairCard");
    const remoteCard = document.getElementById("remoteCard");
    const pairCode = document.getElementById("pairCode");
    const pairError = document.getElementById("pairError");
    const commandError = document.getElementById("commandError");
    const statusText = document.getElementById("statusText");
    const modeText = document.getElementById("modeText");
    const responseText = document.getElementById("responseText");
    const muteButton = document.getElementById("muteButton");

    function token(){ return localStorage.getItem(TOKEN_KEY) || ""; }
    function showPairing(message=""){
      remoteCard.classList.add("hidden"); pairCard.classList.remove("hidden"); pairError.textContent = message;
    }
    function showRemote(){ pairCard.classList.add("hidden"); remoteCard.classList.remove("hidden"); }
    async function api(path, options={}){
      const headers = Object.assign({"Content-Type":"application/json"}, options.headers || {});
      if(token()) headers.Authorization = `Bearer ${token()}`;
      const response = await fetch(path, Object.assign({}, options, {headers}));
      let data = {};
      try { data = await response.json(); } catch (_) {}
      if(response.status === 401){ localStorage.removeItem(TOKEN_KEY); showPairing("Pairing is required."); throw new Error("Pairing required"); }
      if(!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
      return data;
    }
    async function refreshStatus(){
      if(!token()){ showPairing(); return; }
      try{
        const data = await api("/api/status");
        showRemote();
        statusText.textContent = data.status || "Harvis";
        modeText.textContent = data.mode || "Unknown mode";
        responseText.textContent = data.response || "No response yet.";
        muteButton.disabled = data.mode !== "Speaking";
        muteButton.textContent = data.microphone_muted ? "Unmute microphone" : "Mute microphone";
      }catch(error){ if(token()) commandError.textContent = error.message; }
    }
    document.getElementById("pairButton").addEventListener("click", async () => {
      pairError.textContent = "";
      try{
        const data = await api("/api/pair", {method:"POST", body:JSON.stringify({code:pairCode.value.trim()})});
        localStorage.setItem(TOKEN_KEY, data.token); pairCode.value = ""; await refreshStatus();
      }catch(error){ pairError.textContent = error.message; }
    });
    document.getElementById("sendButton").addEventListener("click", async () => {
      const command = document.getElementById("command").value.trim();
      if(!command){ commandError.textContent = "Enter a command first."; return; }
      commandError.textContent = "";
      try{ await api("/api/command", {method:"POST", body:JSON.stringify({command})}); document.getElementById("command").value = ""; await refreshStatus(); }
      catch(error){ commandError.textContent = error.message; }
    });
    muteButton.addEventListener("click", async () => {
      commandError.textContent = "";
      try{ await api("/api/microphone/toggle", {method:"POST", body:"{}"}); await refreshStatus(); }
      catch(error){ commandError.textContent = error.message; }
    });
    document.getElementById("refreshButton").addEventListener("click", refreshStatus);
    refreshStatus(); setInterval(refreshStatus, 1200);
  </script>
</body>
</html>
"""


class _RemoteHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class RemoteControlServer:
    """Serve a paired, LAN-only mobile controller for the running Harvis process."""

    def __init__(
        self,
        *,
        command_handler: CommandHandler,
        status_provider: StatusProvider,
        microphone_toggle_handler: MicrophoneToggleHandler,
        port: int = DEFAULT_REMOTE_PORT,
    ) -> None:
        self._command_handler = command_handler
        self._status_provider = status_provider
        self._microphone_toggle_handler = microphone_toggle_handler
        self._configured_port = self._normalize_port(port, allow_zero=True)
        self._server: _RemoteHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._state_lock = threading.RLock()
        self._pairing_code = self._new_pairing_code()
        self._session_token = secrets.token_urlsafe(32)
        self._pair_failures: dict[str, list[float]] = {}
        self._active_port: int | None = None

    @staticmethod
    def _normalize_port(port: int, *, allow_zero: bool = False) -> int:
        value = int(port)
        minimum = 0 if allow_zero else 1024
        if not minimum <= value <= 65535:
            raise ValueError(f"Remote control port must be between {minimum} and 65535.")
        return value

    @staticmethod
    def _new_pairing_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    @property
    def pairing_code(self) -> str:
        with self._state_lock:
            return self._pairing_code

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            return self._server is not None

    @property
    def port(self) -> int:
        with self._state_lock:
            return self._active_port or self._configured_port

    @property
    def url(self) -> str:
        return f"http://{self._local_ipv4()}:{self.port}"

    def start(self, *, port: int | None = None) -> None:
        requested_port = self._configured_port if port is None else self._normalize_port(port)
        with self._state_lock:
            if self._server is not None and self._configured_port == requested_port:
                return

        self.stop()
        handler_class = self._handler_class()
        server = _RemoteHTTPServer(("0.0.0.0", requested_port), handler_class)

        with self._state_lock:
            self._configured_port = requested_port
            self._active_port = int(server.server_address[1])
            self._pairing_code = self._new_pairing_code()
            self._session_token = secrets.token_urlsafe(32)
            self._pair_failures.clear()
            self._server = server
            thread = threading.Thread(
                target=server.serve_forever,
                name="harvis-remote-control",
                daemon=True,
            )
            self._thread = thread
            thread.start()

    def stop(self) -> None:
        with self._state_lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
            self._active_port = None

        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=2.0)

    def _handler_class(self):
        remote = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "HarvisRemote/1.0"

            def log_message(self, format: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                if not remote._client_allowed(self.client_address[0]):
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "LAN access only."})
                    return
                if self.path == "/":
                    self._send_html(_MOBILE_HTML)
                    return
                if self.path == "/api/status":
                    if not self._authorized():
                        return
                    try:
                        payload = dict(remote._status_provider())
                    except Exception as exc:
                        self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
                        return
                    self._send_json(HTTPStatus.OK, payload)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

            def do_POST(self) -> None:
                if not remote._client_allowed(self.client_address[0]):
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "LAN access only."})
                    return
                if self.path == "/api/pair":
                    payload = self._read_json()
                    if payload is None:
                        return
                    client_ip = self.client_address[0]
                    if remote._pairing_locked(client_ip):
                        self._send_json(
                            HTTPStatus.TOO_MANY_REQUESTS,
                            {"error": "Too many pairing attempts. Try again in one minute."},
                        )
                        return
                    code = str(payload.get("code", "")).strip()
                    if not secrets.compare_digest(code, remote.pairing_code):
                        remote._record_pair_failure(client_ip)
                        self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Incorrect pairing code."})
                        return
                    remote._clear_pair_failures(client_ip)
                    with remote._state_lock:
                        token = remote._session_token
                    self._send_json(HTTPStatus.OK, {"token": token})
                    return

                if not self._authorized():
                    return

                if self.path == "/api/command":
                    payload = self._read_json()
                    if payload is None:
                        return
                    command = " ".join(str(payload.get("command", "")).split()).strip()
                    if not command:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Command cannot be empty."})
                        return
                    try:
                        remote._command_handler(command)
                    except Exception as exc:
                        self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
                        return
                    self._send_json(HTTPStatus.ACCEPTED, {"status": "queued"})
                    return

                if self.path == "/api/microphone/toggle":
                    try:
                        muted = bool(remote._microphone_toggle_handler())
                    except Exception as exc:
                        self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
                        return
                    self._send_json(HTTPStatus.OK, {"microphone_muted": muted})
                    return

                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

            def _authorized(self) -> bool:
                header = self.headers.get("Authorization", "")
                prefix = "Bearer "
                supplied = header[len(prefix) :].strip() if header.startswith(prefix) else ""
                with remote._state_lock:
                    expected = remote._session_token
                if supplied and secrets.compare_digest(supplied, expected):
                    return True
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Pairing is required."})
                return False

            def _read_json(self) -> dict[str, Any] | None:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_REMOTE_BODY_BYTES:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request body."})
                    return None
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
                    return None
                if not isinstance(payload, dict):
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON body must be an object."})
                    return None
                return payload

            def _send_html(self, html: str) -> None:
                body = html.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self._security_headers("text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                self.send_response(status)
                self._security_headers("application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _security_headers(self, content_type: str) -> None:
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                    "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
                )

        return Handler

    def _pairing_locked(self, client_ip: str) -> bool:
        now = time.monotonic()
        with self._state_lock:
            failures = [
                stamp
                for stamp in self._pair_failures.get(client_ip, [])
                if now - stamp <= PAIR_FAILURE_WINDOW_SECONDS
            ]
            self._pair_failures[client_ip] = failures
            return len(failures) >= PAIR_FAILURE_LIMIT

    def _record_pair_failure(self, client_ip: str) -> None:
        now = time.monotonic()
        with self._state_lock:
            failures = self._pair_failures.setdefault(client_ip, [])
            failures.append(now)

    def _clear_pair_failures(self, client_ip: str) -> None:
        with self._state_lock:
            self._pair_failures.pop(client_ip, None)

    @staticmethod
    def _client_allowed(client_ip: str) -> bool:
        try:
            address = ipaddress.ip_address(client_ip.split("%", 1)[0])
        except ValueError:
            return False
        return address.is_private or address.is_loopback or address.is_link_local

    @staticmethod
    def _local_ipv4() -> str:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            address = str(probe.getsockname()[0])
            if address and not address.startswith("127."):
                return address
        except OSError:
            pass
        finally:
            probe.close()

        try:
            address = socket.gethostbyname(socket.gethostname())
            if address:
                return address
        except OSError:
            pass
        return "127.0.0.1"


__all__ = [
    "DEFAULT_REMOTE_PORT",
    "RemoteControlServer",
]
