# Integrar Claude/Hermes ao fluxo Bambu (MCP + Telegram)

Bambu Studio NAO tem plugin nem API para IA. A integracao e ao lado do slicer, via MCP (Hermes tem cliente MCP nativo: `mcp_servers` no config, ferramentas viram `mcp_<servidor>_<ferramenta>`; reiniciar o gateway para carregar).

## Qual MCP serve para que
| Objetivo | Opcao | Nota |
|---|---|---|
| Controlar a impressora + fatiar por CLI + AMS + camera + HMS + pausar/pular peca | `DMontgomery40/bambu-printer-mcp` (npm `bambu-printer-mcp`, Node 24, GPL-2.0) | O mais completo para Bambu; README cita Hermes + Telegram. Variaveis: PRINTER_HOST, BAMBU_SERIAL, BAMBU_TOKEN, BAMBU_MODEL (a1 para o usuario), NOZZLE_DIAMETER. Docs: docs/SETUP.md, docs/FULU.md, docs/SLICING.md. |
| Validar imprimibilidade com renders que o modelo enxerga | `ExaltedTrou6/printable-mcp` | CAD parametrico + render + relatorio + fatia pelo Bambu Studio (tempo/gramas/avisos). |
| So fatiar headless e ler G-code | `ShreddyKrueger75/claude-orcaslicer-mcp` | Usa OrcaSlicer CLI. |
| Apenas controle de impressora, sem fatiar | `griches/bambu-mcp` | Pequeno (dezenas de estrelas), exige LAN Only + Developer Mode, embute certificado extraido do Bambu Connect (area cinzenta). Nao da visao do modelo. |
- Nenhum encontrado exporta imagens por camada do fatiamento: pre-visualizacao por camadas continua sendo do usuario no slicer.
- Conferir estrelas/commits na pagina antes de recomendar; o usuario compara repositorios e se corrige se errar o nome. Nao afirmar "o principal" sem checar.

## Ordem de instalacao (passo a passo, usuario nao e especialista)
1. Bot Telegram: usuario cria no @BotFather (token fica so com ele); ID numerico via @userinfobot.
2. Ligar o bot ao Hermes: usuario roda `hermes gateway setup` (ver hermes-agent/references/troubleshooting.md para o gateway que nao responde).
3. A1: modo LAN (+ Developer Mode se precisar), anotar IP fixo, serial e codigo de acesso. NUNCA pedir/receber o codigo no chat; usuario grava no `.env`/config privada e eu so aponto o caminho.
4. Node 24 (`node -v`), registrar o MCP em `mcp_servers` com `command: npx`, `args: ["-y","bambu-printer-mcp"]` e `env` explicito (Hermes filtra o ambiente do subprocesso). Reiniciar o gateway.
5. Teste somente leitura: status, AMS, erros HMS. Nunca iniciar impressao como teste.
6. So depois: OrcaSlicer/Bambu Studio para fatiamento por CLI.

## Seguranca
- Telegram so para consulta, camera, pausar e pular peca; iniciar impressao so com o usuario presente (bico quente sem supervisao).
- Allowlist so com o ID do usuario.
- Modo LAN desliga a nuvem/Bambu Handy; PC precisa ficar ligado e na mesma rede.
- Confirmar no docs/FULU.md se a A1 usa caminho LAN direto ou a ponte BambuNetwork antes de configurar.
