# Relatório de Vendas — EVO

Automação em Python que gera o relatório de vendas por colaborador no sistema EVO (W12), por filial, e envia o resultado por e-mail HTML com gráficos. Pode rodar manualmente ou em **tarefa agendada** (ver [docs/claude-desktop-automation.md](docs/claude-desktop-automation.md) e [docs/cursor-automation.md](docs/cursor-automation.md)).

## O que faz

1. Faz login no EVO com as credenciais de `evo_config.json`.
2. Para **cada filial** configurada: autentica no evo3 com o `id_filial` correspondente.
3. Busca vendas de **ontem** e do **mês até ontem** para os colaboradores da filial.
4. Gera um `.txt` e um `.csv` por filial em `relatorios/`.
5. Envia um e-mail HTML responsivo por filial (gráficos de contribuição e meta), se `email.ativo` estiver `true`.
6. Ao final do lote, se houve e-mail e `sms.ativo` estiver `true`, envia um SMS de resumo por número em `sms.destinatarios` (API Brevo).

Textos e barras usam **HTML puro**; o donut de contribuição é **SVG só com formas** (sem texto, para não quebrar em clientes de e-mail). Não há anexo de imagem.

## Requisitos

- Python 3.9+
- Nenhuma dependência externa (apenas a biblioteca padrão)

## Instalação

Não é preciso instalar nada para rodar o relatório. Para validar os gráficos localmente (ver abaixo):

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
```

## Configuração

Copie o modelo e preencha com seus dados reais:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

Edite `evo_config.json` na raiz do projeto (mesma pasta dos scripts). Esse arquivo **não** é versionado — fica só na sua máquina ou no runner da automação.

| Campo | Uso |
|-------|-----|
| `dns`, `login`, `senha` | Credenciais globais do EVO |
| `filiais` | Lista de filiais (`id_filial`, `nome`, `colaboradores`, `meta_mes` opcional) |
| `email` | Remetente, destinatário, CC e SMTP |
| `sms` | API Brevo + lista de celulares (aviso após o e-mail) |

**Atenção:** `evo_config.json` contém senha e credenciais SMTP em texto puro. Não compartilhe nem publique esse arquivo. Detalhes em [docs/configuracao.md](docs/configuracao.md).

## Como executar

Todas as filiais, com isolamento de erro (recomendado em automação):

```powershell
py rodar_relatorios_filiais.py
```

Execução direta (todas as filiais no mesmo processo):

```powershell
py gerar_relatorio_vendas.py
```

Apenas uma filial:

```powershell
py gerar_relatorio_vendas.py --id-filial 1
```

## Validar os gráficos do e-mail

Renderiza o e-mail no Chromium (Playwright) e confere se o SVG e o fallback HTML mostram os mesmos números, inclusive simulando um cliente que remove SVG:

```powershell
py scripts/validar_graficos_email.py
```

Gera screenshots `test_grafico_*.png` (com e sem SVG) para conferência visual. Detalhes em [docs/relatorio.md](docs/relatorio.md).

## Arquivos principais

| Arquivo | Função |
|---------|--------|
| `rodar_relatorios_filiais.py` | Orquestra uma chamada por filial (continua se houver erro) |
| `gerar_relatorio_vendas.py` | Login, API, arquivos e envio de e-mail |
| `email_relatorio.py` | HTML responsivo, SVG inline e fallback em tabelas |
| `scripts/validar_graficos_email.py` | Validação dos gráficos com Playwright |
| `evo_config.example.json` | Modelo de configuração (copie para `evo_config.json`) |
| `evo_config.json` | Credenciais reais — local, não versionado |
| `requirements.txt` | Sem dependências (biblioteca padrão) |
| `requirements-dev.txt` | Playwright, só para a validação |
| `relatorios/` | Saídas `.txt` e `.csv` |

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/fluxo.md](docs/fluxo.md) | Acesso humano + fluxo técnico (URLs, tokens) |
| [docs/configuracao.md](docs/configuracao.md) | `evo_config.json`, filiais, colaboradores, meta e e-mail |
| [docs/filtros-e-periodos.md](docs/filtros-e-periodos.md) | Filtros da API e regras de data |
| [docs/relatorio.md](docs/relatorio.md) | Formato do e-mail HTML, gráficos e arquivos |
| [docs/cursor-automation.md](docs/cursor-automation.md) | Execução agendada via Cursor Automation |
| [docs/claude-desktop-automation.md](docs/claude-desktop-automation.md) | Prompt de tarefa agendada no Claude Desktop |
