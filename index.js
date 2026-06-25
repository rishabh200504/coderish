/**
 * Coderish IDE — Frontend Logic
 * ──────────────────────────────
 * Handles:
 *   - Monaco Editor initialisation & theme
 *   - Language switching (starter templates, file-tab names)
 *   - Font size controls
 *   - Run button (Ctrl+Enter shortcut) → /api/run → terminal output
 *   - MiniLang inspector (tokens, AST, bytecode, variables)
 *   - Toast notifications
 *   - Light/Dark theme toggle
 */

/* ══════════════════════════════════════════════════════════════
   STARTER CODE TEMPLATES
══════════════════════════════════════════════════════════════ */
const TEMPLATES = {
  minilang: `# MiniLang — Simple Integer Language
# Supports: let, assignment, print, +, -, *, /

let x = 10;
let y = 20;
let result = x + y * 2;
print result;

# You can also reassign variables:
let a = 100;
let b = a / 4;
print b;
`,

  python: `# Python — Hello World & Fibonacci
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        print(a, end=" ")
        a, b = b, a + b
    print()

print("Hello from Coderish!")
print("First 10 Fibonacci numbers:")
fibonacci(10)

# Arithmetic
result = sum(i * i for i in range(1, 6))
print(f"Sum of squares 1..5 = {result}")
`,

  c: `/* C — Hello World & Prime Check */
#include <stdio.h>
#include <stdbool.h>

bool is_prime(int n) {
    if (n < 2) return false;
    for (int i = 2; i * i <= n; i++)
        if (n % i == 0) return false;
    return true;
}

int main() {
    printf("Hello from Coderish!\\n");
    printf("Primes up to 30: ");
    for (int i = 2; i <= 30; i++)
        if (is_prime(i)) printf("%d ", i);
    printf("\\n");
    return 0;
}
`,

  cpp: `// C++ — Hello World & Sorting Demo
#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;

int main() {
    cout << "Hello from Coderish!" << endl;

    vector<int> nums = {64, 25, 12, 22, 11};
    cout << "Before sort: ";
    for (int n : nums) cout << n << " ";
    cout << endl;

    sort(nums.begin(), nums.end());
    cout << "After sort:  ";
    for (int n : nums) cout << n << " ";
    cout << endl;

    return 0;
}
`,

  java: `// Java — Hello World & Factorial
public class Main {
    static long factorial(int n) {
        if (n <= 1) return 1;
        return n * factorial(n - 1);
    }

    public static void main(String[] args) {
        System.out.println("Hello from Coderish!");
        System.out.println("Factorials 1..10:");
        for (int i = 1; i <= 10; i++) {
            System.out.printf("  %2d! = %d%n", i, factorial(i));
        }
    }
}
`,
};

const LANG_META = {
  minilang: { icon: "🔬", ext: "ml",   monacoLang: "plaintext", label: "MiniLang" },
  python:   { icon: "🐍", ext: "py",   monacoLang: "python",    label: "Python"   },
  c:        { icon: "⚙️", ext: "c",    monacoLang: "c",         label: "C"        },
  cpp:      { icon: "🔷", ext: "cpp",  monacoLang: "cpp",       label: "C++"      },
  java:     { icon: "☕", ext: "java", monacoLang: "java",      label: "Java"     },
};


/* ══════════════════════════════════════════════════════════════
   GLOBAL STATE
══════════════════════════════════════════════════════════════ */
let monacoEditor    = null;
let currentLang     = "minilang";
let editorFontSize  = 15;
let isDarkTheme     = true;

// Dynamic Backend URL routing (detect local environment vs deployed Netlify production)
const API_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "/api/run"
  : "https://coderish-backend.onrender.com/api/run";


/* ══════════════════════════════════════════════════════════════
   ELEMENT REFERENCES
══════════════════════════════════════════════════════════════ */
const $  = id => document.getElementById(id);
const elLangSelect       = $("lang-select");
const elLangIcon         = $("lang-icon");
const elEditorFilename   = $("editor-filename");
const elBtnRun           = $("btn-run");
const elRunSpinner       = $("run-spinner");
const elBtnClear         = $("btn-clear");
const elBtnClearTerminal = $("btn-clear-terminal");
const elBtnCopy          = $("btn-copy");
const elBtnFontInc       = $("btn-font-increase");
const elBtnFontDec       = $("btn-font-decrease");
const elFontSizeLabel    = $("font-size-label");
const elBtnTheme         = $("btn-theme");
const elTerminalBody     = $("terminal-body");
const elTerminalBadge    = $("terminal-badge");
const elStatusLang       = $("status-lang");
const elStatusTime       = $("status-time");
const elStatusExit       = $("status-exit");
const elInspectorPanel   = $("inspector-panel");
const elCursorPos        = $("cursor-pos");
const elToast            = $("toast");


