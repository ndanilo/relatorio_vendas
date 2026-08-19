#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o relatorio de vendas do sistema EVO (W12 / evo5.w12app.com.br) filtrado
por ontem e pelo mes ate ontem, tipos "Contrato/Produto/Servico" e por
colaborador de venda, para uma ou mais filiais.

Requisitos: nenhum. Usa apenas a biblioteca padrao do Python 3 (testado com
Python 3.9+, presente por padrao no macOS).

Uso:
    python3 gerar_relatorio_vendas.py
    python3 gerar_relatorio_vendas.py --id-filial 1

    Para rodar todas as filiais com isolamento de erro, use
    rodar_relatorios_filiais.py.

Configuracao:
    Edite o arquivo "evo_config.json" (mesma pasta deste script). Login e
    e-mail sao globais; cada item em "filiais" tem seu id, nome e lista de
    colaboradores. O arquivo contem senha em texto puro: mantenha-o privado.

Como funciona (resumo tecnico):
    1) Faz login na API nova do EVO (evo-abc-api) e recebe um "tokenEvo3".
    2) Para cada filial: autentica no modulo legado (evo3) com aquele
       idFilial, extrai o antiforgerytoken e consulta listarVendas.
    3) Monta um relatorio .txt/.csv por filial e envia por e-mail em HTML
       responsivo (graficos SVG inline + tabelas) e texto puro como
       alternativa. O assunto inclui o nome da filial. Ao final do lote,
       se houve e-mail enviado e sms.ativo estiver true, envia um SMS
       de resumo por numero em sms.destinatarios (API Brevo).

