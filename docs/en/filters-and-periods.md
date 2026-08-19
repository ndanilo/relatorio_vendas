**Read this in other languages:** **English** | [Português (Brasil)](../pt/filtros-e-periodos.md)

# Filters and periods

Endpoint: `POST https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas`

## Periods (reference = yesterday)

The script does **not** use today's date for sales. The reference is always **yesterday**.

| Situation | "Yesterday" section | "Month" section |
|-----------|----------------------|-----------------|
| Run on any day after the 1st | Yesterday only | 1st of current month → yesterday |
| Run on the **1st** of the month | Yesterday = last day of previous month | 1st of previous month → yesterday (full previous month) |

Examples:

| Script runs on | Yesterday | Month |
|----------------|-----------|-------|
| 07/07/2026 | 06/07/2026 | 01/07/2026 → 06/07/2026 |
| 01/07/2026 | 30/06/2026 | 01/06/2026 → 30/06/2026 |

Fields sent: `Inicio` and `Fim` in `dd/mm/yyyy` format.

## Request body filters

### Main

| Field | Value | Meaning |
|-------|-------|---------|
| `IdFuncionario` | Employee ID | Salesperson |
| `Inicio` / `Fim` | Computed | Period |
| `IdFuncionarioComis` | `""` | No commission filter |
| `IdsFiliais` | `""` | Branch via header, not this field |

### Sale types

| Field | Value |
|-------|-------|
| `Contrato` | `true` |
| `Produto` | `true` |
| `Servico` | `true` |
| `DebitoRecorrente` | `false` |
| `TrocaDeContrato` | `false` |
| `ContratosAdicionais` | `true` |
| `FL_MANUAIS` | `true` |
| `FL_ONLINE` | `true` |
| `FL_CONTRATO_SECUNDARIO` | `false` |
| `ConsideraEspecial` | `true` |

### Specific IDs (empty = all)

`idsContrato`, `idsProduto`, `idsServico` → empty.

### Pagination / grouping

| Field | Value |
|-------|-------|
| `page` | `1` |
| `pageSize` | `1000` |
| `group` | `NOME_FUNCIONARIO_VENDA-asc` |
| `aggregate` | `VALOR_VENDA-sum` |
| `sort` / `filter` | empty |

## Implicit headers (not in the body)

| Header | Source |
|--------|--------|
| `dnsfrontend` | `dns` from config (global) |
| `idfilialfrontend` | `id_filial` of the branch being processed |
| `antiforgerytoken` | Extracted from HTML after that branch's `LogarEvo3` |

## In one sentence

One salesperson per call, yesterday or month-to-yesterday period, Contract + Product + Service + Additional contracts, manual and online sales, no recurring debit, no contract swap, no secondary contract.
