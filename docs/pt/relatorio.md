**Leia em outros idiomas:** [English](../en/report.md) | **Português (Brasil)**

# Formato do relatório

O script gera **um relatório por filial** em três formatos: e-mail HTML, `.txt` e `.csv`.

## E-mail (HTML responsivo)

O e-mail é enviado em duas versões dentro da mesma mensagem:

- **HTML** — versão principal, com cartões, gráficos e barras de contribuição
- **Texto puro** — mesma informação do `.txt`, usada por clientes que não exibem HTML

### Estrutura

1. **Cabeçalho** — nome da filial, períodos (ontem / mês) e data de geração  
2. **Cartões de destaque** — total de ontem e total do mês até ontem  
3. **Meta do mês** — só aparece quando `meta_mes` está configurado na filial  
4. **Contribuição no mês** — gráfico de rosca + barras em HTML com nome, valor e `%`  
5. **Detalhe de ontem** — um bloco por colaborador com cada venda (cliente, item, valor, hora, pagamento)  
6. **Rodapé** — aviso de que `.txt` e `.csv` estão anexados  

### Gráficos

Não há anexo de imagem (CID). Textos e barras usam **HTML puro** (tabelas). O donut de contribuição é **SVG só com formas** — sem `<text>` — porque vários clientes ignoram o posicionamento do texto SVG e colam os rótulos (`MesR$ …`, `…000,0091.1%`).

| Bloco | Formato | Quando aparece |
|-------|---------|----------------|
| Barra de progresso da meta | HTML (rótulos em células separadas + barra) | Só quando `meta_mes` está definido |
| Donut de contribuição | SVG (apenas fatias coloridas) | Sempre que houver venda no mês |
| Total do mês + ranking | HTML (swatch + nome + valor + % + barra própria) | Sempre |

Se o cliente remove ou ignora SVG (Gmail, Outlook/Word), o donut some e restam o total do mês e o ranking — nenhum número se perde.

### Validação dos gráficos

[`scripts/validar_graficos_email.py`](../../scripts/validar_graficos_email.py) renderiza o e-mail no Chromium via Playwright e confere, em quatro cenários fixos, se SVG e HTML representam os mesmos números — inclusive removendo os `<svg>` da página para simular o Gmail.

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
py scripts/validar_graficos_email.py
```

Os cenários que falharem são repetidos (padrão: 3 tentativas). Screenshots ficam em `test_grafico_*.png` (com e sem SVG) e o HTML de cada cenário em `test_email_*.html`; ambos são ignorados pelo git.

### Responsividade

- Largura máxima de 600px, centralizada  
- Layout em tabelas com estilos inline (compatível com Outlook, Gmail e apps móveis)  
- Em telas até 480px os cartões de destaque empilham em coluna única  
- Os SVG usam `width:100%` com `viewBox`, então nunca estouram a tela  
- Nenhuma informação depende de gráfico: valores e percentuais também estão em texto  

## Arquivos gerados

Saídas em `relatorios/`:

- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.txt`
- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.csv`

Exemplo: `relatorio_vendas_unidade-centro_2026-07-31.txt`

O `slug` remove acentos, então `Unidade Centro` vira `unidade-centro`.

A data no nome do arquivo é o **dia de execução** do script (não ontem).

### `.txt`

1. Cabeçalho (`RELATÓRIO DE VENDAS - EVO`, `Filial: …`, data/hora)  
2. Uma seção por colaborador — **Ontem** detalhado + **Mês** só com subtotal  
3. **TOTAIS** — resumo de Ontem e Mês  

### `.csv`

Colunas incluem `FILIAL`, `PERIODO` (`Ontem` ou `Mes`), `COLABORADOR` e os campos da API (`DT_VENDA`, `NOME_COMPRADOR`, `VALOR_VENDA`, etc.).

`PERIODO` continua sem acento (`Mes`) porque é um código de dado, lido por planilhas e integrações. Os textos exibidos no e-mail e no `.txt` usam acentuação normal (`Mês`).

## Assunto do e-mail

Um e-mail por filial (mesmos destinatários globais):

```
Relatório de Vendas - {nome da filial} - {data_de_ontem}
```
