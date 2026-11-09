#!/usr/bin/env python3
"""Auditoria de vazamento: varre arquivos antes de publicar em repo publico.

Procura o que nao pode sair da sua maquina: tokens de bot, chaves de API,
blocos de chave privada, IPs de rede interna, e-mails, caminhos da pasta
pessoal e o seu nome. Pensado para rodar antes de cada `git push`.

Uso:
    python3 tools/audit-leaks.py                      # varre o repo todo
    python3 tools/audit-leaks.py bin/ docs/           # so esses caminhos
    python3 tools/audit-leaks.py --nome "Joao Silva"  # procura tambem seu nome
    python3 tools/audit-leaks.py --json               # saida para script/CI

Codigo de saida:
    0  nada encontrado
    1  achados de severidade MEDIO ou BAIXO (revisar)
    2  achados CRITICOS ou ALTOS (NAO publique)

O relatorio nunca imprime o segredo inteiro: so os primeiros caracteres, o
suficiente para voce localizar a linha.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Nao faz sentido varrer binarios, historico do git ou dependencias.
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "dist", "build", ".mypy_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
                 ".gz", ".xz", ".tar", ".so", ".bin", ".woff", ".woff2", ".ttf", ".mp4"}

RULES: list[tuple[str, str, re.Pattern[str]]] = [
    # ── Impeditivos: um destes num repo publico e um incidente ───────────
    ("CRITICO", "token de bot do Telegram", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b")),
    ("CRITICO", "chave de API (sk/pk/ghp/xox)",
     re.compile(r"\b(?:sk|pk|ghp|gho|ghs|ghu|xox[bapsr])[-_][A-Za-z0-9]{16,}\b")),
    ("CRITICO", "bloco de chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("CRITICO", "atribuicao de segredo com valor", re.compile(
        r"(?i)\b(token|secret|password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret)\b"
        r"\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
    ("CRITICO", "URL com usuario e senha", re.compile(r"://[^/\s:@]+:[^/\s:@]+@")),
    ("CRITICO", "credencial da AWS", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    # ── Expoem sua rede ou identidade ────────────────────────────────────
    ("ALTO", "IP de rede interna", re.compile(
        r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")),
    ("ALTO", "e-mail", re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b")),
    # ── Vazam contexto, nao acesso: revisar, nao necessariamente remover ─
    ("MEDIO", "caminho da pasta pessoal", re.compile(r"(?:/home/|/Users/)[a-z][a-z0-9_.-]+")),
    ("BAIXO", "endereco MAC", re.compile(r"\b[0-9A-F]{2}(?::[0-9A-F]{2}){5}\b", re.I)),
]

SEVERITY_ORDER = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3}
BLOCKING = {"CRITICO", "ALTO"}

# Linha marcada assim e ignorada: para exemplos de documentacao propositais.
ALLOW_MARK = "audit-leaks: ok"


def iter_files(roots: list[Path]) -> list[Path]:
    """Arquivos de texto sob os caminhos dados, sem binarios nem .git."""
    found: list[Path] = []
    for root in roots:
        if root.is_file():
            found.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            found.append(path)
    return found


def scan(path: Path, extra_rules: list[tuple[str, str, re.Pattern[str]]]) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return []  # binario disfarcado de texto: nada a auditar
    except OSError as exc:
        return [{"line": 0, "severity": "ERRO", "rule": "arquivo ilegivel",
                 "match": str(exc), "context": ""}]

    findings: list[dict] = []
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARK in line:
            continue
        for severity, rule, pattern in RULES + extra_rules:
            for match in pattern.finditer(line):
                value = match.group(0)
                findings.append({
                    "line": number,
                    "severity": severity,
                    "rule": rule,
                    "match": value[:20] + ("…" if len(value) > 20 else ""),
                    "context": line.strip()[:100],
                })
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["line"]))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria de vazamento antes de publicar.")
    parser.add_argument("paths", nargs="*", default=["."],
                        help="arquivos ou pastas a varrer (padrao: .)")
    parser.add_argument("--nome", action="append", default=[],
                        help="nome proprio a tratar como dado pessoal (repetivel)")
    parser.add_argument("--json", action="store_true", help="saida JSON")
    args = parser.parse_args()

    extra = [("MEDIO", f"nome pessoal ({n})", re.compile(re.escape(n), re.I))
             for n in args.nome]

    roots = [Path(p) for p in args.paths]
    missing = [str(r) for r in roots if not r.exists()]
    if missing:
        print(f"caminho inexistente: {', '.join(missing)}", file=sys.stderr)
        return 2

    report = {}
    for path in iter_files(roots):
        hits = scan(path, extra)
        if hits:
            report[str(path)] = hits

    total = sum(len(v) for v in report.values())
    blocking = sum(1 for v in report.values() for f in v if f["severity"] in BLOCKING)

    if args.json:
        # Saida exclusivamente JSON: o resumo vai DENTRO do objeto, nunca depois
        # dele, senao o parse do consumidor quebra com "Extra data".
        print(json.dumps({"total": total, "blocking": blocking, "findings": report},
                         indent=2, ensure_ascii=False))
    else:
        if not report:
            print("  nenhum achado — pode publicar")
        for path, findings in report.items():
            print(f"\n--- {path} ---")
            for f in findings:
                print(f"    [{f['severity']:7}] L{f['line']:<4} {f['rule']}: {f['match']}")
                print(f"              > {f['context']}")
        print(f"\n  TOTAL: {total} achado(s), {blocking} impeditivo(s)")
        if blocking:
            print("  NAO PUBLIQUE ate resolver os impeditivos.")

    if blocking:
        return 2
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
