**Read this in other languages:** **English** | [Português (Brasil)](../pt/relatorio.md)

# Report format

The script generates **one sales report per branch** in four formats: HTML email, `.txt`, `.csv`, and a PNG for WhatsApp. Branches with `funcionario_report_ativo` also get a second report, the [consultant goal report](#consultant-goal-report), with its own recipients.

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

## WhatsApp image (PNG)

WhatsApp does not render HTML, so the notification carries the report as an image. The PNG is **drawn with Pillow** in [`imagem_relatorio.py`](../../imagem_relatorio.py), from the same data that feeds the email.

### Why not screenshot the HTML

That was the first approach, using Chromium via Playwright, and it was dropped for two reasons measured in production:

- **Cost.** Chromium takes ~3.8s just to boot, and the orchestrator runs one subprocess per branch, so every branch paid that toll. Drawing directly takes ~0.2s.
- **Native dependencies.** Every HTML-to-image converter embeds a browser engine (Chromium, wkhtmltoimage, WeasyPrint) and needs system libraries `pip` does not install — `libXdamage`, `libnss3`, `libgbm`. In a lean container the attachment simply failed.

The price is maintaining a second layout: `imagem_relatorio.py` mirrors the visual structure of `email_relatorio.py`. To limit the drift, the palette (`COR_*`), `formatar_moeda`, and `cor_colaborador` are imported from the email module — changing a color still applies to both. **Structural changes are not shared:** when you change email blocks, update both files.

### What goes in

Same content as the email, minus two things:

- **No donut.** It is drawn with no labels at all (see above), which works inside the email where the ranking sits right below it, but not alone in an image.
- **No attachment notice** in the footer, which reads only `Relatório automático do sistema EVO.` — the `.txt` and `.csv` do not travel with the image.

Header, cards, goal, month total, ranking, and yesterday's detail all stay. The message carrying the PNG is just the title, since the numbers are in the image itself.

### Font

The font bundled with Pillow (Aileron) only covers ASCII: "Anacã Música" and "Contribuição" would turn into tofu boxes. That is why **DejaVu Sans** (Regular + Bold) is versioned in `assets/fonts/`, with its original license in `LICENSE_DEJAVU`. Drawing therefore depends on no installed font and looks identical on Windows and in the container.

| Item | Value |
|------|-------|
| File | `relatorios/whatsapp_{slug-da-filial}_YYYY-MM-DD.png` |
| Width | `whatsapp.imagem_largura` logical px (default 640) |
| Density | `whatsapp.imagem_escala` (default 2, i.e. 1280 real px) |
| Typical size | 140-350 KB, height between 1000 and 1800 logical px |
| Drawing time | ~0.15s on a quiet day, ~0.3s with 12 sales |

On a busy day the image exceeds a 1:3 ratio. The chat preview is cropped, but the full image opens normally on tap. If text looks blurry on your phone, raise `imagem_escala`.

Drawing requires Pillow, which is **optional**: without it the message goes out as text only and the job continues.

## Consultant goal report

A second report, generated only for branches with `funcionario_report_ativo` and sent to the recipients in `email.funcionario_report` and `whatsapp.funcionario_report` (see [configuration.md](configuration.md#consultant-goal-report)). It answers a question the sales report does not: **at the current pace, will each consultant hit their monthly goal?**

It reuses the month's sales the main report already fetched — no extra EVO request.

### Columns

Per consultant, sorted from worst `%` to best (whoever needs attention comes first):

| Column | Formula |
|--------|---------|
| `Meta` | `meta_funcionario` from the configuration |
| `Realizado` | Month-to-yesterday sales |
| `Projeção` | `realized ÷ elapsed workdays × workdays in the month` |
| `% da meta` | `projection ÷ goal × 100` |
| `Falta` | `max(goal − realized, 0)` |
| `Por dia útil` | `shortfall ÷ remaining workdays` |

`Falta` is clamped at zero: a consultant past the goal owes nothing, so the column never shows negative debt — and `Por dia útil` drops to zero with it.

The final card carries the **branch total**. The currency columns are summed; the `%` is **not** the average of the individual percentages, it is the same formula applied to the totals (`total projection ÷ sum of goals`). Since everyone shares the same workday count, the sum of the projections equals the projection of the sum, so the total can never contradict the rows above it. The total `Falta` is the sum of the already-clamped shortfalls: someone who beat their goal does not cancel out a colleague's debt.

### The `%` flag

The `%` is not just a number — it becomes a flag:

| Situation | Badge | Color |
|-----------|-------|-------|
| `%` **< 100** — will not reach the goal at the current pace | `▼ ABAIXO DA META` | Amber (the same one the sales report uses for an unmet goal) |
| `%` **≥ 100** — reaches or beats the goal | `▲ META ATINGIDA` | Green |

The marker and the uppercase label travel with the color, so the flag survives the PNG in grayscale, the `.txt`, and color-vision deficiency. The card's side stripe and the progress bar also use the status color — there is no donut here to match the employee's identity color, and a green stripe on an `ABAIXO DA META` card would contradict the badge.

Watch out for one difference that looks like an inconsistency but is not: `%` compares the **projection** against the goal, while `Falta` compares the **realized** amount against the goal. A consultant can be flagged positive (on pace) and still owe a large `Falta` for the month.

### Every bar states what it measures

The report has two progress bars with identical shapes and different meanings, so each one carries its value, its reference, and its percentage written alongside:

| Bar | Label | What it measures |
|-----|-------|------------------|
| Total progress, at the top | `Realizado R$ 175.463,25 de R$ 570.000,00` · `30.8%` | Realized over the sum of the goals |
| One per consultant card | `Projeção R$ 97.508,24 de R$ 200.000,00` · `48.8%` | Projection over the individual goal |

The percentage next to a card's bar is the one that decides the badge — which is why `48.8%` sits beside `▼ ABAIXO DA META`. That is also why `Projeção` and `% da meta` are **not** repeated in the number grid below: showing the same value twice would suggest they are different measurements. The grid keeps `Meta`, `Realizado`, `Falta`, and `Por dia útil`.

### Structure

1. **Header** — `RELATÓRIO DE METAS`, branch, month period, and generation time  
2. **Highlight cards** — realized this month and projected month (with the `%` and the badge)  
3. **Goal progress** — bar of realized over the sum of the goals  
4. **Goals per consultant** — one card per consultant + the branch total card, each with its badge, labelled bar, and number grid  
5. **Workday footer** — the metadata behind the math (see below)  

### Workday footer

The report closes with the three calendar figures, in small text, so every number above can be checked:

```
Dias úteis do mês: 23 · Decorridos: 9 · Restantes: 14 — sábado conta 0,5 dia.
Projeção = realizado ÷ dias decorridos × dias úteis do mês. Falta = meta − realizado (mínimo zero). Por dia útil = falta ÷ dias restantes.
```

Elapsed days run from day 1 through **yesterday** — the same window as the sales — so elapsed + remaining = total. Weighting and holiday rules in [configuration.md](configuration.md#workdays-dias_uteis).

Anyone missing `meta_funcionario` is named in the footer, so the absence is explicit instead of silent.

### Formats

The same formats as the sales report minus the `.csv`: HTML email (the primary version), plain text (the email alternative and the `.txt` file), and the WhatsApp PNG. Cards, palette, the 600px shell, and mobile stacking are identical — the layout is built from the same functions in `email_relatorio.py` and `imagem_relatorio.py`.

Email subject:

```
Relatório de Metas - {nome da filial} - {data_de_ontem}
```

### Dispatch order: always last

The goal report is dispatched **after every sales report in the batch**, not alongside the branch that produced it. With two branches and the goal report enabled on one of them, anyone receiving all three sees this order:

1. Sales report for the first branch
2. Sales report for the second branch
3. Goal report

This is decided by the orchestrator, not by the branch: since each branch runs in its own subprocess, it makes two passes — the first with `--sem-metas` across all branches, and the second with `--somente-metas` only on those that enabled the report, after the summary SMS. The second pass logs in again and queries only the month (it skips yesterday, which it does not use); since the period ends yesterday, the result always matches the first pass.

Running `gerar_relatorio_vendas.py` directly, without the orchestrator, the order is the same: goal reports are accumulated and sent after the branch loop.

## Generated files

Outputs in `relatorios/`:

- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.txt`
- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.csv`
- `whatsapp_{slug-da-filial}_YYYY-MM-DD.png` (only when WhatsApp is active)
- `relatorio_metas_{slug-da-filial}_YYYY-MM-DD.txt` (only with `funcionario_report_ativo`)
- `whatsapp_metas_{slug-da-filial}_YYYY-MM-DD.png` (same, plus WhatsApp active)

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
