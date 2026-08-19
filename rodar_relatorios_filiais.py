#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestra a geracao de relatorios EVO para todas as filiais do evo_config.json.

Para cada filial, carrega os parametros (id_filial + colaboradores) e chama
gerar_relatorio_vendas.py isoladamente. Se uma filial falhar, o erro e
registrado e a execucao segue para a proxima.

Uso:
    python3 rodar_relatorios_filiais.py
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "evo_config.json"
RELATORIO_SCRIPT = SCRIPT_DIR / "gerar_relatorio_vendas.py"

# Garante import do modulo irmao quando rodado como script
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from gerar_relatorio_vendas import (  # noqa: E402
    EvoError,
    calcular_periodos,
    carregar_config,
    notificar_sms_resumo,
)


def carregar_filiais():
    if not CONFIG_PATH.exists():
        sys.exit(f"Arquivo de configuracao nao encontrado: {CONFIG_PATH}")
    if not RELATORIO_SCRIPT.exists():
        sys.exit(f"Script de relatorio nao encontrado: {RELATORIO_SCRIPT}")

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    filiais = config.get("filiais")
    if not filiais:
        # Formato legado: uma unica filial na raiz
        if config.get("colaboradores") or config.get("id_funcionario"):
            filiais = [
                {
                    "id_filial": config.get("id_filial", 1),
                    "nome": config.get(
                        "nome_filial", f"Filial {config.get('id_filial', 1)}"
                    ),
                    "colaboradores": config.get("colaboradores")
                    or [
                        {
                            "id_funcionario": config["id_funcionario"],
                            "nome": config.get("nome_colaborador", ""),
                        }
                    ],
                }
            ]
        else:
            sys.exit(
                'Nenhuma filial encontrada em evo_config.json (campo "filiais").'
            )

    validadas = []
    for filial in filiais:
        id_filial = filial.get("id_filial")
        nome = filial.get("nome") or f"Filial {id_filial}"
        colaboradores = filial.get("colaboradores") or []
        if id_filial is None:
            print(f"[AVISO] Ignorando filial sem id_filial: {filial}")
            continue
        if not colaboradores:
            print(f'[AVISO] Filial "{nome}" (id={id_filial}) sem colaboradores; pulando.')
            continue
        validadas.append(
            {
                "id_filial": int(id_filial),
                "nome": nome,
                "colaboradores": colaboradores,
            }
        )
    return validadas


def rodar_filial(filial):
    id_filial = filial["id_filial"]
    nome = filial["nome"]
    qtd = len(filial["colaboradores"])
    print("=" * 70)
    print(f"Filial: {nome} (id={id_filial}) | {qtd} colaborador(es)")
    print("=" * 70)

    cmd = [
        sys.executable,
        str(RELATORIO_SCRIPT),
        "--id-filial",
        str(id_filial),
        "--sem-sms",
    ]
    resultado = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    return resultado.returncode


def main():
    filiais = carregar_filiais()
    if not filiais:
        sys.exit("Nenhuma filial valida para processar.")

    print(f"Orquestrador: {len(filiais)} filial(is) a processar.\n")

    ok = []
    falhas = []

    for filial in filiais:
        try:
            codigo = rodar_filial(filial)
            if codigo == 0:
                ok.append(filial)
                print(f'[OK] Filial "{filial["nome"]}" concluida.\n')
            else:
                falhas.append((filial, f"exit code {codigo}"))
                print(
                    f'[ERRO] Filial "{filial["nome"]}" falhou '
                    f"(codigo {codigo}). Seguindo para a proxima.\n"
                )
        except Exception as exc:
            falhas.append((filial, str(exc)))
            print(
                f'[ERRO] Filial "{filial["nome"]}" falhou: {exc}. '
                "Seguindo para a proxima.\n"
            )

    print("=" * 70)
    print("Resumo do orquestrador")
    print("=" * 70)
    print(f"Sucesso: {len(ok)}/{len(filiais)}")
    for filial in ok:
        print(f'  - {filial["nome"]} (id={filial["id_filial"]})')
    if falhas:
        print(f"Falhas: {len(falhas)}/{len(filiais)}")
        for filial, motivo in falhas:
            print(f'  - {filial["nome"]} (id={filial["id_filial"]}): {motivo}')

    # Um SMS por destinatario apos o lote (nao um por filial)
    if ok:
        try:
            config = carregar_config()
            email_ativo = bool((config.get("email") or {}).get("ativo"))
            if email_ativo:
                ontem_str = calcular_periodos(datetime.now())["ontem_str"]
                print("\nEnviando SMS de resumo...")
                notificar_sms_resumo(config, ontem_str)
        except EvoError as exc:
            print(f"[ERRO] Falha ao enviar SMS de resumo: {exc}")
            falhas.append(({"nome": "SMS", "id_filial": "-"}, str(exc)))

    if falhas:
        sys.exit(1)

    print("Todas as filiais foram processadas com sucesso.")


if __name__ == "__main__":
    main()
