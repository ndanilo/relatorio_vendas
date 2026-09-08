#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notificacao dos relatorios via WhatsApp, usando a API local de notificacoes.

Sao dois tipos de mensagem:
  1) Uma por filial, com o texto formatado e o relatorio em PNG anexado.
  2) Um resumo unico ao final do lote, so texto.

O PNG e o proprio HTML do e-mail gerado sem o grafico circular
(montar_email_html(..., incluir_donut=False)), renderizado no Chromium via
Playwright. Assim a imagem nunca diverge do e-mail.

Playwright e opcional: se nao estiver instalado, ou se a renderizacao
falhar, a mensagem sai apenas com o texto e o job segue.

Contrato da API (multipart/form-data):
    POST {whatsapp.url}
    x-api-key: {whatsapp.api_key}
    campos: to (JID do WhatsApp), message (texto), file (imagem, opcional)
"""

import mimetypes
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from email_relatorio import formatar_moeda, resumir

# Medalhas para o ranking; do 4o colaborador em diante usa um marcador neutro.
MEDALHAS = ("\U0001F947", "\U0001F948", "\U0001F949")
MARCADOR_PADRAO = "\u25AB\uFE0F"

BARRA_CHEIA = "\u2593"
BARRA_VAZIA = "\u2591"
BARRA_BLOCOS = 10


class WhatsAppError(RuntimeError):
    pass


def _cfg(config):
    return config.get("whatsapp") or {}


def whatsapp_ativo(config):
    return bool(_cfg(config).get("ativo"))


# ----------------------------------------------------------------------
# Imagem
# ----------------------------------------------------------------------
def renderizar_png(html, destino, largura=640, escala=2):
    """Renderiza o HTML no Chromium e salva um PNG de pagina inteira.

    Retorna o Path do arquivo, ou None se o Playwright nao estiver
    disponivel ou a renderizacao falhar (a mensagem entao vai sem anexo).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "[AVISO] Playwright nao instalado; a mensagem do WhatsApp vai sem "
            "imagem.\n        Instale com: py -m pip install playwright && "
            "py -m playwright install chromium"
        )
        return None

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            try:
                pagina = navegador.new_page(
                    viewport={"width": int(largura), "height": 900},
                    device_scale_factor=float(escala),
                )
                pagina.set_content(html, wait_until="load")
                pagina.screenshot(path=str(destino), full_page=True)
            finally:
                navegador.close()
    except Exception as exc:  # noqa: BLE001 - imagem e opcional, nao derruba o job
        print(
            f"[AVISO] Falha ao gerar a imagem do relatorio ({exc}); "
            "a mensagem do WhatsApp vai sem anexo."
        )
        return None

    return destino


def gerar_imagem_relatorio(html_sem_donut, destino, config):
    """Aplica largura/escala do evo_config.json e renderiza o PNG."""
    cfg = _cfg(config)
    if not cfg.get("anexar_imagem", True):
        return None
    return renderizar_png(
        html_sem_donut,
        destino,
        largura=cfg.get("imagem_largura", 640),
        escala=cfg.get("imagem_escala", 2),
    )


# ----------------------------------------------------------------------
# Envio
# ----------------------------------------------------------------------
def _tipo_mime(caminho):
    tipo, _ = mimetypes.guess_type(caminho.name)
    return tipo or "application/octet-stream"


