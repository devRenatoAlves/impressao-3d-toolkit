# Pecas funcionais/mecanicas (abridor, gancho, suporte sob forca)

Diferente de relevo/logo (so estetico, qualquer geometria "meio errada" ainda fica bonita), peca mecanica que recebe forca (abridor de garrafa, gancho, clip, suporte) PRECISA de geometria certa ou simplesmente nao funciona. Tratar como classe a parte.

## Fluxo
1. Antes de desenhar, buscar na web as medidas de referencia reais da peca (ex. "bottle opener keychain dimensions notch geometry") — abertura do gancho, profundidade do dente, distancia fulcro-gancho, espessura minima de parede no ponto de maior tensao. Nao chutar essas medidas: sao o que decide se a peca funciona ou nao.
2. Tentar achar um arquivo pronto testado pela comunidade (Printables/MakerWorld) antes de desenhar do zero — mas ambos os sites bloqueiam download automatico via Cloudflare (ver pitfall no SKILL.md principal), entao normalmente cai em desenhar do zero com as medidas validadas do passo 1.
3. Desenhar o perfil 2D com `shapely` (`Point(...).buffer(raio)`, `box(...)`, `unary_union`, `.difference()`) e extrudar com `trimesh.creation.extrude_polygon(poligono, espessura)` — precisa `pip install shapely mapbox-earcut manifold3d` no venv (a falta de engine de triangulacao da erro `No available triangulation engine!`). Isso tambem habilita boolean real (`manifold3d`) se precisar depois.
4. Pra conferir se um furo/fenda realmente ABRE pra borda da peca (ex. boca do abridor) em vez de ficar uma ilha fechada, plotar o poligono 2D direto com matplotlib (`ax.fill`) e uma linha de referencia na borda — e MUITO mais confiavel que olhar o preview 3D (angulo de camera/transparencia engana e pode parecer fechado quando esta aberto, ou vice-versa).
5. Entregar com aviso explicito (nao vender como pronto): recomendar material PETG (nao PLA, mais fragil sob flexao repetida) com 100% infill, e pedir pro usuario imprimir 1 unidade e testar em 2-3 tampinhas reais antes do lote final. Deixar os parametros do script faceis de ajustar (constantes no topo) pra reimprimir rapido se a folga estiver errada.

## O que NAO fazer
- Nao apresentar uma peca mecanica nao testada fisicamente como "pronta", mesmo com preview 3D bonito — preview so confirma forma, nao confirma que a forca de alavanca funciona na tampinha de verdade.
- Nao reusar sem adaptar um design cosmetico (caixas empilhadas tipo relevo) pra peca que recebe forca: caixas sobrepostas nao-manifold sao toleraveis pra estetica mas pioram a resistencia estrutural real; usar extrusao de poligono solido (shapely + extrude_polygon) em vez de box-stacking nessas pecas.
