**Read this in other languages:** **English** | [Português (Brasil)](../pt/relatorio.md)

# Report format

The script generates **one report per branch** in three formats: HTML email, `.txt`, and `.csv`.

## Email (responsive HTML)

The email is sent in two versions within the same message:

- **HTML** — main version, with cards, charts, and contribution bars
- **Plain text** — same information as the `.txt`, for clients that do not render HTML

### Structure

1. **Header** — branch name, periods (yesterday / month), and generation date  
2. **Highlight cards** — yesterday total and month-to-yesterday total  
3. **Monthly goal** — appears only when `meta_mes` is configured for the branch  
4. **Month contribution** — donut chart + HTML bars with name, value, and `%`  
5. **Yesterday detail** — one block per employee with each sale (customer, item, value, time, payment)  
6. **Footer** — notice that `.txt` and `.csv` are attached  

### Charts

There is no image attachment (CID). Text and bars use **plain HTML** (tables). The contribution donut is **SVG with shapes only** — no `<text>` — because many clients ignore SVG text positioning and merge labels (`MesR$ …`, `…000,0091.1%`).

| Block | Format | When it appears |
|-------|--------|-----------------|
| Goal progress bar | HTML (labels in separate cells + bar) | Only when `meta_mes` is set |
| Contribution donut | SVG (colored slices only) | Whenever there are month sales |
| Month total + ranking | HTML (swatch + name + value + % + own bar) | Always |

If the client removes or ignores SVG (Gmail, Outlook/Word), the donut disappears and the month total and ranking remain — no numbers are lost.

### Chart validation

[`scripts/validar_graficos_email.py`](../../scripts/validar_graficos_email.py) renders the email in Chromium via Playwright and checks, in four fixed scenarios, that SVG and HTML represent the same numbers — including removing `<svg>` from the page to simulate Gmail.

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
py scripts/validar_graficos_email.py
```

Failed scenarios are retried (default: 3 attempts). Screenshots go to `test_grafico_*.png` (with and without SVG) and each scenario's HTML to `test_email_*.html`; both are gitignored.

### Responsiveness

- Max width 600px, centered  
- Table layout with inline styles (compatible with Outlook, Gmail, and mobile apps)  
- On screens up to 480px, highlight cards stack in a single column  
- SVG uses `width:100%` with `viewBox`, so it never overflows the screen  
- No information depends on charts: values and percentages are also in text  

## Generated files

Outputs in `relatorios/`:

- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.txt`
- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.csv`

Example: `relatorio_vendas_unidade-centro_2026-07-31.txt`

The `slug` strips accents, so `Unidade Centro` becomes `unidade-centro`.

The date in the filename is the script **run date** (not yesterday).

### `.txt`

1. Header (`RELATÓRIO DE VENDAS - EVO`, `Filial: …`, date/time)  
2. One section per employee — **Yesterday** detailed + **Month** subtotal only  
3. **TOTAIS** — Yesterday and Month summary  

### `.csv`

Columns include `FILIAL`, `PERIODO` (`Ontem` or `Mes`), `COLABORADOR`, and API fields (`DT_VENDA`, `NOME_COMPRADOR`, `VALOR_VENDA`, etc.).

`PERIODO` stays without accent (`Mes`) because it is a data code read by spreadsheets and integrations. Text shown in the email and `.txt` uses normal accents (`Mês`).

## Email subject

One email per branch (same global recipients):

```
Relatório de Vendas - {nome da filial} - {data_de_ontem}
```
