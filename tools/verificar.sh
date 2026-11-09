#!/usr/bin/env bash
# Verificacao final antes de publicar: auditoria, compilacao, links e execucao.
set -u
cd "$(dirname "$0")/.." || exit 1
VENV="$HOME/.local/share/analisar3d-venv/bin/python"
falhas=0

secao() { printf '\n===== %s =====\n' "$1"; }
ok()    { printf '  ok   %s\n' "$1"; }
erro()  { printf '  FALHA %s\n' "$1"; falhas=$((falhas+1)); }

secao "1. auditoria de vazamento"
python3 tools/audit-leaks.py --nome "Renato" > /tmp/audit.out 2>&1
code=$?
tail -3 /tmp/audit.out | sed 's/^/  /'
if [ "$code" -le 1 ]; then ok "nenhum impeditivo"; else erro "achados impeditivos"; fi

secao "2. python compila"
if python3 -m py_compile ferramentas/*.py exemplos/*.py tools/*.py bot-telegram/bin/*.py 2>/dev/null
then ok "todos os .py"; else erro "erro de sintaxe"; fi

secao "3. javascript do plugin"
if node --input-type=module --check < bot-telegram/desktop-plugins/bots-status/plugin.js 2>/dev/null
then ok "plugin.js"; else erro "plugin.js"; fi

secao "4. ferramenta roda sem dependencia (python do sistema)"
STL=$(find "$HOME/Downloads" -iname '*.stl' 2>/dev/null | head -1)
if [ -n "$STL" ] && /usr/bin/python3 ferramentas/analisar3d.py "$STL" >/dev/null 2>&1
then ok "analisar3d.py em STL, sem numpy"; else erro "analisar3d.py em STL"; fi

secao "5. 3MF grande nao estoura a memoria"
BIG=$(find "$HOME/Downloads" -maxdepth 1 -iname '*.3mf' -size +50M 2>/dev/null | head -1)
if [ -n "$BIG" ]; then
  if out=$(/usr/bin/python3 ferramentas/analisar3d.py "$BIG" 2>&1) \
     && printf '%s' "$out" | grep -q "baixa memoria"
  then ok "trocou para modo streaming ($(basename "$BIG"))"
  else erro "modo streaming nao acionou"; fi
else printf '  (sem 3MF grande para testar)\n'; fi

secao "6. links internos do markdown existem"
quebrados=0
for f in README.md docs/*.md; do
  for link in $(grep -oE '\]\(([^)]+\.md)\)' "$f" 2>/dev/null | sed 's/](//;s/)//'); do
    case "$link" in http*) continue ;; esac
    alvo="$(dirname "$f")/$link"
    if [ ! -f "$alvo" ]; then
      printf '  link quebrado: %s -> %s\n' "$f" "$link"
      quebrados=$((quebrados+1))
    fi
  done
done
if [ "$quebrados" -eq 0 ]; then ok "todos os links resolvem"; else erro "$quebrados link(s) quebrado(s)"; fi

secao "7. nomes de caso especifico no CODIGO e na SKILL"
# README e docs podem citar nomes de modelo em exemplos de saida: isso e legitimo.
# O que nao pode e um script ou a skill amarrados a um caso particular.
if grep -rliE 'charizard|togepi' --include='*.py' --include='*.md' ferramentas/ skill/ 2>/dev/null
then erro "codigo/skill preso a um caso especifico"; else ok "ferramentas e skill genericas"; fi

secao "8. .gitignore protege credenciais"
if grep -q '^\.env$' .gitignore; then ok ".env ignorado"; else erro ".env NAO ignorado"; fi

printf '\n===== RESULTADO: %s falha(s) =====\n' "$falhas"
exit $((falhas > 0))
