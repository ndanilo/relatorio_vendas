#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notificacao dos relatorios via WhatsApp, usando a API local de notificacoes.

Sao dois tipos de mensagem:
  1) Uma por filial: o relatorio em PNG, com o titulo como legenda. Os
     numeros ficam so na imagem, para nao repetir tudo em texto.
  2) Um alerta ao final do lote, so texto, e SO quando alguma filial falha.
     No caminho feliz nada e enviado alem das imagens.

O PNG e desenhado por imagem_relatorio.py (Pillow), sem passar por HTML.
Se o desenho falhar por qualquer motivo, a mensagem sai apenas com o texto
e o job segue.

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


class WhatsAppError(RuntimeError):
    pass


def _cfg(config):
    return config.get("whatsapp") or {}


def whatsapp_ativo(config):
    return bool(_cfg(config).get("ativo"))


# ----------------------------------------------------------------------
# Imagem
# ----------------------------------------------------------------------
def gerar_imagem_relatorio(
    config,
    destino,
    nome_filial,
    colaboradores_resultados,
    totais,
    ontem_str,
    periodo_inicio_str,
    meta_mes=None,
):
    """Desenha o PNG do relatorio aplicando os ajustes do evo_config.json.

    Retorna o Path do arquivo, ou None se o anexo estiver desligado ou o
    desenho falhar - nesse caso a mensagem sai so com o texto e o job segue.
    """
    cfg = _cfg(config)
    if not cfg.get("anexar_imagem", True):
        return None

    try:
        from imagem_relatorio import gerar_png
    except ImportError as exc:
        print(
            f"[AVISO] Nao consegui carregar o desenhista do relatorio ({exc}); "
            "a mensagem do WhatsApp vai sem imagem.\n"
            "        Instale as dependencias: python3 -m pip install -r "
            "requirements.txt"
        )
        return None

    try:
        return gerar_png(
            destino,
            nome_filial,
            colaboradores_resultados,
            totais,
            ontem_str,
            periodo_inicio_str,
            meta_mes=meta_mes,
            largura=cfg.get("imagem_largura", 640),
            escala=cfg.get("imagem_escala", 2),
        )
    except Exception as exc:  # noqa: BLE001 - imagem e opcional, nao derruba o job
        print(
            "[AVISO] Nao consegui gerar a imagem do relatorio; a mensagem do "
            "WhatsApp vai sem anexo."
        )
        print(f"        Motivo: {' '.join(str(exc).split())[:200]}")
        return None


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
def _marca(config):
    marca = (config.get("dns") or "").strip()
    if not marca:
        return "Vendas"
    return marca[:1].upper() + marca[1:].lower()


def montar_mensagem_filial(nome_filial, ontem_str):
    """Legenda da imagem: so o titulo. Os numeros ja estao no PNG anexo."""
    return f"*RELATÓRIO DE VENDAS*\n\U0001F4CD _{nome_filial}_ · {ontem_str}"


def montar_mensagem_falhas(config, ontem_str, falhas):
    """Alerta de fim de lote. So existe quando alguma filial falha."""
    linhas = [
        f"\u26A0\uFE0F *Relatórios de Vendas — {_marca(config)} — {ontem_str}*",
        "",
        "Estas filiais não foram enviadas:",
    ]
    for nome, motivo in falhas:
        linhas.append(f"• {nome} — {motivo}")
    return "\n".join(linhas)


# ----------------------------------------------------------------------
# Atalhos usados pelos scripts
# ----------------------------------------------------------------------
def notificar_whatsapp_filial(
    config, nome_filial, ontem_str, imagem=None, dry_run=False
):
    mensagem = montar_mensagem_filial(nome_filial, ontem_str)
    return enviar_whatsapp(config, mensagem, imagem=imagem, dry_run=dry_run)


def notificar_whatsapp_falhas(config, ontem_str, falhas, dry_run=False):
    if not falhas:
        return False
    mensagem = montar_mensagem_falhas(config, ontem_str, falhas)
    return enviar_whatsapp(config, mensagem, dry_run=dry_run)
