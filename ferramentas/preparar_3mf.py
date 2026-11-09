#!/usr/bin/env python3
"""Prepara um 3MF do Bambu Studio: reescala, grava overrides por objeto e
remove filamentos nao usados.

Uso pela linha de comando:
    preparar_3mf.py CORPO.3mf ASAS.3mf SAIDA_DIR [escala=0.75]

Uso como biblioteca (serve para QUALQUER 3MF, nao so o caso de dois arquivos):
    import preparar_3mf as P
    P.build(src, dst, 1.0, {}, keep=(1, 5), cores=('#FFFFFF', '#000000'))

A funcao `build(src, dst, f, global_edits, obj_over=None, keep=None, cores=None)`
escala os itens do build em torno do centro-base de cada um (preservando a
posicao na placa), grava overrides por objeto em `model_settings.config` e
edita `project_settings.config`.

AVISO IMPORTANTE: nunca passe `printer_model` ou `printer_settings_id` em
`global_edits`. Dezenas de outras chaves do config (gcode de inicio/fim, troca
de filamento, perfis compativeis) sao especificas da impressora original e nao
sao atualizadas junto; o Studio rejeita o arquivo inteiro com "Invalid
configuration file". Troque de impressora pela interface do Studio.
"""
import json, re, sys, zipfile, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analisar3d as A
import xml.etree.ElementTree as ET

def scale_items(xml, zin, f):
    root = ET.fromstring(zin.read('3D/3dmodel.model'))
    res = root.find('m:resources', A.NS); cache = {}
    def meshes(p):
        if p not in cache: cache[p] = A.read_mesh_file(zin, p)
        return cache[p]
    objs = {}
    for o in res:
        comps = o.find('m:components', A.NS)
        if comps is not None:
            objs[o.get('id')] = [(c.get('objectid'), A.mat(c.get('transform')), c.get('{%s}path' % A.PROD)) for c in comps]
        elif o.find('m:mesh', A.NS) is not None:
            objs[o.get('id')] = [(o.get('id'), A.IDENT, None)]
    def fix(m):
        tag = m.group(0); oid = re.search(r'objectid="(\d+)"', tag).group(1)
        bt = A.mat(re.search(r'transform="([^"]*)"', tag).group(1))
        pts = []
        for cid, ct, p in objs[oid]:
            vs, tris = meshes(p or '3D/3dmodel.model')[cid]
            t = A.compose(ct, bt); pts += [A.tr(t, v) for v in vs]
        mn, mx, _ = A.bbox(pts)
        c = ((mn[0]+mx[0])/2, (mn[1]+mx[1])/2, mn[2])
        n = [v*f for v in bt[:9]] + [bt[9+k]*f + (1-f)*c[k] for k in range(3)]
        return re.sub(r'transform="[^"]*"', 'transform="%s"' % ' '.join(repr(v) for v in n), tag)
    return re.sub(r'<item [^>]*>', fix, xml)

def set_settings(txt, edits, keep=None, cores=None):
    d = json.loads(txt)
    if keep:
        idx = [k - 1 for k in keep]; n0 = len(d['filament_colour'])
        g_self = len(d.get('filament_self_index', [])) // n0 if d.get('filament_self_index') else 1
        for k, v in list(d.items()):
            if not isinstance(v, list) or not v: continue
            if k == 'flush_volumes_matrix' and len(v) == n0 * n0:
                d[k] = [v[i * n0 + j] for i in idx for j in idx]
            elif len(v) % n0 == 0:
                # Varias chaves guardam grupos de N valores por filamento (ex: 3 variantes de
                # bico, 4 estados de secagem AMS), nao so 1:1. Preservar o agrupamento ao podar,
                # senao o tamanho da lista desalinha com outras chaves (Studio rejeita o 3MF
                # inteiro com "Invalid configuration file" / "sem dado de geometria").
                gp = len(v) // n0
                d[k] = [x for i in idx for x in v[i * gp:(i + 1) * gp]]
        if cores: d['filament_colour'] = list(cores)
        if 'filament_self_index' in d:
            d['filament_self_index'] = [str(i + 1) for i in range(len(keep)) for _ in range(g_self)]
    for k, v in edits.items():
        if k not in d: print('AVISO: chave ausente', k); continue
        d[k] = [v] * len(d[k]) if isinstance(d[k], list) else v
    return json.dumps(d, indent=4, ensure_ascii=False)

