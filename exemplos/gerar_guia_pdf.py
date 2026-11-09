#!/usr/bin/env python3
"""Gera o guia PDF do Mega Charizard X (A1 Combo, 75%). Requer reportlab (venv ~/.local/share/pdf-venv).
Uso: ~/.local/share/pdf-venv/bin/python gerar_guia_pdf.py SAIDA.pdf"""
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont('DV', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVB', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
pdfmetrics.registerFontFamily('DV', normal='DV', bold='DVB', italic='DV', boldItalic='DVB')

AZUL = colors.HexColor('#1F4E79'); LARANJA = colors.HexColor('#D9622B')
CINZA = colors.HexColor('#F2F4F7'); BORDA = colors.HexColor('#C8CED6')
VERDE = colors.HexColor('#E3F4E6'); AMAR = colors.HexColor('#FFF4D6'); VERM = colors.HexColor('#FBE1DD')

body = ParagraphStyle('b', fontName='DV', fontSize=9.2, leading=13.2, spaceAfter=4)
small = ParagraphStyle('s', parent=body, fontSize=8, leading=11)
cell = ParagraphStyle('c', parent=body, fontSize=8, leading=10.5, spaceAfter=0)
cellb = ParagraphStyle('cb', parent=cell, fontName='DVB', textColor=colors.white)
h1 = ParagraphStyle('h1', fontName='DVB', fontSize=15, leading=19, textColor=AZUL, spaceBefore=10, spaceAfter=6)
h2 = ParagraphStyle('h2', fontName='DVB', fontSize=11, leading=15, textColor=LARANJA, spaceBefore=8, spaceAfter=3)
title = ParagraphStyle('t', fontName='DVB', fontSize=26, leading=31, textColor=AZUL, spaceAfter=2)
sub = ParagraphStyle('sub', fontName='DV', fontSize=12, leading=16, textColor=colors.HexColor('#555555'), spaceAfter=10)
bul = ParagraphStyle('bul', parent=body, leftIndent=11, bulletIndent=1, spaceAfter=2)


def P(t, s=body): return Paragraph(t, s)
def H1(t): return Paragraph(t, h1)
def H2(t): return Paragraph(t, h2)
def B(items): return [Paragraph(i, bul, bulletText='•') for i in items]


def tabela(cab, linhas, larg, zebra=True, cor_cab=AZUL):
    dados = [[Paragraph(c, cellb) for c in cab]] + [[Paragraph(str(c), cell) for c in l] for l in linhas]
    t = Table(dados, colWidths=[w * mm for w in larg], repeatRows=1)
    st = [('BACKGROUND', (0, 0), (-1, 0), cor_cab), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('GRID', (0, 0), (-1, -1), 0.4, BORDA), ('LEFTPADDING', (0, 0), (-1, -1), 4),
          ('RIGHTPADDING', (0, 0), (-1, -1), 4), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    if zebra:
        for i in range(1, len(dados)):
            if i % 2 == 0: st.append(('BACKGROUND', (0, i), (-1, i), CINZA))
    t.setStyle(TableStyle(st))
    return t


def caixa(texto, cor=AMAR, titulo=None):
    conteudo = [Paragraph(('<b>%s</b><br/>' % titulo if titulo else '') + texto, cell)]
    t = Table([conteudo], colWidths=[174 * mm])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), cor), ('BOX', (0, 0), (-1, -1), 0.6, BORDA),
                           ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                           ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    return t


def rodape(c, d):
    c.saveState(); c.setFont('DV', 7.5); c.setFillColor(colors.HexColor('#777777'))
    c.drawString(18 * mm, 10 * mm, 'Mega Charizard X · Guia de impressão · Bambu Lab A1 Combo · escala 75%')
    c.drawRightString(192 * mm, 10 * mm, 'Pág. %d' % d.page); c.restoreState()


