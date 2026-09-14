**Leia em outros idiomas:** [English](README.md) | **Português (Brasil)**

# Relatório de Vendas — EVO

Automação em Python que gera o relatório de vendas por colaborador no sistema EVO (W12), por filial, e envia o resultado por e-mail HTML com gráficos e por WhatsApp com o relatório em imagem. Pode rodar manualmente ou em **tarefa agendada** (ver [docs/pt/claude-desktop-automation.md](docs/pt/claude-desktop-automation.md) e [docs/pt/cursor-automation.md](docs/pt/cursor-automation.md)).

## O que faz

1. Faz login no EVO com as credenciais de `evo_config.json`.
2. Para **cada filial** configurada: autentica no evo3 com o `id_filial` correspondente.
3. Busca vendas de **ontem** e do **mês até ontem** para os colaboradores da filial.
4. Gera um `.txt` e um `.csv` por filial em `relatorios/`.
5. Envia um e-mail HTML responsivo por filial (gráficos de contribuição e meta), se `email.ativo` estiver `true`.
6. Notifica cada filial por WhatsApp (API local), anexando o mesmo relatório renderizado em PNG sem o gráfico circular, se `whatsapp.ativo` estiver `true`. A mensagem é só o título — os números estão na imagem.
7. **Depois que todos os relatórios de filial saíram**, envia um segundo relatório — **metas por consultor** — nas filiais com `funcionario_report_ativo`, para destinatários próprios: meta individual, realizado no mês, projeção do mês, `%` da meta, quanto falta e falta por dia útil, cada linha sinalizada com `▼ ABAIXO DA META` ou `▲ META ATINGIDA`. Ele é sempre o último envio, então quem recebe os dois relatórios vê as filiais primeiro.
8. Se alguma filial falhar, manda um aviso por WhatsApp ao final do lote. Dando tudo certo, não há mensagem de fechamento. O SMS (Brevo) foi substituído por esse canal e está desligado.

Textos e barras usam **HTML puro**; o donut de contribuição é **SVG só com formas** (sem texto, para não quebrar em clientes de e-mail). O e-mail não leva anexo de imagem — o PNG existe só para o WhatsApp, que não renderiza HTML.

## Requisitos

- Python 3.9+
- Nenhuma dependência obrigatória (apenas a biblioteca padrão)
- Pillow **opcional**, só para desenhar a imagem anexada no WhatsApp

## Instalação

Para rodar o relatório e enviar e-mail não é preciso instalar nada. Para anexar a imagem no WhatsApp:

```powershell
py -m pip install -r requirements.txt
```

```bash
python3 -m pip install -r requirements.txt
```

É só isso, inclusive em container: não há navegador para baixar nem biblioteca de sistema para instalar. O wheel do Pillow já vem compilado e a fonte usada no desenho está versionada em `assets/fonts`.

Sem o Pillow a mensagem do WhatsApp sai só com o texto e o job continua. Para nem tentar desenhar, deixe `whatsapp.anexar_imagem` como `false`.

## Configuração

Copie o modelo e preencha com seus dados reais:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

Edite `evo_config.json` na raiz do projeto (mesma pasta dos scripts). Esse arquivo **não** é versionado — fica só na sua máquina ou no runner da automação.

| Campo | Uso |
|-------|-----|
| `dns`, `login`, `senha` | Credenciais globais do EVO |
| `filiais` | Lista de filiais (`id_filial`, `nome`, `colaboradores`, `meta_mes` e `funcionario_report_ativo` opcionais) |
| `meta_funcionario` | Por colaborador, dentro de `colaboradores`. Meta individual do relatório de metas |
| `email` | Remetente, destinatário, CC, SMTP e os destinatários de `funcionario_report` |
| `whatsapp` | API local + lista de JIDs (uma mensagem por filial, com a imagem) + JIDs de `funcionario_report` |
| `dias_uteis` | Calendário de dias úteis da projeção (`peso_sabado`, `feriados_extras`) |
| `sms` | API Brevo + lista de celulares. Substituído pelo WhatsApp, desligado |

