**Read this in other languages:** **English** | [Português (Brasil)](../pt/relatorio.md)

# Report format

The script generates **one report per branch** in four formats: HTML email, `.txt`, `.csv`, and a PNG for WhatsApp.

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

## Generated files

Outputs in `relatorios/`:

- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.txt`
- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.csv`
- `whatsapp_{slug-da-filial}_YYYY-MM-DD.png` (only when WhatsApp is active)

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
