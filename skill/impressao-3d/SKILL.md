---
name: impressao-3d
description: "Use ao analisar um 3MF/STL antes de imprimir, ou ajustar encaixes."
version: 1.0.0
author: Renato Alves
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [impressao-3d, 3mf, stl, bambu, slicer, modelagem]
---

# Impressão 3D — analisar antes de gastar filamento

Para quando alguém manda um `.3mf`/`.stl` (ou um link do MakerWorld) e quer
saber **tamanho, risco de falha, cores e configuração antes de imprimir**. O
objetivo é evitar perder horas de máquina e rolos de filamento num modelo que
ia falhar de forma previsível.

## Quando usar

- Um arquivo 3D chegou e a pergunta é "isso vai imprimir bem?"
- "Reduzi para 70% e deu buraco na parede" / "as peças não encaixam"
- Dimensionar um modelo para uma mesa específica
- Decidir ordem de impressão para limitar prejuízo num modelo multi-peça

Não serve para: modelar do zero (isso é CAD/escultura), nem para operar a
impressora remotamente.

## Configure sua impressora aqui

Esta skill assume uma impressora genérica. **Ajuste estes valores** antes de
usar, ou informe-os no pedido:

```
Mesa:   256 x 256 x 256 mm      (Bambu A1; mude para a sua)
Bico:   0,4 mm                  (0,2 mm serve para peças minúsculas)
Cores:  4 slots (AMS) + 1 bobina externa
```

Com bico 0,4 mm, uma parede precisa de **pelo menos 2 linhas (~0,8 mm)** para
não virar buraco. Esse é o número que decide quase toda redução de escala.

## Fluxo

1. **Confirme o tamanho-alvo e a escala.** A altura montada quase nunca está
   no anúncio — costuma estar nos comentários ("escalei X% e deu Y cm").

2. **Rode o analisador:**

   ```bash
   python3 ferramentas/analisar3d.py ARQUIVO.3mf --escala 75 \
       --mesa 256x256x256 --parede-min 1.2
   ```

   STL binário também funciona (só geometria). STL ASCII não — converta.

   Arquivos grandes (acima de ~120 MB de malha) entram automaticamente no
   **modo baixa memória**: dimensões e contagem de triângulos por streaming,
   sem volume nem espessura. Sem isso o processo seria morto pelo OOM killer.
   `--limite-mb` ajusta o corte.

3. **Meça a espessura de parede** quando houver suspeita de parede fina:

   ```bash
   python3 ferramentas/analisar3d.py ARQUIVO.3mf --escala 75 --espessura --amostras 800
   ```

   Precisa de `numpy`, `trimesh` e `rtree`. Leva cerca de 1 minuto.

   **Leia como indicador, não como verdade.** Serve para comparar peças entre
   si ("a asa é a pior, p5 ~0,6 mm"), não como medida absoluta. Olhos, línguas
   e barrigas dão valores perto de zero por causa de cascas finas e faces
   coincidentes — confirme no slicer.

4. **Cruze com a página do modelo**, se houver: descrição do autor +
   comentários + avaliações. Procure por `cm`, `tall`, `scale`, `%`,
   `support`, `glue`.

5. **Entregue um panorama**, não só números — formato abaixo.

## Formato da resposta

Nesta ordem:

1. **Veredito curto** — chance de dar certo e onde está o risco
2. **Por que é seguro ou arriscado** — modelo dividido em placas significa
   falha barata; relatos de quem imprimiu na mesma escala valem muito
3. **Cores versus slots disponíveis**
4. **Tabela de risco por peça/placa** (baixo/médio/alto + motivo)
5. **O que a redução de escala estraga e o que protege**
6. **Custos** — filamento (+15-30% de suporte e purga) e tempo (só o slicer dá
   o número real)
7. **Ordem de impressão** para limitar prejuízo
8. **O que NÃO se sabe** — seja explícito sobre isso

## Reduzir risco

- **Imprima por placa**, das peças baratas para as caras: peças pequenas
  primeiro, UMA peça do par mais arriscado, depois as grandes. Encaixe a seco
  antes de colar.
- **Parede fina ao reduzir:** verifique a pré-visualização por camadas depois
  de escalar. Se houver buraco, suba a escala até a que o autor testou.
