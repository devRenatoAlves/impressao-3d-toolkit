# 1. Bot do Telegram do zero

Do nada até conversar com seu agente pelo celular. Uns 10 minutos.

> **Antes de começar, entenda o risco.** Esse bot não é um chatbot de
> perguntas e respostas: ele tem acesso ao terminal, aos arquivos e ao
> navegador da máquina onde o Hermes roda. Quem conseguir falar com ele
> consegue rodar comando no seu computador. A allowlist do passo 4 não é
> opcional.

---

## Caminho rápido (QR)

Se você já usa o app desktop ou o dashboard web, pule tudo:

1. **Messaging → Telegram → Create with QR**
2. Escaneie o código (ou abra o link) no Telegram
3. Pronto

O Hermes cria o bot no @BotFather por você, detecta seu ID de usuário, grava
`TELEGRAM_BOT_TOKEN` e `TELEGRAM_ALLOWED_USERS` no `.env` do perfil e reinicia
o gateway.

O resto deste documento é o caminho manual — vale ler mesmo usando o QR,
porque os passos 5 a 8 (privacidade em grupo, indicador online, fila de
mensagens) o QR não cobre.

---

## Caminho manual

### Passo 1 — Criar o bot no @BotFather

O @BotFather é o bot oficial do Telegram que cria outros bots.

1. No Telegram, procure **@BotFather** (ou abra [t.me/BotFather](https://t.me/BotFather))
2. Envie `/newbot`
3. **Nome de exibição**: qualquer coisa, ex. `Meu Agente`
4. **Username**: tem que ser único e terminar em `bot`, ex. `meu_agente_bot`
5. Ele responde com o token, no formato:

```
123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
```

> ⚠️ **Esse token é a senha do bot.** Quem tem ele controla o bot. Não cole em
> chat, issue, commit nem vídeo. Se vazar: `/revoke` no @BotFather na hora.

### Passo 2 — Descobrir o seu ID de usuário

Você precisa do **seu** ID numérico para a allowlist. Fale com
[@userinfobot](https://t.me/userinfobot) — ele responde seu ID, algo como
`123456789`.

### Passo 3 — Conectar ao Hermes

O jeito recomendado é o assistente, que grava as credenciais no lugar certo:

```bash
hermes gateway setup
```

Escolha Telegram, cole o token e o seu ID quando pedir.

Preferindo editar à mão, as credenciais vão no **`.env`** — nunca no
`config.yaml`:

```bash
# ${HERMES_HOME:-$HOME/.hermes}/.env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ   # audit-leaks: ok
TELEGRAM_ALLOWED_USERS=123456789
```

### Passo 4 — Confirmar que a allowlist pegou

Sem isso, qualquer pessoa que descobrir o username do bot tem um shell na sua
máquina.

```bash
bots            # deve mostrar: telegram ✓ conectado
```

Teste real: peça para alguém mandar `/help` ao bot. Deve ser recusado.

### Passo 5 — Fazer o bot subir sozinho no boot

Esta é a pegadinha que faz um bot "funcionar" e morrer no próximo reinício.
São **dois** ajustes diferentes:

```bash
hermes gateway install                      # cria o serviço

systemctl --user enable hermes-gateway      # Linux: subir no boot
loginctl enable-linger "$USER"              # Linux: sobreviver ao logout
```

Confira os dois separadamente — `active` não implica `enabled`:

```bash
systemctl --user is-enabled hermes-gateway.service   # quer: enabled
systemctl --user is-active  hermes-gateway.service   # quer: active
```

No Linux também existe o serviço de sistema, que sobe antes do login:

```bash
sudo hermes gateway install --system
```

O `bots` mostra os dois estados na linha `Inicializacao`.

---

## Ajustes que valem a pena

### Indicador de online

O Telegram **não** tem bolinha de online para bots — aquilo é recurso de conta
de pessoa. O mais próximo é a *descrição curta* do bot, que o Hermes pode
escrever automaticamente:

```yaml
# config.yaml
gateway:
  platforms:
    telegram:
      extra:
        status_indicator: true
        status_online: "🟢 Online"
        status_offline: "🔴 Offline"
```

Limites honestos: a descrição é **global** (todos veem, não é por conversa), e
só um desligamento *limpo* escreve "Offline" — se o processo morrer de queda
dura, fica marcado Online. Desligado por padrão, porque mexe no perfil público
do bot.

### Não perder mensagens quando o PC fica desligado

Por padrão o Hermes **descarta** as mensagens que chegaram enquanto o gateway
estava fora. Isso faz sentido em servidor sempre ligado; em desktop que você
desliga à noite, significa perder o que te mandaram — silenciosamente, sem log.

```yaml
# config.yaml
platforms:
  telegram:
    extra:
      drop_pending_on_cold_boot: false
```

Com `false`, a fila é entregue em ordem no próximo boot. Reconexões curtas de
rede nunca perdem a fila, independente dessa chave.

### Usar em grupo

Bots do Telegram têm **modo privacidade ligado por padrão**: dentro de um
grupo, o bot só vê mensagens que começam com `/`, respostas diretas às
mensagens dele e mensagens de serviço.

Para ele ver tudo: @BotFather → `/mybots` → seu bot → **Bot Settings → Group
Privacy → Turn off**.

> ⚠️ **Você precisa remover e re-adicionar o bot ao grupo** depois de mudar
> isso. O Telegram guarda o estado de privacidade de quando o bot entrou e não
> atualiza sozinho.

Alternativa sem mexer na configuração global: promova o bot a **administrador**
do grupo. Bot admin recebe tudo, sempre.

### Menu de comandos e busca inline

O Hermes registra o menu `/` sozinho, com teto de 60 comandos (o Telegram
aceita 100, mas payload grande falha). Se você tem muitas skills, elas podem
não caber:

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

O menu é limitado, mas o **modo inline** não. Ative com `/setinline` no
@BotFather e digite `@seu_bot pdf` em qualquer conversa para buscar entre
todos os comandos e skills, sem teto. Só funciona para quem passa na
allowlist — estranhos recebem lista vazia.

### Deixar o bot mais apresentável

No @BotFather: `/setdescription` (texto antes de iniciar a conversa),
`/setabouttext` (perfil), `/setuserpic` (avatar).

---

## Comandos úteis dentro do chat

| Comando | O que faz |
|---|---|
| `/new` | Começa conversa nova (limpa o contexto) |
| `/status` | Info da sessão atual |
| `/stop` | Para o agente no meio de uma tarefa |
| `/model` | Mostra ou troca o modelo |
| `/approve` / `/deny` | Aprova ou nega um comando perigoso pendente |
| `/sethome` | Marca esta conversa como canal padrão para avisos |
| `/usage` | Consumo de tokens da sessão |
| `/help` | Lista tudo |

---

**Próximo:** [4. Status e liga/desliga do bot](04-status-do-bot.md)
