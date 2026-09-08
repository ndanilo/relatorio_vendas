**Leia em outros idiomas:** [English](../en/report.md) | **Português (Brasil)**

# Formato do relatório

O script gera **um relatório por filial** em quatro formatos: e-mail HTML, `.txt`, `.csv` e um PNG para o WhatsApp.

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

## Imagem do WhatsApp (PNG)

O WhatsApp não renderiza HTML, então a notificação leva o relatório como imagem. O PNG é **desenhado com Pillow** em [`imagem_relatorio.py`](../../imagem_relatorio.py), a partir dos mesmos dados que alimentam o e-mail.

### Por que não fotografar o HTML

Foi a primeira abordagem, com Chromium via Playwright, e ela foi abandonada por dois motivos medidos em produção:

- **Custo.** O Chromium leva ~3,8s só para subir, e o orquestrador roda um subprocesso por filial, então cada filial pagava esse pedágio. O desenho direto leva ~0,2s.
- **Dependências nativas.** Todo conversor HTML→imagem embute um motor de browser (Chromium, wkhtmltoimage, WeasyPrint) e exige libs de sistema que o `pip` não instala — `libXdamage`, `libnss3`, `libgbm`. Em container enxuto o anexo simplesmente falhava.

O preço é manter um segundo layout: `imagem_relatorio.py` repete a estrutura visual de `email_relatorio.py`. Para limitar a divergência, a paleta (`COR_*`), o `formatar_moeda` e a `cor_colaborador` são importados do módulo do e-mail — mexer numa cor continua valendo para os dois. **Mudanças de estrutura, não:** ao alterar blocos do e-mail, ajuste os dois arquivos.

### O que entra

Mesmo conteúdo do e-mail, menos duas coisas:

- **Sem o donut.** Ele é desenhado sem rótulo nenhum (ver acima), o que faz sentido dentro do e-mail, onde o ranking fica logo abaixo, mas não isolado numa imagem.
- **Sem a menção aos anexos** no rodapé, que fica só em `Relatório automático do sistema EVO.` — o `.txt` e o `.csv` não acompanham a imagem.

Cabeçalho, cartões, meta, total do mês, ranking e o detalhe de ontem continuam. A mensagem que acompanha o PNG é só o título, já que os números estão na própria imagem.

### Fonte

A fonte embutida no Pillow (Aileron) só cobre ASCII: "Anacã Música" e "Contribuição" virariam quadradinhos. Por isso a **DejaVu Sans** (Regular + Bold) está versionada em `assets/fonts/`, com a licença original em `LICENSE_DEJAVU`. Assim o desenho não depende de fonte instalada e sai idêntico no Windows e no container.

| Item | Valor |
|------|-------|
| Arquivo | `relatorios/whatsapp_{slug-da-filial}_YYYY-MM-DD.png` |
| Largura | `whatsapp.imagem_largura` px lógicos (padrão 640) |
| Densidade | `whatsapp.imagem_escala` (padrão 2, ou seja 1280px reais) |
| Tamanho típico | 140-350 KB, altura entre 1000 e 1800 px lógicos |
| Tempo de desenho | ~0,15s em dia parado, ~0,3s com 12 vendas |

Em dia cheio a imagem passa de 1:3 de proporção. A prévia no chat sai cortada, mas a imagem completa abre normalmente ao tocar. Se o texto ficar borrado no celular, suba `imagem_escala`.

Desenhar exige Pillow, que é **opcional**: sem ele a mensagem sai só com o texto e o job segue normalmente.

## Arquivos gerados

Saídas em `relatorios/`:

- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.txt`
- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.csv`
- `whatsapp_{slug-da-filial}_YYYY-MM-DD.png` (só quando o WhatsApp está ativo)

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
