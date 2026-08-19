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

---

## URLs usadas (resumo)

| Uso | URL |
|-----|-----|
| App humano (EVO5) | `https://evo5.w12app.com.br/#/app/{dns}/{id_filial}/inicio/geral` |
| Tela de vendas (EVO3) | `https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS` |
| Login API | `https://evo-abc-api.w12app.com.br/api/v1/auth/login` |
| Bridge evo3 | `https://evo3.w12app.com.br/Login/LogarEvo3` |
| Listar vendas | `https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas` |

Endpoints auxiliares vistos no navegador (o script **não** chama):

- `/Gerencial/Gerencial/VerificaRelatorio?id=VENDAS`
- `/Gerencial/Vendas/pVendas`