- **Suporte:** se o perfil do autor usa limite baixo (ex. 25°) e os
  comentários reclamam de falta de suporte, aumente a cobertura nas áreas em
  balanço — e **remova todo suporte dos encaixes**.
- **Peças minúsculas de cor rara:** imprima em branco e pinte com caneta
  acrílica. Pinte antes de colar, não pinte a área de cola, verniz fosco no
  fim. Isso economiza um slot de AMS inteiro.
- **Peso e tempo reais** só saem do slicer. O relatório dá um teto.

## Encaixes: cavidades sem pino

Antes de prometer montagem limpa, **sempre verifique**:

1. Em `model_settings.config`, liste as `part` com `subtype="negative_part"`
   (nomes tipo `Connector-N_A`/`_B`). Cavidade nos dois lados significa corte
   feito com os conectores do Studio.
2. **Meça os objetos soltos chamados `... connector`.** Se, depois da escala do
   projeto, derem décimos de milímetro, **o pino está quebrado**: o autor
   reescalou o modelo e os pinos viraram lixo. Já vi pinos de 0,58 × 0,67 ×
   0,34 mm para cavidades de 10,9 × 12,7 × 4,3 mm.

   Resultado prático: faces planas, duas cavidades vazias, zero alinhamento. A
   peça escorrega na cola e abre fenda.
3. **Gere os pinos a partir das próprias cavidades:**

   ```bash
   python3 ferramentas/gerar_pinos_encaixe.py ARQUIVO.3mf SAIDA_DIR
   ```

   Folga 0,15 mm por lado, 0,3 mm no comprimento. As cavidades do Studio são
   prismas hexagonais — confira a seção num plot antes de exportar.
4. As cavidades também servem de reservatório de cola. Sem pino, só cola de
   gel e fita crepe segurando até secar.
5. **Nunca mande "imprima o pino e teste"** quando o furo só existe numa peça
   grande que a pessoa ainda não imprimiu. Entregue **dois** arquivos de teste
   (~45 min no total):
   - **gabarito**: bloco fino com as cavidades REAIS subtraídas da malha
     original (não de uma aproximação, senão o teste é circular), 1,6 mm de
     fundo, cavidade aberta no topo
   - **escada de folgas**: o mesmo pino em 0,10 / 0,15 / 0,20 mm

   Critério a passar para a pessoa: **entra com pressão do dedo e não cai de
   cabeça para baixo = certo**. Precisa de martelo = folga pequena. Cai sozinho
   = folga grande. Fatie em 0.20 mm para o teste não passar de meia hora.
6. Um STL "todos os pinos" é uma **placa de peças soltas**, não uma montagem.
   Avise, ou a pessoa abre o arquivo e conclui que os pinos não encaixam.

## Fatiar pela linha de comando (tempo e peso REAIS)

O AppImage do Bambu Studio tem CLI headless. Extraia os perfis uma vez:

```bash
./BambuStudio.AppImage --appimage-extract
# perfis em squashfs-root/resources/profiles/BBL/{machine,process,filament}/*.json
```

As pastas são `machine` e `process` — **não** `machine_full`/`process_full`. O
aviso "can not find system preset file .../machine_full/..." no log é normal.

Fatie uma placa por vez para poupar RAM (`--slice 0` fatia todas):

```bash
./BambuStudio.AppImage --debug 1 --slice N --no-check \
  --load-settings "$P/machine/Bambu Lab A1 0.4 nozzle.json;$P/process/0.12mm Fine @BBL A1.json" \
  --outputdir DIR ARQUIVO.3mf
```

Isso troca a impressora de verdade sem editar o 3MF. Leia `DIR/result.json`:
`sliced_plates[0].total_predication` (segundos), `filaments[].total_used_g`,
`warning_message`, `objects[].name/bbox/triangle_count`.

Custo típico: 10-40 s e até 2,5 GB de pico por placa.

Para testar mitigações (brim maior, menos velocidade, suporte diferente) sem
mexer no 3MF: copie o json do process, acrescente as chaves mantendo o
`inherits`, e passe esse json no `--load-settings`. Isso vence os overrides por
objeto gravados no 3MF.

STL solto também fatia:

```bash
./BambuStudio.AppImage --arrange 1 --slice 0 \
  --load-filaments "$P/filament/Bambu PLA Matte @BBL A1.json" arquivo.stl
```

