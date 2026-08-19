**Read this in other languages:** **English** | [Português (Brasil)](README.pt-BR.md)

# Sales Report — EVO

Python automation that generates per-employee sales reports in the EVO (W12) system, by branch, and sends the result as an HTML email with charts. Can run manually or on a **scheduled task** (see [docs/en/claude-desktop-automation.md](docs/en/claude-desktop-automation.md) and [docs/en/cursor-automation.md](docs/en/cursor-automation.md)).

## What it does

1. Logs into EVO with credentials from `evo_config.json`.
2. For **each configured branch**: authenticates on evo3 with the corresponding `id_filial`.
3. Fetches sales from **yesterday** and **month-to-yesterday** for the branch employees.
4. Generates a `.txt` and a `.csv` per branch in `relatorios/`.
5. Sends a responsive HTML email per branch (contribution and goal charts), if `email.ativo` is `true`.
6. At the end of the batch, if email was sent and `sms.ativo` is `true`, sends a summary SMS per number in `sms.destinatarios` (Brevo API).

Text and bars use **plain HTML**; the contribution donut is **SVG with shapes only** (no text, to avoid breaking in email clients). There is no image attachment.

## Requirements

- Python 3.9+
- No external dependencies (standard library only)

## Installation

Nothing to install to run the report. To validate charts locally (see below):

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
```

## Configuration

Copy the template and fill in your real data:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

Edit `evo_config.json` at the project root (same folder as the scripts). This file is **not** versioned — it stays on your machine or the automation runner only.

| Field | Purpose |
|-------|---------|
| `dns`, `login`, `senha` | Global EVO credentials |
| `filiais` | Branch list (`id_filial`, `nome`, `colaboradores`, optional `meta_mes`) |
| `email` | Sender, recipient, CC, and SMTP |
| `sms` | Brevo API + phone list (notification after email) |

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

## Validate email charts

Renders the email in Chromium (Playwright) and checks that SVG and HTML fallback show the same numbers, including simulating a client that strips SVG:

```powershell
py scripts/validar_graficos_email.py
```

Generates `test_grafico_*.png` screenshots (with and without SVG) for visual inspection. Details in [docs/en/report.md](docs/en/report.md).

## Main files

| File | Role |
|------|------|
| `rodar_relatorios_filiais.py` | Orchestrates one call per branch (continues on error) |
| `gerar_relatorio_vendas.py` | Login, API, files, and email delivery |
| `email_relatorio.py` | Responsive HTML, inline SVG, and table fallback |
| `scripts/validar_graficos_email.py` | Chart validation with Playwright |
| `evo_config.example.json` | Configuration template (copy to `evo_config.json`) |
| `evo_config.json` | Real credentials — local, not versioned |
| `requirements.txt` | No dependencies (standard library) |
| `requirements-dev.txt` | Playwright, validation only |
| `relatorios/` | `.txt` and `.csv` outputs |

## Documentation

| Document | Content |
|----------|---------|
| [docs/en/flow.md](docs/en/flow.md) | Human access + technical flow (URLs, tokens) |
| [docs/en/configuration.md](docs/en/configuration.md) | `evo_config.json`, branches, employees, goal, and email |
| [docs/en/filters-and-periods.md](docs/en/filters-and-periods.md) | API filters and date rules |
| [docs/en/report.md](docs/en/report.md) | HTML email format, charts, and files |
| [docs/en/cursor-automation.md](docs/en/cursor-automation.md) | Scheduled run via Cursor Automation |
| [docs/en/claude-desktop-automation.md](docs/en/claude-desktop-automation.md) | Scheduled task prompt for Claude Desktop |
