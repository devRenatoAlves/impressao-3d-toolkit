# impressao-3d-toolkit

**Descobrir se um modelo 3D vai imprimir bem — antes de gastar filamento.**

Você baixa um STL bonito do MakerWorld, manda imprimir, e 9 horas depois tem
uma peça com buraco na asa e encaixe que não encaixa. Este repositório é o
conjunto de ferramentas que eu uso para saber disso **antes**.

Funciona em três camadas, e cada uma serve sozinha:

| Camada | Para quem | Precisa de |
|---|---|---|
| **1. Ferramentas de linha de comando** | qualquer pessoa com impressora 3D | Python 3.9+ |
| **2. Skill de agente de IA** | quem usa Claude Code ou Hermes Agent | a camada 1 |
| **3. Bot de Telegram** | quem quer mandar o arquivo pelo celular | Hermes Agent |

Se você só quer a ferramenta, **a camada 1 basta e não tem dependência
nenhuma.**

---

## Camada 1 — As ferramentas

```bash
git clone https://github.com/devRenatoAlves/impressao-3d-toolkit.git
cd impressao-3d-toolkit

python3 ferramentas/analisar3d.py meu_modelo.stl
```

Sem `pip install`, sem venv. O analisador usa só a biblioteca padrão do Python.

### `analisar3d.py` — o que o arquivo realmente tem

```console
$ python3 ferramentas/analisar3d.py pino_cauda.stl

# Relatorio 3D: pino_cauda.stl

Escala 100%: 8.7 x 7.5 x 3.3 mm, 0.2 cm3, 24 triangulos
```

Num 3MF do Bambu Studio ele lê muito mais: perfil do autor, altura de camada,
paredes, infill, suporte, cores por slot de AMS, peças por placa, nomes
traduzidos do chinês e estimativa de gramas.

**Arquivo grande não quebra.** Modelos de MakerWorld passam de 150 MB e, lidos
de uma vez, estouram a RAM — o processo morre sem imprimir nada. Acima de
120 MB de malha o script troca sozinho para um modo de streaming com memória
constante:

```console
$ python3 ferramentas/analisar3d.py Dragonite+20cm.3mf

# Relatorio 3D (modo baixa memoria): Dragonite+20cm.3mf

O arquivo tem ~915 MB de malha descomprimida, acima do limite de 120 MB.
Medindo por streaming: dimensoes e contagem de triangulos.
Volume, gramas e espessura de parede exigem a malha inteira e ficam de fora.

Total: 48 objetos, 9551024 triangulos

Maiores objetos (escala 100%):
  obj 67      183.2 x  360.6 x  179.0 mm   1181322 tri  <-- NAO CABE NA MESA
  obj 61      187.6 x  200.5 x  325.5 mm    544406 tri  <-- NAO CABE NA MESA
```

Opções: `--escala 75`, `--mesa 256x256x256`, `--parede-min 1.2`,
`--limite-mb 120`.

### `analisar3d.py --espessura` — achar a parede que vai virar buraco

Esta é a resposta para "reduzi para 70% e deu buraco". Com bico de 0,4 mm, uma
parede precisa de **2 linhas (~0,8 mm)**; abaixo disso o slicer simplesmente
não imprime nada ali.

```bash
pip install numpy trimesh rtree
python3 ferramentas/analisar3d.py modelo.3mf --escala 75 --espessura --amostras 800
```

Leia como **comparação entre peças**, não como medida absoluta — serve para
dizer "a asa é a pior parte", não "a asa tem exatamente 0,63 mm".

### `gerar_pinos_encaixe.py` — quando o pino do modelo está quebrado

Um problema comum e invisível: o autor cortou o modelo com os conectores do
Bambu Studio e depois reescalou o projeto. As **cavidades** continuam lá, mas
os **pinos** viraram poeira — já encontrei pinos de 0,58 mm para cavidades de
10,9 mm. Você cola, parece encaixar, e a peça escorrega e abre fenda.

```bash
python3 ferramentas/gerar_pinos_encaixe.py modelo.3mf saida/
```

Gera o pino medindo a cavidade real, com folga de 0,15 mm por lado. Gera
também dois arquivos de teste que imprimem em ~45 min: um gabarito com as
cavidades verdadeiras e uma escada de folgas (0,10 / 0,15 / 0,20 mm).

> **Critério de folga certa:** entra com pressão do dedo e não cai de cabeça
> para baixo. Precisou de martelo, folga pequena. Caiu sozinho, folga grande.

### `gerar_relevo_foto.py` — foto ou logo em relevo

Transforma uma imagem em placa/chaveiro com relevo, separando por cor para
impressão multicolorida.