def _montar_multipart(campos, arquivo=None):
    """Monta um corpo multipart/form-data usando so a biblioteca padrao."""
    boundary = f"----relatorioVendas{uuid.uuid4().hex}"
    partes = []

    for nome, valor in campos.items():
        partes.append(f"--{boundary}\r\n".encode())
        partes.append(
            f'Content-Disposition: form-data; name="{nome}"\r\n\r\n'.encode()
        )
        partes.append(str(valor).encode("utf-8") + b"\r\n")

    if arquivo:
        caminho = Path(arquivo)
        partes.append(f"--{boundary}\r\n".encode())
        partes.append(
            f'Content-Disposition: form-data; name="file"; '
            f'filename="{caminho.name}"\r\n'.encode()
        )
        partes.append(f"Content-Type: {_tipo_mime(caminho)}\r\n\r\n".encode())
        partes.append(caminho.read_bytes() + b"\r\n")

    partes.append(f"--{boundary}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={boundary}"


def enviar_whatsapp(config, mensagem, imagem=None, dry_run=False):
    """Envia a mensagem para cada JID em whatsapp.destinatarios.

    So envia se config["whatsapp"]["ativo"] for true. Com dry_run=True
    imprime o que seria enviado e nao faz nenhuma chamada de rede.
    """
    cfg = _cfg(config)

    if dry_run:
        destinatarios = cfg.get("destinatarios") or []
        anexo = Path(imagem).name if imagem else "sem anexo"
        print(f"  [dry-run] Destinatarios: {', '.join(destinatarios) or '(nenhum)'}")
        print(f"  [dry-run] Anexo: {anexo}")
        print("  [dry-run] Mensagem:")
        for linha in mensagem.splitlines():
            print(f"    | {linha}")
        return True

    if not cfg.get("ativo"):
        print(
            "Envio por WhatsApp desativado "
            "(whatsapp.ativo=false em evo_config.json)."
        )
        return False

    url = (cfg.get("url") or "").strip()
    if not url:
        raise WhatsAppError("whatsapp.url ausente em evo_config.json.")

    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise WhatsAppError("whatsapp.api_key ausente em evo_config.json.")

    destinatarios = cfg.get("destinatarios") or []
    if not destinatarios:
        print("Nenhum destinatario em whatsapp.destinatarios; pulando envio.")
        return False

    if imagem and not cfg.get("anexar_imagem", True):
        imagem = None

    timeout = cfg.get("timeout", 60)
    enviados = 0

    for destinatario in destinatarios:
        jid = str(destinatario).strip()
        if not jid:
            continue

        corpo, content_type = _montar_multipart(
            {"to": jid, "message": mensagem}, imagem
        )
        requisicao = urllib.request.Request(
            url,
            data=corpo,
            method="POST",
            headers={
                "x-api-key": api_key,
                "Content-Type": content_type,
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
                raw = resposta.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode("utf-8", errors="replace")
            raise WhatsAppError(
                f"Falha ao enviar WhatsApp para {jid} "
                f"(HTTP {exc.code}): {detalhe[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise WhatsAppError(
                f"Falha de rede ao enviar WhatsApp para {jid}: {exc.reason}. "
                f"A API local esta rodando em {url}?"
            ) from exc

        anexo = f" (com {Path(imagem).name})" if imagem else ""
        print(f"WhatsApp enviado para {jid}{anexo}.")
        if raw:
            print(f"  Resposta da API: {raw[:300]}")
        enviados += 1

    return enviados > 0


# ----------------------------------------------------------------------
# Mensagens (formatacao WhatsApp: *negrito*, _italico_, sem markdown)
# ----------------------------------------------------------------------
def _plural_vendas(qtd):
    return "1 venda" if qtd == 1 else f"{qtd} vendas"


def _barra_texto(percentual):
    """Substitui a barra de progresso do e-mail, que nao existe em texto."""
    limitado = min(max(percentual, 0), 100)
    cheios = int(round(limitado / 100 * BARRA_BLOCOS))
    return BARRA_CHEIA * cheios + BARRA_VAZIA * (BARRA_BLOCOS - cheios)


def _marca(config):
    marca = (config.get("dns") or "").strip()
    if not marca:
        return "Vendas"
    return marca[:1].upper() + marca[1:].lower()


def montar_mensagem_filial(
    nome_filial,
    colaboradores_resultados,
    totais,
    ontem_str,
    periodo_inicio_str,
    meta_mes=None,
    email_enviado=False,
):
    """Texto da mensagem por filial (a imagem anexa traz o relatorio completo).

    Os numeros aparecem aqui de proposito: e o texto que abre na previa da
    notificacao, que fica pesquisavel no historico e que sobra sozinho se a
    renderizacao do PNG falhar.
    """
    qtd_ontem, total_ontem = resumir(totais["registros_ontem"])
    qtd_mes, total_mes = resumir(totais["registros_mes"])

    linhas = [
        "*RELATÓRIO DE VENDAS*",
        f"\U0001F4CD _{nome_filial}_ · {ontem_str}",
        "",
        f"*Ontem:* {formatar_moeda(total_ontem)} _({_plural_vendas(qtd_ontem)})_",
        f"*Mês ({periodo_inicio_str} a {ontem_str}):* "
        f"{formatar_moeda(total_mes)} _({_plural_vendas(qtd_mes)})_",
    ]

    if meta_mes and meta_mes > 0:
        percentual = total_mes / meta_mes * 100
        falta = max(meta_mes - total_mes, 0)
        detalhe = (
            "meta atingida!" if falta <= 0 else f"faltam {formatar_moeda(falta)}"
        )
        linhas.append("")
        linhas.append(
            f"\U0001F3AF *Meta:* {percentual:.1f}% de {formatar_moeda(meta_mes)}"
        )
        linhas.append(f"{_barra_texto(percentual)} {detalhe}")

    participacoes = []
    for resultado in colaboradores_resultados:
        _, total = resumir(resultado["registros_mes"])
        participacoes.append((resultado["nome"], total))
    participacoes.sort(key=lambda item: item[1], reverse=True)

    if participacoes:
        linhas.append("")
        linhas.append("*Contribuição no mês*")
        for indice, (nome, total) in enumerate(participacoes):
            percentual = (total / total_mes * 100) if total_mes else 0.0
            marcador = (
                MEDALHAS[indice] if indice < len(MEDALHAS) else MARCADOR_PADRAO
            )
            linhas.append(
                f"{marcador} {nome} — {formatar_moeda(total)} _({percentual:.1f}%)_"
            )

    linhas.append("")
    if email_enviado:
        linhas.append(
            "\U0001F4CE Detalhe na imagem; .txt e .csv foram por e-mail."
        )
    else:
        linhas.append("\U0001F4CE Detalhe completo na imagem em anexo.")

    return "\n".join(linhas)


def montar_mensagem_resumo(
    config, ontem_str, filiais_ok, falhas=None, email_enviado=True
):
    """Resumo unico do lote, sem anexo."""
    falhas = falhas or []
    total = len(filiais_ok) + len(falhas)
    icone = "\u274C" if not filiais_ok else ("\u2705" if not falhas else "\u26A0\uFE0F")

    linhas = [
        f"{icone} *Relatórios de Vendas — {_marca(config)} — {ontem_str}*",
        "",
        f"{len(filiais_ok)} de {total} filiais processadas:",
    ]
    for nome in filiais_ok:
        linhas.append(f"• {nome}")

    if falhas:
        linhas.append("")
        linhas.append("*Falhas:*")
        for nome, motivo in falhas:
            linhas.append(f"• {nome} — {motivo}")

    linhas.append("")
    if email_enviado:
        linhas.append(
            "\U0001F4E7 Enviados por e-mail. Confira a caixa de entrada."
        )
    else:
        linhas.append("\U0001F4C4 Arquivos .txt e .csv gerados localmente.")

    return "\n".join(linhas)


# ----------------------------------------------------------------------
# Atalhos usados pelos scripts
# ----------------------------------------------------------------------
def notificar_whatsapp_filial(
    config,
    nome_filial,
    colaboradores_resultados,
    totais,
    ontem_str,
    periodo_inicio_str,
    meta_mes=None,
    email_enviado=False,
    imagem=None,
    dry_run=False,
):
    mensagem = montar_mensagem_filial(
        nome_filial,
        colaboradores_resultados,
        totais,
        ontem_str,
        periodo_inicio_str,
        meta_mes=meta_mes,
        email_enviado=email_enviado,
    )
    return enviar_whatsapp(config, mensagem, imagem=imagem, dry_run=dry_run)


def notificar_whatsapp_resumo(
    config, ontem_str, filiais_ok, falhas=None, email_enviado=True, dry_run=False
):
    mensagem = montar_mensagem_resumo(
        config, ontem_str, filiais_ok, falhas=falhas, email_enviado=email_enviado
    )
    return enviar_whatsapp(config, mensagem, dry_run=dry_run)
