**Read this in other languages:** **English** | [Português (Brasil)](../pt/claude-desktop-automation.md)

# Scheduled run (Claude Desktop)

> **This prompt is not executed by anything in this repository.**
> It lives in the instructions of an external **Claude Desktop project** and is triggered by a scheduled task there. The text is recorded here only to centralize automation documentation in one place.

The Claude agent opens the repository, runs the orchestrator, and responds with a summary of which branches succeeded and which failed.

## Prompt (literal copy)

This is the text exactly as it appears in the Claude project. When you change it there, update this copy too.

```text
You are running the scheduled EVO sales report job.
Steps, in this order:
1. Go to the root of this job's repository.
2. Install dependencies before anything else:
   python3 -m pip install -r requirements.txt
   (on a Windows runner, use: py -m pip install -r requirements.txt)
3. Confirm the chart dependency loads:
   python3 -c "import matplotlib; print(matplotlib.__version__)"
   If installation fails, STOP and report the error. Do not continue.
4. Run the orchestrator (it processes all branches and continues even if
   one fails):
   python3 rodar_relatorios_filiais.py
5. Do not edit evo_config.json unless the run fails due to missing
   configuration. Never invent credentials, goals, or recipients.
6. Reply with a short status: which branches succeeded, which
   failed (with the reason), and any installation errors.
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

Since `pip install` installs nothing, the step 3 `import matplotlib` only passes if the runner already has the package for another reason. On a clean environment it raises `ModuleNotFoundError`, and the prompt itself tells the agent to stop (`STOP and report the error. Do not continue.`) — the report is never generated.

Likely leftover from an older version when charts were images rendered with `matplotlib`.

If the target is this repository, steps 2 and 3 can be replaced with a dependency-free smoke test:

```text
2. Do not install dependencies: the job uses only the Python 3
   standard library. If any step asks for an external package, STOP and report the error.
3. Confirm the main module loads:
   python3 -c "import gerar_relatorio_vendas"
   (on a Windows runner, use: py -c "import gerar_relatorio_vendas")
   If it fails, STOP and report the error. Do not continue.
```

`requirements-dev.txt` (Playwright) exists only for local chart validation and should not be installed by the scheduled task.
