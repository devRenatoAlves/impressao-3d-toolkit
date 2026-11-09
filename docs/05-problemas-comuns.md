# 3. Problemas comuns

## Ordem de diagnóstico

Rode isso primeiro. Responde 90% dos casos:

```bash
bots
```

Depois siga pela primeira linha que estiver errada.

---

## "O bot não responde nada"

### 1. O gateway está de pé?

```
Gateway       ● PARADO
```

```bash
hermes gateway start
```

Se ele não sobe, veja o motivo:

```bash
hermes gateway status
tail -50 "${HERMES_HOME:-$HOME/.hermes}/logs/gateway.log"
```

### 2. Está de pé mas travado?

```
Heartbeat     TRAVADO  sem carimbo ha 44101s (normal: 60s)
```

O processo existe, o `systemctl` diz `active`, e nada funciona. O loop de
eventos congelou.

```bash
hermes gateway restart
```

Para ver *o que* travou antes de reiniciar (não interrompe o processo):

```bash
kill -USR2 <pid do gateway>
tail -100 "${HERMES_HOME:-$HOME/.hermes}/logs/gateway_faulthandler.log"
```

### 3. A plataforma está desligada?

```
telegram     ○ desligado na config
```

Alguém (ou você) pôs `enabled: false`:

```bash
hermes config set platforms.telegram.enabled true
hermes gateway restart
```

### 4. Mudou a config e não reiniciou?

```
telegram     ⟳ aguardando reinicio do gateway
```

```bash
hermes gateway restart
```

### 5. Você está na allowlist?

Se o bot ignora **você** especificamente, mas o gateway está verde: seu ID não
está em `TELEGRAM_ALLOWED_USERS`. Confirme seu ID com
[@userinfobot](https://t.me/userinfobot) e compare.

Isso é recusa silenciosa de propósito — um bot que respondesse "você não tem
permissão" confirmaria a existência dele para qualquer um.

---

## "Funcionava ontem, hoje não"

Quase sempre: **a máquina reiniciou e o serviço não sobe no boot.**

```bash
systemctl --user is-enabled hermes-gateway.service
```

Se responder `disabled`:

```bash
systemctl --user enable hermes-gateway.service
loginctl enable-linger "$USER"
```

O serviço pode ter ficado `active` por meses porque o app desktop o levantava
toda vez que você abria o app. No primeiro boot sem abrir o app, morre.

---

## "Mandei mensagem de madrugada e ele nunca respondeu"

Comportamento esperado, e configurável. Por padrão o Hermes **descarta** a fila
acumulada enquanto estava offline:

```
[Telegram] Cold boot: dropping Telegram updates queued while offline
```

Faz sentido em servidor. Em desktop que você desliga à noite, não:

```yaml
# config.yaml
platforms:
  telegram:
    extra:
      drop_pending_on_cold_boot: false
```

---

## "Em grupo ele ignora tudo"

Modo privacidade do Telegram, **ligado por padrão**. Em grupo o bot só vê:

- mensagens começando com `/`
- respostas diretas a mensagens dele
- mensagens de serviço (entrou/saiu/fixou)

Conserto: @BotFather → `/mybots` → seu bot → **Bot Settings → Group Privacy →
Turn off**.

> **E então remova e re-adicione o bot ao grupo.** O Telegram guarda o estado
> de privacidade de quando o bot entrou. Sem isso, nada muda — é o passo que
> todo mundo esquece.

Alternativa: promover o bot a **admin** do grupo. Admin recebe tudo, sempre,
sem mexer na configuração global.

---

## "Reconecta sozinho toda hora"

```
[Telegram] Telegram network error (attempt 1/10), reconnecting in 5s
[Telegram] Connected to Telegram (polling mode)
```

Instabilidade de rede. Se ele reconecta, **não precisa fazer nada** — está
funcionando como projetado.

Preocupe-se se o estado ficar preso em `retrying` por muito tempo, ou se o
mesmo erro repetir em horário fixo (aí suspeite de DNS, proxy, ou o roteador
dormindo).

Atrás de proxy corporativo que atrapalha, há como ignorar o proxy herdado
(`gateway.trust_env`).

---

## "Faltam comandos no menu `/`"

```
[Telegram] Telegram menu: 60 commands registered, 73 hidden (over 60 limit)
```

O Telegram aceita 100, mas payloads grandes falham, então o Hermes limita a 60.
Priorize o que importa:

```yaml
platforms:
  telegram:
    extra:
      command_menu:
        max_commands: 60
        priority_mode: prepend
        priority:
          - minha_skill
```

Ou use `/commands` no chat para a lista completa, ou ative o **modo inline**
(`/setinline` no @BotFather), que não tem teto: `@seu_bot <busca>`.

---

## Avisos que você pode ignorar

```
platform 'teams' has no valid toolsets configured (unknown name(s): hermes-teams)
platform 'google_chat' has no valid toolsets configured
```

São plataformas que você não usa. Cosmético. Limpa com `hermes tools` se
incomodar.

```
[Telegram] Using sticky IPv4 Telegram API path 149.154.166.110
```

Normal: o adaptador prefere IPv4 por estabilidade.

---

## Onde ficam as coisas

```
$HERMES_HOME/
├── .env                      credenciais (NUNCA no git)
├── config.yaml               configuração (sem segredos)
├── gateway_state.json        estado ao vivo — a fonte de verdade
├── logs/
│   ├── gateway.log           log principal
│   ├── errors.log            só erros
│   └── gateway_faulthandler.log   stacks do kill -USR2
├── bin/status-bots.py        o painel
└── desktop-plugins/bots-status/   o chip
```

`HERMES_HOME` é `~/.hermes`, ou `~/.hermes/profiles/<nome>` se você usa perfis
(`hermes -p <nome>`). Perfis têm config, credenciais e estado separados — um
bot num perfil não aparece no status de outro.

---

## Quando nada disso resolveu

Instale a skill deste repositório e pergunte ao próprio agente:

```
meu bot do telegram está no ar?
```

Ela ensina o agente a cruzar credencial, `gateway_state.json`, estado do
serviço e log — e a não cair nas armadilhas acima.

```bash
cp -r skills/hermes-messaging-bot-visibility "${HERMES_HOME:-$HOME/.hermes}/skills/"
```
