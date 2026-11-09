# 2. Ver o status e ligar/desligar

## A confusão que custa mais tempo: configurado ≠ conectado

Abrindo o `config.yaml` você encontra um bloco assim:

```yaml
platform_toolsets:
  telegram: [hermes-telegram]
  whatsapp: [hermes-whatsapp]
  discord: [hermes-discord]
```

**Isso não quer dizer que você tem três bots.** Esse bloco só declara *quais
ferramentas cada plataforma teria, se existisse* — vem preenchido de fábrica
para todas. É a armadilha número um: dá a impressão de que o WhatsApp está
montado quando nunca houve credencial nenhuma.

Uma plataforma só está viva quando as **duas** coisas são verdade:

1. a credencial dela existe no `.env` (`TELEGRAM_BOT_TOKEN`, etc.)
2. ela aparece em `platforms` dentro do `gateway_state.json`

É exatamente esse cruzamento que o `bots` faz.

---

## A fonte de verdade: `gateway_state.json`

O gateway reescreve `$HERMES_HOME/gateway_state.json` a cada mudança de
conexão. É o lugar certo de olhar — melhor que garimpar log:

```json
{
  "gateway_state": "running",
  "active_agents": 1,
  "restart_requested": false,
  "platforms": {
    "telegram": {
      "state": "connected",
      "needs_attention": false,
      "error_message": null,
      "updated_at": "2026-11-08T16:21:59+00:00"
    }
  }
}
```

Estados possíveis:

| Estado | Significa |
|---|---|
| `connected` | Funcionando |
| `connecting` | Subindo agora |
| `retrying` | Caiu, tentando reconectar sozinho |
| `degraded` | De pé, mas com problema |
| `pending_restart` | Config mudou; só vale após reiniciar o gateway |
| `disabled` | Desligado de propósito na config |
| `not_configured` | Sem credencial |
| `error` | Falhou |

O arquivo **não guarda histórico**. Para recuperar a mensagem do último erro
ainda é preciso ler `$HERMES_HOME/logs/gateway.log` — o `bots` faz isso só
quando alguma plataforma está de fato com problema.

---

## O painel

```bash
bots              # painel colorido
bots --json       # tudo, para script
bots --quick      # resumo de 1 linha (~60 ms, usado pelo chip)
```

Código de saída: `0` saudável, `1` precisa de ação. Serve em cron ou healthcheck.

O que cada linha responde:

- **Gateway** — o processo está de pé? Há quanto tempo? Quantos agentes rodando?
- **Inicializacao** — sobe no boot? Sobrevive ao logout? (são checagens
  diferentes; ver abaixo)
- **Heartbeat** — explicado na próxima seção
- **PLATAFORMAS** — estado real por plataforma, com último erro quando houver

Em máquina sem systemd (macOS, container), o painel cai para a vivacidade do
pid registrado pelo próprio gateway e diz que a persistência no boot é
desconhecida — em vez de mentir "parado" para um gateway que está rodando.

---

## O caso mais traiçoeiro: heartbeat travado

O gateway reescreve o campo `updated_at` a cada 60 segundos. Isso o torna um
heartbeat.

Quando o processo está **vivo** mas esse carimbo passa de 120 segundos, o loop
de eventos congelou: o cron não dispara, a manutenção não roda, e mensagens
podem não ser processadas. O `systemctl` segue dizendo `active` — porque o
processo realmente existe. Nenhum estado de plataforma denuncia isso.

O `bots` mostra:

```
  Heartbeat     TRAVADO  sem carimbo ha 44101s (normal: 60s) — reinicie o gateway
```

Conserto: `hermes gateway restart`.

O Hermes também tem um cão de guarda próprio que, após 3 sondagens falhas,
marca `gateway_state: degraded` com `exit_reason: loop_liveness_watchdog` e sai
com código 75 para o supervisor reiniciar. O painel mostra esse estado também.

---

## O chip no app desktop

Instalando `desktop-plugins/bots-status/`, aparece um chip permanente na barra
de status: bolinha + resumo.

| Cor | Significa |
|---|---|
| 🟢 verde | Tudo conectado |
| 🟡 amarelo | Conectando, reconectando ou aguardando reinício |
| 🔴 vermelho | Parado, travado, degradado ou com erro |
| ⚪ cinza | Nenhuma plataforma configurada |

Atualiza a cada 10 s e **imediatamente** quando o gateway muda de estado (ele
emite o evento `platforms.changed`). Clicar abre a tela de Messaging.

Também instala um painel lateral chamado `bots` com o detalhamento, e uma
entrada no ⌘K ("Bots: abrir Messaging").

### Por que o chip não tem botão de parar

Porque **o chat do app desktop roda pelo mesmo gateway**. Um botão de parar ali
mataria a sua própria sessão no meio de uma conversa.

O Hermes bloqueia isso de propósito: um plugin consegue ler status e alterar
config, mas `systemctl restart` e `hermes gateway restart` são recusados pela
camada de aprovação. O reinício fica no botão nativo da tela Messaging, que o
app sabe tratar com reconexão.

---

## Ligar e desligar

### Pelo app (recomendado)

**Barra lateral → Messaging.** Por plataforma você tem:

- switch de liga/desliga
- badge de estado
- botão **Reiniciar gateway** (o switch só vale depois)
- aprovar/revogar quem pode usar o bot
- QR de criação do bot do Telegram

Também abre por ⌘K → "Open messaging". Não tem atalho de teclado de fábrica —
por isso tanta gente nunca acha essa tela.

### Pelo terminal

```bash
hermes config set platforms.telegram.enabled false
hermes gateway restart
```

A chave `platforms.<nome>.enabled: false` é o interruptor oficial e **vence a
credencial do `.env`**: você desliga sem apagar token nenhum. Até reiniciar, a
plataforma reporta `pending_restart`.

Nunca edite o `config.yaml` à mão — uma indentação errada corrompe o arquivo e
derruba o gateway que está rodando. Use `hermes config set`.

### Parar tudo

```bash
hermes gateway stop     # para o gateway inteiro (todas as plataformas)
hermes gateway start
hermes gateway status
```

---

## Boot e logout são duas checagens diferentes

Esta é a falha que faz um bot "funcionar" até o próximo reinício:

```bash
systemctl --user is-enabled hermes-gateway.service   # sobe no boot?
systemctl --user is-active  hermes-gateway.service   # está de pé agora?
loginctl show-user "$USER" -p Linger                 # sobrevive ao logout?
```

Um serviço pode estar `active` e `disabled` ao mesmo tempo — foi o app desktop
que o levantou. Parece tudo normal até você reiniciar a máquina, e aí o bot
morre calado.

```bash
systemctl --user enable hermes-gateway.service   # conserta o primeiro
loginctl enable-linger "$USER"                   # conserta o terceiro
```

`Linger=yes` **não** implica subir no boot. São coisas independentes.

---

**Próximo:** [5. Problemas comuns](05-problemas-comuns.md)
