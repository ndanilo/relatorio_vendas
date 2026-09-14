#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculo das metas por consultor e o relatorio em texto puro.

Reproduz a planilha modelo-calculo-consultores.xlsx:

    PROJECAO  = realizado / dias_decorridos * dias_uteis_do_mes
    %         = projecao / meta * 100
    FALTA     = max(meta - realizado, 0)
    POR DIA   = falta / dias_uteis_restantes

Duas diferencas propositais em relacao a planilha:

  * FALTA e limitada em zero. Quem passou da meta nao deve nada, entao a
    coluna nunca mostra divida negativa - a mesma regra que o relatorio de
    vendas ja usa em "Faltam ...".
  * O % do total NAO e a media dos percentuais individuais: e a mesma formula
    aplicada aos totais (projecao_total / meta_total). Como todos dividem os
    mesmos dias uteis, a soma das projecoes e igual a projecao da soma, e o
    total nunca contradiz as linhas acima dele.

O status (abaixo/atingida) e resolvido aqui, junto com rotulo, marcador e cor,
para o e-mail e o PNG apenas lerem o campo pronto e nao divergirem.

Dependencias: nenhuma. Apenas a biblioteca padrao.
"""

from datetime import datetime

from email_relatorio import (
    COR_ALERTA,
    COR_POSITIVO,
    COR_SUAVE,
    formatar_moeda,
    formatar_moeda_opcional,
    formatar_percentual,
    resumir,
)

LARGURA_TEXTO = 70


# ----------------------------------------------------------------------
# Formatacao
# ----------------------------------------------------------------------
def formatar_dias(valor):
    """Dias uteis sem o ",0" inutil: 23, 9, 14, mas 22,5 quando ha meio dia."""
    valor = valor or 0
    if float(valor).is_integer():
        return f"{int(valor)}"
    return f"{valor:.1f}".replace(".", ",")


# ----------------------------------------------------------------------
# Status (flag do %)
# ----------------------------------------------------------------------
def status(percentual):
    """Flag do consultor a partir do % da meta projetada.

    Abaixo de 100% o consultor nao chega na meta no ritmo atual, e isso
    aparece sinalizado - marcador e rotulo em caixa alta, nao so a cor, para
    sobreviver ao PNG em escala de cinza e ao .txt.
    """
    if percentual is None:
        return {
            "chave": "indefinido",
            "rotulo": "SEM PROJEÇÃO",
            "marcador": "·",
            "cor": COR_SUAVE,
        }
    if percentual >= 100:
        return {
            "chave": "atingida",
            "rotulo": "META ATINGIDA",
            "marcador": "▲",
            "cor": COR_POSITIVO,
        }
    return {
        "chave": "abaixo",
        "rotulo": "ABAIXO DA META",
        "marcador": "▼",
        "cor": COR_ALERTA,
    }


# ----------------------------------------------------------------------
# Calculo
# ----------------------------------------------------------------------
def _linha(nome, meta, realizado, dias):
    # Sem dia decorrido nao existe ritmo para projetar (roda no primeiro dia
    # util do mes); a linha sai sem projecao em vez de dividir por zero.
    projecao = (
        realizado / dias["passados"] * dias["total"] if dias["passados"] > 0 else None
    )
    percentual = (projecao / meta * 100) if projecao is not None else None
    falta = max(meta - realizado, 0.0)
    por_dia = falta / dias["restantes"] if dias["restantes"] > 0 else None

    return {
        "nome": nome,
        "meta": meta,
        "realizado": realizado,
        "projecao": projecao,
        "percentual": percentual,
        "falta": falta,
        "por_dia": por_dia,
        "no_ritmo": percentual is not None and percentual >= 100,
        "status": status(percentual),
    }


def _total(linhas, dias):
    meta = sum(linha["meta"] for linha in linhas)
    realizado = sum(linha["realizado"] for linha in linhas)
    # Falta ja vem limitada em zero por consultor, entao o total responde
    # "quanto o time ainda deve" - quem passou da meta nao abate a divida
    # de quem esta atras.
    falta = sum(linha["falta"] for linha in linhas)

    projecoes = [linha["projecao"] for linha in linhas]
    projecao = (
        sum(projecoes) if projecoes and all(p is not None for p in projecoes) else None
    )
    percentual = (projecao / meta * 100) if projecao is not None and meta > 0 else None

    return {
        "nome": "Total da filial",
        "meta": meta,
        "realizado": realizado,
        "projecao": projecao,
        "percentual": percentual,
        "falta": falta,
        "por_dia": falta / dias["restantes"] if dias["restantes"] > 0 else None,
        "no_ritmo": percentual is not None and percentual >= 100,
        "status": status(percentual),
    }


def calcular_metas(colaboradores_resultados, colaboradores_config, dias):
    """Monta as linhas por consultor e o total da filial.

    colaboradores_resultados: saida de processar_filial (precisa de
    "id_funcionario", "nome" e "registros_mes").
    colaboradores_config: lista "colaboradores" da filial, de onde sai
    "meta_funcionario". Quem nao tem meta fica de fora e e devolvido em
    "sem_meta" para o log.
    """
    metas = {}
    for colab in colaboradores_config or []:
        meta = colab.get("meta_funcionario")
        if meta:
            metas[colab.get("id_funcionario")] = float(meta)

    linhas = []
    sem_meta = []
    for resultado in colaboradores_resultados:
        meta = metas.get(resultado.get("id_funcionario"))
        if not meta or meta <= 0:
            sem_meta.append(resultado["nome"])
            continue
        _, realizado = resumir(resultado["registros_mes"])
        linhas.append(_linha(resultado["nome"], meta, realizado, dias))

    # Pior % primeiro: quem precisa de atencao aparece no topo. Linhas sem
    # projecao vao para o fim.
    linhas.sort(key=lambda linha: (linha["percentual"] is None, linha["percentual"]))

    return {
        "linhas": linhas,
        "total": _total(linhas, dias),
        "sem_meta": sem_meta,
        "dias": dias,
        # O rodape sai daqui pronto para que o e-mail, o PNG e o .txt exibam
        # exatamente o mesmo texto sem nenhum deles reimplementar a copia.
        "rodape": [linha_dias_uteis(dias), linha_formulas()],
    }


# ----------------------------------------------------------------------
# Rodape (texto identico no e-mail, no PNG e no .txt)
# ----------------------------------------------------------------------
def linha_dias_uteis(dias):
    if dias.get("peso_sabado"):
        sabado = f"sábado conta {formatar_dias(dias['peso_sabado'])} dia"
    else:
        sabado = "sábado não conta"
    return (
        f"Dias úteis do mês: {formatar_dias(dias['total'])} · "
        f"Decorridos: {formatar_dias(dias['passados'])} · "
        f"Restantes: {formatar_dias(dias['restantes'])} — {sabado}."
    )


def linha_formulas():
    return (
        "Projeção = realizado ÷ dias decorridos × dias úteis do mês. "
        "Falta = meta − realizado (mínimo zero). "
        "Por dia útil = falta ÷ dias restantes."
    )


# ----------------------------------------------------------------------
# Relatorio em texto puro (alternativa do e-mail e arquivo .txt)
# ----------------------------------------------------------------------
def _bloco_texto(linha):
    return [
        "=" * LARGURA_TEXTO,
        f"{linha['nome'].upper()} - {linha['status']['marcador']} "
        f"{linha['status']['rotulo']}",
        "=" * LARGURA_TEXTO,
        f"  Meta:         {formatar_moeda(linha['meta'])}",
        f"  Realizado:    {formatar_moeda(linha['realizado'])}",
        f"  Projeção:     {formatar_moeda_opcional(linha['projecao'])} "
        f"({formatar_percentual(linha['percentual'])} da meta)",
        f"  Falta:        {formatar_moeda(linha['falta'])}",
        f"  Por dia útil: {formatar_moeda_opcional(linha['por_dia'])}",
        "",
    ]


def montar_relatorio_metas_texto(nome_filial, metas, periodo_inicio_str, ontem_str):
    """Versao texto puro: alternativa do e-mail HTML e conteudo do .txt."""
    linhas = [
        "RELATÓRIO DE METAS - EVO",
        f"Filial: {nome_filial}",
        f"Período: {periodo_inicio_str} a {ontem_str}",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
    ]

    for linha in metas["linhas"]:
        linhas.extend(_bloco_texto(linha))

    linhas.extend(_bloco_texto(metas["total"]))

    linhas.extend(metas["rodape"])
    if metas["sem_meta"]:
        linhas.append("")
        linhas.append(
            "Sem meta_funcionario configurada (fora deste relatório): "
            + ", ".join(metas["sem_meta"])
        )

    return "\n".join(linhas)
