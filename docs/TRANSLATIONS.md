# Documentation translations

This repository follows the [GitHub community pattern for multilingual docs](https://github.com/nexu-io/open-design/blob/main/TRANSLATIONS.md): English at the repo root, mirrored trees under `docs/en/` and `docs/pt/`, and a language switcher at the top of every doc file.

## Layout

| Location | Language | Role |
|----------|----------|------|
| `README.md` | English | Default README (GitHub home page) |
| `README.pt-BR.md` | Portuguese (Brazil) | Translated README |
| `docs/en/` | English | Full doc set |
| `docs/pt/` | Portuguese (Brazil) | Full doc set |
| `docs/README.md` | — | Language hub (links to `en/` and `pt/`) |

When adding a new locale, create `README.{lang}.md` at the repo root (BCP 47 tag, e.g. `README.es.md`) and a matching `docs/{lang}/` tree with the same documents as `docs/en/`.

## Language switcher

Every README and doc file must start with a switcher linking to all other locales. Bold marks the **current** language.

Example (English doc):

```markdown
**Read this in other languages:** **English** | [Português (Brasil)](../pt/configuration.md)
```

When adding a locale, update the switcher in **every** existing file to include the new language link.

## What to translate

- Headings, paragraphs, table descriptions, warnings, index labels
- **Automation prompts** — copy-paste prompt blocks in `cursor-automation.md` and `claude-desktop-automation.md` must be written in the same language as the surrounding doc (each locale gets its own localized prompt)

## What not to translate

- PowerShell commands, shell commands, and command examples
- JSON examples and config field names (`meta_mes`, `id_filial`, etc.)
- HTTP headers, API field names, endpoint URLs
- File names, directory paths, and repository URLs
- Badge URLs and badge Markdown syntax
- Runtime product output (email subjects, SMS text, report headers) — those stay Portuguese regardless of doc language

## File mapping (en ↔ pt)

| English (`docs/en/`) | Portuguese (`docs/pt/`) |
|----------------------|-------------------------|
| `README.md` | `README.md` |
| `configuration.md` | `configuracao.md` |
| `flow.md` | `fluxo.md` |
| `filters-and-periods.md` | `filtros-e-periodos.md` |
| `report.md` | `relatorio.md` |
| `cursor-automation.md` | `cursor-automation.md` |
| `claude-desktop-automation.md` | `claude-desktop-automation.md` |

New locales should mirror this set. Prefer English filenames in `docs/en/` and locale-appropriate names in other trees when the language uses non-Latin scripts or established local titles.

## Adding or updating a translation

1. Copy structure and section order from the English source (`README.md` or `docs/en/`).
2. Translate prose only; keep code blocks byte-identical unless the block is an automation prompt (translate prompts per locale).
3. Update internal links to stay within the same language folder.
4. Add or update the language switcher at the top of the new file and in every sibling locale file.
5. Add the new locale to `docs/README.md`.

## Maintenance

When English docs change, update every other locale in the same PR (or follow up immediately). Do not leave locales out of sync.
