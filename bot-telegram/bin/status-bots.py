#!/usr/bin/env python3
"""Painel de status dos bots de mensageria do Hermes.

Mostra, em uma tela, o que normalmente so se descobre lendo logs:
  - estado do servico do gateway (rodando, desde quando, se sobe no boot)
  - cada plataforma de mensageria: se esta ligada na config, se tem credencial
    e qual o estado ao vivo relatado pelo proprio gateway
  - estado da impressora Bambu (MCP), quando configurada

A fonte de verdade do estado ao vivo e ``gateway_state.json``, que o proprio
gateway reescreve a cada mudanca de conexao. O log so e consultado para
recuperar a mensagem do ultimo erro, que o arquivo de estado nao historia.

Uso:
    python3 ~/.hermes/bin/status-bots.py            # painel completo
    python3 ~/.hermes/bin/status-bots.py --json     # saida legivel por maquina
    python3 ~/.hermes/bin/status-bots.py --quick    # resumo de 1 linha (barra de status)

Nenhum segredo e impresso: das credenciais so se informa presenca e tamanho.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
ENV_FILE = HERMES_HOME / ".env"
CONFIG_FILE = HERMES_HOME / "config.yaml"
STATE_FILE = HERMES_HOME / "gateway_state.json"
GATEWAY_LOG = HERMES_HOME / "logs" / "gateway.log"
SERVICE = "hermes-gateway.service"

# Plataforma -> variaveis de ambiente que comprovam que ela foi configurada.
# A primeira variavel de cada lista e a credencial obrigatoria.
PLATFORMS: dict[str, list[str]] = {
    "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS", "TELEGRAM_HOME_CHANNEL"],
    "whatsapp": ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN"],
    "discord": ["DISCORD_BOT_TOKEN"],
    "slack": ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"],
    "signal": ["SIGNAL_PHONE_NUMBER"],
    "teams": ["TEAMS_APP_ID"],
    "google_chat": ["GOOGLE_CHAT_PROJECT"],
}

# Estado ao vivo relatado pelo gateway -> (simbolo, cor, texto)
STATE_LABELS: dict[str, tuple[str, str, str]] = {
    "connected": ("✓", "green", "conectado"),
    "connecting": ("…", "yellow", "conectando"),
    "retrying": ("↻", "yellow", "reconectando"),
    "degraded": ("!", "yellow", "degradado"),
    "pending_restart": ("⟳", "yellow", "aguardando reinicio do gateway"),
    "disabled": ("○", "grey", "desligado na config"),
    "not_configured": ("—", "grey", "nao configurada"),
    "error": ("✗", "red", "com erro"),
}

RESET, BOLD = "\033[0m", "\033[1m"
COLORS = {"green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
          "grey": "\033[90m", "bold": BOLD, "": ""}


def colorize(text: str, color: str) -> str:
    if not sys.stdout.isatty() or not COLORS.get(color):
        return text
    return f"{COLORS[color]}{text}{RESET}"


def run(cmd: list[str], timeout: int = 15) -> str:
    """Executa um comando e devolve stdout, ou string vazia se falhar."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return done.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def read_env() -> dict[str, str]:
    """Le o .env do Hermes sem interpretar nada: so pares chave=valor."""
    values: dict[str, str] = {}
    try:
        text = ENV_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def read_runtime_state() -> dict:
    """Estado ao vivo escrito pelo gateway (fonte de verdade das conexoes)."""
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def config_enabled() -> dict[str, bool]:
    """Le ``platforms.<nome>.enabled`` do config.yaml.

    Um ``enabled: false`` explicito vence a credencial do .env — e o liga/desliga
    oficial de uma plataforma. A ausencia da chave significa "decidir pela
    credencial", e nesse caso a plataforma nao aparece neste mapa.
    """
    try:
        text = CONFIG_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        block = data.get("platforms")
        if isinstance(block, dict):
            return {name: bool(cfg["enabled"])
                    for name, cfg in block.items()
                    if isinstance(cfg, dict) and "enabled" in cfg}
        return {}
    except Exception:
        pass

    # Sem PyYAML: varre o bloco platforms: por indentacao, ignorando comentarios.
    found: dict[str, bool] = {}
    inside = False
    current = ""
    for line in text.splitlines():
        if re.match(r"^platforms:\s*$", line):
            inside = True
            continue
        if inside:
            if re.match(r"^\S", line):
                break
            name = re.match(r"^  ([a-z_]+):\s*$", line)
            if name:
                current = name.group(1)
                continue
            flag = re.match(r"^\s{4,}enabled:\s*(true|false)\s*$", line, re.I)
            if flag and current:
                found[current] = flag.group(1).lower() == "true"
    return found