/* ══════════════════════════════════════════════════════════════
   MONACO EDITOR INITIALISATION
══════════════════════════════════════════════════════════════ */
require.config({
  paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs" }
});

require(["vs/editor/editor.main"], () => {
  // Define a custom dark theme matching our CSS design system
  monaco.editor.defineTheme("coderish-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment",    foreground: "475569", fontStyle: "italic" },
      { token: "keyword",    foreground: "818cf8", fontStyle: "bold"   },
      { token: "string",     foreground: "34d399"  },
      { token: "number",     foreground: "fbbf24"  },
      { token: "delimiter",  foreground: "94a3b8"  },
      { token: "type",       foreground: "c084fc"  },
      { token: "identifier", foreground: "e2e8f0"  },
    ],
    colors: {
      "editor.background":           "#0d0e14",
      "editor.foreground":           "#e2e8f0",
      "editor.lineHighlightBackground": "#1a1c28",
      "editor.selectionBackground":  "#6366f140",
      "editorLineNumber.foreground": "#334155",
      "editorLineNumber.activeForeground": "#818cf8",
      "editorCursor.foreground":     "#6366f1",
      "editor.inactiveSelectionBackground": "#6366f120",
      "editorIndentGuide.background": "#1e2033",
      "editorIndentGuide.activeBackground": "#6366f130",
      "scrollbar.shadow":            "#00000060",
      "scrollbarSlider.background":  "#6366f125",
      "scrollbarSlider.hoverBackground": "#6366f145",
    },
  });

  monaco.editor.defineTheme("coderish-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment",  foreground: "64748b", fontStyle: "italic" },
      { token: "keyword",  foreground: "4f46e5", fontStyle: "bold"   },
      { token: "string",   foreground: "059669" },
      { token: "number",   foreground: "d97706" },
    ],
    colors: {
      "editor.background": "#f8fafc",
      "editor.foreground": "#1e293b",
      "editor.lineHighlightBackground": "#eef0f6",
      "editorLineNumber.foreground": "#94a3b8",
    },
  });

  monacoEditor = monaco.editor.create($("monaco-editor"), {
    value: TEMPLATES[currentLang],
    language: LANG_META[currentLang].monacoLang,
    theme: "coderish-dark",
    fontSize: editorFontSize,
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    fontLigatures: true,
    lineNumbers: "on",
    minimap: { enabled: true, scale: 1 },
    scrollBeyondLastLine: false,
    smoothScrolling: true,
    cursorBlinking: "phase",
    cursorSmoothCaretAnimation: "on",
    wordWrap: "on",
    tabSize: 2,
    renderWhitespace: "selection",
    bracketPairColorization: { enabled: true },
    padding: { top: 12, bottom: 12 },
    formatOnType: true,
    suggestOnTriggerCharacters: true,
    quickSuggestions: true,
    automaticLayout: true,
  });

  // Track cursor position
  monacoEditor.onDidChangeCursorPosition(e => {
    elCursorPos.textContent = `Ln ${e.position.lineNumber}, Col ${e.position.column}`;
  });

  // Ctrl+Enter shortcut to run
  monacoEditor.addCommand(
    monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
    () => runCode()
  );
});


/* ══════════════════════════════════════════════════════════════
   LANGUAGE SWITCHING
══════════════════════════════════════════════════════════════ */
function switchLanguage(lang) {
  if (!LANG_META[lang]) return;
  currentLang = lang;

  const meta = LANG_META[lang];

  // Update icon
  elLangIcon.textContent = meta.icon;

  // Update file tab name
  elEditorFilename.textContent = `main.${meta.ext}`;

  // Update status bar
  elStatusLang.textContent = meta.label;

  // Set Monaco language
  if (monacoEditor) {
    const model = monacoEditor.getModel();
    monaco.editor.setModelLanguage(model, meta.monacoLang);
    monacoEditor.setValue(TEMPLATES[lang]);
  }

  // Show/hide MiniLang inspector
  if (lang === "minilang") {
    elInspectorPanel.removeAttribute("aria-hidden");
    elInspectorPanel.style.display = "";
  } else {
    elInspectorPanel.setAttribute("aria-hidden", "true");
    elInspectorPanel.style.display = "none";
  }

  showToast(`Switched to ${meta.label}  ${meta.icon}`);
}

elLangSelect.addEventListener("change", e => switchLanguage(e.target.value));

// Initialise icon on load
elLangIcon.textContent = LANG_META[currentLang].icon;
// Hide inspector for non-MiniLang on first load (minilang is default so show it)


