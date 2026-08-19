#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monta o corpo HTML (responsivo) e os graficos do relatorio de vendas EVO.

Usado por gerar_relatorio_vendas.py. Textos e barras usam HTML puro (tabelas).
O donut de contribuicao e SVG so com formas - sem <text> - porque varios
clientes de e-mail ignoram o posicionamento do texto SVG e colam os rotulos
("MesR$ ..." / "...000,0091.1%"). Nao ha anexos de imagem (CID).

Dependencias: nenhuma. Apenas a biblioteca padrao.
"""

import math
from datetime import datetime

# Paleta usada no e-mail e nos graficos.
COR_TINTA = "#1F2937"
COR_SUAVE = "#6B7280"
COR_BORDA = "#E5E7EB"
COR_FUNDO = "#F5F7FA"
COR_DESTAQUE = "#0E7490"
COR_POSITIVO = "#15803D"
COR_ALERTA = "#B45309"

CORES_COLABORADORES = [
    "#0E7490",
    "#D97706",
    "#15803D",
    "#BE123C",
    "#4338CA",
    "#0891B2",
    "#A16207",
    "#7C3AED",
]


def formatar_moeda(valor):
    texto = f"{(valor or 0):,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def escapar(texto):
    return (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def resumir(registros):
    total = sum(item.get("VALOR_VENDA") or 0 for item in registros)
    return len(registros), total


def cor_colaborador(indice):
    return CORES_COLABORADORES[indice % len(CORES_COLABORADORES)]


# ----------------------------------------------------------------------
# Graficos (SVG so com formas; texto sempre em HTML)
# ----------------------------------------------------------------------
# Varios clientes de e-mail ignoram x/y do <text> e colam os nos em uma
# unica linha ("MesR$ ..." / "...000,0091.1%"). Por isso o SVG nao leva
# nenhum texto legivel - so caminhos e retangulos.
DONUT_TAMANHO = 220
DONUT_RAIO = 82
DONUT_ESPESSURA = 28
DONUT_CIRCUNFERENCIA = 2 * math.pi * DONUT_RAIO
DONUT_FOLGA = 5.0


def gerar_svg_contribuicao(participacoes):
    """Donut SVG so com fatias coloridas (sem texto)."""
    dados = [p for p in participacoes if p["total"] > 0]
    if not dados:
        return None

    total = sum(p["total"] for p in dados)
    centro = DONUT_TAMANHO / 2

    fatias = []
    acumulado = 0.0
    for p in dados:
        fracao = p["total"] / total
        comprimento = fracao * DONUT_CIRCUNFERENCIA
        folga = DONUT_FOLGA if len(dados) > 1 and comprimento > 3 * DONUT_FOLGA else 0.0
        visivel = max(comprimento - folga, 0.5)
        fatias.append(
            f'<circle class="fatia" data-nome="{escapar(p["nome"])}" '
            f'data-percentual="{fracao * 100:.4f}" data-graus="{fracao * 360:.4f}" '
            f'data-comprimento="{visivel:.4f}" '
            f'cx="{centro:g}" cy="{centro:g}" r="{DONUT_RAIO:g}" fill="none" '
            f'stroke="{cor_colaborador(p["indice"])}" '
            f'stroke-width="{DONUT_ESPESSURA:g}" '
            f'stroke-dasharray="{visivel:.4f} {DONUT_CIRCUNFERENCIA - visivel:.4f}" '
            f'stroke-dashoffset="{-acumulado * DONUT_CIRCUNFERENCIA:.4f}" />'
        )
        acumulado += fracao

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {DONUT_TAMANHO} {DONUT_TAMANHO}" '
        f'width="{DONUT_TAMANHO}" height="{DONUT_TAMANHO}" '
        'role="img" data-grafico="contribuicao" '
        'aria-hidden="true" '
        f'style="display:block;margin:0 auto;width:100%;max-width:{DONUT_TAMANHO}px;height:auto;">'
        f'<circle cx="{centro:g}" cy="{centro:g}" r="{DONUT_RAIO:g}" fill="none" '
        f'stroke="{COR_BORDA}" stroke-width="{DONUT_ESPESSURA:g}" />'
        f'<g transform="rotate(-90 {centro:g} {centro:g})">{"".join(fatias)}</g>'
        "</svg>"
    )


# ----------------------------------------------------------------------
# Blocos HTML
# ----------------------------------------------------------------------
def _cartao_kpi(rotulo, valor, detalhe, cor_valor):
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="background:#FFFFFF;border:1px solid {COR_BORDA};'
        'border-radius:10px;">'
        '<tr><td style="padding:14px 16px;font-family:Arial,Helvetica,sans-serif;">'
        f'<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
        f'color:{COR_SUAVE};">{escapar(rotulo)}</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{cor_valor};'
        'padding-top:6px;line-height:1.2;">'
        f"{escapar(valor)}</div>"
        f'<div style="font-size:12px;color:{COR_SUAVE};padding-top:4px;">'
        f"{escapar(detalhe)}</div>"
        "</td></tr></table>"
    )


def _barra_html(largura_percentual, cor, altura=10):
    """Barra horizontal em tabela: renderiza em qualquer cliente de e-mail."""
    largura = min(max(largura_percentual, 0), 100)
    celula_preenchida = (
        f'<td class="preenchimento" width="{largura:g}%" '
        f'data-percentual="{largura:g}" '
        f'style="background:{cor};height:{altura}px;font-size:0;'
        f'line-height:{altura}px;border-radius:{altura}px;">&nbsp;</td>'
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" class="trilho" style="background:{COR_BORDA};'
        f'border-radius:{altura}px;">'
        "<tr>"
        f"{celula_preenchida if largura > 0 else ''}"
        f'<td style="font-size:0;line-height:{altura}px;">&nbsp;</td>'
        "</tr></table>"
    )


def _swatch(cor):
    """Quadrado de cor para a legenda (mais claro que uma barra empilhada)."""
    return (
        '<table role="presentation" width="12" cellpadding="0" cellspacing="0" '
        f'border="0" style="width:12px;"><tr>'
        f'<td width="12" height="12" style="width:12px;height:12px;background:{cor};'
        'border-radius:3px;font-size:0;line-height:12px;">&nbsp;</td>'
        "</tr></table>"
    )


def _bloco_meta(total_mes, meta_mes):
    """Barra de meta em HTML puro: textos separados e tipografia estavel."""
    percentual = (total_mes / meta_mes) * 100
    cor = COR_POSITIVO if percentual >= 100 else COR_DESTAQUE

    return (
        '<tr data-bloco="meta" data-grafico="meta">'
        '<td style="padding:0 0 20px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="background:#FFFFFF;border:1px solid {COR_BORDA};'
        'border-radius:10px;">'
        '<tr><td style="padding:16px 18px;font-family:Arial,Helvetica,sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        "<tr>"
        f'<td style="font-size:13px;color:{COR_TINTA};padding-bottom:10px;'
        'padding-right:12px;">'
        f"{escapar(formatar_moeda(total_mes))} de "
        f"{escapar(formatar_moeda(meta_mes))}</td>"
        f'<td align="right" valign="top" style="font-size:16px;font-weight:bold;'
        f'color:{cor};padding-bottom:10px;white-space:nowrap;width:1%;">'
        f"{percentual:.1f}%</td>"
        "</tr>"
        f'<tr><td colspan="2">'
        f"{_barra_html(min(percentual, 100), cor, altura=12)}"
        "</td></tr>"
        "</table></td></tr></table></td></tr>"
    )


def _linhas_participacao(participacoes):
    """Uma linha por colaborador: swatch + nome + valor + barra propria."""
    linhas = []
    for p in participacoes:
        largura = max(round(p["percentual"]), 1) if p["total"] > 0 else 0
        cor = cor_colaborador(p["indice"])
        barra = _barra_html(largura, cor, altura=10)
        linhas.append(
            '<tr class="participacao" '
            f'data-nome="{escapar(p["nome"])}" '
            f'data-percentual="{p["percentual"]:.1f}">'
            '<td style="padding:0 0 16px 0;font-family:Arial,Helvetica,sans-serif;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            "<tr>"
            f'<td width="18" valign="middle" style="width:18px;padding:0 8px 6px 0;">'
            f"{_swatch(cor)}</td>"
            f'<td style="font-size:14px;font-weight:bold;color:{COR_TINTA};'
            'padding-bottom:6px;">'
            f'{escapar(p["nome"])}</td>'
            f'<td align="right" valign="middle" style="font-size:13px;color:{COR_TINTA};'
            'padding-bottom:6px;white-space:nowrap;padding-left:8px;">'
            f'{escapar(formatar_moeda(p["total"]))}</td>'
            f'<td align="right" valign="middle" width="56" style="width:56px;'
            f'font-size:13px;font-weight:bold;color:{cor};padding-bottom:6px;'
            'white-space:nowrap;padding-left:8px;">'
            f'{p["percentual"]:.1f}%</td>'
            "</tr>"
            f'<tr><td colspan="4">{barra}</td></tr>'
            "</table></td></tr>"
        )
    return "".join(linhas)


def _bloco_contribuicao(participacoes, total_mes):
    """Um unico cartao: donut (formas) + total em HTML + ranking por colaborador."""
    svg = gerar_svg_contribuicao(participacoes)
    donut_html = ""
    if svg:
        # Outlook ignora SVG; o comentario evita o cartao vazio no Word.
        donut_html = (
            "<!--[if !mso]><!-->"
            '<tr data-bloco="svg" data-grafico="contribuicao">'
            '<td align="center" style="padding:4px 0 4px 0;">'
            f"{svg}"
            "</td></tr>"
            "<!--<![endif]-->"
        )

    return (
        '<tr data-bloco="contribuicao" data-grafico="contribuicao">'
        '<td style="padding:0 0 20px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="background:#FFFFFF;border:1px solid {COR_BORDA};'
        'border-radius:10px;">'
        '<tr><td style="padding:18px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td align="center" style="padding:0 0 12px 0;'
        'font-family:Arial,Helvetica,sans-serif;">'
        f'<div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;'
        f'color:{COR_SUAVE};">Total do mês</div>'
        f'<div style="font-size:22px;font-weight:bold;color:{COR_TINTA};'
        'padding-top:4px;line-height:1.2;">'
        f"{escapar(formatar_moeda(total_mes))}</div>"
        "</td></tr>"
        f"{donut_html}"
        '<tr><td style="border-top:1px solid '
        f'{COR_BORDA};padding-top:16px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f"{_linhas_participacao(participacoes)}"
        "</table></td></tr>"
        "</table></td></tr></table></td></tr>"
    )


def _cartao_venda(item):
    valor = item.get("VALOR_VENDA") or 0
    data_venda = (item.get("DT_VENDA") or "")[:16].replace("T", " ")
    hora = data_venda[11:16] if len(data_venda) >= 16 else data_venda
    descricao = item.get("DESCRICAO") or item.get("DS_ITEM") or ""
    pagamento = item.get("FORMA_PAGAMENTO") or ""

    return (
        '<tr><td style="padding:10px 0;border-top:1px solid '
        f'{COR_BORDA};font-family:Arial,Helvetica,sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        "<tr>"
        f'<td style="font-size:13px;font-weight:bold;color:{COR_TINTA};">'
        f'{escapar(item.get("NOME_COMPRADOR", ""))}</td>'
        f'<td align="right" style="font-size:13px;font-weight:bold;'
        f'color:{COR_TINTA};white-space:nowrap;padding-left:8px;">'
        f"{escapar(formatar_moeda(valor))}</td>"
        "</tr>"
        f'<tr><td colspan="2" style="font-size:12px;color:{COR_SUAVE};padding-top:3px;">'
        f"{escapar(descricao)}</td></tr>"
        f'<tr><td colspan="2" style="font-size:11px;color:{COR_SUAVE};padding-top:3px;">'
        f"{escapar(hora)} &middot; {escapar(pagamento)}</td></tr>"
        "</table></td></tr>"
    )


def _secao_colaborador(resultado, indice, ontem_str, periodo_label):
    qtd_ontem, total_ontem = resumir(resultado["registros_ontem"])
    qtd_mes, total_mes = resumir(resultado["registros_mes"])
    cor = cor_colaborador(indice)

    if resultado["registros_ontem"]:
        vendas_html = "".join(
            _cartao_venda(item) for item in resultado["registros_ontem"]
        )
    else:
        vendas_html = (
            f'<tr><td style="padding:10px 0;border-top:1px solid {COR_BORDA};'
            f'font-family:Arial,Helvetica,sans-serif;font-size:13px;color:{COR_SUAVE};">'
            "Nenhuma venda registrada.</td></tr>"
        )

    return (
        '<tr><td style="padding:0 0 16px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="background:#FFFFFF;border:1px solid {COR_BORDA};'
        'border-radius:10px;">'
        f'<tr><td style="padding:16px 18px;border-left:4px solid {cor};'
        'border-radius:10px;font-family:Arial,Helvetica,sans-serif;">'
        f'<div style="font-size:15px;font-weight:bold;color:{COR_TINTA};">'
        f'{escapar(resultado["nome"])}</div>'
        f'<div style="font-size:12px;color:{COR_SUAVE};padding-top:4px;">'
        f"Ontem ({escapar(ontem_str)}): {escapar(formatar_moeda(total_ontem))} "
        f"em {qtd_ontem} venda(s)</div>"
        f'<div style="font-size:12px;color:{COR_SUAVE};padding-top:2px;">'
        f"{escapar(periodo_label)}: {escapar(formatar_moeda(total_mes))} "
        f"em {qtd_mes} venda(s)</div>"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'border="0" style="padding-top:8px;">'
        f"{vendas_html}"
        "</table>"
        "</td></tr></table></td></tr>"
    )


def _titulo_secao(texto):
    return (
        '<tr><td style="padding:4px 0 12px 0;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:{COR_SUAVE};">'
        f"{escapar(texto)}</td></tr>"
    )


# ----------------------------------------------------------------------
# Montagem do e-mail
# ----------------------------------------------------------------------
def montar_email_html(
    nome_filial,
    colaboradores_resultados,
    totais,
    ontem_str,
    periodo_inicio_str,
    meta_mes=None,
):
    """Retorna o corpo HTML completo do e-mail (graficos SVG inline + HTML)."""
    _, total_ontem = resumir(totais["registros_ontem"])
    qtd_ontem, _ = resumir(totais["registros_ontem"])
    qtd_mes, total_mes = resumir(totais["registros_mes"])
    periodo_label = f"Mês ({periodo_inicio_str} a {ontem_str})"

    participacoes = []
    for indice, resultado in enumerate(colaboradores_resultados):
        _, total = resumir(resultado["registros_mes"])
        participacoes.append(
            {
                "indice": indice,
                "nome": resultado["nome"],
                "total": total,
                "percentual": (total / total_mes * 100) if total_mes else 0.0,
            }
        )
    participacoes.sort(key=lambda p: p["total"], reverse=True)

    partes = []

    partes.append(
        '<tr><td style="padding:0 0 18px 0;font-family:Arial,Helvetica,sans-serif;">'
        f'<div style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;'
        f'color:{COR_DESTAQUE};font-weight:bold;">Relatório de Vendas</div>'
        f'<div style="font-size:24px;font-weight:bold;color:{COR_TINTA};'
        'padding-top:4px;line-height:1.25;">'
        f"{escapar(nome_filial)}</div>"
        f'<div style="font-size:13px;color:{COR_SUAVE};padding-top:6px;">'
        f"Ontem: {escapar(ontem_str)} &middot; {escapar(periodo_label)}</div>"
        f'<div style="font-size:11px;color:{COR_SUAVE};padding-top:2px;">'
        f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}</div>'
        "</td></tr>"
    )

    partes.append(
        '<tr><td style="padding:0 0 16px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr>'
        '<td class="kpi" width="50%" valign="top" style="padding:0 6px 12px 0;">'
        f"{_cartao_kpi('Ontem', formatar_moeda(total_ontem), f'{qtd_ontem} venda(s)', COR_TINTA)}"
        "</td>"
        '<td class="kpi" width="50%" valign="top" style="padding:0 0 12px 6px;">'
        f"{_cartao_kpi('Mês até ontem', formatar_moeda(total_mes), f'{qtd_mes} venda(s)', COR_DESTAQUE)}"
        "</td>"
        "</tr></table></td></tr>"
    )

    if meta_mes and meta_mes > 0:
        percentual_meta = (total_mes / meta_mes) * 100
        falta = max(meta_mes - total_mes, 0)
        cor_meta = COR_POSITIVO if percentual_meta >= 100 else COR_ALERTA
        detalhe = (
            "Meta atingida"
            if falta <= 0
            else f"Faltam {formatar_moeda(falta)}"
        )
        partes.append(
            '<tr><td style="padding:0 0 12px 0;">'
            + _cartao_kpi(
                f"Meta do mês ({formatar_moeda(meta_mes)})",
                f"{percentual_meta:.1f}%",
                detalhe,
                cor_meta,
            )
            + "</td></tr>"
        )
        partes.append(_bloco_meta(total_mes, meta_mes))

    partes.append(_titulo_secao("Contribuição no mês"))
    partes.append(_bloco_contribuicao(participacoes, total_mes))

    partes.append(_titulo_secao(f"Detalhe de ontem ({ontem_str})"))
    for indice, resultado in enumerate(colaboradores_resultados):
        partes.append(
            _secao_colaborador(resultado, indice, ontem_str, periodo_label)
        )

    partes.append(
        '<tr><td style="padding:8px 0 0 0;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:11px;color:{COR_SUAVE};line-height:1.5;">'
        "Relatório automático do sistema EVO. "
        "Os arquivos .txt e .csv estão anexados a este e-mail.</td></tr>"
    )

    html = (
        "<!DOCTYPE html>"
        '<html lang="pt-BR"><head>'
        '<meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        "<style>"
        "@media only screen and (max-width:480px){"
        ".kpi{display:block !important;width:100% !important;padding:0 0 12px 0 !important;}"
        "}"
        "</style>"
        "</head>"
        f'<body style="margin:0;padding:0;background:{COR_FUNDO};">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="background:{COR_FUNDO};">'
        '<tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'border="0" style="width:100%;max-width:600px;">'
        f"{''.join(partes)}"
        "</table></td></tr></table></body></html>"
    )

    return html