Sem filamento carregado o peso sai 0,00 g.

## O que o script lê de um 3MF

- `3D/3dmodel.model` + `3D/Objects/*.model` — malhas e transformações
- `Metadata/model_settings.config` — nome, extrusora (= slot de cor), placas
- `Metadata/project_settings.config` — cores, camada, paredes, infill, suporte
- `Metadata/slice_info.config` — tempo e gramas, **só se o 3MF vier fatiado**

## Pitfalls

- **Peças espalhadas nas placas:** o 3MF **não** guarda a pose de montagem, então
  a altura montada não sai do arquivo. Estime pela peça inteira não cortada, se
  houver, e confirme com os comentários.
- **Item de build sem placa** ("fora das placas") não é impresso — costuma ser a
  versão inteira sem cortes.
- **O script mede caixa envolvente**, não espessura real nem balanço. Sempre
  mande conferir a pré-visualização por camadas depois de escalar.
- **Escale uniformemente em TODAS as peças**, senão os encaixes não batem.
- **Gramas superestimam corpos ocos:** a estimativa é ~35% do volume sólido da
  malha, mas um corpo grande de casca fina pode pesar muito menos. Dê o número
  do autor como referência e o do script como teto.
- **Perfil do autor de outra impressora** (P1S/X1/P2S têm velocidades altas):
  troque para a sua impressora no Studio antes de fatiar.
- **NUNCA troque `printer_model`/`printer_settings_id` editando o texto do
  `project_settings.config`.** Dá "Invalid configuration file", porque dezenas
  de outras chaves (gcode de início/fim, troca de filamento, perfis
  compatíveis) são específicas da impressora original e não são atualizadas
  junto. Só a interface do Studio troca o pacote inteiro de forma consistente.
- **Chaves "por filamento" não são listas simples.** Várias
  (`filament_self_index`, `nozzle_temperature`, `filament_dev_ams_drying_*`)
  guardam **grupos de 2 a 4 valores por filamento**. Ao reduzir cores, uma poda
  que assuma um valor por filamento deixa a lista com tamanho desencontrado e o
  Studio rejeita o arquivo inteiro — mesmo com o zip e a geometria idênticos ao
  original. Pode listas cujo tamanho seja **múltiplo** do número de filamentos,
  preservando o agrupamento. Valide antes de entregar.
- **Depurando um 3MF editado que não abre:** gere primeiro uma cópia SEM
  nenhuma edição pelo mesmo caminho de código. Se ela abrir, o bug está nas
  edições, não no empacotamento; aí bissecte aplicando uma parte por vez.
  `zipfile.testzip()` e hash das malhas descartam corrupção de bytes, mas
  **não** provam consistência semântica do config.
- **MakerWorld e Printables bloqueiam browser automatizado** (Cloudflare), mesmo
  clicando no captcha. Não insista: peça o arquivo baixado à mão. A API REST do
  MakerWorld, porém, responde a `curl` simples com User-Agent de navegador:
  - modelo: `/api/v1/design-service/design/<designId>`
  - comentários: `/api/v1/comment-service/comment?designId=<id>&top=20`
    (só os 20 mais recentes; paginação é ignorada)
  - avaliações com texto: `/api/v1/comment-service/rating?designId=<id>&instanceId=<id>&top=50`

  Baixe com `curl -o arquivo.json` e use `json.load(..., strict=False)` — há
  caracteres de controle no texto dos usuários.
- **Nomes em chinês** são comuns: 身体 corpo, 左/右 esq/dir, 腿 perna, 手 mão,
  翅 asa, 头 cabeça, 肚皮 barriga, 尾 cauda, 舌头 língua, 眼 olho,
  组合体 conjunto de peças pequenas. Traduza ao responder.
- **Placas alternativas** (ex. duas versões de asa) não devem ser somadas:
  escolha uma.

## Peças funcionais e relevo de foto

- Peça que recebe força (abridor, gancho, suporte): ver
  `references/pecas-funcionais-mecanicas.md`.
- Chaveiro/placa a partir de foto ou logo, e pedestal sob modelo de terceiro:
  ver `references/relevo-fotografico-e-pedestais.md` (usa
  `ferramentas/gerar_relevo_foto.py`).
