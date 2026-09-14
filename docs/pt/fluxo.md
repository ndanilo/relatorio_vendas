**Leia em outros idiomas:** [English](../en/flow.md) | **Português (Brasil)**

# Fluxo de acesso

## Acesso humano (navegador)

Use este caminho para validar outro perfil ou conferir IDs de colaboradores na tela.

### 1. Entrar no EVO5

URL típica (ajuste `dns` e filial):

```
https://evo5.w12app.com.br/#/app/{dns}/{id_filial}/inicio/geral
```

Exemplo (`minha-academia`, filial `1`):

```
https://evo5.w12app.com.br/#/app/minha-academia/1/inicio/geral
```

Faça login com usuário e senha do perfil.

### 2. Abrir o relatório de vendas (EVO3)

Após o login, o sistema pode redirecionar para o módulo legado. A tela de vendas fica em:

```
https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS
```

Nessa tela você escolhe colaborador, período e tipos de venda. Os mesmos filtros são replicados pelo script.

### 3. Descobrir o ID do colaborador

No HTML da página, o select de colaboradores costuma ser `#dropFunc`, por exemplo:

```html
<option value="101">COLABORADOR A</option>
```

O `value` é o `id_funcionario` usado em `evo_config.json`.

### 4. Conferir a chamada no DevTools (opcional)

1. Abra DevTools → Network.
2. Aplique o filtro e busque vendas.
3. Localize a requisição `listarVendas`.
4. Confira body (filtros) e headers (`antiforgerytoken`, `dnsfrontend`, `idfilialfrontend`).

---

## Fluxo técnico (script)

O script não usa Playwright. Ele reproduz o fluxo HTTP do navegador com a biblioteca padrão do Python.

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
                                    │ /listarVendas    │  (por colaborador × 2 períodos)
                                    └────────┬─────────┘
                                             ▼
                                    relatorio .txt / .csv (+ e-mail)
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │ API local        │
                                    │ /notifications   │  (WhatsApp: texto + PNG)
                                    └────────┬─────────┘
                                             │ fim do lote (todas as filiais)
                                             ▼
                                    ┌──────────────────┐
                                    │ metas por        │
                                    │ consultor        │  (e-mail + PNG, outra lista)
                                    └──────────────────┘
```

### Passo 1 — Login na API nova

| Item | Valor |
|------|--------|
| URL | `https://evo-abc-api.w12app.com.br/api/v1/auth/login` |
| Método | `POST` |
| Content-Type | `application/json` |
| Origin / Referer | `https://evo5.w12app.com.br` |

Payload (resumo): `dns`, `login`, `senha`, `fusoHorario`, etc.

Resposta importante: `usuario.tokenEvo3` (já vem percent-encoded; **não** reaplicar `urlencode`).

### Passo 2 — Autenticar no módulo legado (evo3), por filial

Repetido para cada item de `filiais` no config:

| Item | Valor |
|------|--------|
| URL base | `https://evo3.w12app.com.br/Login/LogarEvo3` |
| Método | `GET` |
| Query | `TokenEvo3`, `idFilial` (da filial atual), `redirectToView=Index/VENDAS`, `redirectToController=Gerencial`, `redirectToArea=Gerencial` |

A página HTML traz:

```html
<input name="__RequestVerificationToken" type="hidden" value="..." />
```

O script extrai esse valor e envia depois no header `antiforgerytoken` (é assim que o JS do evo3 faz). O header `idfilialfrontend` usa o `id_filial` da filial em processamento.

Se a extração falhar, o HTML é salvo em `debug_pagina_evo3.html` para inspeção.

### Passo 3 — Listar vendas (por filial × colaborador)

| Item | Valor |
|------|--------|
| URL | `https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas` |
| Método | `POST` |
| Content-Type | `application/x-www-form-urlencoded` |
| Referer | `https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS` |
| Origin | `https://evo3.w12app.com.br` |

