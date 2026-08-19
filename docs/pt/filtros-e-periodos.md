**Leia em outros idiomas:** [English](../en/filters-and-periods.md) | **Português (Brasil)**

# Filtros e períodos

Endpoint: `POST https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas`

## Períodos (referência = ontem)

O script **não** usa a data de hoje nas vendas. A referência é sempre **ontem**.

| Situação | Seção “Ontem” | Seção “Mês” |
|----------|---------------|-------------|
| Rodar em qualquer dia após o dia 1 | Só ontem | Dia 1 do mês atual → ontem |
| Rodar no **dia 1** do mês | Ontem = último dia do mês anterior | Dia 1 do mês anterior → ontem (mês anterior completo) |

Exemplos:

| Script roda em | Ontem | Mês |
|----------------|-------|-----|
| 07/07/2026 | 06/07/2026 | 01/07/2026 → 06/07/2026 |
| 01/07/2026 | 30/06/2026 | 01/06/2026 → 30/06/2026 |

Campos enviados: `Inicio` e `Fim` no formato `dd/mm/yyyy`.

## Filtros do corpo da requisição

### Principais

| Campo | Valor | Significado |
|-------|--------|-------------|
| `IdFuncionario` | ID do colaborador | Vendedor |
| `Inicio` / `Fim` | Calculados | Período |
| `IdFuncionarioComis` | `""` | Sem filtro de comissão |
| `IdsFiliais` | `""` | Filial via header, não neste campo |

### Tipos de venda

| Campo | Valor |
|-------|--------|
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

### IDs específicos (vazios = todos)

`idsContrato`, `idsProduto`, `idsServico` → vazios.

### Paginação / agrupamento

| Campo | Valor |
|-------|--------|
| `page` | `1` |
| `pageSize` | `1000` |
| `group` | `NOME_FUNCIONARIO_VENDA-asc` |
| `aggregate` | `VALOR_VENDA-sum` |
| `sort` / `filter` | vazios |

## Headers implícitos (não vão no body)

| Header | Origem |
|--------|--------|
| `dnsfrontend` | `dns` do config (global) |
| `idfilialfrontend` | `id_filial` da filial em processamento |
| `antiforgerytoken` | Extraído do HTML após `LogarEvo3` daquela filial |

## Em uma frase

Um vendedor por chamada, período ontem ou mês-até-ontem, Contrato + Produto + Serviço + Contratos adicionais, vendas manuais e online, sem débito recorrente, sem troca de contrato, sem contrato secundário.