Nao ha anexos de imagem: os graficos vao dentro do proprio HTML, entao
aparecem mesmo quando o cliente bloqueia imagens externas ou anexos.
"""

import argparse
import csv
import http.cookiejar
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from email_relatorio import montar_email_html

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "evo_config.json"
OUTPUT_DIR = SCRIPT_DIR / "relatorios"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

LOGIN_URL = "https://evo-abc-api.w12app.com.br/api/v1/auth/login"
LOGAR_EVO3_URL = "https://evo3.w12app.com.br/Login/LogarEvo3"
LISTAR_VENDAS_URL = "https://evo3.w12app.com.br/Gerencial/Vendas/listarVendas"
INDEX_VENDAS_REFERER = "https://evo3.w12app.com.br/Gerencial/Gerencial/Index/VENDAS"
BREVO_SMS_URL = "https://api.brevo.com/v3/transactionalSMS/send"


class EvoError(RuntimeError):
    pass


def carregar_config():
    if not CONFIG_PATH.exists():
        sys.exit(
            f"Arquivo de configuracao nao encontrado: {CONFIG_PATH}\n"
            "Crie o evo_config.json (veja o exemplo que foi gerado junto "
            "com este script)."
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


class EvoClient:
    """Cliente HTTP simples (sem dependencias externas) para o sistema EVO."""

    def __init__(self, config):
        self.config = config
        self.dns = config["dns"]
        self.id_filial = None
        self.antiforgerytoken = None
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar)
        )

    def _request(self, url, data=None, headers=None, method=None):
        headers = dict(headers or {})
        headers.setdefault("User-Agent", USER_AGENT)
        if data is not None and not isinstance(data, (bytes, bytearray)):
            data = data.encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            return self.opener.open(req, timeout=30)
        except urllib.error.HTTPError as exc:
            corpo = exc.read().decode("utf-8", errors="replace")
            raise EvoError(
                f"Erro HTTP {exc.code} ao chamar {url}:\n{corpo[:1000]}"
            ) from exc

    def login(self):
        payload = json.dumps(
            {
                "dns": self.dns,
                "login": self.config["login"],
                "senha": self.config["senha"],
                "fusoHorario": 180,
                "gofit": False,
                "idFilial": None,
                "etapaAtual": 1,
                "chaveOTP": "",
            }
        )
        resp = self._request(
            LOGIN_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://evo5.w12app.com.br",
                "Referer": "https://evo5.w12app.com.br/",
            },
        )
        body = json.loads(resp.read().decode("utf-8"))
        token_evo3 = body.get("usuario", {}).get("tokenEvo3")
        if not token_evo3:
            raise EvoError(
                "Login falhou ou 'tokenEvo3' nao veio na resposta. "
                "Confira usuario/senha em evo_config.json."
            )
        return token_evo3

    def logar_evo3(self, token_evo3, id_filial):
        # tokenEvo3 ja vem percent-encoded na resposta do login; NAO
        # reaplicar urlencode nele (senao vira double-encoding).
        url = (
            f"{LOGAR_EVO3_URL}"
            f"?TokenEvo3={token_evo3}"
            f"&idFilial={id_filial}"
            "&redirectToView=Index/VENDAS"
            "&redirectToController=Gerencial"
            "&redirectToArea=Gerencial"
        )
        resp = self._request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://evo5.w12app.com.br/",
            },
        )
        return resp.read().decode("utf-8", errors="replace")

    def autenticar_filial(self, token_evo3, id_filial):
        """Troca a sessao evo3 para a filial e atualiza o antiforgerytoken."""
        html_index = self.logar_evo3(token_evo3, id_filial)
        self.id_filial = id_filial
        self.antiforgerytoken = self.extrair_antiforgerytoken(html_index)

    @staticmethod
    def extrair_antiforgerytoken(html):
        # O evo3 embute o token ASP.NET em um input hidden; o JS da pagina
        # envia esse valor no header "antiforgerytoken" (ou "AntiForgeryToken").
        padroes = [
            r'name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']',
            r'value=["\']([^"\']+)["\'][^>]*name=["\']__RequestVerificationToken["\']',
            r"antiforgerytoken['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"name=['\"]antiforgerytoken['\"][^>]*(?:value|content)=['\"]([^'\"]+)['\"]",
            r"(?:value|content)=['\"]([^'\"]+)['\"][^>]*name=['\"]antiforgerytoken['\"]",
            r"id=['\"]antiforgerytoken['\"][^>]*value=['\"]([^'\"]+)['\"]",
            r"headers\s*:\s*\{[^}]*antiforgerytoken['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
        ]
        for padrao in padroes:
            m = re.search(padrao, html, re.IGNORECASE)
            if m:
                return m.group(1)
        debug_path = SCRIPT_DIR / "debug_pagina_evo3.html"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        raise EvoError(
            "Nao encontrei o 'antiforgerytoken' na pagina retornada pelo EVO.\n"
            f"Salvei a pagina em {debug_path} para inspecao - abra esse "
            "arquivo, procure por 'antiforgerytoken' e me avise o trecho "
            "encontrado para eu ajustar o script."
        )

    def listar_vendas(self, inicio_str, fim_str, id_funcionario, page_size=1000):
        if not self.antiforgerytoken or self.id_filial is None:
            raise EvoError(
                "Filial ainda nao autenticada (chame autenticar_filial antes)."
            )

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "antiforgerytoken": self.antiforgerytoken,
            "dnsfrontend": self.dns,
            "idfilialfrontend": str(self.id_filial),
            "Referer": INDEX_VENDAS_REFERER,
            "Origin": "https://evo3.w12app.com.br",
        }
        corpo = urllib.parse.urlencode(
            {
                "sort": "",
                "page": 1,
                "pageSize": page_size,
                "group": "NOME_FUNCIONARIO_VENDA-asc",
                "aggregate": "VALOR_VENDA-sum",
                "filter": "",
                "IdFuncionario": id_funcionario or "",
                "IdFuncionarioComis": "",
                "Inicio": inicio_str,
                "Fim": fim_str,
                "Contrato": "true",
                "Produto": "true",
                "Servico": "true",
                "DebitoRecorrente": "false",
                "TrocaDeContrato": "false",
                "ContratosAdicionais": "true",
                "FL_MANUAIS": "true",
                "FL_ONLINE": "true",
                "FL_CONTRATO_SECUNDARIO": "false",
                "idsContrato": "",
                "idsProduto": "",
                "idsServico": "",
                "IdsFiliais": "",
                "ConsideraEspecial": "true",
            }
        )
        resp = self._request(LISTAR_VENDAS_URL, data=corpo, headers=headers)
        return json.loads(resp.read().decode("utf-8"))


# ----------------------------------------------------------------------
# Configuracao / filiais
# ----------------------------------------------------------------------
def obter_colaboradores_legado(config):
    colaboradores = config.get("colaboradores")
    if colaboradores:
        return colaboradores
    if config.get("id_funcionario"):
        return [
            {
                "id_funcionario": config["id_funcionario"],
                "nome": config.get("nome_colaborador", ""),
            }
        ]
    return []


def obter_filiais(config, id_filial=None):
    """Retorna lista de filiais. Aceita o formato novo e o legado.

    Se id_filial for informado, retorna apenas essa filial.
    """
    filiais = config.get("filiais")
    if filiais:
        for filial in filiais:
            if "id_filial" not in filial:
                raise EvoError('Cada filial precisa de "id_filial".')
            if not filial.get("nome"):
                raise EvoError(
                    f'Filial id={filial["id_filial"]} precisa de "nome" '
                    "(titulo usado no relatorio e no assunto do e-mail)."
                )
            if not filial.get("colaboradores"):
                raise EvoError(
                    f'Filial "{filial["nome"]}" precisa de ao menos um '
                    'item em "colaboradores".'
                )
    else:
        colaboradores = obter_colaboradores_legado(config)
        if not colaboradores:
            raise EvoError(
                "Configure ao menos uma filial em evo_config.json "
                '(campo "filiais") ou o formato legado com "colaboradores".'
            )
        filiais = [
            {
                "id_filial": config.get("id_filial", 1),
                "nome": config.get(
                    "nome_filial", f"Filial {config.get('id_filial', 1)}"
                ),
                "colaboradores": colaboradores,
            }
        ]

    if id_filial is None:
        return filiais

    filtradas = [f for f in filiais if int(f["id_filial"]) == int(id_filial)]
    if not filtradas:
        raise EvoError(
            f"Filial id={id_filial} nao encontrada em evo_config.json."
        )
    return filtradas


def slugify(texto):
    # Nomes de filial tem acento; o nome do arquivo continua em ASCII.
    texto = unicodedata.normalize("NFKD", texto.strip().lower())
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "-", texto, flags=re.IGNORECASE)
    return texto.strip("-") or "filial"


# ----------------------------------------------------------------------
# Montagem do relatorio
# ----------------------------------------------------------------------
def extrair_registros(dados_json):
    registros = []
    for grupo in dados_json.get("Data", []):
        registros.extend(grupo.get("Items", []))
    return registros


def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")


def calcular_periodos(agora=None):
    """Define ontem e o intervalo mensal com base na data de execucao.

    Regra normal: ontem + mes do dia 1 ate ontem.
    Se rodar no dia 1 do mes: ontem = ultimo dia do mes anterior e o
    intervalo mensal cobre o mes anterior inteiro (dia 1 ate ontem).
    """
    agora = agora or datetime.now()
    ontem = agora - timedelta(days=1)

    if agora.day == 1:
        periodo_inicio = ontem.replace(day=1)
    else:
        periodo_inicio = agora.replace(day=1)

    return {
        "ontem_str": formatar_data(ontem),
        "periodo_inicio_str": formatar_data(periodo_inicio),
        "periodo_fim_str": formatar_data(ontem),
    }


def resumir_registros(registros):
    total = sum(item.get("VALOR_VENDA") or 0 for item in registros)
    return len(registros), total


def formatar_linhas_vendas(registros):
    linhas = []
    if not registros:
        linhas.append("  Nenhuma venda encontrada.")
        return linhas
    for item in registros:
        valor = item.get("VALOR_VENDA") or 0
        data_venda = (item.get("DT_VENDA") or "")[:16].replace("T", " ")
        linhas.append(
            f"  - {data_venda} | {item.get('NOME_COMPRADOR', '')} | "
            f"{item.get('DESCRICAO') or item.get('DS_ITEM', '')} | "
            f"R$ {valor:.2f} | {item.get('FORMA_PAGAMENTO', '')}"
        )
    return linhas


def montar_secao(titulo, registros):
    qtd, total = resumir_registros(registros)
    linhas = [titulo]
    linhas.extend(formatar_linhas_vendas(registros))
    linhas.append(f"  Subtotal: {qtd} venda(s) | R$ {total:.2f}")
    return linhas, qtd, total


def montar_secao_resumo(titulo, registros):
    qtd, total = resumir_registros(registros)
    linhas = [titulo]
    if not registros:
        linhas.append("  Nenhuma venda encontrada.")
    linhas.append(f"  Subtotal: {qtd} venda(s) | R$ {total:.2f}")
    return linhas


def montar_relatorio_texto(
    nome_filial, colaboradores_resultados, totais, ontem_str, periodo_inicio_str
):
    linhas = [
        "RELATÓRIO DE VENDAS - EVO",
        f"Filial: {nome_filial}",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
    ]

    for resultado in colaboradores_resultados:
        nome = resultado["nome"]
        linhas.append("=" * 70)
        linhas.append(nome.upper())
        linhas.append("=" * 70)
        linhas.append("")

        secao_ontem, _, _ = montar_secao(
            f"Ontem ({ontem_str})",
            resultado["registros_ontem"],
        )
        secao_mes = montar_secao_resumo(
            f"Mês ({periodo_inicio_str} a {ontem_str})",
            resultado["registros_mes"],
        )
        linhas.extend(secao_ontem)
        linhas.append("")
        linhas.extend(secao_mes)
        linhas.append("")

    linhas.append("=" * 70)
    linhas.append("TOTAIS (todos os colaboradores)")
    linhas.append("=" * 70)
    linhas.append("")

    secao_total_ontem = montar_secao_resumo(
        f"Ontem ({ontem_str})",
        totais["registros_ontem"],
    )
    secao_total_mes = montar_secao_resumo(
        f"Mês ({periodo_inicio_str} a {ontem_str})",
        totais["registros_mes"],
    )
    linhas.extend(secao_total_ontem)
    linhas.append("")
    linhas.extend(secao_total_mes)

    return "\n".join(linhas)


CAMPOS_CSV = [
    "FILIAL",
    "PERIODO",
    "COLABORADOR",
    "DT_VENDA",
    "NOME_COMPRADOR",
    "DESCRICAO",
    "DS_ITEM",
    "VALOR_ITEM",
    "VALOR_VENDA",
    "DS_DESCONTO",
    "VALOR_DESCONTO",
    "FORMA_PAGAMENTO",
    "NOME_CONSULTOR",
    "ID_VENDA",
]


def preparar_registros_csv(registros, colaborador, periodo, nome_filial):
    linhas = []
    for item in registros:
        linha = dict(item)
        linha["FILIAL"] = nome_filial
        linha["COLABORADOR"] = colaborador
        linha["PERIODO"] = periodo
        linhas.append(linha)
    return linhas


def salvar_csv(registros, caminho):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_CSV, extrasaction="ignore")
        writer.writeheader()
        for item in registros:
            writer.writerow(item)


# ----------------------------------------------------------------------
# Envio por e-mail
# ----------------------------------------------------------------------
def enviar_email(config, assunto, corpo_texto, anexos=None, corpo_html=None):
    """Envia o relatorio por e-mail usando smtplib (biblioteca padrao).

    Retorna True se o e-mail foi enviado; False se estiver desativado.
    So envia se config["email"]["ativo"] for true. Preencha os campos de
    "email" no evo_config.json antes de habilitar.

    corpo_texto e sempre enviado como alternativa em texto puro; corpo_html
    (quando informado) vira a versao principal. Os graficos vao inline no
    proprio HTML (SVG + tabelas), sem anexos de imagem.
    """
    import smtplib
    from email.message import EmailMessage

    email_cfg = config.get("email") or {}
    if not email_cfg.get("ativo"):
        print("Envio por e-mail desativado (email.ativo=false em evo_config.json).")
        return False

    destinatario = email_cfg["destinatario"]
    cc = (email_cfg.get("cc") or "").strip()

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = email_cfg["remetente"]
    msg["To"] = destinatario
    if cc:
        msg["Cc"] = cc
    msg.set_content(corpo_texto)

    if corpo_html:
        msg.add_alternative(corpo_html, subtype="html")

    for caminho in anexos or []:
        caminho = Path(caminho)
        with open(caminho, "rb") as f:
            dados = f.read()
        maintype, subtype = ("text", "csv") if caminho.suffix == ".csv" else ("text", "plain")
        msg.add_attachment(dados, maintype=maintype, subtype=subtype, filename=caminho.name)

    with smtplib.SMTP(email_cfg["smtp_servidor"], email_cfg.get("smtp_porta", 587)) as smtp:
        smtp.starttls()
        smtp.login(email_cfg["smtp_usuario"], email_cfg["smtp_senha_app"])
        smtp.send_message(msg)
    if cc:
        print(f"E-mail enviado para {destinatario} (cc: {cc}).")
    else:
        print(f"E-mail enviado para {destinatario}.")
    return True


def _conteudo_sms_ascii(texto):
    """Remove acentos para SMS com unicodeEnabled=false."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in normalizado if not unicodedata.combining(ch))


