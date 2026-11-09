# 2. Usar com um agente de IA

As ferramentas da camada 1 medem. A skill desta camada **interpreta**.

A diferença importa mais do que parece. O script devolve:

```
p5 espessura: 0.63 mm
```

A skill sabe o que fazer com isso:

> A asa a 75% fica com parede de ~0,63 mm. Seu bico é 0,4 mm, então precisa de
> no mínimo 0,8 mm para fechar duas linhas — nessa escala a asa vai sair
> furada. Suba para 85%, ou troque para o bico 0,2 só nessa placa. O autor
> avisa nos comentários que testou em 80%.

Esse tipo de resposta é conhecimento acumulado, não cálculo. É o que está
escrito no `SKILL.md`.

---

## Instalar

O formato é o **Agent Skills** da Anthropic, lido tanto pelo Claude Code quanto
pelo Hermes Agent.

```bash
# Claude Code
cp -r skill/impressao-3d ~/.claude/skills/

# Hermes Agent
cp -r skill/impressao-3d "${HERMES_HOME:-$HOME/.hermes}/skills/"
```

A skill referencia as ferramentas por caminho relativo (`ferramentas/...`).
Mantenha o repositório clonado em algum lugar estável e diga ao agente onde
ele está, ou ajuste os caminhos no `SKILL.md`.

### Configure a sua impressora

O `SKILL.md` vem com os valores de uma **Bambu A1**:

```
Mesa:   256 x 256 x 256 mm
Bico:   0,4 mm
Cores:  4 slots (AMS) + 1 bobina externa
```

Edite o bloco no topo do arquivo para a sua máquina. Se a sua mesa é menor, o
agente vai avisar de peças que não caberiam — e esse é metade do valor.

---

## O que perguntar

Depois de instalada, a conversa é normal:

> *"analisa esse 3mf a 75% e diz se vale a pena"*

> *"por que a asa desse modelo sai furada quando eu reduzo?"*

> *"as peças desse modelo cortado vão encaixar ou vai abrir fenda?"*

> *"quantas cores esse modelo pede? dá pra fazer com 4 slots?"*

> *"em que ordem eu imprimo pra perder menos filamento se der errado?"*

A última é subestimada: num modelo de 14 placas, começar pela asa (a peça mais
arriscada) custa 2 horas descobrir o problema. Começar pelo corpo custa 9.

---

## O formato da resposta

A skill instrui o agente a devolver um panorama em ordem fixa, não só números:

1. **Veredito** — chance de dar certo e onde está o risco
2. **Por que é seguro ou arriscado** — modelo dividido em placas significa
   falha barata; relatos de quem imprimiu na mesma escala valem muito
3. **Cores versus os slots que você tem**
4. **Tabela de risco por peça** (baixo/médio/alto, com motivo)
5. **O que a redução de escala estraga e o que protege**
6. **Custos** — filamento (+15-30% de suporte e purga) e tempo
7. **Ordem de impressão**
8. **O que NÃO se sabe** — explicitamente

O item 8 é o que mais evita decisão errada. Altura montada, tempo real e peso
real **não saem do arquivo** — o 3MF não guarda a pose de montagem, e gramas
só existem se o arquivo foi salvo já fatiado. A skill manda dizer isso em vez
de chutar.

---

## O que a skill sabe e a documentação não conta

- **Fatiar pela linha de comando** para obter tempo e peso reais, incluindo
  como trocar a impressora do perfil sem corromper o 3MF.
- **A API do MakerWorld responde a `curl`** mesmo com a página bloqueada por
  Cloudflare — e quais endpoints trazem as avaliações com texto, que é onde
  está a informação útil ("escalei 75% e deu 20 cm").
- **A armadilha das chaves por filamento**: por que um 3MF editado pode ser
  recusado pelo Studio com a geometria idêntica byte a byte.
- **Como detectar pino de encaixe quebrado** antes de imprimir 9 horas de peça.
- **Quando parar de insistir**: Printables e MakerWorld bloqueiam browser
  automatizado; depois de 2 tentativas, a skill manda pedir o arquivo em vez de
  ficar lutando com captcha.

---

## Limites honestos

A skill não substitui o slicer e não finge que substitui:

- **Espessura de parede é indicador**, não medida. Compara peças entre si.
- **Gramas superestimam corpos ocos** — a estimativa é ~35% do volume sólido da
  malha, e uma casca fina grande pesa muito menos.
- **Tempo real só o slicer dá.**
- **Altura montada** quase nunca está no arquivo; vem dos comentários.

Os números de folga (0,15 mm) e de parede mínima (0,8 mm) vêm de **uma**
impressora com **um** filamento. Imprima o teste de folga antes de confiar.

---

**Próximo:** [3. Bot de Telegram do zero](03-bot-telegram-do-zero.md)
