"""
Safety constants and defaults for npm package analysis.

Core principle: All fetched package content is **UNTRUSTED**.
Package code is **NEVER** executed.
Network access is explicit and limited to fetching registry data.
"""

# ── Hard safety defaults ──────────────────────────────────────────────────────

NEVER_EXECUTE_PACKAGE_CODE: bool = True
NEVER_RUN_NPM_INSTALL: bool = True
NEVER_RUN_LIFECYCLE_SCRIPTS: bool = True

SAFETY_NOTICE = (
    "SAFETY: This tool fetches and inspects npm packages as UNTRUSTED content.\n"
    "        Package code is never executed. All content is isolated under packages/."
)

# ── Suspicious code patterns ──────────────────────────────────────────────────
# Each entry: pattern (regex), category, severity (high/medium/low).
# Presence of a pattern is a signal for further review, not a verdict.

SUSPICIOUS_PATTERNS: list[dict] = [
    # Credential / secret harvesting
    {
        "pattern": r"process\.env\.(?:AWS|GITHUB|NPM|CI|TOKEN|SECRET|PASSWORD|KEY|CRED)",
        "category": "credential-access",
        "severity": "high",
    },
    {
        "pattern": r"(?i)(?:password|passwd|secret|token|apikey|api_key)\s*[=:]\s*['\"]",
        "category": "credential-access",
        "severity": "high",
    },
    {
        "pattern": r"Authorization\s*:\s*['\"]Bearer",
        "category": "credential-access",
        "severity": "high",
    },
    # Network exfiltration
    {
        "pattern": r"(?:http|https)\.request\s*\(",
        "category": "network",
        "severity": "medium",
    },
    {
        "pattern": r"\bfetch\s*\(",
        "category": "network",
        "severity": "medium",
    },
    {
        "pattern": r"\bXMLHttpRequest\b",
        "category": "network",
        "severity": "low",
    },
    # Code execution / eval
    {
        "pattern": r"\beval\s*\(",
        "category": "code-execution",
        "severity": "high",
    },
    {
        "pattern": r"\bnew\s+Function\s*\(",
        "category": "code-execution",
        "severity": "high",
    },
    {
        "pattern": r"\bvm\.runIn(?:New|This)Context\s*\(",
        "category": "code-execution",
        "severity": "high",
    },
    {
        "pattern": r"\bexecSync\s*\(",
        "category": "code-execution",
        "severity": "high",
    },
    {
        "pattern": r"\bspawnSync\s*\(",
        "category": "code-execution",
        "severity": "high",
    },
    {
        "pattern": r"\bchild_process\b",
        "category": "code-execution",
        "severity": "medium",
    },
    # Obfuscation
    {
        "pattern": r"\bBuffer\.from\s*\(['\"][A-Za-z0-9+/]{20,}",
        "category": "obfuscation",
        "severity": "medium",
    },
    {
        "pattern": r"\bString\.fromCharCode\s*\(",
        "category": "obfuscation",
        "severity": "medium",
    },
    {
        "pattern": r"\batob\s*\(",
        "category": "obfuscation",
        "severity": "low",
    },
    # Filesystem access
    {
        "pattern": r"\bfs\.(?:read|write|append|unlink|rm|rmdir|mkdir)\b",
        "category": "filesystem",
        "severity": "medium",
    },
    # OS / environment reconnaissance
    {
        "pattern": r"\bos\.(?:homedir|userInfo|tmpdir)\s*\(",
        "category": "system-info",
        "severity": "medium",
    },
    {
        "pattern": r"\bprocess\.env\b",
        "category": "system-info",
        "severity": "low",
    },
]

# ── Dangerous file extensions ─────────────────────────────────────────────────

DANGEROUS_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".sh", ".bash", ".zsh", ".fish",       # Unix shell scripts
        ".ps1", ".psm1", ".psd1",             # PowerShell
        ".bat", ".cmd",                        # Windows batch
        ".exe", ".dll", ".so", ".dylib",      # Native binaries
        ".node",                              # Native Node.js addons
        ".wasm",                              # WebAssembly
    }
)

# ── npm registry ──────────────────────────────────────────────────────────────

ALLOWED_REGISTRY_HOST: str = "registry.npmjs.org"