def enviar_sms_brevo(config, conteudo):
    """Envia SMS transacional via API Brevo para cada numero em sms.destinatarios.

    So envia se config["sms"]["ativo"] for true. Usa apenas a biblioteca padrao.
    """
    sms_cfg = config.get("sms") or {}
    if not sms_cfg.get("ativo"):
        print("Envio por SMS desativado (sms.ativo=false em evo_config.json).")
        return

    api_key = (sms_cfg.get("api_key") or "").strip()
    if not api_key:
        raise EvoError("sms.api_key ausente em evo_config.json.")

    destinatarios = sms_cfg.get("destinatarios") or []
    if not destinatarios:
        print("Nenhum destinatario SMS em sms.destinatarios; pulando envio.")
        return

    sender = sms_cfg.get("sender") or "Relatorios"
    organisation_prefix = (sms_cfg.get("organisation_prefix") or "").strip()
    sms_type = sms_cfg.get("type") or "transactional"
    unicode_enabled = bool(sms_cfg.get("unicode_enabled", False))
    conteudo_envio = conteudo if unicode_enabled else _conteudo_sms_ascii(conteudo)

    for recipient in destinatarios:
        telefone = str(recipient).strip().lstrip("+")
        if not telefone:
            continue
        payload = {
            "sender": sender,
            "recipient": telefone,
            "content": conteudo_envio,
            "type": sms_type,
            "unicodeEnabled": unicode_enabled,
        }
        if organisation_prefix:
            payload["organisationPrefix"] = organisation_prefix
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            BREVO_SMS_URL,
            data=body,
            method="POST",
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
            print(f"SMS enviado para {telefone}.")
            if raw:
                print(f"  Resposta Brevo: {raw[:300]}")
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode("utf-8", errors="replace")
            raise EvoError(
                f"Falha ao enviar SMS para {telefone} (HTTP {exc.code}): {detalhe}"
            ) from exc
        except urllib.error.URLError as exc:
            raise EvoError(f"Falha de rede ao enviar SMS para {telefone}: {exc}") from exc


