"""
================================================================================
  Online Compiler IDE — Backend Server
================================================================================
  A lightweight HTTP server built on Python's standard library.
  No external pip dependencies required.

  Endpoints:
    GET  /              → serves index.html
    GET  /<file>        → serves static files (css, js)
    POST /api/run       → compiles & runs code, returns JSON result

  Supported Languages:
    - minilang  (built-in via minilang.py)
    - python
    - c
    - cpp
    - java

  Start with:
    python server.py
================================================================================
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
#  MiniLang integration — import the pipeline from minilang.py
# ---------------------------------------------------------------------------

# Ensure the compiler directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from minilang import Lexer, Parser, Compiler, VM, disassemble
    MINILANG_AVAILABLE = True
except ImportError:
    MINILANG_AVAILABLE = False


# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------

HOST          = "0.0.0.0"
PORT          = int(os.environ.get("PORT", 8000))
TIMEOUT_SECS  = 10           # max execution time per run
STATIC_DIR    = os.path.dirname(os.path.abspath(__file__))   # same folder as server.py

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".ico":  "image/x-icon",
    ".png":  "image/png",
}


# ---------------------------------------------------------------------------
#  Language Runners
# ---------------------------------------------------------------------------

def run_minilang(code: str) -> dict:
    """
    Execute MiniLang source through the full compiler pipeline.
    Returns rich metadata: tokens, AST, disassembly, stdout, errors.
    """
    if not MINILANG_AVAILABLE:
        return {
            "stdout": "",
            "stderr": "MiniLang engine not found. Ensure minilang.py is in the same directory.",
            "exit_code": 1,
            "metadata": {}
        }

    # Capture stdout (print statements from the VM)
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    metadata = {}

    try:
        # ── Lex ──────────────────────────────────────────────────────────────
        lexer  = Lexer(code)
        tokens = lexer.tokenize()
        metadata["tokens"] = [
            {"type": t.type, "value": str(t.value), "line": t.line}
            for t in tokens
        ]

        # ── Parse ─────────────────────────────────────────────────────────────
        parser = Parser(tokens)
        ast    = parser.parse()
        metadata["ast"] = [repr(node) for node in ast.statements]

        # ── Compile ───────────────────────────────────────────────────────────
        compiler = Compiler()
        bytecode = compiler.compile(ast)
        metadata["bytecode"] = [repr(instr) for instr in bytecode]

        # ── Run (capture print output) ────────────────────────────────────────
        old_stdout = sys.stdout
        sys.stdout = captured_stdout
        try:
            vm = VM(bytecode)
            vm.run()
        finally:
            sys.stdout = old_stdout

        metadata["globals"] = vm.globals

        return {
            "stdout":    captured_stdout.getvalue(),
            "stderr":    "",
            "exit_code": 0,
            "metadata":  metadata,
        }

    except Exception as exc:
        sys.stdout = sys.__stdout__   # safety reset
        return {
            "stdout":    captured_stdout.getvalue(),
            "stderr":    f"{type(exc).__name__}: {exc}",
            "exit_code": 1,
            "metadata":  metadata,
        }


def run_python(code: str) -> dict:
    """Execute Python source code in a subprocess."""
    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECS,
        )
        elapsed = time.time() - start
        return {
            "stdout":    proc.stdout,
            "stderr":    proc.stderr,
            "exit_code": proc.returncode,
            "elapsed":   round(elapsed, 4),
            "metadata":  {},
        }
    except subprocess.TimeoutExpired:
        return _timeout_result()
    except Exception as e:
        return _error_result(str(e))


def run_c(code: str) -> dict:
    """Compile with gcc and execute."""
    return _compile_and_run(
        code,
        source_ext=".c",
        compile_cmd_fn=lambda src, exe: ["gcc", src, "-o", exe, "-lm"],
    )


def run_cpp(code: str) -> dict:
    """Compile with g++ and execute."""
    return _compile_and_run(
        code,
        source_ext=".cpp",
        compile_cmd_fn=lambda src, exe: ["g++", src, "-o", exe, "-std=c++17"],
    )


def run_java(code: str) -> dict:
    """
    Compile with javac and run with java.
    Attempts to auto-detect the public class name from the source;
    defaults to 'Main' if none is found.
    """
    import re
    # Detect public class name
    match = re.search(r'\bpublic\s+class\s+(\w+)', code)
    class_name = match.group(1) if match else "Main"

    tmp_dir = tempfile.mkdtemp(prefix="minilang_java_")
    try:
        src_path = os.path.join(tmp_dir, f"{class_name}.java")
        with open(src_path, "w") as f:
            f.write(code)

        # ── Compile ───────────────────────────────────────────────────────────
        start = time.time()
        compile_proc = subprocess.run(
            ["javac", src_path],
            capture_output=True, text=True, timeout=TIMEOUT_SECS,
        )
        if compile_proc.returncode != 0:
            return {
                "stdout":    "",
                "stderr":    compile_proc.stderr,
                "exit_code": compile_proc.returncode,
                "elapsed":   round(time.time() - start, 4),
                "metadata":  {"stage": "compilation"},
            }

        # ── Run ───────────────────────────────────────────────────────────────
        run_proc = subprocess.run(
            ["java", "-cp", tmp_dir, class_name],
            capture_output=True, text=True, timeout=TIMEOUT_SECS,
        )
        elapsed = time.time() - start
        return {
            "stdout":    run_proc.stdout,
            "stderr":    run_proc.stderr,
            "exit_code": run_proc.returncode,
            "elapsed":   round(elapsed, 4),
            "metadata":  {},
        }
    except subprocess.TimeoutExpired:
        return _timeout_result()
    except FileNotFoundError:
        return _error_result(
            "javac/java not found. Please install the JDK and add it to your system PATH."
        )
    except Exception as e:
        return _error_result(str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _compile_and_run(code: str, source_ext: str, compile_cmd_fn) -> dict:
    """Generic helper for C/C++: write source → compile → execute → cleanup."""
    tmp_dir = tempfile.mkdtemp(prefix="minilang_cc_")
    try:
        src_path = os.path.join(tmp_dir, f"prog{source_ext}")
        exe_path = os.path.join(tmp_dir, "prog.exe" if sys.platform == "win32" else "prog")

        with open(src_path, "w") as f:
            f.write(code)

        # ── Compile ───────────────────────────────────────────────────────────
        start        = time.time()
        compile_proc = subprocess.run(
            compile_cmd_fn(src_path, exe_path),
            capture_output=True, text=True, timeout=TIMEOUT_SECS,
        )
        if compile_proc.returncode != 0:
            return {
                "stdout":    "",
                "stderr":    compile_proc.stderr,
                "exit_code": compile_proc.returncode,
                "elapsed":   round(time.time() - start, 4),
                "metadata":  {"stage": "compilation"},
            }

        # ── Execute ───────────────────────────────────────────────────────────
        run_proc = subprocess.run(
            [exe_path],
            capture_output=True, text=True, timeout=TIMEOUT_SECS,
        )
        elapsed = time.time() - start
        return {
            "stdout":    run_proc.stdout,
            "stderr":    run_proc.stderr,
            "exit_code": run_proc.returncode,
            "elapsed":   round(elapsed, 4),
            "metadata":  {},
        }
    except subprocess.TimeoutExpired:
        return _timeout_result()
    except FileNotFoundError as e:
        compiler_name = "gcc" if source_ext == ".c" else "g++"
        return _error_result(
            f"{compiler_name} not found. Please install MinGW / GCC and add it to your PATH."
        )
    except Exception as e:
        return _error_result(str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _timeout_result() -> dict:
    return {
        "stdout":    "",
        "stderr":    f"Execution timed out after {TIMEOUT_SECS} seconds. Check for infinite loops.",
        "exit_code": -1,
        "elapsed":   TIMEOUT_SECS,
        "metadata":  {},
    }


def _error_result(msg: str) -> dict:
    return {
        "stdout":    "",
        "stderr":    msg,
        "exit_code": 1,
        "metadata":  {},
    }


# ---------------------------------------------------------------------------
#  HTTP Request Handler
# ---------------------------------------------------------------------------

LANGUAGE_RUNNERS = {
    "minilang": run_minilang,
    "python":   run_python,
    "c":        run_c,
    "cpp":      run_cpp,
    "java":     run_java,
}


class CompilerHandler(BaseHTTPRequestHandler):
    """Handles all HTTP requests for the Online Compiler IDE."""

    # Silence the default request logging noise; we print our own
    def log_message(self, format, *args):
        print(f"  [{self.client_address[0]}] {format % args}")

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self):
        """Serve static files from the STATIC_DIR directory."""
        # Normalise path
        path = self.path.split("?")[0]   # strip query string
        if path == "/" or path == "":
            path = "/index.html"

        # Security: reject any path traversal attempts
        requested = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not requested.startswith(STATIC_DIR):
            self._send_error(403, "Forbidden")
            return

        if not os.path.isfile(requested):
            self._send_error(404, f"Not found: {path}")
            return

        ext      = os.path.splitext(requested)[1].lower()
        mimetype = MIME_TYPES.get(ext, "application/octet-stream")

        with open(requested, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type",   mimetype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self):
        """Handle the /api/run endpoint."""
        if self.path != "/api/run":
            self._send_error(404, "Unknown API endpoint")
            return

        # Read and decode request body
        length   = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, status=400)
            return

        language = body.get("language", "").lower().strip()
        code     = body.get("code", "")

        if not language:
            self._send_json({"error": "Missing 'language' field"}, status=400)
            return
        if language not in LANGUAGE_RUNNERS:
            self._send_json(
                {"error": f"Unsupported language: {language!r}. "
                           f"Supported: {list(LANGUAGE_RUNNERS.keys())}"},
                status=400,
            )
            return
        if not code.strip():
            self._send_json({"error": "No code provided."}, status=400)
            return

        # Run the code
        print(f"  >> Running [{language}] ({len(code)} chars)")
        start  = time.time()
        result = LANGUAGE_RUNNERS[language](code)
        result.setdefault("elapsed", round(time.time() - start, 4))
        result["language"] = language

        self._send_json(result)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _send_json(self, data: dict, status: int = 200):
        """Serialise `data` as JSON and send it with CORS headers."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",                "application/json; charset=utf-8")
        self.send_header("Content-Length",              str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        self._send_json({"error": message}, status=code)


# ---------------------------------------------------------------------------
#  Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), CompilerHandler)
    print("=" * 55)
    print("  Online Compiler IDE — Backend Server")
    print("=" * 55)
    print(f"  Listening at : http://{HOST}:{PORT}")
    print(f"  Serving from : {STATIC_DIR}")
    print(f"  MiniLang     : {'OK' if MINILANG_AVAILABLE else 'NOT FOUND (minilang.py missing)'}")
    print(f"  Timeout      : {TIMEOUT_SECS}s per execution")
    print("  Press Ctrl+C to stop.")
    print("=" * 55)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
