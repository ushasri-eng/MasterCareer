import os
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, url_for


BASE_DIR = Path(__file__).resolve().parent
BOT_FILE = BASE_DIR / "bot.py"
LOG_FILE = BASE_DIR / "bot.log"

app = Flask(__name__)
bot_process = None
process_lock = threading.Lock()


HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Telegram Career Bot Control</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #eef3f8;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d8e0ea;
      --green: #16784f;
      --red: #b42318;
      --blue: #2563eb;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      display: grid;
      place-items: center;
      padding: 24px;
    }

    main {
      width: min(760px, 100%);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 28px;
      box-shadow: 0 18px 40px rgba(23, 32, 51, 0.08);
    }

    header {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      border-bottom: 1px solid var(--line);
      padding-bottom: 20px;
      margin-bottom: 22px;
    }

    h1 {
      font-size: 24px;
      line-height: 1.2;
      margin: 0 0 8px;
    }

    p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }

    .status {
      min-width: 112px;
      text-align: center;
      font-weight: 700;
      border-radius: 999px;
      padding: 8px 12px;
      border: 1px solid currentColor;
    }

    .running {
      color: var(--green);
    }

    .stopped {
      color: var(--red);
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 24px;
    }

    button, a.button {
      appearance: none;
      border: 0;
      border-radius: 6px;
      color: #ffffff;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 15px;
      font-weight: 700;
      min-height: 44px;
      min-width: 120px;
      padding: 0 18px;
      text-decoration: none;
    }

    .start {
      background: var(--green);
    }

    .stop {
      background: var(--red);
    }

    .refresh {
      background: var(--blue);
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.45;
    }

    .log-title {
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 8px;
      text-transform: uppercase;
    }

    pre {
      background: #101828;
      border-radius: 8px;
      color: #e6edf7;
      font-size: 13px;
      line-height: 1.5;
      margin: 0;
      min-height: 190px;
      overflow: auto;
      padding: 16px;
      white-space: pre-wrap;
      word-break: break-word;
    }

    @media (max-width: 620px) {
      body {
        padding: 14px;
      }

      main {
        padding: 20px;
      }

      header {
        display: block;
      }

      .status {
        display: inline-block;
        margin-top: 14px;
      }

      button, a.button {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Telegram Career Bot Control</h1>
        <p>Start or stop the Telegram bot that replies through Gemini.</p>
      </div>
      <div class="status {{ 'running' if running else 'stopped' }}">
        {{ 'Running' if running else 'Stopped' }}
      </div>
    </header>

    <form class="actions" method="post">
      <button class="start" formaction="{{ url_for('start_bot') }}" {% if running %}disabled{% endif %}>Start Bot</button>
      <button class="stop" formaction="{{ url_for('stop_bot') }}" {% if not running %}disabled{% endif %}>Stop Bot</button>
      <a class="button refresh" href="{{ url_for('index') }}">Refresh</a>
    </form>

    <div class="log-title">Bot log</div>
    <pre>{{ log }}</pre>
  </main>
</body>
</html>
"""


def is_running():
    return bot_process is not None and bot_process.poll() is None


def read_log():
    if not LOG_FILE.exists():
        return "No log yet. Start the bot to create one."

    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-80:]) or "Log file is empty."


@app.route("/")
def index():
    return render_template_string(HTML, running=is_running(), log=read_log())


@app.post("/start")
def start_bot():
    global bot_process

    with process_lock:
        if is_running():
            return redirect(url_for("index"))

        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NO_WINDOW

        log_handle = open(LOG_FILE, "a", encoding="utf-8")
        try:
            bot_process = subprocess.Popen(
                [sys.executable, str(BOT_FILE)],
                cwd=BASE_DIR,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        finally:
            log_handle.close()

    return redirect(url_for("index"))


@app.post("/stop")
def stop_bot():
    global bot_process

    with process_lock:
        if not is_running():
            bot_process = None
            return redirect(url_for("index"))

        bot_process.terminate()

        try:
            bot_process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            bot_process.kill()
            bot_process.wait(timeout=5)
        finally:
            bot_process = None

    return redirect(url_for("index"))


@app.get("/api/status")
def api_status():
    return jsonify({"running": is_running()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