def processar_filial(cliente, token_evo3, filial, periodos, agora, config):
    id_filial = filial["id_filial"]
    nome_filial = filial["nome"]
    colaboradores = filial["colaboradores"]
    meta_mes = filial.get("meta_mes")
    ontem_str = periodos["ontem_str"]
    periodo_inicio_str = periodos["periodo_inicio_str"]
    periodo_fim_str = periodos["periodo_fim_str"]

    print(f"\n--- Filial: {nome_filial} (id={id_filial}) ---")
    print("  Autenticando no evo3...")
    cliente.autenticar_filial(token_evo3, id_filial)

    print(f"  Buscando vendas para {len(colaboradores)} colaborador(es)...")
    print(f"  Ontem: {ontem_str} | Mes: {periodo_inicio_str} a {periodo_fim_str}")

    colaboradores_resultados = []
    todos_ontem = []
    todos_mes = []
    todos_csv = []

    for colab in colaboradores:
        nome = colab["nome"]
        id_func = colab["id_funcionario"]
        print(f"    - {nome}")

        dados_ontem = cliente.listar_vendas(ontem_str, ontem_str, id_func)
        registros_ontem = extrair_registros(dados_ontem)

        dados_mes = cliente.listar_vendas(periodo_inicio_str, periodo_fim_str, id_func)
        registros_mes = extrair_registros(dados_mes)

        colaboradores_resultados.append(
            {
                "nome": nome,
                "registros_ontem": registros_ontem,
                "registros_mes": registros_mes,
            }
        )
        todos_ontem.extend(registros_ontem)
        todos_mes.extend(registros_mes)
        todos_csv.extend(
            preparar_registros_csv(registros_ontem, nome, "Ontem", nome_filial)
        )
        todos_csv.extend(
            preparar_registros_csv(registros_mes, nome, "Mes", nome_filial)
        )

    totais = {"registros_ontem": todos_ontem, "registros_mes": todos_mes}
    texto = montar_relatorio_texto(
        nome_filial,
        colaboradores_resultados,
        totais,
        ontem_str,
        periodo_inicio_str,
    )
    print("\n" + texto + "\n")

    OUTPUT_DIR.mkdir(exist_ok=True)
    data_arquivo = agora.strftime("%Y-%m-%d")
    slug = slugify(nome_filial)
    txt_path = OUTPUT_DIR / f"relatorio_vendas_{slug}_{data_arquivo}.txt"
    csv_path = OUTPUT_DIR / f"relatorio_vendas_{slug}_{data_arquivo}.csv"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(texto)
    salvar_csv(todos_csv, csv_path)

    print(f"  Relatorio salvo em:\n    {txt_path}\n    {csv_path}")

    html = montar_email_html(
        nome_filial,
        colaboradores_resultados,
        totais,
        ontem_str,
        periodo_inicio_str,
        meta_mes=meta_mes,
    )

    assunto = f"Relatório de Vendas - {nome_filial} - {ontem_str}"
    return enviar_email(
        config,
        assunto=assunto,
        corpo_texto=texto,
        anexos=[txt_path, csv_path],
        corpo_html=html,
    )


