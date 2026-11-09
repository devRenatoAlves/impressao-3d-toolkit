# 1. Ferramentas de linha de comando

Todas rodam direto, sem Hermes, sem bot, sem agente de IA. A principal não
precisa nem de `pip install`.

Requisito mínimo: **Python 3.9+**.

---

## `analisar3d.py`

Lê um `.3mf` (Bambu Studio, Orca, MakerWorld) ou um `.stl` **binário** e diz o
que o arquivo realmente tem.

```bash
python3 ferramentas/analisar3d.py ARQUIVO [opções]
```

| Opção | Padrão | O que faz |
|---|---|---|
| `--escala N` | `100` | Aplica escala em %, e mede tudo já escalado |
| `--mesa LxPxA` | `256x256x250` | Volume da sua mesa, em mm. Avisa o que não cabe |
| `--parede-min N` | `1.2` | Parede mínima aceitável, em mm |
| `--espessura` | desligado | Mede espessura de parede (precisa de numpy/trimesh) |
| `--amostras N` | `1500` | Amostras da medida de espessura |
| `--limite-mb N` | `120` | Acima disso, usa o modo baixa memória. `0` desliga |

### Em um STL

```console
$ python3 ferramentas/analisar3d.py pino_cauda.stl

# Relatorio 3D: pino_cauda.stl

Escala 100%: 8.7 x 7.5 x 3.3 mm, 0.2 cm3, 24 triangulos
```

STL **ASCII não é suportado** — o script avisa e pede para converter. Qualquer
slicer salva em binário.

### Em um 3MF

Aqui o relatório é muito maior, porque o 3MF carrega a configuração do autor:

- perfil usado (impressora, altura de camada, paredes, infill, suporte)
- cores e qual slot de AMS cada peça usa
- peças por placa, com nomes traduzidos do chinês
- estimativa de gramas por cor
- tempo e peso **reais**, se o arquivo tiver sido salvo já fatiado

### Modo baixa memória (automático)

Um 3MF de MakerWorld com milhões de triângulos, lido de uma vez, aloca
gigabytes e o processo é **morto pelo OOM killer** — você vê o terminal
encerrar sem mensagem nenhuma e acha que o programa é quebrado.

O script mede o tamanho da malha pelo índice do zip (sem ler conteúdo) e, acima
de 120 MB, troca para um parser incremental com memória constante:

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
  obj 69      287.2 x  184.0 x  148.6 mm    844784 tri  <-- NAO CABE NA MESA
```

O que você perde nesse modo: volume, gramas e espessura — as três coisas que
exigem a malha inteira na memória. Dimensões e contagem continuam exatas.

### `--espessura`: achar a parede que vai virar buraco

A pergunta "reduzi para 70% e deu buraco, por quê?" se responde aqui.

Com bico de 0,4 mm, uma parede precisa de **pelo menos 2 linhas, ~0,8 mm**.
Abaixo disso o slicer não tem onde colocar material e deixa o vão aberto.
Reduzir a escala reduz a parede na mesma proporção — uma asa de 1,1 mm a 100%
vira 0,77 mm a 70% e some.

```bash
pip install numpy trimesh rtree
python3 ferramentas/analisar3d.py modelo.3mf --escala 75 --espessura --amostras 800
```

Leva cerca de 1 minuto com 800 amostras.

> **Leia como comparação, não como medição.** Serve para dizer "entre estas 14
> peças, a asa é a pior". Não serve para afirmar "a asa tem 0,63 mm".
>
> Valores perto de zero em olhos, línguas e barrigas são quase sempre
> artefato: casca fina ou faces coincidentes confundem o lançamento de raios.
> Confirme no slicer, na pré-visualização por camadas.

---

## `gerar_pinos_encaixe.py`

Resolve um problema específico e difícil de perceber.

Quando alguém corta um modelo grande em peças usando os **conectores** do Bambu
Studio, o arquivo fica com cavidades hexagonais nas duas metades e pinos soltos
para imprimir. Se o autor depois **reescala o projeto**, as cavidades
acompanham, mas os pinos encolhem junto e viram nada. Já medi pinos de
**0,58 × 0,67 × 0,34 mm** para cavidades de **10,9 × 12,7 × 4,3 mm**.

Resultado: duas faces planas com buracos vazios. Você cola, parece que
encaixou, e a peça escorrega enquanto a cola seca, desalinhando e abrindo
fenda.

```bash
pip install numpy trimesh shapely
python3 ferramentas/gerar_pinos_encaixe.py modelo.3mf saida/
```

O script mede a cavidade **real** da malha e gera o pino correspondente com
folga de 0,15 mm por lado e 0,3 mm no comprimento.

Gera também **dois arquivos de teste** que imprimem juntos em ~45 minutos:

1. **Gabarito** — bloco fino com as cavidades verdadeiras subtraídas da malha
   original, fundo de 1,6 mm, cavidade aberta no topo.
2. **Escada de folgas** — o mesmo pino em 0,10 / 0,15 / 0,20 mm.

> **Como escolher a folga:** o pino certo **entra com pressão do dedo e não cai
> quando você vira de cabeça para baixo**. Se precisou de martelo, a folga é
> pequena. Se caiu sozinho, é grande.

Fatie os testes em 0,20 mm (não 0,12) ou o teste leva mais de meia hora.

Detalhe que confunde: o STL "todos os pinos" é uma **placa de peças soltas**
para imprimir, não uma montagem. Abrir no slicer e ver pinos espalhados é o
esperado.

---

## `gerar_relevo_foto.py`

Converte uma imagem em placa ou chaveiro com relevo, separando as cores em
STLs distintos para impressão multicolorida.

```bash
pip install numpy Pillow scipy trimesh
python3 ferramentas/gerar_relevo_foto.py imagem.png saida/ --altura 3
```

Funciona melhor com logo e arte de traço, que têm cores chapadas. Foto comum
precisa de recorte e correção de perspectiva antes — o `--help` mostra as
opções.

---

## `preparar_3mf.py`

Edita um 3MF do Bambu Studio sem abrir o slicer: reescala preservando a posição
na placa, grava ajustes por objeto e **remove filamentos que você não tem**,
remapeando os slots.

Pela linha de comando:

```bash
python3 ferramentas/preparar_3mf.py CORPO.3mf ASAS.3mf saida/ 0.75
```

Como biblioteca, para qualquer 3MF:

```python
import sys; sys.path.insert(0, 'ferramentas')
import preparar_3mf as P