/* ══════════════════════════════════════════════════════════════
   FONT SIZE CONTROL
══════════════════════════════════════════════════════════════ */
function setFontSize(size) {
  editorFontSize = Math.min(28, Math.max(10, size));
  elFontSizeLabel.textContent = `${editorFontSize}px`;
  if (monacoEditor) monacoEditor.updateOptions({ fontSize: editorFontSize });
}
elBtnFontInc.addEventListener("click", () => setFontSize(editorFontSize + 1));
elBtnFontDec.addEventListener("click", () => setFontSize(editorFontSize - 1));


/* ══════════════════════════════════════════════════════════════
   THEME TOGGLE
══════════════════════════════════════════════════════════════ */
elBtnTheme.addEventListener("click", () => {
  isDarkTheme = !isDarkTheme;
  document.body.classList.toggle("theme-light", !isDarkTheme);
  if (monacoEditor) {
    monaco.editor.setTheme(isDarkTheme ? "coderish-dark" : "coderish-light");
  }
  $("theme-icon-moon").style.display = isDarkTheme ? "" : "none";
  $("theme-icon-sun").style.display  = isDarkTheme ? "none" : "";
  showToast(isDarkTheme ? "Dark theme activated 🌙" : "Light theme activated ☀️");
});


/* ══════════════════════════════════════════════════════════════
   CLEAR & COPY
══════════════════════════════════════════════════════════════ */
elBtnClear.addEventListener("click", () => {
  if (monacoEditor) monacoEditor.setValue("");
  monacoEditor.focus();
});

elBtnClearTerminal.addEventListener("click", () => {
  elTerminalBody.innerHTML = "";
  setTerminalBadge("idle");
  elStatusTime.textContent = "";
  elStatusExit.textContent = "";
  elStatusExit.className = "";
});

elBtnCopy.addEventListener("click", async () => {
  if (!monacoEditor) return;
  const code = monacoEditor.getValue();
  try {
    await navigator.clipboard.writeText(code);
    showToast("Code copied to clipboard ✓");
  } catch {
    showToast("Copy failed — please copy manually.");
  }
});


/* ══════════════════════════════════════════════════════════════
   RUN CODE
══════════════════════════════════════════════════════════════ */
elBtnRun.addEventListener("click", runCode);

async function runCode() {
  if (!monacoEditor) return;
  const code = monacoEditor.getValue().trim();
  if (!code) { showToast("Write some code first!"); return; }

  // UI: loading state
  setRunning(true);
  setTerminalBadge("running");
  appendTerminalHeader(currentLang, null, "running");

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: currentLang, code }),
    });

    const result = await response.json();
    renderRunResult(result);
  } catch (err) {
    renderNetworkError(err);
  } finally {
    setRunning(false);
  }
}

/* ── Render a successful/failed run result ── */
function renderRunResult(result) {
  const isSuccess = result.exit_code === 0;
  const isTimeout = result.exit_code === -1;
  const status = isTimeout ? "timeout" : isSuccess ? "success" : "error";

  // Update status bar
  const elapsed = result.elapsed != null ? `${(result.elapsed * 1000).toFixed(1)}ms` : "";
  elStatusTime.textContent = elapsed ? `⏱ ${elapsed}` : "";
  elStatusExit.textContent = `Exit ${result.exit_code}`;
  elStatusExit.className   = isSuccess ? "ok" : "fail";

  // Update terminal badge
  setTerminalBadge(status);

  // Re-render the last (running) header as final status
  const existingRunning = elTerminalBody.querySelector(".term-header.running");
  if (existingRunning) existingRunning.classList.remove("running");

  // Append new styled header
  appendTerminalHeader(currentLang, elapsed, status);

  // stdout
  if (result.stdout) {
    appendTerminalLine("stdout", result.stdout);
  } else if (!result.stderr) {
    appendTerminalLine("empty", "(no output)");
  }

  // stderr
  if (result.stderr) {
    appendTerminalLine("stderr", result.stderr);
  }

  // MiniLang Inspector
  if (currentLang === "minilang" && result.metadata) {
    populateInspector(result.metadata);
  }

  scrollTerminal();
}

/* ── Render a network/fetch error ── */
function renderNetworkError(err) {
  setTerminalBadge("error");
  appendTerminalLine("stderr", `Network error: ${err.message}\nIs the server running? Start it with: python server.py`);
  scrollTerminal();
}