Headers extras: `antiforgerytoken`, `dnsfrontend`, `idfilialfrontend`, `X-Requested-With: XMLHttpRequest`.

Para cada colaborador da filial, o script chama a API **duas vezes**:

1. Ontem → ontem  
2. Início do período mensal → ontem  

Detalhes dos filtros e das datas: [filtros-e-periodos.md](filtros-e-periodos.md).

### Passo 4 — Notificar por WhatsApp (por filial + resumo)

Depois do e-mail de cada filial, o script desenha o relatório em PNG (Pillow, sem passar por HTML) e chama a API local de notificações:

| Item | Valor |
|------|--------|
| URL | `whatsapp.url` (ex.: `http://127.0.0.1:3001/notifications`) |
| Método | `POST` |
| Content-Type | `multipart/form-data` |
| Autenticação | Header `x-api-key` |
| Campos | `to` (JID), `message` (texto), `file` (PNG, opcional) |

Não há mensagem de fechamento no caminho feliz: se todas as filiais passarem, o lote termina com as imagens já enviadas. Só quando alguma filial falha sai um último aviso, só texto, listando o que não foi enviado. O Pillow é opcional: sem ele a mensagem vai sem anexo. Configuração em [configuracao.md](configuracao.md).

### Passo 5 — Relatório de metas por consultor (opcional, no fim do lote)

Último passo de **todo o lote**, não de cada filial: só depois que todas as filiais despacharam seus relatórios de vendas (e o SMS de resumo saiu) é que as metas são enviadas. Assim quem recebe os dois relatórios lê primeiro as filiais e depois o fechamento por consultor.

Como cada filial roda em um subprocesso próprio, o orquestrador faz duas passadas:

| Passada | Comando | O que despacha |
|---------|---------|----------------|
| 1ª, para toda filial | `--id-filial N --sem-resumo --sem-metas` | Relatório de vendas (e-mail + WhatsApp) |
| SMS | — | Resumo do lote (hoje desligado) |
| 2ª, só com `funcionario_report_ativo` | `--id-filial N --sem-resumo --somente-metas` | Relatório de metas (e-mail + WhatsApp) |

A segunda passada refaz o login e consulta **apenas o mês** — o dia de ontem não é buscado, porque o relatório de metas não usa. Como o período termina em ontem, a consulta é sempre determinística: o resultado é idêntico ao da primeira passada.

Dentro da passada de metas:

1. `dias_uteis.calcular_dias_uteis` monta o calendário do mês do período (segunda a sexta = 1, sábado = 0,5, feriados = 0).
2. `metas_consultores.calcular_metas` cruza cada colaborador com sua `meta_funcionario` e calcula projeção, `%`, falta e falta por dia útil.
3. O e-mail vai para `email.funcionario_report.destinatarios` e o PNG para `whatsapp.funcionario_report.destinatarios` — listas separadas das do relatório de vendas, porque meta individual é dado sensível.

Rodando `gerar_relatorio_vendas.py` direto (sem o orquestrador), tudo acontece em um processo só: as metas ficam acumuladas em memória e saem depois do laço de filiais, sem consulta repetida.

Formato e fórmulas em [relatorio.md](relatorio.md#relatório-de-metas-por-consultor).

---

## URLs usadas (resumo)

| Uso | URL |
|-----|-----|
| App humano (EVO5) | `https://evo5.w12app.com.br/#/app/{dns}/{id_filial}/inicio/geral` |
| Tela de vendas (EVO3) | `https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS` |
| Login API | `https://evo-abc-api.w12app.com.br/api/v1/auth/login` |
| Bridge evo3 | `https://evo3.w12app.com.br/Login/LogarEvo3` |
| Listar vendas | `https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas` |
| Notificação WhatsApp | `whatsapp.url` do `evo_config.json` (API local) |

Endpoints auxiliares vistos no navegador (o script **não** chama):

- `/Gerencial/Gerencial/VerificaRelatorio?id=VENDAS`
- `/Gerencial/Vendas/pVendas`
