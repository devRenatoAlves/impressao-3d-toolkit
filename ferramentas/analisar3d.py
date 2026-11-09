#!/usr/bin/env python3
"""Analisa um 3MF (Bambu Studio/MakerWorld) ou STL binario e imprime um relatorio.

Uso: analisar3d.py ARQUIVO [--escala 75] [--mesa 256x256x256] [--parede-min 1.2]
Python puro (sem trimesh/numpy). Le: placas, dimensoes por peca, cores/filamentos,
perfil do autor, dados de fatiamento (tempo/gramas) quando existirem.
"""
import argparse, html, os, re, struct, sys, zipfile
import xml.etree.ElementTree as ET

CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD = 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
NS = {'m': CORE}
IDENT = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
VENV_PY = os.path.expanduser('~/.local/share/analisar3d-venv/bin/python')

# Termos comuns de nomes de pecas em chines -> portugues (trocas simples, na ordem)
TRAD = [('组合体', 'conjunto-pequenas'), ('身体', 'corpo'), ('肚皮', 'barriga'), ('尾火', 'cauda-fogo'),
        ('左', 'esq-'), ('右', 'dir-'), ('腿', 'perna'), ('手', 'mao'), ('翅', 'asa'), ('中翅', 'asa-meio'),
        ('头', 'cabeca'), ('下巴', 'mandibula'), ('舌头', 'lingua'), ('眼', 'olho'), ('牙', 'dente'),
        ('指甲', 'unha'), ('肩角', 'chifre-ombro'), ('尾', 'cauda'), ('里', ' interna'), ('外', ' externa'),
        ('下', 'baixo-'), ('上', 'cima-'), ('前', 'frente-'), ('后', 'tras-')]


def pt(nome):
    for zh, p in sorted(TRAD, key=lambda x: -len(x[0])):
        nome = nome.replace(zh, p)
    return nome


def tr(t, p):
    x, y, z = p
    return (t[0]*x + t[3]*y + t[6]*z + t[9],
            t[1]*x + t[4]*y + t[7]*z + t[10],
            t[2]*x + t[5]*y + t[8]*z + t[11])


def mat(s):
    return [float(v) for v in s.split()] if s else IDENT