def process_alive(pid: int) -> bool:
    """Existe processo com esse pid? Usado quando nao ha systemd para consultar."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe, so nao e nosso
    except (OSError, OverflowError):
        return False
    return True


def service_state(runtime: dict) -> dict[str, object]:
    """Estado do supervisor do gateway.

    Caminho principal: o servico de usuario do systemd. Em maquinas sem systemd
    (macOS com launchd, containers, gateway rodado a mao) o fallback e a
    vivacidade do pid que o proprio gateway registrou em gateway_state.json —
    menos informacao, mas nunca relata "parado" para um gateway que esta de pe.
    """
    raw = run(["systemctl", "--user", "show", SERVICE,
               "-p", "ActiveState", "-p", "SubState", "-p", "UnitFileState",
               "-p", "ExecMainStartTimestamp", "-p", "MainPID", "-p", "MemoryCurrent",
               "-p", "NRestarts"])

    if not raw:
        pid = str(runtime.get("pid") or "")
        alive = pid.isdigit() and process_alive(int(pid))
        return {
            "supervisor": "nenhum (systemd indisponivel)",
            "active": bool(alive),
            "sub_state": "n/a",
            "autostart": None,     # desconhecido: nao ha unit para consultar
            "linger": None,
            "pid": pid or "0",
            "uptime": "",
            "memory_mb": None,
            "restarts": "0",
        }

    props: dict[str, str] = {}
    for line in raw.splitlines():
        key, _, value = line.partition("=")
        props[key] = value

    started = props.get("ExecMainStartTimestamp", "")
    uptime = ""
    if started:
        # Formato do systemd: "Sun 2026-11-08 13:21:40 -03"
        match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", started)
        if match:
            begin = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            delta = datetime.now() - begin
            hours, rest = divmod(int(delta.total_seconds()), 3600)
            uptime = f"{hours}h{rest // 60:02d}min"

    memory_mb = None
    try:
        memory_mb = int(props.get("MemoryCurrent", "")) // (1024 * 1024)
    except ValueError:
        pass

    linger = "yes" in run(["loginctl", "show-user", os.environ.get("USER", ""),
                           "-p", "Linger"]).lower()

    return {
        "supervisor": "systemd (--user)",
        "active": props.get("ActiveState") == "active",
        "sub_state": props.get("SubState", "?"),
        "autostart": props.get("UnitFileState") == "enabled",
        "pid": props.get("MainPID", "0"),
        "uptime": uptime,
        "memory_mb": memory_mb,
        "restarts": props.get("NRestarts", "0"),
        "linger": linger,
    }


def tail_log(window: int = 400_000) -> list[str]:
    """Ultimas linhas do log do gateway.

    Le so o fim do arquivo: o log passa de 700 KB e cresce. Lido UMA vez e
    reaproveitado por todas as plataformas — antes cada uma reabria o arquivo.
    """
    try:
        size = GATEWAY_LOG.stat().st_size
        with GATEWAY_LOG.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(max(0, size - window))
            return handle.readlines()
    except OSError:
        return []


def last_log_error(platform: str, lines: list[str]) -> str:
    """Mensagem do ultimo erro da plataforma nas linhas ja lidas por tail_log."""
    needle = platform.lower()
    found = ""
    for line in lines:
        low = line.lower()
        if needle in low and re.search(r"\berror\b|fatal|unauthorized|\b401\b|\b409\b", low):
            found = f"{line[:19]} {line.split(': ', 2)[-1].strip()[:100]}"
    return found


def printer_state() -> dict[str, object]:
    """Alcancabilidade da impressora Bambu pela porta MQTT (8883), sem autenticar."""
    env = read_env()
    host = env.get("PRINTER_HOST") or env.get("BAMBU_PRINTER_HOST") or env.get("BAMBU_HOST") or ""
    if not host:
        return {"configured": False}
    reachable = False
    try:
        with socket.create_connection((host, 8883), timeout=3):
            reachable = True
    except OSError:
        pass
    return {"configured": True, "host": host, "reachable": reachable}


def resolve_state(name: str, *, live: dict, enabled: dict, has_credential: bool) -> str:
    """Estado final de uma plataforma, cruzando as tres fontes.

    Precedencia: desligado explicito na config > estado ao vivo do gateway >
    inferencia pela credencial.
    """
    if enabled.get(name) is False:
        return "disabled"
    row = live.get(name)
    if isinstance(row, dict) and row.get("state"):
        return str(row["state"])
    return "pending_restart" if has_credential else "not_configured"


def heartbeat_age(runtime: dict) -> float | None:
    """Segundos desde o ultimo carimbo em gateway_state.json.

    A manutencao interna do gateway reescreve ``updated_at`` a cada 60 s, logo o
    campo funciona como heartbeat. Processo vivo com carimbo velho (>120 s pela
    doc oficial) e o caso "parece rodando mas nada esta sendo agendado" — que
    nem o systemd nem o estado da plataforma revelam.
    """
    stamp = runtime.get("updated_at")
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).total_seconds()


HEARTBEAT_STALE_S = 120.0


def collect(*, probe_printer: bool = True) -> dict[str, object]:
    env = read_env()
    runtime = read_runtime_state()
    live = runtime.get("platforms") if isinstance(runtime.get("platforms"), dict) else {}
    enabled = config_enabled()
    service = service_state(runtime)

    # O log so e lido se alguma plataforma estiver de fato com problema.
    log_lines: list[str] | None = None

    platforms = {}
    for name, keys in PLATFORMS.items():
        primary = keys[0]
        credential = env.get(primary, "")
        state = resolve_state(name, live=live, enabled=enabled, has_credential=bool(credential))
        row = live.get(name) if isinstance(live.get(name), dict) else {}
        entry: dict[str, object] = {
            "state": state,
            "configured": bool(credential),
            "enabled_in_config": enabled.get(name),
            "credential_var": primary,
            "credential_len": len(credential),
            "extra_vars": {k: bool(env.get(k)) for k in keys[1:]},
            "needs_attention": bool(row.get("needs_attention")),
            "updated_at": row.get("updated_at") or "",
            "error_message": row.get("error_message") or "",
        }
        if credential and state not in ("connected", "not_configured", "disabled"):
            if log_lines is None:
                log_lines = tail_log()
            entry["last_log_error"] = last_log_error(name, log_lines)
        platforms[name] = entry

    age = heartbeat_age(runtime)
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "hermes_home": str(HERMES_HOME),
        "service": service,
        "gateway_state": runtime.get("gateway_state", "unknown"),
        "exit_reason": runtime.get("exit_reason") or "",
        "heartbeat_age_s": round(age, 1) if age is not None else None,
        "heartbeat_stale": bool(service["active"] and age is not None and age > HEARTBEAT_STALE_S),
        "active_agents": runtime.get("active_agents"),
        "code_version": runtime.get("code_version", ""),
        "platforms": platforms,
        "printer": printer_state() if probe_printer else {"configured": False},
        "gateway_log": str(GATEWAY_LOG),
    }


def summarize(data: dict) -> dict[str, str]:
    """Resumo de uma linha para a barra de status do app desktop."""
    service = data["service"]
    platforms: dict = data["platforms"]
    live = {n: i for n, i in platforms.items() if i["state"] != "not_configured"}

    if not service["active"]:
        return {"dot": "red", "label": "Bots off", "detail": "Gateway parado — nada e recebido"}
    # Processo vivo com heartbeat velho: o cron e a manutencao congelaram.
    if data.get("heartbeat_stale"):
        return {"dot": "red", "label": "Gateway travado",
                "detail": f"Heartbeat parado ha {int(data['heartbeat_age_s'])}s — reinicie"}
    if str(data.get("gateway_state")) == "degraded":
        return {"dot": "red", "label": "Gateway degradado",
                "detail": str(data.get("exit_reason") or "ver gateway status")}
    if not live:
        return {"dot": "grey", "label": "Sem bots", "detail": "Nenhuma plataforma configurada"}

    connected = [n for n, i in live.items() if i["state"] == "connected"]
    broken = [n for n, i in live.items() if i["state"] in ("error", "degraded")]
    waiting = [n for n, i in live.items()
               if i["state"] in ("connecting", "retrying", "pending_restart")]
    off = [n for n, i in live.items() if i["state"] == "disabled"]

    # Sem systemd nao ha uptime: nao monte "de pe ha " com o valor vazio.
    uptime = service["uptime"]
    up = f"Gateway de pe ha {uptime}" if uptime else "Gateway de pe"

    if broken:
        return {"dot": "red", "label": f"{broken[0]} com erro",
                "detail": str(platforms[broken[0]].get("error_message") or "Abra Messaging")}
    if waiting:
        state = platforms[waiting[0]]["state"]
        return {"dot": "yellow", "label": f"{waiting[0]} {STATE_LABELS[state][2]}",
                "detail": up}
    if connected:
        extra = f" (+{len(off)} off)" if off else ""
        return {"dot": "green", "label": f"{', '.join(connected)} ok{extra}", "detail": up}
    return {"dot": "grey", "label": "Bots desligados",
            "detail": f"{len(off)} plataforma(s) desligada(s) na config"}


def render(data: dict) -> str:
    service = data["service"]
    lines: list[str] = []
    lines.append(colorize(f"BOTS DO HERMES — {data['generated_at']}", "bold"))
    lines.append("")

    # ── Servico do gateway ───────────────────────────────────────────────
    if service["active"]:
        head = colorize("● RODANDO", "green")
        detail = f"pid {service['pid']}"
        if service["uptime"]:
            detail += f", ha {service['uptime']}"
        if service["memory_mb"] is not None:
            detail += f", {service['memory_mb']} MB"
        if data.get("active_agents") is not None:
            detail += f", {data['active_agents']} agente(s) ativo(s)"
    else:
        head = colorize("● PARADO", "red")
        detail = "nenhuma mensagem sera recebida"
    lines.append(f"  Gateway       {head}  {colorize(detail, 'grey')}")

    if service.get("autostart") is None:
        # Sem systemd nao existe unit para perguntar: nao invente um veredito.
        lines.append(f"  Supervisor    {colorize(str(service.get('supervisor', '?')), 'yellow')}"
                     f"  {colorize('persistencia no boot desconhecida', 'grey')}")
    else:
        boot = (colorize("sobe no boot", "green") if service["autostart"]
                else colorize("NAO sobe no boot (precisa start manual)", "yellow"))
        survive = ("sobrevive ao logout" if service["linger"]
                   else colorize("morre no logout", "yellow"))
        lines.append(f"  Inicializacao {boot}; {colorize(survive, 'grey')}")
    if service["restarts"] not in ("0", ""):
        lines.append(f"  Reinicios     {service['restarts']}")

    # Heartbeat: a unica pista do gateway vivo mas com agendamento congelado.
    age = data.get("heartbeat_age_s")
    if data.get("heartbeat_stale"):
        nota = f"sem carimbo ha {int(age)}s (normal: 60s) — reinicie o gateway"
        lines.append(f"  Heartbeat     {colorize('TRAVADO', 'red')}  {colorize(nota, 'grey')}")
    elif age is not None:
        nota = f"carimbo de {int(age)}s atras"
        lines.append(f"  Heartbeat     {colorize('ok', 'green')}  {colorize(nota, 'grey')}")
    if str(data.get("gateway_state")) == "degraded":
        lines.append(f"  Estado        {colorize('DEGRADADO', 'red')}  "
                     f"{colorize(str(data.get('exit_reason') or ''), 'grey')}")
    lines.append("")

    # ── Plataformas ──────────────────────────────────────────────────────
    lines.append(colorize("  PLATAFORMAS", "bold"))
    for name, info in sorted(data["platforms"].items()):
        symbol, color, text = STATE_LABELS.get(
            str(info["state"]), ("?", "yellow", str(info["state"])))
        lines.append(f"    {name:12} {colorize(f'{symbol} {text}', color)}")
        if info.get("error_message"):
            lines.append(f"      {colorize('erro: ' + str(info['error_message'])[:100], 'grey')}")
        elif info.get("last_log_error"):
            lines.append(f"      {colorize('ultimo erro no log: ' + str(info['last_log_error']), 'grey')}")
        if info["state"] == "connected" and info.get("updated_at"):
            since = str(info["updated_at"])[:19].replace("T", " ")
            lines.append(f"      {colorize('conectado desde ' + since + ' UTC', 'grey')}")
    lines.append("")

    # ── Impressora ───────────────────────────────────────────────────────
    printer = data["printer"]
    if printer["configured"]:
        state = (colorize("✓ alcancavel", "green") if printer["reachable"]
                 else colorize("✗ fora de alcance (desligada ou outra rede)", "red"))
        lines.append(f"  Impressora    {state}  {colorize(str(printer['host']), 'grey')}")
    else:
        lines.append(f"  Impressora    {colorize('— nao sondada', 'grey')}")
    lines.append("")

    lines.append(colorize("  Ligar/desligar um bot: app desktop → barra lateral → Messaging", "grey"))
    lines.append(colorize(f"  Log completo: {data['gateway_log']}", "grey"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Painel de status dos bots do Hermes.")
    parser.add_argument("--json", action="store_true", help="imprime JSON em vez do painel")
    parser.add_argument("--quick", action="store_true",
                        help="resumo de 1 linha em JSON, sem sondar a impressora")
    args = parser.parse_args()

    data = collect(probe_printer=not args.quick)
    if args.quick:
        print(json.dumps(summarize(data), ensure_ascii=False))
    elif args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render(data))

    # 0 = saudavel; 1 = algo exige acao (parado, travado ou degradado).
    healthy = (data["service"]["active"]
               and not data["heartbeat_stale"]
               and data["gateway_state"] != "degraded")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
