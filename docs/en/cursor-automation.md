**Read this in other languages:** **English** | [Português (Brasil)](../pt/cursor-automation.md)

# Scheduled run (Cursor Automation)

The report runs as a scheduled **Cursor Automation**. Each run uses a fresh container, but the job has no external dependencies: email charts are inline SVG + HTML tables, generated with the standard library only.

## Ready-to-paste prompt

Paste this text into the Automation instructions field:

```text
You are running the scheduled EVO sales report job.

Steps, in this order:

1. Go to the root of this job's repository.
2. Do not install dependencies: the job uses only the Python 3 standard library.
3. Run the orchestrator (it processes all branches and continues even if
   one fails):
   python3 rodar_relatorios_filiais.py
4. Do not edit evo_config.json unless the run fails due to missing
   configuration. Never invent credentials, goals, or recipients.
5. Reply with a short status: which branches succeeded and which
   failed (with the reason).
```

## What the agent should run

| Step | Command | Why |
|------|---------|-----|
| 1 | `cd` to repository root | Scripts use paths relative to their own directory |
| 2 | `python3 rodar_relatorios_filiais.py` | Processes all branches, isolating errors |
| 3 | Report status | Know which branches failed without opening logs |

## Exit codes

`rodar_relatorios_filiais.py` returns:

- `0` — all branches processed successfully
- `1` — at least one branch failed (others continued normally)

Use this to decide whether the run should be flagged as failed.

## Credentials and configuration

The `evo_config.json` file (EVO login + SMTP + Brevo key) must exist at the repository root in the Automation environment. It is **not** versioned — copy the template before running:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

In automation, inject the file via secret/volume before execution, or keep a filled copy on the runner only.

The agent must **not** create or guess credentials. If the file is missing, the script exits with a clear message and the run should be reported as failed.

Field details in [configuration.md](configuration.md).

## Suggested schedule

Since the report always looks at **yesterday** (see [filters-and-periods.md](filters-and-periods.md)), any time of day works. A morning schedule delivers the previous day's close before business hours.
