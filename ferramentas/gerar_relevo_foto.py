#!/usr/bin/env python3
"""Gera um STL de relevo (chaveiro/placa) a partir de uma imagem recortada
(logo ja com perspectiva corrigida, se necessario). Roda no venv
~/.local/share/analisar3d-venv (precisa numpy, trimesh, pillow, scipy).

Uso:
  ~/.local/share/analisar3d-venv/bin/python gerar_relevo_foto.py IMG.png SAIDA.stl \
      [--largura-mm 45] [--altura-mm 36] [--placa-mm 2.0] [--relevo-mm 1.0] \
      [--grid-w 160] [--grid-h 128] [--dilatar 2] [--sem-argola]

Thresholding: marca como "primeiro plano" (relevo) pixels brancos (brilho alto,
baixa saturacao) OU vermelhos (R alto, R-G e R-B grandes). Ajustar no codigo
se o logo usar outras cores predominantes.

Por que threshold na RESOLUCAO ORIGINAL e nao depois do resize: um
`Image.resize()` direto (LANCZOS) borra tracos finos (aneis, texto pequeno,
selos circulares) para uma cor intermediaria que cai fora do threshold —
manchas finas simplesmente desaparecem do relevo. Aqui o threshold roda na
imagem cheia, dilata (engrossa) o traco pra garantir largura minima
imprimivel (~0,4mm de bico), e SO DEPOIS reduz pra grade via "block-max"
(reshape em blocos + `.any()`), que preserva qualquer pixel verdadeiro do
bloco em vez de borrar. Dilatar tambem e necessario pra imprimir: um traco
de 1 pixel pode nao fechar no slicer.
"""
import argparse
import numpy as np
import trimesh
from PIL import Image
from scipy import ndimage


def _block_max(mask, grid_h, grid_w):
    """Reduz mask (H,W) bool pra (grid_h,grid_w) por 'ou logico' em blocos.
    Faz pad ATE multiplo de grid ANTES de fazer reshape: se H ou W nao for
    multiplo exato de grid_h/grid_w, um reshape direto corta (descarta) a
    faixa de baixo/direita da imagem em silencio — conteudo perto da borda
    (ex. um selo no canto) some sem nenhum erro ou aviso."""
    h, w = mask.shape
    bh = -(-h // grid_h)  # ceil
    bw = -(-w // grid_w)
    ph, pw = bh * grid_h, bw * grid_w
    padded = np.zeros((ph, pw), dtype=bool)
    padded[:h, :w] = mask
    return padded.reshape(grid_h, bh, grid_w, bw).any(axis=(1, 3))


def build(img_path, out_path, largura_mm=45.0, altura_mm=36.0, placa_mm=2.0,
          relevo_mm=1.0, grid_w=160, grid_h=128, dilatar=2, argola=True):
    img = Image.open(img_path).convert("RGB")
    arr = np.asarray(img).astype(int)
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    brightness = (R + G + B) / 3
    is_white_full = (brightness > 150) & (np.abs(R - G) < 40) & (np.abs(G - B) < 40)
    is_red_full = (R > 120) & (R - G > 40) & (R - B > 40)
    if dilatar > 0:
        is_white_full = ndimage.binary_dilation(is_white_full, iterations=dilatar)
        is_red_full = ndimage.binary_dilation(is_red_full, iterations=dilatar)

    is_white = _block_max(is_white_full, grid_h, grid_w)
    is_red = _block_max(is_red_full, grid_h, grid_w)
    foreground = is_white | is_red

    px_w = largura_mm / grid_w
    px_h = altura_mm / grid_h

    meshes = []
    plate = trimesh.creation.box(extents=[largura_mm, altura_mm, placa_mm])
    plate.apply_translation([largura_mm / 2, altura_mm / 2, placa_mm / 2])
    meshes.append(plate)

    # funde pixels adjacentes de uma mesma linha num unico box (senao vira
    # dezenas de milhares de caixas e o export/preview fica pesado)
    ys, xs = np.where(foreground)
    rows = {}
    for y, x in zip(ys, xs):
        rows.setdefault(y, []).append(x)

    for y, xlist in rows.items():
        xlist = sorted(xlist)
        start = prev = xlist[0]
        for x in xlist[1:] + [None]:
            if x is None or x != prev + 1:
                run_w = (prev - start + 1) * px_w
                cx = (start + prev + 1) / 2 * px_w
                cy = (grid_h - y - 0.5) * px_h  # flip Y: linha 0 da imagem = topo
                b = trimesh.creation.box(extents=[run_w, px_h, relevo_mm])
                b.apply_translation([cx, cy, placa_mm + relevo_mm / 2])
                meshes.append(b)
                if x is not None:
                    start = x
            prev = x if x is not None else prev

    if argola:
        # annulus = anel manifold pronto, nao precisa de boolean/CSG pra furo
        ring = trimesh.creation.annulus(r_min=3.0, r_max=6.5, height=3.0)
        ring.apply_translation([-3.0, altura_mm - 4.0, placa_mm / 2])
        meshes.append(ring)

    full = trimesh.util.concatenate(meshes)
    full.export(out_path)
    return full


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("imagem")
    ap.add_argument("saida_stl")
    ap.add_argument("--largura-mm", type=float, default=45.0)
    ap.add_argument("--altura-mm", type=float, default=36.0)
    ap.add_argument("--placa-mm", type=float, default=2.0)
    ap.add_argument("--relevo-mm", type=float, default=1.0)
    ap.add_argument("--grid-w", type=int, default=160)
    ap.add_argument("--grid-h", type=int, default=128)
    ap.add_argument("--dilatar", type=int, default=2,
                     help="iteracoes de dilatacao do traco antes do downsample (0 desliga)")
    ap.add_argument("--sem-argola", action="store_true")
    a = ap.parse_args()
    m = build(a.imagem, a.saida_stl, a.largura_mm, a.altura_mm, a.placa_mm,
              a.relevo_mm, a.grid_w, a.grid_h, a.dilatar, argola=not a.sem_argola)
    print(f"salvo: {a.saida_stl} | verts={len(m.vertices)} faces={len(m.faces)}")
