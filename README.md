**Read this in other languages:** **English** | [Português (Brasil)](README.pt-BR.md)

# Sales Report — EVO

Python automation that generates per-employee sales reports in the EVO (W12) system, by branch, and sends the result as an HTML email with charts and as a WhatsApp message with the report as an image. Can run manually or on a **scheduled task** (see [docs/en/claude-desktop-automation.md](docs/en/claude-desktop-automation.md) and [docs/en/cursor-automation.md](docs/en/cursor-automation.md)).

## What it does

1. Logs into EVO with credentials from `evo_config.json`.
2. For **each configured branch**: authenticates on evo3 with the corresponding `id_filial`.
3. Fetches sales from **yesterday** and **month-to-yesterday** for the branch employees.
4. Generates a `.txt` and a `.csv` per branch in `relatorios/`.
5. Sends a responsive HTML email per branch (contribution and goal charts), if `email.ativo` is `true`.
6. Notifies each branch on WhatsApp (local API), attaching the same report rendered as a PNG without the donut chart, if `whatsapp.ativo` is `true`. The message is just the title — the numbers are in the image.
7. **After every branch report has gone out**, sends a second report — **consultant goals** — for branches with `funcionario_report_ativo`, to its own recipients: per-consultant goal, month-to-date, month projection, `%` of goal, shortfall, and shortfall per workday, each row flagged `▼ PROJEÇÃO DA META` or `▲ PROJEÇÃO DA META` — the marker, not the wording, says whether the projection reaches the goal. It is always the last dispatch, so whoever receives both reports gets the branches first.
8. If a branch fails, sends a WhatsApp alert at the end of the batch. When everything succeeds there is no closing message. SMS (Brevo) was replaced by this channel and is disabled.

Text and bars use **plain HTML**; the contribution donut is **SVG with shapes only** (no text, to avoid breaking in email clients). The email carries no image attachment — the PNG exists only for WhatsApp, which does not render HTML.

## Requirements

- Python 3.9+
- No required dependencies (standard library only)
- Pillow **optional**, only to draw the image attached on WhatsApp

## Installation

Nothing to install to run the report and send email. To attach the WhatsApp image:

```powershell
py -m pip install -r requirements.txt
```

```bash
python3 -m pip install -r requirements.txt
```

That is all, containers included: there is no browser to download and no system library to install. The Pillow wheel ships precompiled and the font used for drawing is versioned in `assets/fonts`.

Without Pillow the WhatsApp message goes out as text only and the job continues. To skip drawing entirely, set `whatsapp.anexar_imagem` to `false`.

## Configuration

Copy the template and fill in your real data:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

Edit `evo_config.json` at the project root (same folder as the scripts). This file is **not** versioned — it stays on your machine or the automation runner only.

| Field | Purpose |
|-------|---------|
| `dns`, `login`, `senha` | Global EVO credentials |
| `filiais` | Branch list (`id_filial`, `nome`, `colaboradores`, optional `meta_mes` and `funcionario_report_ativo`) |
| `meta_funcionario` | Per employee, inside `colaboradores`. Individual goal for the consultant goal report |
| `email` | Sender, recipient, CC, SMTP, and `funcionario_report` recipients |
| `whatsapp` | Local API + JID list (one message per branch, with the report image) + `funcionario_report` JIDs |
| `dias_uteis` | Workday calendar for the projection (`peso_sabado`, `feriados_extras`) |
| `sms` | Brevo API + phone list. Replaced by WhatsApp, disabled |

**Warning:** `evo_config.json` contains password and SMTP credentials in plain text. Do not share or publish this file. Details in [docs/en/configuration.md](docs/en/configuration.md).

## How to run

All branches, with error isolation (recommended for automation):

```powershell
py rodar_relatorios_filiais.py
```

Direct run (all branches in the same process):

```powershell
py gerar_relatorio_vendas.py
```

Single branch only:

```powershell
py gerar_relatorio_vendas.py --id-filial 1
```

Full rehearsal without dispatching anything: generates files and images and prints the WhatsApp messages, but sends no email, no SMS, and makes no API call.

```powershell
py rodar_relatorios_filiais.py --dry-run
py gerar_relatorio_vendas.py --id-filial 1 --dry-run
```

Only the consultant goal report, or only the sales report (the orchestrator uses both to keep the goal report last — see [docs/en/flow.md](docs/en/flow.md)):

```powershell
py gerar_relatorio_vendas.py --id-filial 1 --somente-metas
py gerar_relatorio_vendas.py --id-filial 1 --sem-metas
```

## Validate email charts

Renders the email in Chromium (Playwright) and checks that SVG and HTML fallback show the same numbers, including simulating a client that strips SVG. Development only — the scheduled job does not need this:

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
py scripts/validar_graficos_email.py
```

Generates `test_grafico_*.png` screenshots (with and without SVG) for visual inspection. Details in [docs/en/report.md](docs/en/report.md).

## Main files

| File | Role |
|------|------|
| `rodar_relatorios_filiais.py` | Orchestrates one call per branch (continues on error) |
| `gerar_relatorio_vendas.py` | Login, API, files, and email delivery |
| `email_relatorio.py` | Responsive HTML, inline SVG, and table fallback (both reports) |
| `imagem_relatorio.py` | Draws the reports as a PNG with Pillow (WhatsApp attachment) |
| `metas_consultores.py` | Consultant goal math (projection, `%`, shortfall) and plain-text report |
| `dias_uteis.py` | Brazilian workday calendar. Also runs standalone: `py dias_uteis.py 2026-09` |
| `notificacao_whatsapp.py` | WhatsApp messages and local API call |
| `assets/fonts/` | Versioned DejaVu Sans, used to draw the PNG |
| `scripts/validar_graficos_email.py` | Chart validation with Playwright |
| `evo_config.example.json` | Configuration template (copy to `evo_config.json`) |
| `evo_config.json` | Real credentials — local, not versioned |
| `requirements.txt` | Pillow (optional, only for the WhatsApp image) |
| `requirements-dev.txt` | Playwright, validation only |
| `relatorios/` | `.txt`, `.csv`, and the WhatsApp PNG outputs |

## Documentation

| Document | Content |
|----------|---------|
| [docs/en/flow.md](docs/en/flow.md) | Human access + technical flow (URLs, tokens) |
| [docs/en/configuration.md](docs/en/configuration.md) | `evo_config.json`, branches, employees, goals, email, and workdays |
| [docs/en/filters-and-periods.md](docs/en/filters-and-periods.md) | API filters and date rules |
| [docs/en/report.md](docs/en/report.md) | HTML email format, charts, consultant goal report, and files |
| [docs/en/cursor-automation.md](docs/en/cursor-automation.md) | Scheduled run via Cursor Automation |
| [docs/en/claude-desktop-automation.md](docs/en/claude-desktop-automation.md) | Scheduled task prompt for Claude Desktop |
