#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Desenha o relatorio de vendas como PNG, para anexar na notificacao do
WhatsApp (que nao renderiza HTML).

Por que nao rasterizar o HTML do e-mail: todo conversor HTML->imagem carrega
um motor de browser junto (Chromium, wkhtmltoimage, WeasyPrint) e, em
container enxuto, isso vira dependencia de libs X11 que o pip nao instala
(libXdamage, libnss3, libgbm...). Aqui o desenho sai direto do Pillow:
~0,2s por relatorio contra ~4s do Chromium, sem nenhuma dependencia nativa.

O preco e manter um segundo layout - este arquivo repete a estrutura visual
de email_relatorio.py. A paleta, o formato de moeda e a cor por colaborador
sao importados de la, entao pelo menos isso nunca diverge.

A fonte fica versionada em assets/fonts: a fonte embutida no Pillow so cobre
ASCII e transformaria "Anaca Musica" e "Contribuicao" em quadradinhos.

Dependencia: Pillow.
"""

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from email_relatorio import (
    COR_ALERTA,
    COR_BORDA,
    COR_DESTAQUE,
    COR_FUNDO,
    COR_POSITIVO,
    COR_SUAVE,
    COR_TINTA,
    cor_colaborador,
    formatar_moeda,
    formatar_moeda_opcional,
    formatar_percentual,
    resumir,
)

FONTES_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FONTE_REGULAR = FONTES_DIR / "DejaVuSans.ttf"
FONTE_NEGRITO = FONTES_DIR / "DejaVuSans-Bold.ttf"

BRANCO = "#FFFFFF"

# Todas as medidas abaixo estao em px logicos; a escala multiplica na hora
# de pintar. Assim imagem_escala=2 dobra a nitidez sem mexer no layout.
LARGURA_PADRAO = 640
MARGEM = 20
RAIO = 10
PADDING = 24
ESPACO_CARTOES = 12


class _Tela:
    """Desenha em px logicos e aplica a escala ao pintar.

    Com draw=None nada e pintado: a mesma rotina mede a altura final antes
    de criar a imagem no tamanho exato, evitando cortar ou sobrar fundo.
    """

    _fontes = {}
    _medidor = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def __init__(self, escala, draw=None):
        self.escala = escala
        self.draw = draw

    def _px(self, valor):
        return int(round(valor * self.escala))

    def fonte(self, tamanho, negrito=False):
        chave = (self._px(tamanho), negrito)
        if chave not in _Tela._fontes:
            caminho = FONTE_NEGRITO if negrito else FONTE_REGULAR
            _Tela._fontes[chave] = ImageFont.truetype(str(caminho), chave[0])
        return _Tela._fontes[chave]

    def largura(self, texto, tamanho, negrito=False):
        fonte = self.fonte(tamanho, negrito)
        return _Tela._medidor.textlength(texto, font=fonte) / self.escala

    def truncar(self, texto, tamanho, largura_max, negrito=False):
        if self.largura(texto, tamanho, negrito) <= largura_max:
            return texto
        reticencias = "\u2026"
        corte = texto
        while corte and self.largura(
            corte + reticencias, tamanho, negrito
        ) > largura_max:
            corte = corte[:-1]
        return (corte.rstrip() + reticencias) if corte else ""

    def texto(self, x, y, texto, tamanho, cor, negrito=False, ancora="la"):
        # A ancora vertical e sempre "a" (ascendente da fonte), nunca "t"
        # (topo da tinta): "t" e medido por glifo, entao o "Ê" desceria e o
        # ponto de "180.000,00" subiria para o alto da linha.
        if self.draw is not None and texto:
            self.draw.text(
                (self._px(x), self._px(y)),
                texto,
                font=self.fonte(tamanho, negrito),
                fill=cor,
                anchor=ancora,
            )

    def largura_espacada(self, texto, tamanho, tracking, negrito=False):
        if not texto:
            return 0
        return (
            sum(self.largura(char, tamanho, negrito) for char in texto)
            + tracking * (len(texto) - 1)
        )

    def texto_espacado(self, x, y, texto, tamanho, cor, tracking, negrito=False):
        """Rotulos em caixa alta do e-mail usam letter-spacing; o Pillow nao
        tem isso, entao o texto sai caractere a caractere."""
        cursor = x
        for char in texto:
            self.texto(cursor, y, char, tamanho, cor, negrito=negrito)
            cursor += self.largura(char, tamanho, negrito) + tracking

    def cartao(self, x, y, largura, altura, cor_faixa=None):
        if self.draw is None:
            return
        self.draw.rounded_rectangle(
            [self._px(x), self._px(y), self._px(x + largura), self._px(y + altura)],
            radius=self._px(RAIO),
            fill=BRANCO,
            outline=COR_BORDA,
            width=max(1, self._px(1)),
        )
        if cor_faixa:
            # Equivalente ao border-left:4px dos cartoes de colaborador.
            self.draw.rounded_rectangle(
                [self._px(x), self._px(y), self._px(x + 8), self._px(y + altura)],
                radius=self._px(RAIO),
                fill=cor_faixa,
            )
            self.draw.rectangle(
                [self._px(x + 4), self._px(y), self._px(x + 9), self._px(y + altura)],
                fill=BRANCO,
            )

    def regua(self, x, y, largura):
        if self.draw is not None:
            self.draw.rectangle(
                [self._px(x), self._px(y), self._px(x + largura), self._px(y) + 1],
                fill=COR_BORDA,
            )

    def barra(self, x, y, largura, percentual, cor, altura=10):
        if self.draw is None:
            return
        raio = self._px(altura / 2)
        self.draw.rounded_rectangle(
            [self._px(x), self._px(y), self._px(x + largura), self._px(y + altura)],
            radius=raio,
            fill=COR_BORDA,
        )
        preenchido = largura * min(max(percentual, 0), 100) / 100
        if preenchido <= 0:
            return
        # Abaixo de uma bolinha o rounded_rectangle degenera; garante o minimo.
        preenchido = max(preenchido, altura)
        self.draw.rounded_rectangle(
            [self._px(x), self._px(y), self._px(x + preenchido), self._px(y + altura)],
            radius=raio,
            fill=cor,
        )

    def swatch(self, x, y, lado, cor):
        if self.draw is not None:
            self.draw.rounded_rectangle(
                [self._px(x), self._px(y), self._px(x + lado), self._px(y + lado)],
                radius=self._px(3),
                fill=cor,
            )


# ----------------------------------------------------------------------
# Blocos (cada funcao recebe o y do topo e devolve o y de baixo)
# ----------------------------------------------------------------------
def _cabecalho(tela, y, titulo, nome_filial, subtitulo):
    tela.texto_espacado(MARGEM, y, titulo, 11, COR_DESTAQUE, 1.4, negrito=True)
    y += 18
    tela.texto(MARGEM, y, nome_filial, 24, COR_TINTA, negrito=True)
    y += 34
    tela.texto(MARGEM, y, subtitulo, 13, COR_SUAVE)
    y += 19
    tela.texto(
        MARGEM,
        y,
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        11,
        COR_SUAVE,
    )
    return y + 16 + 18


def _cartao_kpi(tela, x, y, largura, rotulo, valor, detalhe, cor_valor):
    altura = 84
    tela.cartao(x, y, largura, altura)
    interno = x + 16
    tela.texto_espacado(interno, y + 15, rotulo, 11, COR_SUAVE, 0.9)
    tela.texto(interno, y + 34, valor, 20, cor_valor, negrito=True)
    tela.texto(interno, y + 62, detalhe, 12, COR_SUAVE)
    return y + altura


def _bloco_kpis(tela, y, largura, total_ontem, qtd_ontem, total_mes, qtd_mes):
    coluna = (largura - ESPACO_CARTOES) / 2
    _cartao_kpi(
        tela,
        MARGEM,
        y,
        coluna,
        "ONTEM",
        formatar_moeda(total_ontem),
        f"{qtd_ontem} venda(s)",
        COR_TINTA,
    )
    fim = _cartao_kpi(
        tela,
        MARGEM + coluna + ESPACO_CARTOES,
        y,
        coluna,
        "MÊS ATÉ ONTEM",
        formatar_moeda(total_mes),
        f"{qtd_mes} venda(s)",
        COR_DESTAQUE,
    )
    return fim + 16


def _bloco_meta(tela, y, largura, total_mes, meta_mes):
    percentual = total_mes / meta_mes * 100
    falta = max(meta_mes - total_mes, 0)
    cor = COR_POSITIVO if percentual >= 100 else COR_ALERTA
    y = _cartao_kpi(
        tela,
        MARGEM,
        y,
        largura,
        f"META DO MÊS ({formatar_moeda(meta_mes)})",
        f"{percentual:.1f}%",
        "Meta atingida" if falta <= 0 else f"Faltam {formatar_moeda(falta)}",
        cor,
    )
    return _barra_meta(tela, y + 12, largura, total_mes, meta_mes)


def _barra_meta(tela, y, largura, total_mes, meta_mes):
    """So o cartao da barra de progresso (o relatorio de metas usa apenas ele)."""
    percentual = total_mes / meta_mes * 100
    cor_barra = COR_POSITIVO if percentual >= 100 else COR_DESTAQUE
    altura = 74
    tela.cartao(MARGEM, y, largura, altura)
    interno = MARGEM + 18
    util = largura - 36
    tela.texto(
        interno,
        y + 17,
        f"{formatar_moeda(total_mes)} de {formatar_moeda(meta_mes)}",
        13,
        COR_TINTA,
    )
    tela.texto(
        MARGEM + largura - 18,
        y + 15,
        f"{percentual:.1f}%",
        16,
        cor_barra,
        negrito=True,
        ancora="ra",
    )
    tela.barra(interno, y + 44, util, percentual, cor_barra, altura=12)
    return y + altura + 20


def _titulo_secao(tela, y, texto):
    tela.texto_espacado(MARGEM, y, texto.upper(), 12, COR_SUAVE, 1.2)
    return y + 28


def _bloco_contribuicao(tela, y, largura, participacoes, total_mes):
    interno = MARGEM + 18
    util = largura - 36
    altura = 74 + 16 + len(participacoes) * 42
    tela.cartao(MARGEM, y, largura, altura)

    centro = MARGEM + largura / 2
    rotulo = "TOTAL DO MÊS"
    tela.texto_espacado(
        centro - tela.largura_espacada(rotulo, 12, 1.2) / 2,
        y + 16,
        rotulo,
        12,
        COR_SUAVE,
        1.2,
    )
    tela.texto(
        centro,
        y + 34,
        formatar_moeda(total_mes),
        22,
        COR_TINTA,
        negrito=True,
        ancora="ma",
    )

    linha_y = y + 74
    tela.regua(interno, linha_y, util)
    linha_y += 16

    for participacao in participacoes:
        cor = cor_colaborador(participacao["indice"])
        tela.swatch(interno, linha_y + 3, 12, cor)
        texto_valor = formatar_moeda(participacao["total"])
        texto_pct = f"{participacao['percentual']:.1f}%"
        largura_pct = tela.largura(texto_pct, 13, negrito=True)
        largura_valor = tela.largura(texto_valor, 13)
        espaco_nome = util - 20 - largura_valor - largura_pct - 24
        tela.texto(
            interno + 20,
            linha_y,
            tela.truncar(participacao["nome"], 14, espaco_nome, negrito=True),
            14,
            COR_TINTA,
            negrito=True,
        )
        tela.texto(
            interno + util - largura_pct - 12,
            linha_y + 1,
            texto_valor,
            13,
            COR_TINTA,
            ancora="ra",
        )
        tela.texto(
            interno + util, linha_y + 1, texto_pct, 13, cor, negrito=True, ancora="ra"
        )
        largura_barra = max(participacao["percentual"], 1) if participacao["total"] else 0
        tela.barra(interno, linha_y + 22, util, largura_barra, cor)
        linha_y += 42

    return y + altura + 20


def _bloco_colaborador(tela, y, largura, resultado, indice, ontem_str, periodo_label):
    qtd_ontem, total_ontem = resumir(resultado["registros_ontem"])
    qtd_mes, total_mes = resumir(resultado["registros_mes"])
    vendas = resultado["registros_ontem"]
    cor = cor_colaborador(indice)

    interno = MARGEM + 18
    util = largura - 36
    altura = 84 + (len(vendas) * 58 if vendas else 34)
    tela.cartao(MARGEM, y, largura, altura, cor_faixa=cor)

    tela.texto(interno, y + 16, resultado["nome"], 15, COR_TINTA, negrito=True)
    tela.texto(
        interno,
        y + 38,
        f"Ontem ({ontem_str}): {formatar_moeda(total_ontem)} "
        f"em {qtd_ontem} venda(s)",
        12,
        COR_SUAVE,
    )
    tela.texto(
        interno,
        y + 55,
        f"{periodo_label}: {formatar_moeda(total_mes)} em {qtd_mes} venda(s)",
        12,
        COR_SUAVE,
    )

    linha_y = y + 80
    if not vendas:
        tela.regua(interno, linha_y, util)
        tela.texto(interno, linha_y + 11, "Nenhuma venda registrada.", 13, COR_SUAVE)
        return y + altura + 16

    for item in vendas:
        tela.regua(interno, linha_y, util)
        valor = formatar_moeda(item.get("VALOR_VENDA") or 0)
        largura_valor = tela.largura(valor, 13, negrito=True)
        comprador = tela.truncar(
            item.get("NOME_COMPRADOR", ""), 13, util - largura_valor - 12, negrito=True
        )
        tela.texto(interno, linha_y + 11, comprador, 13, COR_TINTA, negrito=True)
        tela.texto(
            interno + util, linha_y + 11, valor, 13, COR_TINTA, negrito=True, ancora="ra"
        )

        descricao = item.get("DESCRICAO") or item.get("DS_ITEM") or ""
        tela.texto(
            interno, linha_y + 29, tela.truncar(descricao, 12, util), 12, COR_SUAVE
        )

        data_venda = (item.get("DT_VENDA") or "")[:16].replace("T", " ")
        hora = data_venda[11:16] if len(data_venda) >= 16 else data_venda
        pagamento = item.get("FORMA_PAGAMENTO") or ""
        tela.texto(
            interno,
            linha_y + 45,
            tela.truncar(f"{hora} · {pagamento}".strip(" ·"), 11, util),
            11,
            COR_SUAVE,
        )
        linha_y += 58

    return y + altura + 16


def _rodape(tela, y):
    tela.texto(MARGEM, y + 8, "Relatório automático do sistema EVO.", 11, COR_SUAVE)
    return y + 8 + 16


# ----------------------------------------------------------------------
# Montagem
# ----------------------------------------------------------------------
def _participacoes(colaboradores_resultados, total_mes):
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
    return participacoes


def _desenhar(
    tela,
    largura_conteudo,
    nome_filial,
    colaboradores_resultados,
    totais,
    ontem_str,
    periodo_inicio_str,
    meta_mes,
):
    """Passa por todos os blocos e devolve a altura total usada.

    Roda duas vezes: uma so para medir (tela sem draw) e outra pintando.
    """
    qtd_ontem, total_ontem = resumir(totais["registros_ontem"])
    qtd_mes, total_mes = resumir(totais["registros_mes"])
    periodo_label = f"Mês ({periodo_inicio_str} a {ontem_str})"

    y = PADDING
    y = _cabecalho(
        tela,
        y,
        "RELATÓRIO DE VENDAS",
        nome_filial,
        f"Ontem: {ontem_str} · {periodo_label}",
    )
    y = _bloco_kpis(
        tela, y, largura_conteudo, total_ontem, qtd_ontem, total_mes, qtd_mes
    )
    if meta_mes and meta_mes > 0:
        y = _bloco_meta(tela, y, largura_conteudo, total_mes, meta_mes)

    y = _titulo_secao(tela, y, "Contribuição no mês")
    y = _bloco_contribuicao(
        tela,
        y,
        largura_conteudo,
        _participacoes(colaboradores_resultados, total_mes),
        total_mes,
    )

    y = _titulo_secao(tela, y, f"Detalhe de ontem ({ontem_str})")
    for indice, resultado in enumerate(colaboradores_resultados):
        y = _bloco_colaborador(
            tela, y, largura_conteudo, resultado, indice, ontem_str, periodo_label
        )

    y = _rodape(tela, y)
    return y + PADDING


def gerar_png(
    destino,
    nome_filial,
    colaboradores_resultados,
    totais,
    ontem_str,
    periodo_inicio_str,
    meta_mes=None,
    largura=LARGURA_PADRAO,
    escala=2,
):
    """Desenha o relatorio e salva o PNG. Retorna o Path do arquivo."""
    return _salvar(
        destino,
        _desenhar,
        (
            nome_filial,
            colaboradores_resultados,
            totais,
            ontem_str,
            periodo_inicio_str,
            meta_mes,
        ),
        largura,
        escala,
    )


def _salvar(destino, desenhar, argumentos, largura, escala):
    """Mede a altura com uma tela sem tinta e repinta na imagem do tamanho exato."""
    argumentos = (largura - 2 * MARGEM,) + tuple(argumentos)

    altura = desenhar(_Tela(escala), *argumentos)

    imagem = Image.new(
        "RGB",
        (int(round(largura * escala)), int(round(altura * escala))),
        COR_FUNDO,
    )
    desenhar(_Tela(escala, ImageDraw.Draw(imagem)), *argumentos)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino, format="PNG", optimize=True)
    return destino


# ----------------------------------------------------------------------
# Relatorio de metas por consultor
# ----------------------------------------------------------------------
# Espelha email_relatorio.montar_email_metas_html: mesmos cartoes, mesmo selo
# de status e o mesmo rodape de dias uteis.
ALTURA_LINHA_METRICA = 38


def _quebrar(tela, texto, tamanho, largura_max):
    """Quebra o texto em linhas que cabem na largura (o Pillow nao faz isso)."""
    linhas = []
    atual = ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if atual and tela.largura(tentativa, tamanho) > largura_max:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
    if atual:
        linhas.append(atual)
    return linhas


def _metrica(tela, x, y, rotulo, valor, cor):
    tela.texto_espacado(x, y, rotulo.upper(), 10, COR_SUAVE, 0.7)
    tela.texto(x, y + 15, valor, 15, cor, negrito=True)


def _cartao_meta(tela, y, largura, linha):
    status = linha["status"]
    interno = MARGEM + 18
    util = largura - 36
    coluna = util / 2
    tem_barra = linha["percentual"] is not None

    altura = 16 + 22 + (18 if tem_barra else 0) + 3 * ALTURA_LINHA_METRICA + 8
    # Faixa lateral na cor do status, nao na cor do colaborador: aqui nao ha
    # donut para casar a cor, e faixa verde em cartao "ABAIXO DA META" mentiria.
    tela.cartao(MARGEM, y, largura, altura, cor_faixa=status["cor"])

    tela.texto(interno, y + 16, linha["nome"], 15, COR_TINTA, negrito=True)
    tela.texto(
        interno + util,
        y + 19,
        f"{status['marcador']} {status['rotulo']}",
        11,
        status["cor"],
        negrito=True,
        ancora="ra",
    )

    linha_y = y + 38
    if tem_barra:
        tela.barra(interno, linha_y, util, min(linha["percentual"], 100), status["cor"])
        linha_y += 18

    pares = [
        (
            ("Meta", formatar_moeda(linha["meta"]), COR_TINTA),
            ("Realizado", formatar_moeda(linha["realizado"]), COR_DESTAQUE),
        ),
        (
            ("Projeção", formatar_moeda_opcional(linha["projecao"]), status["cor"]),
            ("% da meta", formatar_percentual(linha["percentual"]), status["cor"]),
        ),
        (
            ("Falta", formatar_moeda(linha["falta"]), COR_TINTA),
            ("Por dia útil", formatar_moeda_opcional(linha["por_dia"]), COR_TINTA),
        ),
    ]
    for esquerda, direita in pares:
        _metrica(tela, interno, linha_y, *esquerda)
        _metrica(tela, interno + coluna, linha_y, *direita)
        linha_y += ALTURA_LINHA_METRICA

    return y + altura + 16


def _rodape_metas(tela, y, largura, metas):
    notas = list(metas["rodape"])
    if metas["sem_meta"]:
        notas.append(
            "Sem meta_funcionario configurada (fora deste relatório): "
            + ", ".join(metas["sem_meta"])
        )
    notas.append("Relatório automático do sistema EVO.")

    y += 8
    for nota in notas:
        for texto in _quebrar(tela, nota, 11, largura):
            tela.texto(MARGEM, y, texto, 11, COR_SUAVE)
            y += 16
    return y


def _desenhar_metas(
    tela, largura_conteudo, nome_filial, metas, periodo_inicio_str, ontem_str
):
    total = metas["total"]
    status = total["status"]

    y = PADDING
    y = _cabecalho(
        tela,
        y,
        "RELATÓRIO DE METAS",
        nome_filial,
        f"Mês ({periodo_inicio_str} a {ontem_str})",
    )

    coluna = (largura_conteudo - ESPACO_CARTOES) / 2
    _cartao_kpi(
        tela,
        MARGEM,
        y,
        coluna,
        "REALIZADO NO MÊS",
        formatar_moeda(total["realizado"]),
        f"de {formatar_moeda(total['meta'])} em metas",
        COR_TINTA,
    )
    y = _cartao_kpi(
        tela,
        MARGEM + coluna + ESPACO_CARTOES,
        y,
        coluna,
        "PROJEÇÃO DO MÊS",
        formatar_moeda_opcional(total["projecao"]),
        f"{formatar_percentual(total['percentual'])} da meta · "
        f"{status['marcador']} {status['rotulo']}",
        status["cor"],
    )
    y += 16

    if total["meta"] > 0:
        y = _barra_meta(tela, y, largura_conteudo, total["realizado"], total["meta"])

    y = _titulo_secao(tela, y, "Metas por consultor")
    for linha in metas["linhas"]:
        y = _cartao_meta(tela, y, largura_conteudo, linha)
    y = _cartao_meta(tela, y, largura_conteudo, total)

    y = _rodape_metas(tela, y, largura_conteudo, metas)
    return y + PADDING


def gerar_png_metas(
    destino,
    nome_filial,
    metas,
    periodo_inicio_str,
    ontem_str,
    largura=LARGURA_PADRAO,
    escala=2,
):
    """Desenha o relatorio de metas e salva o PNG. Retorna o Path do arquivo."""
    return _salvar(
        destino,
        _desenhar_metas,
        (nome_filial, metas, periodo_inicio_str, ontem_str),
        largura,
        escala,
    )