def add_obj_meta(cfg, oid, kv):
    m = re.search(r'(<object id="%s">.*?<metadata key="extruder" value="[^"]*"/>)' % oid, cfg, re.S)
    assert m, oid
    ins = ''.join('\n    <metadata key="%s" value="%s"/>' % (k, v) for k, v in kv.items()
                  if 'key="%s"' % k not in cfg[m.start():cfg.find('</object>', m.start())])
    return cfg[:m.end()] + ins + cfg[m.end():]

def build(src, dst, f, global_edits, obj_over=None, tongue_white=False, disable=(), keep=None, cores=None):
    zin = zipfile.ZipFile(src); out = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
    for it in zin.infolist():
        data = zin.read(it.filename)
        if it.filename == '3D/3dmodel.model':
            x = scale_items(data.decode('utf8'), zin, f)
            for oid in disable:
                x = re.sub(r'(<item objectid="%s"[^>]*?)printable="1"' % oid, r'\1printable="0"', x)
            data = x.encode('utf8')
        elif it.filename == 'Metadata/project_settings.config':
            data = set_settings(data.decode('utf8'), global_edits, keep, cores).encode('utf8')
        elif it.filename == 'Metadata/model_settings.config':
            cfg = data.decode('utf8')
            cfg = cfg.replace('key="print_sequence" value="by object"', 'key="print_sequence" value="by layer"')  # por objeto gera aviso de colisao no Studio
            if tongue_white:
                cfg = re.sub(r'(<object id="12">\s*<metadata key="name" value="[^"]*"/>\s*<metadata key="extruder" value=")2"', r'\g<1>3"', cfg)
            for oid, kv in (obj_over or {}).items(): cfg = add_obj_meta(cfg, oid, kv)
            if keep:
                mp = {str(o): str(i + 1) for i, o in enumerate(keep)}
                cfg = re.sub(r'(key="extruder" value=")(\d+)"', lambda m: m.group(1) + mp.get(m.group(2), '1') + '"', cfg)
                cfg = re.sub(r'(key="filament_maps" value=")([^"]*)"',
                             lambda m: m.group(1) + ' '.join(m.group(2).split()[:len(keep)]) + '"', cfg)
            data = cfg.encode('utf8')
        out.writestr(it, data)
    out.close()

if __name__ == '__main__':
    corpo, asas, od = sys.argv[1:4]; f = float(sys.argv[4]) if len(sys.argv) > 4 else 0.75
    ge = {'detect_thin_wall': '1', 'outer_wall_speed': '100', 'outer_wall_acceleration': '3000'}
    O = {}
    for i in (85, 59, 75, 95): O[i] = {'layer_height': '0.12', 'wall_loops': '3', 'outer_wall_speed': '70'}
    for i in (89, 44, 92, 70, 98, 81): O[i] = {'layer_height': '0.08', 'outer_wall_speed': '45', 'sparse_infill_density': '20%'}
    for i in (25, 29, 12): O[i] = {'layer_height': '0.08', 'outer_wall_speed': '35', 'sparse_infill_density': '100%'}
    for i in (10, 23, 16): O[i] = {'outer_wall_speed': '60'}
    for i in (4, 27, 33, 38): O[i] = {'outer_wall_speed': '90', 'support_threshold_angle': '40'}
    O[100] = {'outer_wall_speed': '90'}
    for i in (36, 52, 102, 83, 77): O[i] = {'outer_wall_speed': '110'}
    for i in (63, 72): O[i] = {'outer_wall_speed': '110', 'sparse_infill_density': '15%'}
    for i in (7, 19): O[i] = {'wall_loops': '3', 'outer_wall_speed': '70', 'support_threshold_angle': '40'}
    O = {str(k): v for k, v in O.items()}
    build(corpo, od + '/01_Corpo_A1_75.3mf', f, ge, O, tongue_white=True, keep=(1, 3, 4), cores=('#000000', '#FFFFFF', '#459BC7'),
          disable=('40', '54', '31', '46', '50', '56', '48', '2', '61', '66'))
    ga = {'detect_thin_wall': '1', 'wall_loops': '3', 'outer_wall_speed': '70', 'outer_wall_acceleration': '2500',
          'nozzle_temperature': '215', 'sparse_infill_density': '8%'}
    build(asas, od + '/02_Asas_A1_75.3mf', f, ga, keep=(1, 5), cores=('#000000', '#3185DF'))
