# Configuração

Todo o comportamento configurável fica em `evo_config.json` (mesma pasta do script).

Login, DNS e e-mail são **globais**. Filiais e colaboradores ficam em `filiais`.

## Estrutura

```json
{
  "dns": "minha-academia",
  "login": "usuario@exemplo.com.br",
  "senha": "...",

  "filiais": [
    {
      "id_filial": 1,
      "nome": "Unidade Centro",
      "meta_mes": 500000,
      "colaboradores": [
        {"id_funcionario": 101, "nome": "Colaborador A"},
        {"id_funcionario": 102, "nome": "Colaborador B"}
      ]
    },
    {
      "id_filial": 2,
      "nome": "Unidade Zona Sul",
      "colaboradores": [
        {"id_funcionario": 201, "nome": "Colaborador C"}
      ]
    }
  ],

  "email": {
    "ativo": true,
    "remetente": "remetente@exemplo.com",
    "destinatario": "para@exemplo.com",
    "cc": "",
    "smtp_servidor": "smtp-relay.brevo.com",
    "smtp_porta": 587,
    "smtp_usuario": "...",
    "smtp_senha_app": "..."
  },

  "sms": {
    "ativo": true,
    "api_key": "xkeysib-...",
    "sender": "Relatorios",
    "destinatarios": ["5511999999999"],
    "type": "transactional",
    "unicode_enabled": false
  }
}
```

## Campos globais

| Campo | Descrição |
|-------|-----------|
| `dns` | Tenant no EVO (ex.: `minha-academia`) |
| `login` / `senha` | Credenciais do perfil (iguais para todas as filiais) |
| `email` | Remetente, destinatário, CC e SMTP (iguais para todas as filiais) |
| `sms` | Notificação Brevo após o e-mail da filial (opcional) |

## Filiais

Cada item em `filiais`:

| Campo | Descrição |
|-------|-----------|
| `id_filial` | ID numérico da filial no EVO (`idFilial` / `idfilialfrontend`) |
| `nome` | Título da filial (relatório + assunto do e-mail) |
| `meta_mes` | Opcional. Meta de faturamento do mês (número, sem `R$`) |
| `colaboradores` | Lista de vendedores daquela filial |

Cada colaborador:

- `id_funcionario` — ID do select `#dropFunc` na tela de vendas da filial  
- `nome` — rótulo no relatório  

Para adicionar outra filial, inclua outro objeto em `filiais` com seu `id_filial`, `nome` e lista de colaboradores. Não é preciso duplicar login nem e-mail.

### Meta do mês (`meta_mes`)

Valor de referência usado no e-mail para mostrar o quanto do mês já foi atingido.

| Situação | O que aparece no e-mail |
|----------|-------------------------|
| `meta_mes` definido (ex.: `500000`) | Cartão com `% da meta`, quanto falta, e um gráfico de progresso |
| `meta_mes` ausente ou `0` | Apenas totais do dia/mês e a contribuição por colaborador |

A meta é por filial e por mês. Deixe o campo de fora enquanto não tiver um número oficial — o relatório continua funcionando normalmente.

### Formato legado (ainda aceito)

Se `filiais` não existir, o script aceita `id_filial` + `colaboradores` (ou `id_funcionario` / `nome_colaborador`) no nível raiz, como no formato antigo. Prefira migrar para `filiais`.

## E-mail

| Campo | Descrição |
|-------|-----------|
| `ativo` | `true` envia um e-mail **por filial**; `false` só gera arquivos |
| `remetente` | From |
| `destinatario` | To |
| `cc` | Cópia opcional (`""` se não quiser) |
| `smtp_*` | Servidor SMTP |

Assunto dinâmico:

```
Relatório de Vendas - {nome da filial} - {data de ontem}
```

## SMS (Brevo)

Um SMS **por número** em `destinatarios`, ao final do lote (não um por filial).  
Com `rodar_relatorios_filiais.py`, a notificação sai depois que as filiais terminam.  
Se `email.ativo` for `false` (ou nenhum e-mail for enviado), o SMS não é disparado.

| Campo | Descrição |
|-------|-----------|
| `ativo` | `true` envia o SMS de resumo; `false` desliga |
| `api_key` | Chave da API Brevo (`xkeysib-...`), header `api-key` |
| `sender` | Remetente alfanumérico (máx. 11 caracteres), ex.: `Relatorios` |
| `organisation_prefix` | Opcional. Se preenchido, a Brevo prefixa esse texto no SMS |
| `destinatarios` | Lista de celulares com DDI+DDD+número, sem `+` (ex.: `"5511999999999"`) |
| `type` | Em geral `transactional` |
| `unicode_enabled` | `false` (padrão aqui): o script remove acentos do texto |

Endpoint: `POST https://api.brevo.com/v3/transactionalSMS/send`

Conteúdo do SMS (a marca vem de `dns`, ex.: `minha-academia` → `Minha-academia`):

```
Relatorio(s) de Vendas - Minha-academia - DD/MM/AAAA enviado por e-mail. Confira a caixa de entrada.
```

## Segurança

O arquivo guarda senha, credenciais SMTP e chave da API Brevo em texto puro. Mantenha-o privado — copie a partir de `evo_config.example.json` e nunca o publique.
