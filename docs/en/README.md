**Read this in other languages:** **English** | [Português (Brasil)](../pt/README.md)

# Sales Report — EVO

Documentation for the automated process that generates per-employee sales reports in the EVO (W12) system.

## What this project does

1. Logs into EVO with global credentials from `evo_config.json`.
2. For **each configured branch**: authenticates on evo3 with that branch's `id_filial`.
3. Fetches sales from **yesterday** and **month-to-yesterday** for the branch employees.
4. Generates a `.txt` and a `.csv` per branch in `relatorios/`.
5. Sends a responsive HTML email per branch, with contribution and goal charts, if `email.ativo` is `true`.
6. At the end of the batch, if email was sent and `sms.ativo` is `true`, sends a summary SMS per number in `sms.destinatarios` (Brevo API).

## Installation

None: the report uses only the Python 3 standard library. Charts are inline SVG with HTML table fallback, with no image attachment.

To validate charts locally:

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
py scripts/validar_graficos_email.py
```

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

Requirements: Python 3.9+ (standard library only). Configuration: copy `evo_config.example.json` to `evo_config.json` and fill in (see [configuration.md](configuration.md)).

Validate email charts:

```powershell
py scripts/validar_graficos_email.py
```

## Documentation index

| Document | Content |
|----------|---------|
| [flow.md](flow.md) | Human access + technical flow (URLs, tokens) |
| [configuration.md](configuration.md) | `evo_config.json`, branches, employees, goal, and email |
| [filters-and-periods.md](filters-and-periods.md) | API filters and date rules |
| [report.md](report.md) | HTML email format, charts, and files |
| [cursor-automation.md](cursor-automation.md) | Scheduled run via Cursor Automation |
| [claude-desktop-automation.md](claude-desktop-automation.md) | Scheduled task prompt for Claude Desktop |

## Main files

| File | Role |
|------|------|
| `rodar_relatorios_filiais.py` | Orchestrates one call per branch (continues on error) |
| `gerar_relatorio_vendas.py` | Generates the report (login, API, files, email) |
| `email_relatorio.py` | Builds responsive HTML, SVG, and table fallback |
| `scripts/validar_graficos_email.py` | Validates charts by rendering with Playwright |
| `evo_config.example.json` | Configuration template (copy to `evo_config.json`) |
| `evo_config.json` | Real credentials — local, not versioned |
| `requirements.txt` | No dependencies (standard library) |
| `requirements-dev.txt` | Playwright, validation only |
| `relatorios/` | `.txt` and `.csv` outputs |

**Warning:** `evo_config.json` contains a password in plain text and is not versioned. Use `evo_config.example.json` as a template.

Translation guidelines: [TRANSLATIONS.md](../TRANSLATIONS.md)
