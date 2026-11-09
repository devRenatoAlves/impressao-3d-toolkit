"""Gera pinos de alinhamento a partir das cavidades (negative_part) de um 3MF.

Contexto: modelos cortados no Bambu Studio com "connectors" guardam, em cada
face de corte, um `negative_part` (cavidade) nos DOIS lados e um objeto
"connector" solto que deveria ser o pino. Quando o autor reescala o projeto, o
objeto do pino as vezes vira lixo (decimos de milimetro) e o usuario fica com
duas cavidades e nenhum pino -> pecas sem alinhamento, fenda e rebarba na cola.

Este script le as cavidades, encolhe a secao para dar folga e extruda no
comprimento das duas cavidades somadas.

Uso: editar SRC, ESCALA e a lista PARES (descobertos com o passo 1 do
README abaixo) e rodar com o venv:
    ~/.local/share/analisar3d-venv/bin/python gerar_pinos_encaixe.py

Como descobrir os PARES:
1. `Metadata/model_settings.config`: achar os `part` com
   `subtype="negative_part"` (nomes tipo Connector-1_A / Connector-1_B). O
   sufixo _A/_B casa os dois lados do mesmo encaixe.
2. A geometria de cada part e um <object> extra DENTRO do
   `3D/Objects/object_<N>.model` da peca (as cavidades tem ~19 vertices;
   a malha da peca tem dezenas de milhares).
3. ESCALA = norma das colunas do `transform` do <item> em `3D/3dmodel.model`.
"""
import os
import re
import zipfile

import numpy as np
import shapely.geometry as sg
import trimesh

SRC = "/caminho/para/modelo.3mf"
DEST = os.path.expanduser("~/Downloads/pinos")
ESCALA = 1.0
FOLGA_LATERAL = 0.15  # mm por lado (PLA, bico 0,4: 0,15 entra com pressao leve)
FOLGA_FUNDO = 0.3     # mm no comprimento total

# (nome, arquivo_cavidade_A, sub_id_A, arquivo_cavidade_B, sub_id_B)
PARES = []

z = zipfile.ZipFile(SRC)
PV = re.compile(rb'<vertex x="([-0-9.eE]+)" y="([-0-9.eE]+)" z="([-0-9.eE]+)"')
PT = re.compile(rb'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"')


def subobject(fname, sub_id):
    data = z.read("3D/Objects/" + fname)
    for mo in re.finditer(rb'<object id="(\d+)"[^>]*>(.*?)</object>', data, re.S):
        if mo.group(1).decode() != str(sub_id):
            continue
        V = np.array(PV.findall(mo.group(2)), dtype=float) * ESCALA
        T = np.array(PT.findall(mo.group(2)), dtype=int)
        return trimesh.Trimesh(vertices=V, faces=T, process=False)
    raise KeyError(sub_id)


def pino(cav_a, cav_b):
    eixo = int(np.argmin(cav_a.extents))  # eixo de insercao = menor dimensao
    prof = (cav_a.extents[eixo]
            + cav_b.extents[int(np.argmin(cav_b.extents))] - FOLGA_FUNDO)
    outros = [i for i in range(3) if i != eixo]
    poly = sg.MultiPoint([tuple(p) for p in cav_a.vertices[:, outros]]).convex_hull
    poly = poly.buffer(-FOLGA_LATERAL, join_style=2)
    if poly.is_empty:
        raise ValueError("cavidade pequena demais para a folga pedida")
    corpo = trimesh.creation.extrude_polygon(poly, prof)
    corpo.apply_translation(-corpo.centroid)
    return corpo, (poly.bounds[2] - poly.bounds[0],
                   poly.bounds[3] - poly.bounds[1], prof)


def main():
    os.makedirs(DEST, exist_ok=True)
    pecas = []
    for nome, fa, sa, fb, sb in PARES:
        A, B = subobject(fa, sa), subobject(fb, sb)
        p, dims = pino(A, B)
        p.export(os.path.join(DEST, nome + ".stl"))
        print("%-30s pino %.2f x %.2f x %.2f mm" % (nome, *dims))
        pecas.append(p)
    x = 0.0
    juntos = []
    for p in pecas:
        q = p.copy()
        q.apply_translation([x - q.bounds[0][0] + 3, 0, -q.bounds[0][2]])
        juntos.append(q)
        x = q.bounds[1][0]
    if juntos:
        trimesh.util.concatenate(juntos).export(
            os.path.join(DEST, "0_todos_os_pinos.stl"))


if __name__ == "__main__":
    main()