/* ── Terminal DOM helpers ── */
function appendTerminalHeader(lang, elapsed, status) {
  const meta    = LANG_META[lang] || { icon: "▶", label: lang };
  const icons   = { running: "⏳", success: "✅", error: "❌", timeout: "⚠️" };
  const labels  = { running: "Running…", success: "Done", error: "Error", timeout: "Timeout" };

  const div = document.createElement("div");
  div.className = `term-block`;
  div.innerHTML = `
    <div class="term-header ${status}">
      <span class="term-header-icon">${icons[status] || "▶"}</span>
      <span class="term-header-lang ${status}">${meta.label}</span>
      <span style="color:var(--text-muted);font-size:0.7rem">${labels[status] || status}</span>
      ${elapsed ? `<span class="term-header-time">${elapsed}</span>` : ""}
    </div>`;
  elTerminalBody.appendChild(div);
}

function appendTerminalLine(type, text) {
  const pre = document.createElement("pre");
  pre.className = `term-block term-${type} anim-fadein`;
  pre.textContent = text;
  elTerminalBody.appendChild(pre);
}

function scrollTerminal() {
  elTerminalBody.scrollTop = elTerminalBody.scrollHeight;
}

/* ── Run button loading state ── */
function setRunning(active) {
  elBtnRun.classList.toggle("loading", active);
  elBtnRun.disabled = active;
}

/* ── Terminal badge state ── */
function setTerminalBadge(state) {
  elTerminalBadge.className = `terminal-badge ${state}`;
  const labels = { idle: "idle", running: "running…", success: "success", error: "error", timeout: "timeout" };
  elTerminalBadge.textContent = labels[state] || state;
}


/* ══════════════════════════════════════════════════════════════
   MINILANG INSPECTOR
══════════════════════════════════════════════════════════════ */
// Tab switching
document.querySelectorAll(".insp-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".insp-tab").forEach(t  => { t.classList.remove("active"); t.setAttribute("aria-selected","false"); });
    document.querySelectorAll(".insp-view").forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    btn.setAttribute("aria-selected","true");
    const target = btn.getAttribute("aria-controls");
    $(target).classList.add("active");
  });
});

function populateInspector(meta) {
  // ── Tokens ──
  const { tokens, ast, bytecode, globals } = meta;

  const tokensTbody = $("tokens-tbody");
  if (tokens && tokens.length > 0) {
    $("tokens-placeholder").style.display = "none";
    $("tokens-table").style.display = "table";
    tokensTbody.innerHTML = tokens.map((t, i) => `
      <tr>
        <td>${i}</td>
        <td class="token-type">${t.type}</td>
        <td class="token-val">${escHtml(String(t.value ?? ""))}</td>
        <td>${t.line}</td>
      </tr>`).join("");
  }

  // ── AST ──
  const astList = $("ast-list");
  if (ast && ast.length > 0) {
    $("ast-placeholder").style.display = "none";
    astList.style.display = "block";
    astList.innerHTML = ast.map(node => `<li>${escHtml(node)}</li>`).join("");
  }

  // ── Bytecode ──
  const bytecodeList = $("bytecode-list");
  if (bytecode && bytecode.length > 0) {
    $("bytecode-placeholder").style.display = "none";
    bytecodeList.style.display = "block";
    bytecodeList.innerHTML = bytecode.map((instr, idx) => {
      const parts  = instr.trim().split(/\s+/);
      const opcode = parts[0];
      const arg    = parts.slice(1).join(" ");
      const isHalt = opcode === "HALT";
      return `<div class="bc-row ${isHalt ? "bc-halt" : ""}">
        <span class="bc-addr">${String(idx).padStart(3,"0")}</span>
        <span class="bc-op">${escHtml(opcode)}</span>
        ${arg ? `<span class="bc-arg">${escHtml(arg)}</span>` : ""}
      </div>`;
    }).join("");
  }

  // ── Variables ──
  const varsTbody = $("vars-tbody");
  if (globals && Object.keys(globals).length > 0) {
    $("vars-placeholder").style.display = "none";
    $("vars-table").style.display = "table";
    varsTbody.innerHTML = Object.entries(globals).map(([k, v]) => `
      <tr>
        <td class="token-type">${escHtml(k)}</td>
        <td class="token-val">${escHtml(String(v))}</td>
      </tr>`).join("");
  }
}

function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


/* ══════════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
══════════════════════════════════════════════════════════════ */
let toastTimer = null;
function showToast(msg, duration = 2400) {
  elToast.textContent = msg;
  elToast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elToast.classList.remove("show"), duration);
}


/* ══════════════════════════════════════════════════════════════
   KEYBOARD SHORTCUT: Ctrl+Enter (outside Monaco focus)
══════════════════════════════════════════════════════════════ */
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    runCode();
  }
});


/* ══════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════ */
(function init() {
  // Sync the lang icon on first render
  elLangIcon.textContent = LANG_META[currentLang].icon;
  elStatusLang.textContent = LANG_META[currentLang].label;
  // Show inspector for default MiniLang
  elInspectorPanel.removeAttribute("aria-hidden");
})();
