**Leia em outros idiomas:** [English](../en/report.md) | **Português (Brasil)**

# Formato do relatório

O script gera **um relatório de vendas por filial** em quatro formatos: e-mail HTML, `.txt`, `.csv` e um PNG para o WhatsApp. Nas filiais com `funcionario_report_ativo` sai também um segundo relatório, o [de metas por consultor](#relatório-de-metas-por-consultor), com destinatários próprios.

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

## Relatório de metas por consultor

Segundo relatório, gerado só nas filiais com `funcionario_report_ativo` e enviado para os destinatários de `email.funcionario_report` e `whatsapp.funcionario_report` (veja [configuracao.md](configuracao.md#relatório-de-metas-por-consultor)). Ele responde a uma pergunta que o relatório de vendas não responde: **no ritmo atual, cada consultor bate a meta do mês?**

Reaproveita as vendas do mês que o relatório principal já buscou — não há consulta extra ao EVO.

### Colunas

Por consultor, ordenados do pior `%` para o melhor (quem precisa de atenção aparece primeiro):

| Coluna | Fórmula |
|--------|---------|
| `Meta` | `meta_funcionario` da configuração |
| `Realizado` | Vendas do mês até ontem |
| `Projeção` | `realizado ÷ dias decorridos × dias úteis do mês` |
| `% da meta` | `projeção ÷ meta × 100` |
| `Falta` | `max(meta − realizado, 0)` |
| `Por dia útil` | `falta ÷ dias úteis restantes` |

`Falta` é limitada em zero: quem passou da meta não deve nada, então a coluna nunca mostra dívida negativa — e `Por dia útil` vai a zero junto.

O cartão final traz o **total da filial**. As colunas em reais são somadas; o `%` **não** é a média dos percentuais individuais, é a mesma fórmula aplicada aos totais (`projeção total ÷ soma das metas`). Como todos dividem os mesmos dias úteis, a soma das projeções é igual à projeção da soma, e o total nunca contradiz as linhas acima dele. `Falta` do total é a soma das faltas já limitadas: quem bateu a meta não abate a dívida de quem está atrás.

### Sinalização do `%`

O `%` não é só um número — ele vira uma flag:

| Situação | Selo | Cor |
|----------|------|-----|
| `%` **< 100** — não chega na meta no ritmo atual | `▼ ABAIXO DA META` | Âmbar (a mesma da meta não batida no relatório de vendas) |
| `%` **≥ 100** — chega ou passa da meta | `▲ META ATINGIDA` | Verde |

O marcador e o rótulo em caixa alta acompanham a cor, então a flag sobrevive ao PNG em escala de cinza, ao `.txt` e a quem não distingue as cores. A faixa lateral do cartão e a barra de progresso também usam a cor do status — aqui não há gráfico circular para casar com a cor de identidade do colaborador, e faixa verde em cartão `ABAIXO DA META` diria o contrário do selo.

Atenção a uma diferença que parece inconsistência e não é: `%` compara a **projeção** com a meta, enquanto `Falta` compara o **realizado** com a meta. Um consultor pode estar sinalizado como positivo (no ritmo) e ainda ter uma `Falta` alta no mês.

### Toda barra diz o que mede

O relatório tem duas barras de progresso com formas idênticas e significados diferentes, então cada uma leva o valor, a referência e o percentual escritos ao lado:

| Barra | Rótulo | O que mede |
|-------|--------|-----------|
| Progresso do total, no topo | `Realizado R$ 175.463,25 de R$ 570.000,00` · `30.8%` | Realizado sobre a soma das metas |
| Uma por cartão de consultor | `Projeção R$ 97.508,24 de R$ 200.000,00` · `48.8%` | Projeção sobre a meta individual |

O percentual ao lado da barra do cartão é o mesmo que decide o selo — daí `48.8%` vir junto de `▼ ABAIXO DA META`. Por isso `Projeção` e `% da meta` **não** se repetem na grade de números abaixo: mostrar o mesmo valor duas vezes daria a impressão de serem medidas distintas. A grade fica com `Meta`, `Realizado`, `Falta` e `Por dia útil`.

### Estrutura

1. **Cabeçalho** — `RELATÓRIO DE METAS`, filial, período do mês e data de geração  
2. **Cartões de destaque** — realizado no mês e projeção do mês (com o `%` e o selo)  
3. **Progresso da meta** — barra do realizado sobre a soma das metas  
4. **Metas por consultor** — um cartão por consultor + o cartão do total da filial, cada um com selo, barra rotulada e a grade de números  
5. **Rodapé de dias úteis** — a metadata que sustenta a conta (veja abaixo)  

### Rodapé de dias úteis

O relatório fecha com as três medidas do calendário, em texto pequeno, para que qualquer número acima possa ser conferido:

```
Dias úteis do mês: 23 · Decorridos: 9 · Restantes: 14 — sábado conta 0,5 dia.
Projeção = realizado ÷ dias decorridos × dias úteis do mês. Falta = meta − realizado (mínimo zero). Por dia útil = falta ÷ dias restantes.
```

Os decorridos vão do dia 1 até **ontem** — a mesma janela das vendas —, então decorridos + restantes = total. Regra de peso e feriados em [configuracao.md](configuracao.md#dias-úteis-dias_uteis).

Quem está sem `meta_funcionario` aparece nomeado no rodapé, para a ausência ser explícita em vez de silenciosa.

### Formatos

Mesmos três formatos do relatório de vendas, menos o `.csv`: e-mail HTML (a versão principal), texto puro (alternativa do e-mail e arquivo `.txt`) e o PNG do WhatsApp. Cartões, paleta, casca de 600px e empilhamento no celular são os mesmos — o layout é montado com as mesmas funções de `email_relatorio.py` e `imagem_relatorio.py`.

Assunto do e-mail:

```
Relatório de Metas - {nome da filial} - {data_de_ontem}
```

### Ordem de envio: sempre o último

O relatório de metas é despachado **depois de todos os relatórios de vendas do lote**, e não junto da filial que o originou. Com duas filiais e o relatório de metas em uma delas, quem recebe os três vê nesta ordem:

1. Relatório de vendas da primeira filial
2. Relatório de vendas da segunda filial
3. Relatório de metas

O que decide isso é o orquestrador, e não a filial: como cada filial roda em um subprocesso próprio, ele faz duas passadas — a primeira com `--sem-metas` em todas as filiais, e a segunda com `--somente-metas` só nas que habilitaram o relatório, depois do SMS de resumo. A segunda passada refaz o login e consulta só o mês (não busca o dia de ontem, que ela não usa); como o período vai até ontem, o resultado é sempre o mesmo da primeira passada.

Rodando `gerar_relatorio_vendas.py` direto, sem o orquestrador, a ordem é a mesma: as metas ficam acumuladas e saem depois do laço de filiais.

## Arquivos gerados

Saídas em `relatorios/`:

- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.txt`
- `relatorio_vendas_{slug-da-filial}_YYYY-MM-DD.csv`
- `whatsapp_{slug-da-filial}_YYYY-MM-DD.png` (só quando o WhatsApp está ativo)
- `relatorio_metas_{slug-da-filial}_YYYY-MM-DD.txt` (só com `funcionario_report_ativo`)
- `whatsapp_metas_{slug-da-filial}_YYYY-MM-DD.png` (idem, e com o WhatsApp ativo)

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
