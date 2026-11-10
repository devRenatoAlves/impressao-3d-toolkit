# impressao-3d-toolkit

**Find out whether a 3D model will print well — before you burn the filament.**

You download a good-looking STL from MakerWorld, hit print, and nine hours
later you own a part with a hole through the wing and joints that do not fit.
This repository is the set of tools I use to know that **beforehand**.

It comes in three layers, and each one is useful on its own:

| Layer | For | Requires |
|---|---|---|
| **1. Command-line tools** | anyone with a 3D printer | Python 3.9+ |
| **2. AI agent skill** | Claude Code or Hermes Agent users | layer 1 |
| **3. Telegram bot** | sending files from your phone | Hermes Agent |

If you only want the tool, **layer 1 is enough and has no dependencies at
all.**

> Documentation is in Portuguese (the author's language), but the tools
> themselves are plain CLI programs — this README covers everything you need to
> use them.

---

## Layer 1 — The tools

```bash
git clone https://github.com/devRenatoAlves/impressao-3d-toolkit.git
cd impressao-3d-toolkit

python3 ferramentas/analisar3d.py my_model.stl
```

No `pip install`, no virtualenv. The analyser uses only the Python standard
library.

### `analisar3d.py` — what the file actually contains

```console
$ python3 ferramentas/analisar3d.py tail_pin.stl

# Relatorio 3D: tail_pin.stl

Escala 100%: 8.7 x 7.5 x 3.3 mm, 0.2 cm3, 24 triangulos
```

On a Bambu Studio `.3mf` it reads far more: the author's print profile, layer
height, wall count, infill, supports, colours per AMS slot, parts per plate,
part names translated from Chinese, and a weight estimate.

| Flag | Default | Meaning |
|---|---|---|
| `--escala N` | `100` | Apply a scale in %, and measure everything already scaled |
| `--mesa WxDxH` | `256x256x250` | Your build volume in mm; warns about what will not fit |
| `--parede-min N` | `1.2` | Minimum acceptable wall thickness, in mm |
| `--espessura` | off | Measure wall thickness (needs numpy/trimesh) |
| `--amostras N` | `1500` | Samples for the thickness measurement |
| `--limite-mb N` | `120` | Above this, switch to low-memory mode. `0` disables |

**Large files do not crash it.** MakerWorld models routinely exceed 150 MB and,
read all at once, exhaust RAM — the process is killed by the OOM killer with no
output at all, which looks like a broken program. The script measures the mesh
size from the zip index (without reading any content) and, above 120 MB,
switches to an incremental parser with constant memory:

```console
$ python3 ferramentas/analisar3d.py Dragonite+20cm.3mf

# Relatorio 3D (modo baixa memoria): Dragonite+20cm.3mf

O arquivo tem ~915 MB de malha descomprimida, acima do limite de 120 MB.
Total: 48 objetos, 9551024 triangulos

Maiores objetos (escala 100%):
  obj 67      183.2 x  360.6 x  179.0 mm   1181322 tri  <-- NAO CABE NA MESA
  obj 61      187.6 x  200.5 x  325.5 mm    544406 tri  <-- NAO CABE NA MESA
```

What you lose in that mode: volume, grams and thickness — the three things that
need the whole mesh in memory. Dimensions and triangle counts stay exact.

### `--espessura`: find the wall that will become a hole

This answers "I scaled it to 70% and it came out with a hole — why?"

With a 0.4 mm nozzle a wall needs **at least 2 extrusion lines, about
0.8 mm**. Below that the slicer has nowhere to put material and leaves the gap
open. Scaling down shrinks walls proportionally: a 1.1 mm wing at 100% becomes
0.77 mm at 70% and disappears.

```bash
pip install numpy trimesh rtree
python3 ferramentas/analisar3d.py model.3mf --escala 75 --espessura --amostras 800
```

> **Read it as a comparison, not a measurement.** It is good for "of these 14
> parts, the wing is the worst". It is not good for "the wing is exactly
> 0.63 mm".
>
> Near-zero values on eyes, tongues and bellies are almost always artifacts —
> thin shells and coincident faces confuse the ray casting. Confirm in the
> slicer's layer preview.

### `gerar_pinos_encaixe.py` — when the model's alignment pins are broken

This solves a specific failure that is hard to notice.

When someone cuts a large model into parts using Bambu Studio's **connectors**,
the file ends up with hexagonal cavities in both halves plus loose pins to
print. If the author then **rescales the project**, the cavities scale with it
but so do the pins — and they become nothing. I have measured pins of
**0.58 × 0.67 × 0.34 mm** for cavities of **10.9 × 12.7 × 4.3 mm**.

The result: two flat faces with empty holes. You glue them, it seems to fit,
and the part slides while the glue cures — misaligning and opening a visible
seam.

```bash
pip install numpy trimesh shapely
python3 ferramentas/gerar_pinos_encaixe.py model.3mf out/
```

The script measures the **real** cavity from the mesh and generates the
matching pin with 0.15 mm clearance per side and 0.3 mm along the length.

It also generates **two test pieces** that print together in about 45 minutes:

1. **Jig** — a thin block with the real cavities subtracted from the original
   mesh (not from an approximation, or the test would be circular), 1.6 mm
   floor, cavity open at the top.
2. **Clearance ladder** — the same pin at 0.10 / 0.15 / 0.20 mm.

> **How to pick the clearance:** the right pin **goes in with thumb pressure
> and does not fall out when you turn the part upside down**. If you needed a
> hammer, the clearance is too tight. If it fell out on its own, too loose.

Slice the tests at 0.20 mm (not 0.12) or the test takes over half an hour.

One thing that confuses people: an "all pins" STL is a **plate of loose
parts** to print, not an assembly. Seeing scattered pins in the slicer is
expected.

### `gerar_relevo_foto.py` — a photo or logo in relief

Turns an image into a plate or keychain with raised relief, splitting colours
into separate STLs for multi-material printing.

```bash
pip install numpy Pillow scipy trimesh
python3 ferramentas/gerar_relevo_foto.py logo.png out/ --altura 3
```

Works best with logos and line art, which have flat colour regions. A regular
photo needs cropping and perspective correction first — see `--help`.

### `preparar_3mf.py` — rescale and reduce colours without opening the slicer

Rescales while preserving each part's position on the plate, writes per-object
overrides, and **removes filaments you do not own**, remapping the slots
correctly.

```python
import sys; sys.path.insert(0, 'ferramentas')
import preparar_3mf as P

# Keep only filaments 1 and 5, renaming the colours. f=1.0 means no rescale.
P.build(src, dst, 1.0, {}, keep=(1, 5), cores=('#FFFFFF', '#000000'))
```

Useful when a model asks for 5 colours and your AMS has 4: consolidate, then
hand-paint the small parts in the colour you dropped.

> ⚠️ **Never pass `printer_model` or `printer_settings_id`** in `global_edits`.
> Studio answers "Invalid configuration file" and rejects the whole file,
> because dozens of other keys (start/end gcode, filament change, compatible
> profiles) are specific to the original printer and are not updated along with
> it. To change printers, open the file and use Studio's own selector.

Another trap, if you plan to modify the code: several keys in
`project_settings.config` store **groups of 2 to 4 values per filament**, not
one value per filament. Pruning that assumes one value per colour leaves the
list at the wrong length and Studio rejects everything — even with the geometry
byte-for-byte identical. The script already handles this.

---

## Layer 2 — The skill

If you use an AI agent that supports Agent Skills (**Claude Code** or **Hermes
Agent**), the `skill/` directory teaches the agent to use the tools above **and
to interpret the results**.

That last part is the whole point. The script says `p5 = 0.63 mm`. The skill
knows what that means:

> The wing at 75% ends up with a ~0.63 mm wall. Your nozzle is 0.4 mm, so it
> needs at least 0.8 mm to close two lines — at this scale the wing will print
> with holes. Go up to 85%, or switch to the 0.2 mm nozzle for that plate only.
> The author notes in the comments that they tested at 80%.

```bash
# Claude Code — personal skills, available in every project
cp -r skill/impressao-3d ~/.claude/skills/

# Hermes Agent
cp -r skill/impressao-3d "${HERMES_HOME:-$HOME/.hermes}/skills/"
```

In both, the agent loads the skill on its own when the conversation matches the
`description`. In Claude Code you can also invoke it directly with
`/impressao-3d`.

**Set your printer** at the top of `SKILL.md` — build volume, nozzle and colour
count ship configured for a Bambu A1.

The skill also carries things the official docs do not cover: how to slice from
the command line to get **real** time and weight, why MakerWorld's REST API
answers plain `curl` while the web page is behind Cloudflare, and the grouped
per-filament keys that make Studio refuse an edited 3MF.

---

## Layer 3 — The Telegram bot

With [Hermes Agent](https://github.com/NousResearch/hermes-agent), the same
agent answers on Telegram. You send the file from your phone and get the
report back — handy when the model is on your PC and you are standing at the
printer.

This layer exists because of a practical problem: **when the bot dies, nothing
tells you.** Telegram has no offline indicator for bots; the chat just goes
quiet. So `bot-telegram/` ships the visibility tooling:

- `bin/status-bots.py` — one command that answers "is it up?", including
  detection of a gateway that is alive but whose event loop has frozen
- `desktop-plugins/bots-status/` — a permanent status dot in the desktop app
- `skill/hermes-messaging-bot-visibility/` — teaches the agent to diagnose it

Guides (Portuguese): [set up the bot](docs/03-bot-telegram-do-zero.md) ·
[status and on/off](docs/04-status-do-bot.md) ·
[troubleshooting](docs/05-problemas-comuns.md)

> ⚠️ **The bot has access to your computer** — terminal, files, browser. The
> allowlist (`TELEGRAM_ALLOWED_USERS`) is not optional. Without it, anyone who
> discovers your bot's username has a shell on your machine.

---

## Before publishing a fork

`tools/audit-leaks.py` scans for secrets and personal data. It exits with code
2 and refuses to approve if it finds a token, API key, private-range IP or
email address.

```bash
python3 tools/audit-leaks.py --nome "Your Name"
```

`tools/verificar.sh` runs the full pre-publish check: leak audit, compilation,
real execution against sample files, markdown links, and whether any tool is
still tied to one specific model.

---

## Disclaimers

I am not affiliated with Bambu Lab, Nous Research or MakerWorld. These tools
read public file formats (3MF is an open standard) and never modify anything
in place — they always write to an output directory.

The clearance and thickness numbers come from **my** printer and **my**
filament. Treat them as a starting point and print the clearance test before
trusting them.

## License

MIT — see [LICENSE](LICENSE).