```bash
pip install numpy Pillow scipy trimesh
python3 ferramentas/gerar_relevo_foto.py logo.png saida/ --altura 3
```

### `preparar_3mf.py` — reescalar e reduzir cores sem abrir o slicer

Reescala preservando a posição na placa, grava ajustes por objeto e remove
filamentos que você não tem (remapeando os slots corretamente).

```python
import preparar_3mf as P
P.build(origem, destino, 1.0, {}, keep=(1, 5), cores=('#FFFFFF', '#000000'))
```

> ⚠️ Nunca troque `printer_model` por edição de texto no 3MF. O Studio rejeita
> o arquivo inteiro, porque dezenas de outras chaves são gcode específico da
> impressora original. Troque de impressora pela interface do Studio.

---

## Camada 2 — A skill

Se você usa um agente de IA com suporte a Agent Skills (**Claude Code** ou
**Hermes Agent**), a pasta `skill/` ensina o agente a usar as ferramentas acima
**e a interpretar o resultado**.

A diferença é essa última parte. O script diz "p5 = 0,63 mm". A skill sabe que
isso significa "a asa vai sair furada nessa escala, suba para 80% ou troque
para bico 0,2".

```bash
# Claude Code
cp -r skill/impressao-3d ~/.claude/skills/

# Hermes Agent
cp -r skill/impressao-3d "${HERMES_HOME:-$HOME/.hermes}/skills/"
```

Depois você conversa normalmente:

> *"analisa esse 3mf a 75% e me diz se vale imprimir"*

A skill traz também o que a documentação não conta: como fatiar pela linha de
comando para obter tempo e peso **reais**, por que a API do MakerWorld funciona
mas a página bloqueia, e a armadilha das chaves "por filamento" que fazem o
Studio recusar um 3MF editado.

**Ajuste a sua impressora** no topo do `SKILL.md` — mesa, bico e número de
cores vêm configurados para uma Bambu A1.

---

## Camada 3 — O bot de Telegram

Com o [Hermes Agent](https://github.com/NousResearch/hermes-agent), o mesmo
agente atende no Telegram. Você fotografa, manda o arquivo pelo celular e
recebe o laudo — útil quando o modelo está no PC e você está na frente da
impressora.

Esta camada só existe porque surgiu um problema prático: **o bot cai e nada
avisa.** O Telegram não mostra bot offline; a conversa só fica muda. Então
`bot-telegram/` traz as ferramentas de visibilidade:

- `bin/status-bots.py` — um comando que responde "está no ar?", incluindo
  detecção de gateway vivo mas com o loop travado
- `desktop-plugins/bots-status/` — bolinha permanente na barra de status do app
- `skill/hermes-messaging-bot-visibility/` — ensina o agente a diagnosticar isso

Guias: **[montar o bot do zero](docs/03-bot-telegram-do-zero.md)** ·
**[ver o status e ligar/desligar](docs/04-status-do-bot.md)** ·
**[problemas comuns](docs/05-problemas-comuns.md)**

> ⚠️ **O bot tem acesso ao seu computador** — terminal, arquivos, navegador.
> A allowlist (`TELEGRAM_ALLOWED_USERS`) não é opcional. Sem ela, qualquer
> pessoa que descobrir o nome do bot tem um shell na sua máquina.

---

## Documentação

| | |
|---|---|
| [01 — Ferramentas de linha de comando](docs/01-ferramentas-cli.md) | cada script, com exemplos |
| [02 — Usar com um agente de IA](docs/02-skill-no-agente.md) | instalar a skill, o que perguntar |
| [03 — Bot de Telegram do zero](docs/03-bot-telegram-do-zero.md) | BotFather, allowlist, boot |
| [04 — Status e liga/desliga do bot](docs/04-status-do-bot.md) | saber se está no ar |
| [05 — Problemas comuns](docs/05-problemas-comuns.md) | o bot calou, e agora |

---

## Antes de publicar um fork

`tools/audit-leaks.py` varre segredos e dados pessoais. Sai com código 2 e se
recusa a aprovar se achar token, chave de API, IP de rede interna ou e-mail.

```bash
python3 tools/audit-leaks.py --nome "Seu Nome"
```

---

## Avisos

Não sou afiliado à Bambu Lab, à Nous Research nem ao MakerWorld. As ferramentas
leem formatos de arquivo públicos (3MF é um padrão aberto) e não modificam nada
no lugar — sempre escrevem em um diretório de saída.

Os números de folga e espessura vêm da **minha** impressora e do meu filamento.
Trate como ponto de partida e imprima o teste de folga antes de confiar.

## Licença

MIT — veja [LICENSE](LICENSE).
