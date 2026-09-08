**Read this in other languages:** **English** | [Português (Brasil)](../pt/configuracao.md)

# Configuration

All configurable behavior lives in `evo_config.json` (same folder as the script).

Login, DNS, and email are **global**. Branches and employees live under `filiais`.

## Structure

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
    "ativo": false,
    "api_key": "xkeysib-...",
    "sender": "Relatorios",
    "destinatarios": ["5511999999999"],
    "type": "transactional",
    "unicode_enabled": false
  },

  "whatsapp": {
    "ativo": true,
    "url": "http://127.0.0.1:3001/notifications",
    "api_key": "...",
    "destinatarios": ["5511999999999@c.us"],
    "anexar_imagem": true,
    "imagem_largura": 640,
    "imagem_escala": 2,
    "timeout": 60
  }
}
```

## Global fields

| Field | Description |
|-------|-------------|
| `dns` | EVO tenant (e.g. `minha-academia`) |
| `login` / `senha` | Profile credentials (same for all branches) |
| `email` | Sender, recipient, CC, and SMTP (same for all branches) |
| `whatsapp` | Local API notification: one per branch, with the report as an image |
| `sms` | Brevo notification. Replaced by WhatsApp; kept disabled |

## Branches

Each item in `filiais`:

| Field | Description |
|-------|-------------|
| `id_filial` | Numeric branch ID in EVO (`idFilial` / `idfilialfrontend`) |
| `nome` | Branch title (report + email subject) |
| `meta_mes` | Optional. Monthly revenue goal (number, no `R$`) |
| `colaboradores` | List of salespeople for that branch |

Each employee:

- `id_funcionario` — ID from the `#dropFunc` select on the branch sales screen  
- `nome` — label in the report  

To add another branch, include another object in `filiais` with its `id_filial`, `nome`, and employee list. No need to duplicate login or email.

### Monthly goal (`meta_mes`)

Reference value used in the email to show how much of the month has been reached.

| Situation | What appears in the email |
|-----------|---------------------------|
| `meta_mes` set (e.g. `500000`) | Card with `% of goal`, amount remaining, and a progress chart |
| `meta_mes` missing or `0` | Day/month totals and per-employee contribution only |

The goal is per branch and per month. Omit the field until you have an official number — the report keeps working normally.

### Legacy format (still accepted)

If `filiais` is missing, the script accepts `id_filial` + `colaboradores` (or `id_funcionario` / `nome_colaborador`) at the root level, as in the old format. Prefer migrating to `filiais`.

## Email

| Field | Description |
|-------|-------------|
| `ativo` | `true` sends one email **per branch**; `false` generates files only |
| `remetente` | From |
| `destinatario` | To |
| `cc` | Optional copy (`""` if not needed) |
| `smtp_*` | SMTP server |

Dynamic subject:

```
Relatório de Vendas - {nome da filial} - {data de ontem}
```

## WhatsApp (local API)

The primary notification channel. Two different kinds of message:

| When | Content |
|------|---------|
| One **per branch**, right after the email | The report as a PNG, with the title as caption |
| One **alert** at the end of the batch, only if something fails | Text only: which branches were not sent and why |

On the happy path only the per-branch messages go out — there is no closing summary, since the images already say everything.

The image caption is deliberately short — the numbers are already in the PNG, so there is no point repeating them as text:

```
*RELATÓRIO DE VENDAS*
📍 _Anacã Música_ · 07/09/2026
```

The PNG is drawn with Pillow from the same data that feeds the email, with the same content and palette: header, KPIs, goal, contribution, and yesterday's detail. Left out are the donut chart (it carries no labels, so it does not break in email clients, and would be unreadable on its own) and the attachment notice in the footer, since `.txt` and `.csv` do not travel with the image.

| Field | Description |
|-------|-------------|
| `ativo` | `true` sends the notifications; `false` disables the channel |
| `url` | Local API endpoint (e.g. `http://127.0.0.1:3001/notifications`) |
| `api_key` | Sent in the `x-api-key` header |
| `destinatarios` | List of JIDs. Contacts end in `@c.us`, groups in `@g.us` |
| `anexar_imagem` | `false` sends text only, skipping the PNG render |
| `imagem_largura` | Render width in CSS px (default `640`) |
| `imagem_escala` | Density factor. `2` doubles the pixels for sharper text |
| `timeout` | Seconds to wait for the API (default `60`) |

Generated request (`multipart/form-data`, fields `to`, `message`, and `file`):

```
POST /notifications
x-api-key: ...
Content-Type: multipart/form-data; boundary=----relatorioVendas...
```

Pillow is **optional**: without it, or if drawing fails, the message goes out as text only and the job continues. Install with `python3 -m pip install -r requirements.txt` — no browser and no system library involved.

To preview messages and images without sending anything, use `--dry-run`:

```powershell
py rodar_relatorios_filiais.py --dry-run
py gerar_relatorio_vendas.py --id-filial 1 --dry-run
```

## SMS (Brevo) — disabled

Replaced by WhatsApp. The code stays in the project and works again by flipping `sms.ativo` to `true`.

One SMS **per number** in `destinatarios`, at the end of the batch (not one per branch).  
With `rodar_relatorios_filiais.py`, the notification is sent after branches finish.  
If `email.ativo` is `false` (or no email was sent), SMS is not triggered.

| Field | Description |
|-------|-------------|
| `ativo` | `true` sends the summary SMS; `false` disables it |
| `api_key` | Brevo API key (`xkeysib-...`), header `api-key` |
| `sender` | Alphanumeric sender (max 11 characters), e.g. `Relatorios` |
| `organisation_prefix` | Optional. If set, Brevo prefixes this text in the SMS |
| `destinatarios` | List of mobile numbers with country+area code, no `+` (e.g. `"5511999999999"`) |
| `type` | Usually `transactional` |
| `unicode_enabled` | `false` (default here): the script strips accents from the text |

Endpoint: `POST https://api.brevo.com/v3/transactionalSMS/send`

SMS content (brand comes from `dns`, e.g. `minha-academia` → `Minha-academia`):

```
Relatorio(s) de Vendas - Minha-academia - DD/MM/AAAA enviado por e-mail. Confira a caixa de entrada.
```

## Security

The file stores password, SMTP credentials, the Brevo API key, and the local WhatsApp API key in plain text. Keep it private — copy from `evo_config.example.json` and never publish it.