**Atenção:** `evo_config.json` contém senha e credenciais SMTP em texto puro. Não compartilhe nem publique esse arquivo. Detalhes em [docs/pt/configuracao.md](docs/pt/configuracao.md).

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

Ensaio geral, sem disparar nada: gera arquivos e imagens e mostra as mensagens do WhatsApp, mas não envia e-mail, SMS nem chama a API.

```powershell
py rodar_relatorios_filiais.py --dry-run
py gerar_relatorio_vendas.py --id-filial 1 --dry-run
```

Só o relatório de metas, ou só o de vendas (o orquestrador usa os dois para deixar as metas por último — veja [docs/pt/fluxo.md](docs/pt/fluxo.md)):

```powershell
py gerar_relatorio_vendas.py --id-filial 1 --somente-metas
py gerar_relatorio_vendas.py --id-filial 1 --sem-metas
```

## Validar os gráficos do e-mail

Renderiza o e-mail no Chromium (Playwright) e confere se o SVG e o fallback HTML mostram os mesmos números, inclusive simulando um cliente que remove SVG. Só para desenvolvimento — o job agendado não precisa disso:

```powershell
py -m pip install -r requirements-dev.txt
py -m playwright install chromium
py scripts/validar_graficos_email.py
```

Gera screenshots `test_grafico_*.png` (com e sem SVG) para conferência visual. Detalhes em [docs/pt/relatorio.md](docs/pt/relatorio.md).

## Arquivos principais

| Arquivo | Função |
|---------|--------|
| `rodar_relatorios_filiais.py` | Orquestra uma chamada por filial (continua se houver erro) |
| `gerar_relatorio_vendas.py` | Login, API, arquivos e envio de e-mail |
| `email_relatorio.py` | HTML responsivo, SVG inline e fallback em tabelas (os dois relatórios) |
| `imagem_relatorio.py` | Desenha os relatórios em PNG com Pillow (anexo do WhatsApp) |
| `metas_consultores.py` | Conta das metas (projeção, `%`, falta) e o relatório em texto |
| `dias_uteis.py` | Calendário de dias úteis do Brasil. Roda avulso: `py dias_uteis.py 2026-09` |
| `notificacao_whatsapp.py` | Mensagens do WhatsApp e chamada da API local |
| `assets/fonts/` | DejaVu Sans versionada, usada no desenho do PNG |
| `scripts/validar_graficos_email.py` | Validação dos gráficos com Playwright |
| `evo_config.example.json` | Modelo de configuração (copie para `evo_config.json`) |
| `evo_config.json` | Credenciais reais — local, não versionado |
| `requirements.txt` | Pillow (opcional, só para a imagem do WhatsApp) |
| `requirements-dev.txt` | Playwright, só para a validação |
| `relatorios/` | Saídas `.txt`, `.csv` e os PNG do WhatsApp |

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/pt/fluxo.md](docs/pt/fluxo.md) | Acesso humano + fluxo técnico (URLs, tokens) |
| [docs/pt/configuracao.md](docs/pt/configuracao.md) | `evo_config.json`, filiais, colaboradores, metas, e-mail e dias úteis |
| [docs/pt/filtros-e-periodos.md](docs/pt/filtros-e-periodos.md) | Filtros da API e regras de data |
| [docs/pt/relatorio.md](docs/pt/relatorio.md) | Formato do e-mail HTML, gráficos, relatório de metas e arquivos |
| [docs/pt/cursor-automation.md](docs/pt/cursor-automation.md) | Execução agendada via Cursor Automation |
| [docs/pt/claude-desktop-automation.md](docs/pt/claude-desktop-automation.md) | Prompt de tarefa agendada no Claude Desktop |
