**Read this in other languages:** **English** | [Português (Brasil)](../pt/claude-desktop-automation.md)

# Scheduled run (Claude Desktop)

> **This prompt is not executed by anything in this repository.**
> It lives in the instructions of an external **Claude Desktop project** and is triggered by a scheduled task there. The text is recorded here only to centralize automation documentation in one place.

The Claude agent opens the repository, runs the orchestrator, and responds with a summary of which branches succeeded and which failed.

## Prompt (literal copy)

This is the text exactly as it appears in the Claude project. When you change it there, update this copy too.

> **Note:** The prompt below is intentionally left in Portuguese — it is operational copy-paste text used as-is in the Claude Desktop project.

```text
Voce esta executando o job agendado de relatorio de vendas do sistema EVO.
Passos, nesta ordem:
1. Va para a raiz do repositorio deste job.
2. Instale as dependencias antes de qualquer outra coisa:
   python3 -m pip install -r requirements.txt
   (em runner Windows, use: py -m pip install -r requirements.txt)
3. Confirme que a dependencia de graficos carrega:
   python3 -c "import matplotlib; print(matplotlib.__version__)"
   Se a instalacao falhar, PARE e relate o erro. Nao siga adiante.
4. Rode o orquestrador (ele processa todas as filiais e continua mesmo se
   uma delas falhar):
   python3 rodar_relatorios_filiais.py
5. Nao edite evo_config.json, a menos que a execucao falhe por configuracao
   ausente. Nunca invente credenciais, metas ou destinatarios.
6. Responda com um status curto: quais filiais tiveram sucesso, quais
   falharam (com o motivo) e qualquer erro de instalacao.
```

## Exit codes

`rodar_relatorios_filiais.py` returns:

- `0` — all branches processed successfully
- `1` — at least one branch failed (others continued normally)

Use this to decide whether the run should be flagged as failed.

## Credentials and configuration

The `evo_config.json` file (EVO login + SMTP + Brevo key) must exist at the repository root on the machine that runs the task.

It is **not** part of the repository: it is in `.gitignore` and never versioned. To create yours, copy the template and fill in real values:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

The agent must **not** create or guess credentials. If the file is missing, the script exits with a clear message and the run should be reported as failed.

Field details in [configuration.md](configuration.md).

## Suggested schedule

Since the report always looks at **yesterday** (see [filters-and-periods.md](filters-and-periods.md)), any time of day works. A morning schedule delivers the previous day's close before business hours.

## Known mismatch: steps 2 and 3

Steps 2 and 3 of the prompt do not match this repository:

- `requirements.txt` **installs nothing** — it explicitly states the report uses only the Python 3 standard library.
- `matplotlib` is not used anywhere in this project. Email charts are **inline SVG with HTML table fallback**, generated with no external dependency.

Since `pip install` installs nothing, the step 3 `import matplotlib` only passes if the runner already has the package for another reason. On a clean environment it raises `ModuleNotFoundError`, and the prompt itself tells the agent to stop (`PARE e relate o erro. Nao siga adiante.`) — the report is never generated.

Likely leftover from an older version when charts were images rendered with `matplotlib`.

If the target is this repository, steps 2 and 3 can be replaced with a dependency-free smoke test:

```text
2. Nao instale dependencias: o job usa apenas a biblioteca padrao do
   Python 3. Se algum passo pedir um pacote externo, PARE e relate o erro.
3. Confirme que o modulo principal carrega:
   python3 -c "import gerar_relatorio_vendas"
   (em runner Windows, use: py -c "import gerar_relatorio_vendas")
   Se falhar, PARE e relate o erro. Nao siga adiante.
```

`requirements-dev.txt` (Playwright) exists only for local chart validation and should not be installed by the scheduled task.