def compose(a, b):
    """aplica a, depois b (formato 3MF: vetor linha)."""
    ra = [a[0:3], a[3:6], a[6:9]]
    rb = [b[0:3], b[3:6], b[6:9]]
    r = [[sum(ra[i][k]*rb[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    t = [sum(a[9+k]*rb[k][j] for k in range(3)) + b[9+j] for j in range(3)]
    return [*r[0], *r[1], *r[2], *t]


def bbox(pts):
    mn = [min(p[k] for p in pts) for k in range(3)]
    mx = [max(p[k] for p in pts) for k in range(3)]
    return mn, mx, [mx[k]-mn[k] for k in range(3)]


def volume(vs, tris, t):
    """volume com sinal (mm3) apos aplicar a transformacao t."""
    v = 0.0
    for a, b, c in tris:
        p, q, r = tr(t, vs[a]), tr(t, vs[b]), tr(t, vs[c])
        v += (p[0]*(q[1]*r[2]-q[2]*r[1]) - p[1]*(q[0]*r[2]-q[2]*r[0]) + p[2]*(q[0]*r[1]-q[1]*r[0]))
    return v/6.0


def read_mesh_file(z, path):
    root = ET.fromstring(z.read(path.lstrip('/')))
    out = {}
    for o in root.iter('{%s}object' % CORE):
        mesh = o.find('m:mesh', NS)
        if mesh is not None:
            vs = [(float(v.get('x')), float(v.get('y')), float(v.get('z'))) for v in mesh.find('m:vertices', NS)]
            tris = [(int(t.get('v1')), int(t.get('v2')), int(t.get('v3'))) for t in mesh.find('m:triangles', NS)]
            out[o.get('id')] = (vs, tris)
    return out


def json_list(text, key):
    m = re.search(r'"%s":\s*(\[[^\]]*\])' % key, text)
    return re.findall(r'"([^"]*)"', m.group(1)) if m else []


def json_val(text, key):
    m = re.search(r'"%s":\s*"([^"]*)"' % key, text)
    return m.group(1) if m else None


def analyse_3mf(path, escala, mesa, parede_min, espessura=False, amostras=1500):
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    root = ET.fromstring(z.read('3D/3dmodel.model'))
    cache = {}

    def meshes(p):
        if p not in cache:
            cache[p] = read_mesh_file(z, p)
        return cache[p]

    res = root.find('m:resources', NS)
    objs = {}
    for o in res:
        comps = o.find('m:components', NS)
        if comps is not None:
            objs[o.get('id')] = [(c.get('objectid'), mat(c.get('transform')), c.get('{%s}path' % PROD)) for c in comps]
        elif o.find('m:mesh', NS) is not None:
            objs[o.get('id')] = [(o.get('id'), IDENT, None)]

    items, partes_por_item = {}, {}
    for it in root.find('m:build', NS):
        bt = mat(it.get('transform'))
        pts, vol, partes = [], 0.0, []
        for cid, ct, p in objs[it.get('objectid')]:
            vs, tris = meshes(p or '3D/3dmodel.model')[cid]
            t = compose(ct, bt)
            pts += [tr(t, v) for v in vs]
            vol += volume(vs, tris, t)
            partes.append((vs, tris, t))
        items[it.get('objectid')] = (pts, abs(vol))
        partes_por_item[it.get('objectid')] = partes

    cfg_txt = z.read('Metadata/model_settings.config').decode('utf8', 'replace') if 'Metadata/model_settings.config' in names else ''
    cfg = ET.fromstring(cfg_txt) if cfg_txt else None
    onome, oext = {}, {}
    plates = []
    if cfg is not None:
        for o in cfg.findall('object'):
            md = {m.get('key'): m.get('value') for m in o.findall('metadata') if m.get('key')}
            onome[o.get('id')] = pt(md.get('name', o.get('id')))
            oext[o.get('id')] = md.get('extruder')
        for p in cfg.findall('plate'):
            md = {m.get('key'): m.get('value') for m in p.findall('metadata') if m.get('key')}
            ids = []
            for mi in p.findall('model_instance'):
                d = {m.get('key'): m.get('value') for m in mi.findall('metadata') if m.get('key')}
                ids.append(d.get('object_id'))
            plates.append((md.get('plater_id'), ids))
    ids_in_plates = {i for _, ids in plates for i in ids}
    fora = [i for i in items if i not in ids_in_plates]

    ps = z.read('Metadata/project_settings.config').decode('utf8', 'replace') if 'Metadata/project_settings.config' in names else ''
    cores = json_list(ps, 'filament_colour')
    tipos = json_list(ps, 'filament_type')
    dens = json_list(ps, 'filament_density')

    f = escala / 100.0
    L = []
    P = L.append
    P('# Relatorio 3D: %s' % path.split('/')[-1])
    desc = re.search(r'name="Description">(.*?)</metadata>', z.read('3D/3dmodel.model').decode('utf8', 'replace'), re.S)
    P('')
    P('Escala analisada: **%g%%**  | Mesa: %s mm' % (escala, 'x'.join('%g' % v for v in mesa)))

    P('\n## Perfil do autor')
    for k in ('printer_model', 'layer_height', 'wall_loops', 'sparse_infill_density', 'sparse_infill_pattern',
              'enable_support', 'support_type', 'support_threshold_angle', 'brim_type', 'nozzle_temperature'):
        v = json_val(ps, k)
        if v is None:
            lst = json_list(ps, k)
            v = ', '.join(lst) if lst else None
        if v is not None:
            P('- %s: %s' % (k, v))
    m = re.search(r'"nozzle_diameter":\s*\[\s*"([^"]+)"', ps)
    if m:
        P('- nozzle_diameter: %s' % m.group(1))

    P('\n## Filamentos (%d)' % len(cores))
    usados = {}
    for i in items:
        e = oext.get(i)
        if e:
            usados.setdefault(e, []).append(onome.get(i, i))
    for n, c in enumerate(cores, 1):
        t = tipos[n-1] if n-1 < len(tipos) else '?'
        P('- Slot %d: %s %s' % (n, c, t))
    if len(cores) > 4:
        P('- AVISO: mais de 4 filamentos: um AMS nao basta (precisa 2o AMS ou troca manual).')

    si = z.read('Metadata/slice_info.config').decode('utf8', 'replace') if 'Metadata/slice_info.config' in names else ''
    fil = re.findall(r'<filament [^>]*>', si)
    if fil:
        P('\n## Dados de fatiamento (do arquivo)')
        for tag in fil:
            P('- ' + tag)
        for tag in re.findall(r'<metadata key="(?:prediction|weight)"[^>]*>', si):
            P('- ' + tag)
    else:
        P('\n(Arquivo sem fatiamento: tempo e gramas nao disponiveis; fatie no Bambu Studio.)')

    P('\n## Placas (dimensoes na escala %g%%)' % escala)
    avisos = []
    for pid, ids in plates:
        ids = [i for i in ids if i in items]
        if not ids:
            continue
        allp = [q for i in ids for q in items[i][0]]
        _, _, d = bbox(allp)
        ds = [v*f for v in d]
        P('\n### Placa %s: conjunto %.0f x %.0f x %.0f mm' % (pid, *ds))
        if ds[0] > mesa[0] or ds[1] > mesa[1] or ds[2] > mesa[2]:
            avisos.append('Placa %s pode nao caber na mesa (%.0f x %.0f x %.0f).' % (pid, *ds))
        for i in ids:
            _, _, d1 = bbox(items[i][0])
            d1 = [v*f for v in d1]
            vol = items[i][1]*f**3/1000.0
            fino = min(d1)
            flag = ''
            if fino < parede_min:
                flag = '  <-- dimensao minima %.2f mm < %.1f' % (fino, parede_min)
                avisos.append('Placa %s, %s: dimensao minima %.2f mm.' % (pid, onome.get(i, i), fino))
            ex = oext.get(i)
            P('- %s: %.0f x %.0f x %.0f mm, %.1f cm3%s%s' % (onome.get(i, i), *d1, vol,
              (', filamento %s' % ex) if ex else '', flag))
    if fora:
        P('\n### Fora das placas (nao sera impresso, se nao for movido)')
        for i in fora:
            _, _, d1 = bbox(items[i][0])
            P('- %s: %.0f x %.0f x %.0f mm' % (onome.get(i, i), *[v*f for v in d1]))

    # ---- filamento por slot (so pecas que estao em placas) ----
    vol_slot = {}
    for _, ids in plates:
        for i in ids:
            if i in items and oext.get(i):
                vol_slot[oext[i]] = vol_slot.get(oext[i], 0.0) + items[i][1]*f**3/1000.0
    if vol_slot:
        P('\n## Filamento por cor (estimativa)')
        P('Volume solido das pecas por slot. Gramas = volume x densidade. "Realista" ~ 35% do solido (2 paredes + infill 10% + topo/fundo); suporte, purga e torre de limpeza NAO entram.')
        tot_max = tot_real = 0.0
        for k in sorted(vol_slot, key=int):
            n = int(k)
            d = float(dens[n-1]) if n-1 < len(dens) else 1.25
            g = vol_slot[k]*d
            tot_max += g
            tot_real += g*0.35
            P('- Slot %s (%s): %.0f cm3 solido -> ate %.0f g, realista ~%.0f g' % (
                k, cores[n-1] if n-1 < len(cores) else '?', vol_slot[k], g, g*0.35))
        P('- Total: ate %.0f g, realista ~%.0f g (mais suporte/purga, some 15-30%%). ATENCAO: placas alternativas (ex.: duas versoes de asa) entram as duas na soma; descarte a que nao for imprimir.' % (tot_max, tot_real))

    # ---- espessura de parede (opcional, precisa de trimesh no venv) ----
    if espessura:
        try:
            import numpy as np
            import trimesh
        except ImportError:
            P('\n(Espessura: trimesh nao instalado. Rode com --espessura de novo: o script usa o venv automaticamente se existir.)')
        else:
            P('\n## Espessura de parede (raio para dentro a partir de %d pontos por peca, escala %g%%)' % (amostras, escala))
            P('Limite alerta: %.1f mm. Perto de 0,8 mm (2 linhas de 0,4) a parede ja falha.' % parede_min)
            rng = np.random.default_rng(1)
            for pid, ids in plates:
                for i in ids:
                    if i not in partes_por_item:
                        continue
                    ms = []
                    for vs, tris, t in partes_por_item[i]:
                        V = np.array(vs)
                        R = np.array([t[0:3], t[3:6], t[6:9]])
                        ms.append(trimesh.Trimesh(V @ R + np.array(t[9:12]), np.array(tris), process=False))
                    m = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]
                    m.vertices *= f
                    n = len(m.faces)
                    idx = rng.choice(n, min(amostras, n), replace=False)
                    c = m.triangles_center[idx]
                    nm = m.face_normals[idx]
                    org = c - nm*1e-3
                    loc, ir, it_ = m.ray.intersects_location(org, -nm, multiple_hits=False)
                    if len(ir) == 0:
                        continue
                    # so conta parede oposta: a face atingida precisa estar virada contra o raio
                    # (descarta quinas e triangulos vizinhos, que davam espessura ~0 falsa)
                    oposta = (m.face_normals[it_] * nm[ir]).sum(axis=1) < -0.5
                    loc, ir = loc[oposta], ir[oposta]
                    if len(ir) == 0:
                        continue
                    dist = np.linalg.norm(loc - org[ir], axis=1)
                    dist = dist[dist > 0.01]
                    if len(dist) == 0:
                        continue
                    p5 = float(np.percentile(dist, 5))
                    frac = float((dist < parede_min).mean())*100
                    marca = ''
                    if frac >= 10 or p5 < 0.8:
                        marca = '  <-- ATENCAO'
                        avisos.append('Placa %s, %s: %.0f%% da superficie tem menos de %.1f mm de espessura (p5=%.2f mm).' % (pid, onome.get(i, i), frac, parede_min, p5))
                    P('- placa %s %s: p5=%.2f mm, min=%.2f mm, %.0f%% < %.1f mm%s' % (pid, onome.get(i, i), p5, float(dist.min()), frac, parede_min, marca))

    P('\n## Avisos')
    if not avisos:
        P('- nenhum aviso automatico.')
    for a in avisos:
        P('- ' + a)
    P('\nLimites desta analise: dimensoes sao da caixa envolvente; a espessura (--espessura) e uma amostragem por raios, nao fatiamento. Nao detecta overhang nem encaixe. Confira a pre-visualizacao por camadas no slicer.')
    if desc:
        d = desc.group(1)
        for _ in range(3):
            d = html.unescape(d)
        d = re.sub(r'<[^>]+>', ' ', d)
        P('\n## Descricao do autor (resumo)\n' + re.sub(r'\s+', ' ', d).strip()[:1500])
    return '\n'.join(L)


def mesh_bytes(z):
    """Tamanho DESCOMPRIMIDO das malhas do 3MF, lido do indice do zip.

    Nao le nenhum byte de conteudo: o cabecalho do zip ja traz `file_size`.
    Serve para decidir, antes de alocar nada, se o arquivo cabe na memoria.
    """
    total = 0
    for info in z.infolist():
        name = info.filename.lower()
        if name.endswith('.model'):
            total += info.file_size
    return total


def stream_bbox(z, path):
    """Caixa envolvente e contagem de triangulos por objeto, sem montar listas.

    `read_mesh_file` guarda todos os vertices e triangulos em listas Python
    (dezenas de bytes por item): num 3MF de ~2 milhoes de triangulos isso passa
    de 3 GB e o processo e morto pelo OOM killer antes de imprimir qualquer
    coisa. Aqui o XML e consumido incrementalmente e cada elemento e descartado
    logo apos ser lido, entao a memoria fica constante.

    Devolve {object_id: (min_xyz, max_xyz, n_triangulos)}. Nao calcula volume
    nem espessura: isso exige a malha inteira.
    """
    out = {}
    with z.open(path.lstrip('/')) as handle:
        oid = None
        lo = [float('inf')] * 3
        hi = [float('-inf')] * 3
        ntri = 0
        for event, elem in ET.iterparse(handle, events=('start', 'end')):
            tag = elem.tag.split('}')[-1]
            if event == 'start' and tag == 'object':
                oid = elem.get('id')
                lo = [float('inf')] * 3
                hi = [float('-inf')] * 3
                ntri = 0
            elif event == 'end':
                if tag == 'vertex':
                    for i, k in enumerate('xyz'):
                        val = float(elem.get(k))
                        if val < lo[i]:
                            lo[i] = val
                        if val > hi[i]:
                            hi[i] = val
                    elem.clear()
                elif tag == 'triangle':
                    ntri += 1
                    elem.clear()
                elif tag == 'object':
                    if oid is not None and lo[0] != float('inf'):
                        out[oid] = (tuple(lo), tuple(hi), ntri)
                    elem.clear()
                    oid = None
    return out


def analyse_3mf_streaming(path, escala, mesa, limite_mb):
    """Relatorio reduzido para 3MF grande: dimensoes por objeto, sem volume."""
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if n.lower().endswith('.model')]
    f = escala / 100

    L = ['# Relatorio 3D (modo baixa memoria): %s' % path.split('/')[-1], '',
         'O arquivo tem ~%d MB de malha descomprimida, acima do limite de %d MB.'
         % (mesh_bytes(z) / 1e6, limite_mb),
         'Medindo por streaming: dimensoes e contagem de triangulos.',
         'Volume, gramas e espessura de parede exigem a malha inteira e ficam de fora.', '']

    total_tri = 0
    maiores = []
    for name in sorted(names):
        for oid, (lo, hi, ntri) in stream_bbox(z, name).items():
            dims = tuple((hi[i] - lo[i]) * f for i in range(3))
            total_tri += ntri
            maiores.append((max(dims), dims, ntri, oid, name))

    maiores.sort(reverse=True)
    L.append('Total: %d objetos, %d triangulos' % (len(maiores), total_tri))
    L.append('')
    L.append('Maiores objetos (escala %g%%):' % escala)
    for _, dims, ntri, oid, name in maiores[:15]:
        aviso = '  <-- NAO CABE NA MESA' if any(d > m for d, m in zip(dims, mesa)) else ''
        L.append('  obj %-6s %6.1f x %6.1f x %6.1f mm  %8d tri%s'
                 % (oid, dims[0], dims[1], dims[2], ntri, aviso))
    if len(maiores) > 15:
        L.append('  ... e mais %d objeto(s)' % (len(maiores) - 15))

    L += ['', 'Observacao: estas sao as dimensoes de cada objeto SOLTO, nao da peca',
          'montada. Um modelo cortado em pecas nao guarda a pose de montagem no 3MF.']
    return '\n'.join(L)


def analyse_stl(path, escala, mesa, parede_min):
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0]
    if 84 + n*50 != len(data):
        sys.exit('STL ASCII nao suportado: converta para binario ou use 3MF.')
    pts, tris, vs = [], [], []
    for k in range(n):
        v = struct.unpack('<12fH', data[84+k*50:84+(k+1)*50])
        base = len(vs)
        vs += [v[3:6], v[6:9], v[9:12]]
        tris.append((base, base+1, base+2))
    _, _, d = bbox(vs)
    f = escala/100
    vol = abs(volume(vs, tris, IDENT))*f**3/1000
    out = ['# Relatorio 3D: %s' % path.split('/')[-1], '',
           'Escala %g%%: %.1f x %.1f x %.1f mm, %.1f cm3, %d triangulos' % (escala, *[x*f for x in d], vol, n)]
    if any(x*f > m for x, m in zip(d, mesa)):
        out.append('AVISO: pode nao caber na mesa.')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(
        description='Analisa um 3MF (Bambu Studio/MakerWorld) ou STL binario.')
    ap.add_argument('arquivo')
    ap.add_argument('--escala', type=float, default=100,
                    help='escala a aplicar, em %% (padrao: 100)')
    ap.add_argument('--mesa', default='256x256x250',
                    help='volume da mesa em mm, LxPxA (padrao: 256x256x250)')
    ap.add_argument('--parede-min', type=float, default=1.2,
                    help='parede minima aceitavel em mm (padrao: 1.2)')
    ap.add_argument('--espessura', action='store_true',
                    help='mede espessura de parede (usa trimesh no venv; mais lento)')
    ap.add_argument('--amostras', type=int, default=1500,
                    help='amostras para a medida de espessura (padrao: 1500)')
    ap.add_argument('--limite-mb', type=int, default=120,
                    help='acima deste tamanho de malha, usa o modo baixa memoria '
                         '(padrao: 120; 0 desliga o limite)')
    a = ap.parse_args()
    if a.espessura and os.path.exists(VENV_PY) and os.path.realpath(sys.prefix) != os.path.realpath(os.path.dirname(os.path.dirname(VENV_PY))):
        os.execv(VENV_PY, [VENV_PY] + sys.argv)
    mesa = [float(v) for v in a.mesa.split('x')]
    if a.arquivo.lower().endswith('.stl'):
        print(analyse_stl(a.arquivo, a.escala, mesa, a.parede_min))
        return

    # Um 3MF grande carregado inteiro estoura a RAM e o processo e morto pelo
    # OOM killer sem imprimir nada. Mede antes (pelo indice do zip, sem ler
    # conteudo) e troca de modo em vez de morrer.
    if a.limite_mb > 0:
        with zipfile.ZipFile(a.arquivo) as z:
            grande = mesh_bytes(z) > a.limite_mb * 1_000_000
        if grande:
            if a.espessura:
                print('aviso: --espessura ignorado, o arquivo e grande demais '
                      'para carregar a malha inteira.', file=sys.stderr)
            print(analyse_3mf_streaming(a.arquivo, a.escala, mesa, a.limite_mb))
            return

    print(analyse_3mf(a.arquivo, a.escala, mesa, a.parede_min, a.espessura, a.amostras))


if __name__ == '__main__':
    main()