def main(saida):
    doc = SimpleDocTemplate(saida, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=17 * mm, title='Guia de impressão - Mega Charizard X (A1 Combo)',
                            author='Hermes')
    S = []
    # ---------- Capa / resumo
    S += [P('Mega Charizard X', title), P('Guia de impressão e montagem · Bambu Lab A1 Combo · ~20 cm de altura', sub)]
    S.append(caixa('Modelo de <b>multicolor por peças coladas</b> (MakerWorld 1461745). Os 3MF originais foram analisados e '
                   'preparados para a sua A1 Combo (AMS lite, bicos 0,4 e 0,2). Este guia diz <b>o que imprimir, em que ordem, '
                   'com quais ajustes</b> e como montar. Onde algo não pôde ser verificado, está marcado como <b>não verificado</b>.',
                   VERDE, 'Resumo'))
    S.append(Spacer(1, 6))
    S.append(tabela(['Item', 'Valor'], [
        ['Escala', '<b>75%</b> uniforme, aplicada nos arquivos entregues → ~20 cm de altura × ~30 cm de largura (valor dos comentários da comunidade; o 3MF não guarda a pose montada). Se as asas saírem com furos, suba para 80% (~21,6 cm).'],
        ['Impressora', 'Bambu Lab A1 Combo, mesa 256 × 256 × 256 mm, AMS lite (4 slots). Bicos: 0,4 e 0,2.'],
        ['Arquivos', '<b>01_Corpo_A1_75.3mf</b> (10 placas, 3 cores) + <b>02_Asas_A1_75.3mf</b> (2 placas, 2 cores). As asas de 5 peças do arquivo 01 foram desativadas, porque a versão com suporte reforçado vem do arquivo 02.'],
        ['Cores (4)', 'Preto, azul-claro #56B7E6, azul #0080FF, branco. Língua e olhos são impressos em <b>branco</b> e pintados depois.'],
        ['Filamento', 'Estimativa sem suporte: ~190 g preto, ~45 g azul-claro, ~19 g azul, ~3 g branco ≈ <b>255 g</b>. Com suporte e purga: <b>~300 a 330 g</b>.'],
        ['Tempo', '<b>Não verificado.</b> O autor informa 36,2 h a 100% na X1. Só o fatiador dá o tempo real a 75%.'],
        ['Colagem', 'Super Bonder (gel). O modelo não se monta sem cola.'],
    ], [32, 142]))
    S.append(Spacer(1, 6))
    S.append(H1('1. Antes de começar'))
    S.append(H2('Material necessário'))
    S += B(['PLA preto (~200 g), azul-claro, azul, branco. Mesma marca/lote em cada cor evita diferença de tom entre peças coladas.',
            'Super Bonder gel (a versão líquida escorre nas juntas), ativador/spray opcional.',
            'Lixa 220 a 600, estilete, alicate de corte, pinça, palito de dente para aplicar cola.',
            'Tinta acrílica ou caneta acrílica (vermelho, preto, e branco para retoque) e pincel fino; verniz acrílico fosco.',
            'Fita de pintor, luvas, e uma bancada com luz boa para o ajuste a seco.'])
    S.append(H2('Abrir os arquivos no Bambu Studio'))
    S += B(['Abra o 01 e confira: impressora <b>Bambu Lab A1 0.4 nozzle</b>, mesa <b>Textured PEI</b> (ou a que você usa), filamentos mapeados nos slots do AMS lite.',
            'O projeto traz 5 filamentos; o vermelho (slot 2) <b>não é mais usado</b>. Se o Studio reclamar de 5 cores, apague o filamento vermelho: nada usa ele.',
            'No 01 são usados: preto, branco, azul-claro. No 02: preto e azul. Troque as bobinas do AMS entre os dois arquivos, ou deixe as 4 cores montadas e só mapeie.',
            'Confirme visualmente a escala: o corpo montado deve dar cerca de 20 cm de altura (a maior peça solta, o corpo B, tem ~12 cm).',
            '<b>Atenção:</b> não abri os arquivos no Bambu Studio (não rodo o Studio aqui). Eu conferi XML, dimensões e ajustes por script. Fatie cada placa e olhe a pré-visualização por camadas antes de imprimir.'])

    # ---------- Ordem
    S.append(H1('2. Ordem de impressão (menor para maior prejuízo)'))
    S.append(P('Cada placa é independente. Imprimir as peças baratas primeiro testa filamento, escala e encaixe antes das horas longas. '
               'As placas abaixo usam os números do arquivo indicado.'))
    S.append(tabela(['#', 'Arquivo · placa', 'Conteúdo', 'Cor', 'Risco', 'Observação'], [
        ['1', '01 · placa 7', 'Língua', 'Branco', 'Baixo', 'Teste de escala e fluxo. Será pintada de vermelho.'],
        ['2', '01 · placa 6', 'Olhos (esq. e dir.)', 'Branco', 'Baixo', 'Pintar depois. Peça minúscula: cuidado ao remover da mesa.'],
        ['3', '01 · placa 2', 'Dentes e unhas', 'Branco', 'Baixo', 'Números 1 = esquerda/em cima, 2 = direita/embaixo. Marque as peças ao tirar.'],
        ['4', '<b>02 · placa 1</b>', '<b>Asas pretas (teste de risco)</b>', 'Preto', '<b>Alto</b>', 'Imprima <b>uma peça</b> antes do resto. Ver seção 4.'],
        ['5', '02 · placa 2', 'Asas azuis', 'Azul', 'Alto', 'Se a placa 1 saiu sem furos, siga.'],
        ['6', '01 · placa 1', 'Cabeça e mandíbula', 'Preto + azul-claro', 'Baixo', 'Camada de 0,12 mm para melhor rosto.'],
        ['7', '01 · placa 4', 'Cauda de fogo e peças pequenas', 'Azul-claro', 'Médio', 'Overhang. Sem suporte nos encaixes.'],
        ['8', '01 · placa 5', 'Barriga', 'Azul-claro', 'Médio', 'Pode não encaixar no corpo (ver seção 6).'],
        ['9', '01 · placa 8', 'Asa do meio (preta)', 'Preto', 'Médio', 'A peça mais alta (138 mm). Brim e suporte forte.'],
        ['10', '01 · placa 3', 'Corpo, pernas e mãos', 'Preto', 'Baixo/Médio', '<b>Por último</b>: é a impressão mais longa e pesada.'],
    ], [7, 24, 38, 24, 16, 65]))
    S.append(Spacer(1, 6))
    S.append(caixa('Se um passo falhar, pare e ajuste. Cada placa é barata de repetir, e as placas do corpo são as únicas longas. '
                   'Imprimir o corpo antes de testar as asas é o erro mais caro possível.', AMAR, 'Regra principal'))

    # ---------- Ajustes
    S.append(H1('3. Ajustes por tipo de peça'))
    S.append(P('Os arquivos já têm estes ajustes <b>gravados por peça</b> (camada, paredes, velocidade da parede externa e infill). '
               'A <b>temperatura</b> é por filamento e não por peça, então ajuste no Studio quando indicado. '
               'Valores vêm do perfil do autor (0,16 mm, 220 °C) e de prática comum de PLA na A1; teste cada um numa peça barata.'))
    S.append(tabela(['Peça', 'Bico / camada', 'Parede ext.', 'Temp.', 'Paredes / infill', 'Notas'], [
        ['Corpo, mãos (preto)', '0,4 / 0,16', '110 mm/s', '220 °C', '2 / 10% gyroid', 'Fatiado como o autor, só mais lento na parede externa.'],
        ['Pernas', '0,4 / 0,16', '110 mm/s', '220 °C', '2 / 15%', 'Levam o peso do modelo: mais infill.'],
        ['Cabeça, mandíbula', '0,4 / 0,12', '70 mm/s', '215–220 °C', '3 / 10%', 'O rosto merece mais tempo. Gravado no arquivo.'],
        ['Barriga, cauda', '0,4 / 0,16', '90 mm/s', '215–220 °C', '2 / 10%', 'Suporte a 40° (gravado). Tirar suporte dos encaixes.'],
        ['Peças pequenas (azul-claro, placa 4)', '0,4 / 0,16', '60 mm/s', '215 °C', '2 / 10%', 'Brim de 10 mm vem do arquivo.'],
        ['Dentes e unhas', '0,4 / 0,08 (ou 0,2 / 0,08)', '45 mm/s', '215 °C', '2 / 20%', 'Mínimo de 8–10 s por camada (ver cooling). Imprima todos juntos.'],
        ['Olhos, língua', '0,2 / 0,08 (ou 0,4 / 0,08)', '35 mm/s', '215 °C', '– / 100%', 'Tudo sólido. Branco para pintar.'],
        ['<b>Asas</b> (arquivo 02)', '0,4 / 0,16', '70 mm/s', '<b>215 °C</b>', '<b>3</b> / 8%', 'Temperatura e paredes já ajustadas no arquivo. Ver seção 4.'],
        ['Asa do meio (arquivo 01)', '0,4 / 0,16', '70 mm/s', '220 → <b>215 °C</b>', '3 / 10%', 'Baixe a temperatura do preto para 215 °C nessa placa.'],
    ], [30, 29, 19, 20, 24, 52]))
    S.append(H2('Ajustes globais gravados nos arquivos'))
    S += B(['Detect thin wall: <b>ligado</b>. Sem isso, paredes finas das asas podem sumir.',
            'Parede externa 100 mm/s (arquivo 01) e 70 mm/s (arquivo 02), no lugar dos <b>200 mm/s</b> do perfil do autor. '
            'A 200 mm/s, o overhang das asas e o acabamento sofrem.',
            'Aceleração da parede externa 3000 (corpo) e 2500 (asas), contra 5000 do perfil original.',
            'Perfil de impressora/processo já era <b>A1</b> nos arquivos do autor (0.16mm Optimal @BBL A1).'])
    S.append(H2('Ajustes que você faz no Studio'))
    S += B(['<b>Ventoinha</b>: peças pequenas (dentes, unhas, língua, olhos) precisam de tempo mínimo por camada de 8–10 s e ventoinha em 100% para o plástico não empapar. '
            '(Filament → Cooling → "Layer time" / "Slow printing down for better layer cooling".)',
            '<b>Torre de limpeza</b>: placas de uma cor só não precisam dela; desligue nelas para economizar filamento. Placa 1 (cabeça) mistura preto e azul-claro: deixe ligada.',
            '<b>Purga preto → claro</b> gasta bastante. Reduza o multiplicador de purga se o resultado ficar limpo, e confira na pré-visualização.',
            '<b>Mesa</b>: PLA a 55–60 °C na Textured PEI, 1ª camada a 220 °C. Limpe a mesa com álcool isopropílico antes das peças altas.'])

    # ---------- Asas
    S.append(H1('4. Asas: o ponto de maior risco'))
    S.append(P('A medição por raios nas peças (<b>estimativa, não é fatiamento</b>) mostra paredes de <b>0,56 a 0,95 mm</b> no pior caso (percentil 5) a 75%, '
               'com até 43% da superfície de uma peça abaixo de 1,2 mm. O bico de 0,4 só gera parede de forma confiável a partir de ~0,8 mm (2 linhas). '
               'Há risco de furos nas asas. O autor também avisou isso.'))
    S.append(H2('O que o arquivo de asas (02) já resolve'))
    S += B(['Suporte pintado à mão (~1,8 a 2,6 mil triângulos por peça) e suporte normal a 40° por objeto. Veio da versão "2ª geração, suporte reforçado", que a comunidade criou por causa do overhang.',
            'Detect thin wall ligado, 3 paredes, parede externa 70 mm/s, 215 °C, infill 8%.',
            'Escala 75% já aplicada. Geometria idêntica à do arquivo original (hashes de vértices iguais): a melhoria é o suporte, <b>não a espessura</b>.'])
    S.append(H2('O que fazer'))
    S += B(['Imprima uma peça de teste e <b>fatie com a pré-visualização por camadas</b>: procure buracos nas paredes finas, camadas isoladas e "paredes ausentes".',
            'Se aparecerem furos: (a) suba a escala para <b>80%</b> em todo o projeto; (b) ou use o bico <b>0,2</b> só nas peças com furo; (c) ou aumente o número de paredes e ative "Arachne".',
            'Imprima as peças da asa com <b>brim de 5 mm</b>: são altas, finas e soltam da mesa.',
            'Mantenha a ventoinha em 100% e a temperatura em 215 °C no overhang. Se o filamento estiver úmido, seque antes (PLA ~45–55 °C por 4–6 h).'])
    S.append(H2('Bico 0,2: quando vale a pena'))
    S += B(['Paredes finas: com 0,2 cabem 3 a 4 linhas onde o 0,4 faz 1 ou 2, e os furos somem. O custo é <b>muito mais tempo</b> (não medi quanto).',
            'Só nas peças com problema. Medidas piores: L42 e r42 da asa de 1ª geração; <b>L 2 1</b> e <b>R 2 1</b> da asa de 2ª geração (arquivo 02, placa 1).',
            'Como trocar: troque o bico fisicamente, selecione o perfil "A1 0.2 nozzle" no Studio, camada 0,08–0,12 mm, e calibre o fluxo. Não basta mudar o diâmetro no software.'])
    S.append(caixa('Se as 2 primeiras peças de asa saírem inteiras e sem furos, o resto do projeto é de baixo risco. '
                   'Se não, resolva as asas (80% ou 0,2) <b>antes</b> de imprimir o corpo.', VERM, 'Decisão'))
    S.append(Spacer(1, 4))

    S.append(H1('5. Suporte'))
    S += B(['Tipo normal/árvore híbrido, ângulo de 40° nas asas, barriga e cauda (gravado por peça). O perfil original usa 25°, que comentários apontam como pouco para as asas.',
            'Distância vertical de contato ~0,2 mm e 2 camadas de interface, para a base sair sem estragar a superfície azul. Ajuste no Studio, em Support.',
            'Remova todo suporte das regiões de <b>encaixe</b> (cauda, barriga). Suporte nos encaixes impede o ajuste a seco.',
            'Retire o suporte com pinça e estilete; para marcas, lixa 400 a 600.'])

    # ---------- Barriga e montagem
    S.append(H1('6. Montagem'))
    S.append(P('Não existe um manual de montagem completo no arquivo; consulte as fotos do MakerWorld e os comentários. '
               'Esta ordem é uma sugestão geral, <b>não verificada</b> contra o modelo montado.'))
    S += B(['<b>Ajuste a seco primeiro</b>: encaixe todas as peças de cada região sem cola e anote o que não encaixa.',
            'Lixe encaixes apertados com lixa 400. Não force: PLA fino quebra.',
            'Barriga: o autor relata que parte dela pode não encaixar no corpo. Dica dele: aquecer rapidamente com um isqueiro para amolecer e encaixar. '
            'Use calor leve, afastado, e sempre longe das cores claras (marcam e deformam).',
            'Sugestão de ordem: pernas → mãos → corpo → barriga → cabeça (com mandíbula, dentes) → cauda → asas por último.',
            'Cole com gel em pontos pequenos, 1 região por vez, e segure ~30 s. Super Bonder em excesso embranquece o PLA escuro.',
            'Asas: monte as metades preta e azul em superfície plana, seque bem, e só então fixe no corpo.'])

    S.append(H1('7. Acabamento e pintura'))
    S += B(['<b>Língua</b>: vermelho acrílico. <b>Olhos</b>: pinte conforme a referência do personagem. Use caneta/pincel fino e teste numa sobra.',
            'Pinte <b>antes de colar</b>, mas deixe a área de cola sem tinta (tinta impede a Super Bonder).',
            'Lixa fina nas linhas de camada das áreas visíveis e remova fiapos (stringing) com isqueiro rápido ou estilete.',
            'Verniz acrílico fosco no final, fino e em camadas, para uniformizar o brilho.'])

    # ---------- Problemas
    S.append(PageBreak())
    S.append(H1('8. Problemas comuns e o que fazer'))
    S.append(tabela(['Sintoma', 'Causa provável', 'O que tentar'], [
        ['Furos na asa', 'Parede < 0,8 mm', 'Detect thin wall ligado; escala 80%; bico 0,2 só nessa peça; conferir a pré-visualização.'],
        ['Asa com camadas caídas/"macarrão" no overhang', 'Pouco suporte, parede externa rápida, temperatura alta', '40° de suporte; 70 mm/s; 215 °C; ventoinha 100%.'],
        ['Peça alta tombando/descolando', 'Aderência fraca', 'Brim; limpar a mesa com álcool; reduzir velocidade nas primeiras camadas.'],
        ['Dente/unha derretida ou borbulhada', 'Camada muito rápida', 'Tempo mínimo 8–10 s por camada; imprimir todas juntas; ventoinha 100%.'],
        ['Barriga não encaixa', 'Tolerância apertada', 'Ajuste a seco, lixar, aquecimento leve (dica do autor); sem suporte nos encaixes.'],
        ['Cola esbranquiçada', 'Excesso de Super Bonder', 'Usar gel em pontos pequenos; acetona só com cuidado; retocar com tinta.'],
        ['Diferença de tom entre peças pretas', 'Bobinas diferentes', 'Usar o mesmo rolo/marca/lote por cor.'],
        ['Troca de cor suja ou gasta demais', 'Purga alta', 'Reduzir multiplicador de purga; ordenar objetos; desligar torre em placa de uma cor.'],
    ], [48, 48, 78]))

    S.append(H1('9. Checklist rápido'))
    S.append(tabela(['✓', 'Item'], [
        ['☐', 'Conferi escala e altura montada (~20 cm) na pré-visualização.'],
        ['☐', 'Fatiei <b>cada placa</b> e olhei camada a camada nas asas.'],
        ['☐', 'Língua e olhos impressos em branco; plano de pintura definido.'],
        ['☐', 'AMS lite com preto, branco, azul-claro e azul, e mapeamento correto.'],
        ['☐', 'Mesa limpa com álcool; PLA seco.'],
        ['☐', 'Primeiro teste de asa impresso e aprovado antes do corpo.'],
        ['☐', 'Ajuste a seco de todas as peças antes de colar.'],
    ], [10, 164], zebra=False))
    S.append(H1('10. O que não foi verificado'))
    S += B(['Tempo e gramas reais (os arquivos não vieram fatiados).',
            'Altura montada exata (só estimada dos comentários; 75% ≈ 20 cm).',
            'Se as asas ficam sem furo a 75% com o bico de 0,4 (depende do fatiador).',
            'A abertura dos 3MF no Bambu Studio (conferi só por script: XML válido, dimensões e ajustes gravados).',
            'A ordem de montagem sugerida e a diferença visual de tom entre os azuis.',
            'Os valores de velocidade e temperatura são ponto de partida, não receita testada na sua A1.'])
    S.append(Spacer(1, 6))
    S.append(P('Licença do modelo: Standard Digital File License (MakerWorld). Uso pessoal; não redistribuir os arquivos nem vender peças impressas sem permissão do autor.', small))

    doc.build(S, onFirstPage=rodape, onLaterPages=rodape)


if __name__ == '__main__':
    main(sys.argv[1])
