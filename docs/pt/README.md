**Leia em outros idiomas:** [English](../en/README.md) | **Português (Brasil)**

# Relatório de Vendas — EVO

Documentação do processo automatizado que gera o relatório de vendas por colaborador no sistema EVO (W12).

## O que este projeto faz

1. Faz login no EVO com as credenciais globais de `evo_config.json`.
2. Para **cada filial** configurada: autentica no evo3 com aquele `id_filial`.
3. Busca vendas de **ontem** e do **mês até ontem** para os colaboradores da filial.
4. Gera um `.txt` e um `.csv` por filial em `relatorios/`.
5. Envia um e-mail HTML responsivo por filial, com gráficos de contribuição e meta, se `email.ativo` estiver `true`.
6. Ao final do lote, se houve e-mail e `sms.ativo` estiver `true`, envia um SMS de resumo por número em `sms.destinatarios` (API Brevo).

## Instalação

Nenhuma: o relatório usa apenas a biblioteca padrão do Python 3. Os gráficos são SVG inline com fallback em tabelas HTML, sem anexo de imagem.

Para validar os gráficos localmente:

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
py scripts/validar_graficos_email.py
```

## Como executar

Todas as filiais, com isolamento de erro (recomendado em automação):

```powershell
py rodar_relatorios_filiais.py
```

Uma execução direta (todas as filiais no mesmo processo):

```powershell
py gerar_relatorio_vendas.py
```

Apenas uma filial:

```powershell
py gerar_relatorio_vendas.py --id-filial 1
```

Requisitos: Python 3.9+ (biblioteca padrão apenas). Configuração: copie `evo_config.example.json` para `evo_config.json` e preencha (veja [configuracao.md](configuracao.md)).

Validar os gráficos do e-mail:

```powershell
py scripts/validar_graficos_email.py
```

## Índice da documentação

| Documento | Conteúdo |
|-----------|----------|
| [fluxo.md](fluxo.md) | Acesso humano + fluxo técnico (URLs, tokens) |
| [configuracao.md](configuracao.md) | `evo_config.json`, filiais, colaboradores, meta e e-mail |
| [filtros-e-periodos.md](filtros-e-periodos.md) | Filtros da API e regras de data |
| [relatorio.md](relatorio.md) | Formato do e-mail HTML, gráficos e arquivos |
| [cursor-automation.md](cursor-automation.md) | Execução agendada via Cursor Automation |
| [claude-desktop-automation.md](claude-desktop-automation.md) | Prompt de tarefa agendada no Claude Desktop |

## Arquivos principais

| Arquivo | Função |
|---------|--------|
| `rodar_relatorios_filiais.py` | Orquestra uma chamada por filial (continua se houver erro) |
| `gerar_relatorio_vendas.py` | Gera o relatório (login, API, arquivos, e-mail) |
| `email_relatorio.py` | Monta o HTML responsivo, os SVG e o fallback em tabelas |
| `scripts/validar_graficos_email.py` | Valida os gráficos renderizando com Playwright |
| `evo_config.example.json` | Modelo de configuração (copie para `evo_config.json`) |
| `evo_config.json` | Credenciais reais — local, não versionado |
| `requirements.txt` | Sem dependências (biblioteca padrão) |
| `requirements-dev.txt` | Playwright, só para a validação |
| `relatorios/` | Saídas `.txt` e `.csv` |

**Atenção:** `evo_config.json` contém senha em texto puro e não é versionado. Use `evo_config.example.json` como modelo.

Diretrizes de tradução: [TRANSLATIONS.md](../TRANSLATIONS.md)
