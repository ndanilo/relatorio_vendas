**Read this in other languages:** **English** | [Português (Brasil)](../pt/fluxo.md)

# Access flow

## Human access (browser)

Use this path to validate another profile or check employee IDs on screen.

### 1. Log into EVO5

Typical URL (adjust `dns` and branch):

```
https://evo5.w12app.com.br/#/app/{dns}/{id_filial}/inicio/geral
```

Example (`minha-academia`, branch `1`):

```
https://evo5.w12app.com.br/#/app/minha-academia/1/inicio/geral
```

Log in with the profile username and password.

### 2. Open the sales report (EVO3)

After login, the system may redirect to the legacy module. The sales screen is at:

```
https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS
```

On that screen you choose employee, period, and sale types. The script replicates the same filters.

### 3. Find the employee ID

In the page HTML, the employee select is usually `#dropFunc`, for example:

```html
<option value="101">COLABORADOR A</option>
```

The `value` is the `id_funcionario` used in `evo_config.json`.

### 4. Inspect the call in DevTools (optional)

1. Open DevTools → Network.
2. Apply the filter and search for sales.
3. Locate the `listarVendas` request.
4. Check body (filters) and headers (`antiforgerytoken`, `dnsfrontend`, `idfilialfrontend`).

---

## Technical flow (script)

The script does not use Playwright. It reproduces the browser HTTP flow with the Python standard library.

```
┌─────────────┐     POST login      ┌──────────────────┐
│  evo_config │ ──────────────────► │ evo-abc-api      │
│  login/senha│                     │ /auth/login      │
└─────────────┘                     └────────┬─────────┘
                                             │ tokenEvo3
                                             ▼
                                    ┌──────────────────┐
                                    │ evo3             │
                                    │ /Login/LogarEvo3 │
                                    └────────┬─────────┘
                                             │ HTML + __RequestVerificationToken
                                             ▼
                                    ┌──────────────────┐
                                    │ evo3             │
                                    │ /listarVendas    │  (per employee × 2 periods)
                                    └────────┬─────────┘
                                             ▼
                                    relatorio .txt / .csv (+ e-mail)
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │ local API        │
                                    │ /notifications   │  (WhatsApp: text + PNG)
                                    └────────┬─────────┘
                                             │ end of batch (all branches)
                                             ▼
                                    ┌──────────────────┐
                                    │ consultant goal  │
                                    │ report           │  (email + PNG, other list)
                                    └──────────────────┘
```

### Step 1 — Login on the new API

| Item | Value |
|------|-------|
| URL | `https://evo-abc-api.w12app.com.br/api/v1/auth/login` |
| Method | `POST` |
| Content-Type | `application/json` |
| Origin / Referer | `https://evo5.w12app.com.br` |

Payload (summary): `dns`, `login`, `senha`, `fusoHorario`, etc.

Important response: `usuario.tokenEvo3` (already percent-encoded; **do not** reapply `urlencode`).

### Step 2 — Authenticate on the legacy module (evo3), per branch

Repeated for each item in `filiais` in the config:

| Item | Value |
|------|-------|
| Base URL | `https://evo3.w12app.com.br/Login/LogarEvo3` |
| Method | `GET` |
| Query | `TokenEvo3`, `idFilial` (current branch), `redirectToView=Index/VENDAS`, `redirectToController=Gerencial`, `redirectToArea=Gerencial` |

The HTML page includes:

```html
<input name="__RequestVerificationToken" type="hidden" value="..." />
```

The script extracts this value and sends it later in the `antiforgerytoken` header (same as evo3 JS). The `idfilialfrontend` header uses the `id_filial` of the branch being processed.

If extraction fails, the HTML is saved to `debug_pagina_evo3.html` for inspection.

### Step 3 — List sales (per branch × employee)

| Item | Value |
|------|-------|
| URL | `https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas` |
| Method | `POST` |
| Content-Type | `application/x-www-form-urlencoded` |
| Referer | `https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS` |
| Origin | `https://evo3.w12app.com.br` |

Extra headers: `antiforgerytoken`, `dnsfrontend`, `idfilialfrontend`, `X-Requested-With: XMLHttpRequest`.

For each employee in the branch, the script calls the API **twice**:

1. Yesterday → yesterday  
2. Start of monthly period → yesterday  

Filter and date details: [filters-and-periods.md](filters-and-periods.md).

### Step 4 — Notify on WhatsApp (per branch + summary)

After each branch email, the script draws the report as a PNG (Pillow, no HTML involved) and calls the local notification API:

| Item | Value |
|------|--------|
| URL | `whatsapp.url` (e.g. `http://127.0.0.1:3001/notifications`) |
| Method | `POST` |
| Content-Type | `multipart/form-data` |
| Auth | `x-api-key` header |
| Fields | `to` (JID), `message` (text), `file` (PNG, optional) |

There is no closing message on the happy path: if every branch succeeds, the batch ends with the images already sent. Only when a branch fails does a final text-only alert go out listing what was not sent. Pillow is optional: without it the message goes without the attachment. Configuration in [configuration.md](configuration.md).

### Step 5 — Consultant goal report (optional, at the end of the batch)

The last step of **the whole batch**, not of each branch: goal reports only go out after every branch has dispatched its sales report (and the summary SMS has been sent). That way anyone receiving both reports reads the branches first and the per-consultant closing last.

Since each branch runs in its own subprocess, the orchestrator makes two passes:

| Pass | Command | What it dispatches |
|------|---------|--------------------|
| 1st, every branch | `--id-filial N --sem-resumo --sem-metas` | Sales report (email + WhatsApp) |
| SMS | — | Batch summary (currently disabled) |
| 2nd, only with `funcionario_report_ativo` | `--id-filial N --sem-resumo --somente-metas` | Goal report (email + WhatsApp) |

The second pass logs in again and queries **only the month** — yesterday is not fetched, because the goal report does not use it. Since the period ends yesterday, the query is deterministic: the result is identical to the first pass.

Inside the goal pass:

1. `dias_uteis.calcular_dias_uteis` builds the calendar for the period's month (Monday to Friday = 1, Saturday = 0.5, holidays = 0).
2. `metas_consultores.calcular_metas` matches each employee with their `meta_funcionario` and computes projection, `%`, shortfall, and shortfall per workday.
3. The email goes to `email.funcionario_report.destinatarios` and the PNG to `whatsapp.funcionario_report.destinatarios` — lists separate from the sales report's, since individual goals are sensitive.

Running `gerar_relatorio_vendas.py` directly (without the orchestrator), everything happens in a single process: goal reports are held in memory and sent after the branch loop, with no repeated query.

Format and formulas in [report.md](report.md#consultant-goal-report).

---

## URLs used (summary)

| Purpose | URL |
|---------|-----|
| Human app (EVO5) | `https://evo5.w12app.com.br/#/app/{dns}/{id_filial}/inicio/geral` |
| Sales screen (EVO3) | `https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS` |
| API login | `https://evo-abc-api.w12app.com.br/api/v1/auth/login` |
| evo3 bridge | `https://evo3.w12app.com.br/Login/LogarEvo3` |
| List sales | `https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas` |
| WhatsApp notification | `whatsapp.url` from `evo_config.json` (local API) |

Auxiliary endpoints seen in the browser (the script **does not** call them):

- `/Gerencial/Gerencial/VerificaRelatorio?id=VENDAS`
- `/Gerencial/Vendas/pVendas`
