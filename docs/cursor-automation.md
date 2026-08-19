# Execução agendada (Cursor Automation)

O relatório roda como uma **Cursor Automation** agendada. Cada execução usa um container novo, mas o job não tem dependências externas: os gráficos do e-mail são SVG inline + tabelas HTML, gerados só com a biblioteca padrão.

## Prompt pronto para colar

Cole este texto no campo de instruções da Automation:

```text
Voce esta executando o job agendado de relatorio de vendas do sistema EVO.

Passos, nesta ordem:

1. Va para a raiz do repositorio deste job.
2. Nao instale dependencias: o job usa apenas a biblioteca padrao do Python 3.
3. Rode o orquestrador (ele processa todas as filiais e continua mesmo se
   uma delas falhar):
   python3 rodar_relatorios_filiais.py
4. Nao edite evo_config.json, a menos que a execucao falhe por configuracao
   ausente. Nunca invente credenciais, metas ou destinatarios.
5. Responda com um status curto: quais filiais tiveram sucesso e quais
   falharam (com o motivo).
```

## O que o agente deve executar

| Passo | Comando | Por quê |
|-------|---------|---------|
| 1 | `cd` para a raiz do repositório | Os scripts usam caminhos relativos ao próprio diretório |
| 2 | `python3 rodar_relatorios_filiais.py` | Processa todas as filiais, isolando erros |
| 3 | Reportar status | Saber quais filiais falharam sem abrir logs |

## Códigos de saída

`rodar_relatorios_filiais.py` retorna:

- `0` — todas as filiais processadas com sucesso
- `1` — pelo menos uma filial falhou (as demais continuaram normalmente)

Use isso para decidir se a execução deve ser sinalizada como falha.

## Credenciais e configuração

O arquivo `evo_config.json` (login EVO + SMTP + chave Brevo) precisa existir na raiz do repositório no ambiente da Automation. Ele **não** é versionado — copie o modelo antes de rodar:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

Em automação, injete o arquivo por secret/volume antes da execução, ou mantenha uma cópia preenchida apenas no runner.

O agente **não** deve criar nem adivinhar credenciais. Se o arquivo não existir, o script encerra com uma mensagem clara e a execução deve ser reportada como falha.

Detalhes de cada campo em [configuracao.md](configuracao.md).

## Horário sugerido

Como o relatório sempre olha para **ontem** (ver [filtros-e-periodos.md](filtros-e-periodos.md)), qualquer horário do dia funciona. Um agendamento no início da manhã entrega o fechamento do dia anterior antes do expediente.