# Manter só os filamentos 1 e 5, renomeando as cores. f=1.0 = sem reescalar.
P.build(origem, destino, 1.0, {}, keep=(1, 5), cores=('#FFFFFF', '#000000'))
```

Útil quando o modelo pede 5 cores e seu AMS tem 4: você consolida, e pinta à
mão as peças pequenas da cor que sobrou.

> ⚠️ **Nunca passe `printer_model` ou `printer_settings_id`** em `global_edits`.
> O Studio responde "Invalid configuration file" e recusa o arquivo inteiro,
> porque dezenas de outras chaves (gcode de início e fim, troca de filamento,
> perfis compatíveis) são específicas da impressora original e não são
> atualizadas junto. Para trocar de impressora, abra o arquivo e use o seletor
> do Studio.

Outra armadilha, caso você vá mexer no código: várias chaves do
`project_settings.config` guardam **grupos de 2 a 4 valores por filamento**, não
um valor por filamento. Uma poda que assuma um valor por cor deixa a lista com
tamanho errado e o Studio rejeita tudo — mesmo com a geometria idêntica,
byte a byte. O script já trata isso.

---

## Tempo e peso reais: fatiar pela linha de comando

Nenhum script aqui substitui o slicer para estimar tempo e gramas. Mas o
AppImage do Bambu Studio tem CLI, então dá para automatizar.

Extraia os perfis uma vez:

```bash
./BambuStudio.AppImage --appimage-extract
P=squashfs-root/resources/profiles/BBL
```

As pastas são `machine` e `process` — não `machine_full`/`process_full`. O aviso
`can not find system preset file .../machine_full/...` no log é normal e
inofensivo.

Fatie **uma placa por vez** para não estourar a memória (`--slice 0` fatia
todas):

```bash
./BambuStudio.AppImage --debug 1 --slice 1 --no-check \
  --load-settings "$P/machine/Bambu Lab A1 0.4 nozzle.json;$P/process/0.12mm Fine @BBL A1.json" \
  --outputdir saida/ modelo.3mf
```

Isso troca a impressora de verdade, sem editar o 3MF — resolve o caso do modelo
feito para X1 que você quer na A1.

Leia `saida/result.json`:

| Campo | O que é |
|---|---|
| `sliced_plates[0].total_predication` | tempo, em segundos |
| `filaments[].total_used_g` | gramas por filamento |
| `warning_message` | avisos do slicer |
| `objects[].name/bbox/triangle_count` | por objeto |

Custo típico: 10-40 s e até 2,5 GB de pico por placa.

Cuidado: `filaments[].id` no `result.json` **não** é o slot de cor. A cor real
está no gcode, nas linhas `; filament:` e `; filament_colour`.

---

**Próximo:** [2. Usar com um agente de IA](02-skill-no-agente.md)