def montar_conteudo_sms_resumo(config, ontem_str):
    """Texto unico de SMS apos o(s) e-mail(s) do grupo (ex.: marca do tenant)."""
    marca = (config.get("dns") or "Vendas").strip()
    if marca:
        marca = marca[:1].upper() + marca[1:].lower()
    else:
        marca = "Vendas"
    return (
        f"📌 Relatorio(s) de Vendas - {marca} - {ontem_str} "
        "enviado por e-mail. Confira a caixa de entrada."
    )


def notificar_sms_resumo(config, ontem_str):
    """Envia um SMS por numero em sms.destinatarios (resumo do grupo)."""
    enviar_sms_brevo(config, conteudo=montar_conteudo_sms_resumo(config, ontem_str))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Gera relatorio de vendas EVO por filial/colaborador."
    )
    parser.add_argument(
        "--id-filial",
        type=int,
        default=None,
        help="Processa apenas a filial com este id_filial (opcional).",
    )
    parser.add_argument(
        "--sem-sms",
        action="store_true",
        help="Nao envia SMS ao final (usado pelo orquestrador, que notifica uma vez).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config = carregar_config()
    filiais = obter_filiais(config, id_filial=args.id_filial)
    agora = datetime.now()
    periodos = calcular_periodos(agora)

    cliente = EvoClient(config)

    print("1/2 - Fazendo login...")
    token_evo3 = cliente.login()

    print(f"2/2 - Processando {len(filiais)} filial(is)...")
    emails_enviados = 0
    for filial in filiais:
        if processar_filial(cliente, token_evo3, filial, periodos, agora, config):
            emails_enviados += 1

    if emails_enviados and not args.sem_sms:
        notificar_sms_resumo(config, periodos["ontem_str"])


if __name__ == "__main__":
    try:
        main()
    except EvoError as exc:
        sys.exit(f"\nErro: {exc}")
