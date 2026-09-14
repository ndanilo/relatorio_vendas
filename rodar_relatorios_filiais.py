#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestra a geracao de relatorios EVO para todas as filiais do evo_config.json.

Para cada filial, carrega os parametros (id_filial + colaboradores) e chama
gerar_relatorio_vendas.py isoladamente. Se uma filial falhar, o erro e
registrado e a execucao segue para a proxima.

Uso:
    python3 rodar_relatorios_filiais.py
    python3 rodar_relatorios_filiais.py --dry-run
"""

import argparse
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
    configurar_saida_utf8,
    notificar_sms_resumo,
)
from notificacao_whatsapp import (  # noqa: E402
    WhatsAppError,
    notificar_whatsapp_falhas,
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
                # Decide se a filial entra na segunda passada (metas).
                "funcionario_report_ativo": bool(
                    filial.get("funcionario_report_ativo")
                ),
            }
        )
    return validadas


def rodar_filial(filial, dry_run=False, extra=None, titulo=None):
    id_filial = filial["id_filial"]
    nome = filial["nome"]
    qtd = len(filial["colaboradores"])
    print("=" * 70)
    if titulo:
        print(f"{titulo}: {nome} (id={id_filial})")
    else:
        print(f"Filial: {nome} (id={id_filial}) | {qtd} colaborador(es)")
    print("=" * 70)

    cmd = [
        sys.executable,
        str(RELATORIO_SCRIPT),
        "--id-filial",
        str(id_filial),
        "--sem-resumo",
    ]
    cmd.extend(extra or [])
    if dry_run:
        cmd.append("--dry-run")
    resultado = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    return resultado.returncode


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Roda o relatorio de vendas EVO para todas as filiais."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gera arquivos e imagens e mostra as mensagens, mas nao envia "
        "e-mail, SMS nem faz chamadas de API.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    configurar_saida_utf8()
    args = parse_args(argv)
    filiais = carregar_filiais()
    if not filiais:
        sys.exit("Nenhuma filial valida para processar.")

    print(f"Orquestrador: {len(filiais)} filial(is) a processar.\n")

    ok = []
    falhas = []

    # Primeira passada: so os relatorios de vendas. As metas ficam para depois
    # de todas as filiais, com "--somente-metas", para que quem recebe os dois
    # nao veja o e-mail de metas no meio dos relatorios de vendas.
    for filial in filiais:
        try:
            codigo = rodar_filial(filial, dry_run=args.dry_run, extra=["--sem-metas"])
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

    # Fim do despacho de vendas: cada filial ja mandou a propria imagem por
    # WhatsApp, entao aqui so sai o SMS (hoje desligado).
    erro_notificacao = None
    ontem_str = None
    try:
        config = carregar_config()
        email_ativo = bool((config.get("email") or {}).get("ativo"))
        ontem_str = calcular_periodos(datetime.now())["ontem_str"]
        if ok and email_ativo and not args.dry_run:
            print("\nEnviando SMS de resumo...")
            notificar_sms_resumo(config, ontem_str)
    except (EvoError, WhatsAppError) as exc:
        erro_notificacao = str(exc)
        print(f"[ERRO] Falha na notificacao de fim de lote: {exc}")

    # Segunda passada: relatorio de metas das filiais que o habilitaram, agora
    # que todos os relatorios de vendas ja sairam.
    com_metas = [f for f in ok if f["funcionario_report_ativo"]]
    if com_metas:
        print(f"\nRelatorio de metas: {len(com_metas)} filial(is).\n")
    for filial in com_metas:
        try:
            codigo = rodar_filial(
                filial,
                dry_run=args.dry_run,
                extra=["--somente-metas"],
                titulo="Metas",
            )
            if codigo == 0:
                print(f'[OK] Metas de "{filial["nome"]}" enviadas.\n')
            else:
                falhas.append((filial, f"metas: exit code {codigo}"))
                print(
                    f'[ERRO] Metas de "{filial["nome"]}" falharam '
                    f"(codigo {codigo}).\n"
                )
        except Exception as exc:
            falhas.append((filial, f"metas: {exc}"))
            print(f'[ERRO] Metas de "{filial["nome"]}" falharam: {exc}.\n')

    if falhas and ontem_str:
        try:
            print("\nAvisando as falhas por WhatsApp...")
            notificar_whatsapp_falhas(
                carregar_config(),
                ontem_str,
                [(filial["nome"], motivo) for filial, motivo in falhas],
                dry_run=args.dry_run,
            )
        except (EvoError, WhatsAppError) as exc:
            erro_notificacao = str(exc)
            print(f"[ERRO] Falha ao avisar as falhas: {exc}")

    if falhas or erro_notificacao:
        sys.exit(1)

    print("Todas as filiais foram processadas com sucesso.")


if __name__ == "__main__":
    main()
