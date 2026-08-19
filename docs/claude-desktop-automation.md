# Execução agendada (Claude Desktop)

> **Este prompt não é executado por nada neste repositório.**
> Ele vive nas instruções de um **projeto do Claude Desktop**, externo a este código, e é disparado por uma tarefa agendada de lá. O texto está registrado aqui apenas para centralizar a documentação da automação em um único lugar.

O agente do Claude abre o repositório, executa o orquestrador e responde com um resumo de quais filiais tiveram sucesso e quais falharam.

## Prompt (cópia literal)

Este é o texto exatamente como está no projeto do Claude. Ao alterá-lo lá, atualize esta cópia também.

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

## Códigos de saída

`rodar_relatorios_filiais.py` retorna:

- `0` — todas as filiais processadas com sucesso
- `1` — pelo menos uma filial falhou (as demais continuaram normalmente)

Use isso para decidir se a execução deve ser sinalizada como falha.

## Credenciais e configuração

O arquivo `evo_config.json` (login EVO + SMTP + chave Brevo) precisa existir na raiz do repositório, na máquina que roda a tarefa.

Ele **não** faz parte do repositório: está no `.gitignore` e nunca é versionado. Para criar o seu, copie o modelo e preencha com valores reais:

```powershell
Copy-Item evo_config.example.json evo_config.json
```

O agente **não** deve criar nem adivinhar credenciais. Se o arquivo não existir, o script encerra com uma mensagem clara e a execução deve ser reportada como falha.

Detalhes de cada campo em [configuracao.md](configuracao.md).

## Horário sugerido

Como o relatório sempre olha para **ontem** (ver [filtros-e-periodos.md](filtros-e-periodos.md)), qualquer horário do dia funciona. Um agendamento no início da manhã entrega o fechamento do dia anterior antes do expediente.

## Divergência conhecida: passos 2 e 3

Os passos 2 e 3 do prompt não correspondem a este repositório:

- `requirements.txt` **não instala nada** — declara explicitamente que o relatório usa apenas a biblioteca padrão do Python 3.
- `matplotlib` não é usado em lugar nenhum deste projeto. Os gráficos do e-mail são **SVG inline com fallback em tabelas HTML**, gerados sem dependência externa.

Como o `pip install` não instala nada, o `import matplotlib` do passo 3 só passa se o runner já tiver o pacote por outro motivo. Em um ambiente limpo ele levanta `ModuleNotFoundError`, e o próprio prompt manda o agente parar (`PARE e relate o erro. Nao siga adiante.`) — o relatório nunca chega a ser gerado.

Provável resquício de uma versão antiga, de quando os gráficos eram imagens renderizadas com `matplotlib`.

Se o alvo for este repositório, os passos 2 e 3 podem ser trocados por um smoke test sem dependências:

```text
2. Nao instale dependencias: o job usa apenas a biblioteca padrao do
   Python 3. Se algum passo pedir um pacote externo, PARE e relate o erro.
3. Confirme que o modulo principal carrega:
   python3 -c "import gerar_relatorio_vendas"
   (em runner Windows, use: py -c "import gerar_relatorio_vendas")
   Se falhar, PARE e relate o erro. Nao siga adiante.
```

`requirements-dev.txt` (Playwright) existe apenas para a validação local dos gráficos e não deve ser instalado pela tarefa agendada.
