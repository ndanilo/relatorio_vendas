#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valida os graficos do e-mail renderizando o HTML no Chromium (Playwright).

Roda so em desenvolvimento: o job agendado continua usando apenas a
biblioteca padrao. Sao duas familias de cenario:

  * Relatorio de vendas: garante que o SVG inline e a versao em HTML puro
    representam os mesmos numeros, e que a versao HTML sobrevive quando o
    cliente de e-mail remove o SVG (Gmail) ou o ignora (Outlook).
  * Relatorio de metas: garante que projecao, %, falta e falta por dia
    aparecem com os valores das formulas da planilha, que a flag de status
    (abaixo/atingida) casa com o %, e que o % do total sai da razao entre os
    totais - nao da media dos percentuais individuais.

Os numeros esperados sao calculados aqui, direto das formulas, e nao
importados do codigo sob teste.

Uso:
    py -m pip install -r requirements-dev.txt
    py -m playwright install chromium
    py scripts/validar_graficos_email.py
    py scripts/validar_graficos_email.py --tentativas 5 --ver

Saida: codigo 0 quando todas as checagens passam; 1 caso contrario.
Screenshots de cada cenario ficam em test_grafico_*.png (ignorados no git).
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RAIZ = SCRIPT_DIR.parent
sys.path.insert(0, str(RAIZ))

from email_relatorio import montar_email_html, montar_email_metas_html  # noqa: E402
from metas_consultores import calcular_metas  # noqa: E402

# Tolerancias das checagens geometricas (em pontos percentuais / pixels).
TOLERANCIA_PERCENTUAL = 1.5
TOLERANCIA_PIXEL = 2.0


def _venda(comprador, valor, hora="10:30"):
    return {
        "NOME_COMPRADOR": comprador,
        "VALOR_VENDA": valor,
        "DT_VENDA": f"2026-07-30T{hora}:00",
        "DESCRICAO": "Plano trimestral",
        "FORMA_PAGAMENTO": "Cartao de credito",
    }


def cenarios():
    """Casos fixos usados na validacao (numeros previsiveis)."""
    return [
        {
            "nome": "padrao",
            "meta_mes": 500000,
            "colaboradores": [
                ("Colaborador A", [_venda("Ana Souza", 1200.0)], 240000.0),
                ("Colaborador B", [_venda("Bruno Lima", 800.0, "14:05")], 120000.0),
                ("Colaborador C", [], 40000.0),
            ],
        },
        {
            "nome": "meta-atingida",
            "meta_mes": 100000,
            "colaboradores": [
                ("Colaborador D", [_venda("Carla Dias", 5000.0)], 90000.0),
                ("Colaborador E", [_venda("Diego Reis", 2500.0)], 60000.0),
            ],
        },
        {
            "nome": "colaborador-unico",
            "meta_mes": 80000,
            "colaboradores": [
                ("Colaborador D", [_venda("Elena Motta", 3000.0)], 45000.0),
            ],
        },
        {
            "nome": "sem-vendas",
            "meta_mes": 200000,
            "colaboradores": [
                ("Colaborador A", [], 0.0),
                ("Colaborador B", [], 0.0),
            ],
        },
    ]


DIAS_UTEIS_PADRAO = {
    "total": 23.0,
    "passados": 9.0,
    "restantes": 14.0,
    "peso_sabado": 0.5,
}


def cenarios_metas():
    """Cenarios do relatorio de metas: (nome, meta, realizado no mes).

    As metas de "metas-padrao" sao desproporcionais de proposito: quem tem a
    meta pequena vai muito bem e quem tem a grande vai mal, entao a media dos
    percentuais (120.1%, marcador "▲") contradiz o % do total (90.2%, marcador
    "▼"). Trocar a formula do total pela media dos percentuais erra o numero,
    a barra e o marcador - as tres coisas quebram a checagem.

    "metas-atingida" tem um consultor que passou da meta: falta e falta por
    dia tem de sair zeradas, nunca negativas. Ali a soma das faltas limitadas
    (40 mil) tambem difere de meta_total - realizado_total (30 mil), que e o
    comportamento documentado.
    """
    return [
        {
            "nome": "metas-padrao",
            "tipo": "metas",
            "dias": DIAS_UTEIS_PADRAO,
            "consultores": [
                ("Consultor A", 200000.0, 70000.0),
                ("Consultor B", 20000.0, 15000.0),
                ("Consultor C", 170000.0, 52619.85),
            ],
        },
        {
            "nome": "metas-atingida",
            "tipo": "metas",
            "dias": DIAS_UTEIS_PADRAO,
            "consultores": [
                ("Consultor D", 100000.0, 110000.0),
                ("Consultor E", 80000.0, 40000.0),
            ],
        },
        {
            "nome": "metas-sem-vendas",
            "tipo": "metas",
            "dias": DIAS_UTEIS_PADRAO,
            "consultores": [
                ("Consultor A", 200000.0, 0.0),
                ("Consultor B", 150000.0, 0.0),
            ],
        },
    ]


def montar_html_metas(cenario):
    """Constroi o HTML do relatorio de metas e os numeros esperados."""
    dias = cenario["dias"]

    resultados = []
    config = []
    for indice, (nome, meta, realizado) in enumerate(cenario["consultores"]):
        resultados.append(
            {
                "id_funcionario": indice,
                "nome": nome,
                "registros_mes": (
                    [_venda(f"Mes {nome}", realizado)] if realizado else []
                ),
            }
        )
        config.append({"id_funcionario": indice, "meta_funcionario": meta})

    metas = calcular_metas(resultados, config, dias)
    html = montar_email_metas_html(
        f"Unidade Centro ({cenario['nome']})", metas, "01/09/2026", "13/09/2026"
    )

    # Formulas da planilha, recalculadas aqui de forma independente.
    linhas = {}
    meta_total = realizado_total = projecao_total = falta_total = 0.0
    for nome, meta, realizado in cenario["consultores"]:
        projecao = realizado / dias["passados"] * dias["total"]
        percentual = projecao / meta * 100
        falta = max(meta - realizado, 0.0)
        linhas[nome] = {
            "meta": meta,
            "realizado": realizado,
            "projecao": projecao,
            "percentual": percentual,
            "falta": falta,
            "por_dia": falta / dias["restantes"],
            "status": "atingida" if percentual >= 100 else "abaixo",
        }
        meta_total += meta
        realizado_total += realizado
        projecao_total += projecao
        falta_total += falta

    percentual_total = projecao_total / meta_total * 100
    esperado = {
        "dias": dias,
        "linhas": linhas,
        "total": {
            "meta": meta_total,
            "realizado": realizado_total,
            "projecao": projecao_total,
            "percentual": percentual_total,
            "falta": falta_total,
            "por_dia": falta_total / dias["restantes"],
            "status": "atingida" if percentual_total >= 100 else "abaixo",
        },
    }
    return html, esperado


def montar_html(cenario):
    """Constroi o HTML do e-mail e os totais esperados para o cenario."""
    resultados = []
    todos_ontem = []
    todos_mes = []

    for nome, vendas_ontem, total_mes in cenario["colaboradores"]:
        # Uma unica venda sintetica representa o mes: o relatorio so usa o
        # somatorio de VALOR_VENDA para a contribuicao.
        registros_mes = (
            [_venda(f"Mes {nome}", total_mes)] if total_mes > 0 else []
        )
        resultados.append(
            {
                "nome": nome,
                "registros_ontem": vendas_ontem,
                "registros_mes": registros_mes,
            }
        )
        todos_ontem.extend(vendas_ontem)
        todos_mes.extend(registros_mes)

    totais = {"registros_ontem": todos_ontem, "registros_mes": todos_mes}
    html = montar_email_html(
        f"Unidade Centro ({cenario['nome']})",
        resultados,
        totais,
        "30/07/2026",
        "01/07/2026",
        meta_mes=cenario["meta_mes"],
    )

    total_mes = sum(item["VALOR_VENDA"] for item in todos_mes)
    meta = cenario["meta_mes"]
    percentual_meta = (total_mes / meta * 100) if meta else 0.0
    esperado = {
        "total_mes": total_mes,
        "meta_mes": meta,
        "percentual_meta": percentual_meta,
        "proporcao_barra_meta": min(percentual_meta / 100, 1.0),
        "participacoes": {
            nome: (valor / total_mes * 100) if total_mes else 0.0
            for nome, _, valor in cenario["colaboradores"]
        },
    }
    return html, esperado


def _quase_igual(obtido, esperado, tolerancia):
    return abs(obtido - esperado) <= tolerancia


def _texto_normalizado(pagina):
    return pagina.inner_text("body").replace("\u00a0", " ").replace("\n", " ")


def checar_textos(pagina, esperado, falhas):
    """Garante que rotulos HTML nao colam como 'MesR$' ou '...000,0091.1%'."""
    from email_relatorio import formatar_moeda

    corpo = _texto_normalizado(pagina)

    for colado in ("MesR$", "MêsR$"):
        if colado in corpo:
            falhas.append(f"Texto colado: '{colado}' (rotulo dentro do SVG)")

    if esperado["meta_mes"]:
        moeda_meta = formatar_moeda(esperado["meta_mes"])
        percentual = f"{esperado['percentual_meta']:.1f}%"
        if f"{moeda_meta}{percentual}" in corpo:
            falhas.append(
                f"Texto colado: '{moeda_meta}{percentual}' (percentual grudado na meta)"
            )

    if pagina.query_selector("svg text") is not None:
        falhas.append("SVG contem <text>; clientes de e-mail colam esses rotulos")


def checar_svg(pagina, esperado, falhas):
    """Donut (so formas) coerente com os numeros; meta e sempre HTML."""
    donut = pagina.query_selector('svg[data-grafico="contribuicao"]')
    tem_vendas = esperado["total_mes"] > 0

    if tem_vendas and donut is None:
        falhas.append("SVG do donut ausente")
    if not tem_vendas and donut is not None:
        falhas.append("SVG do donut presente sem vendas no mes")

    if donut is not None:
        if donut.query_selector("text") is not None:
            falhas.append("Donut ainda tem texto SVG")
        fatias = donut.query_selector_all("circle.fatia")
        if not fatias:
            falhas.append("Donut sem fatias")
        soma_graus = sum(float(f.get_attribute("data-graus")) for f in fatias)
        if not _quase_igual(soma_graus, 360.0, 0.5):
            falhas.append(f"Fatias somam {soma_graus:.2f} graus (esperado 360)")

        for fatia in fatias:
            nome = fatia.get_attribute("data-nome")
            obtido = float(fatia.get_attribute("data-percentual"))
            alvo = esperado["participacoes"].get(nome)
            if alvo is None:
                falhas.append(f"Fatia inesperada no donut: {nome}")
            elif not _quase_igual(obtido, alvo, TOLERANCIA_PERCENTUAL):
                falhas.append(
                    f"Fatia {nome}: {obtido:.1f}% no SVG vs {alvo:.1f}% esperado"
                )

        caixa = donut.bounding_box()
        if not caixa or caixa["width"] < 100 or caixa["height"] < 100:
            falhas.append("Donut renderizou com area pequena demais")

    if pagina.query_selector('svg[data-grafico="meta"]') is not None:
        falhas.append("Meta nao deve mais usar SVG (texto quebrava no e-mail)")


def checar_html(pagina, esperado, falhas):
    """Meta e ranking em HTML: numeros, barras e layout legivel."""
    from email_relatorio import formatar_moeda

    meta = pagina.query_selector('tr[data-bloco="meta"][data-grafico="meta"]')
    if meta is None:
        falhas.append("Bloco HTML da meta ausente")
    else:
        if not meta.is_visible():
            falhas.append("Bloco da meta oculto")
        texto_meta = meta.inner_text().replace("\u00a0", " ")
        esperado_valor = (
            f"{formatar_moeda(esperado['total_mes'])} de "
            f"{formatar_moeda(esperado['meta_mes'])}"
        )
        if esperado_valor not in texto_meta:
            falhas.append(f"Meta sem o texto '{esperado_valor}'")
        percentual = f"{esperado['percentual_meta']:.1f}%"
        if percentual not in texto_meta:
            falhas.append(f"Meta sem o percentual '{percentual}'")
        if f"{formatar_moeda(esperado['meta_mes'])}{percentual}" in texto_meta:
            falhas.append("Percentual da meta colado ao valor em reais")

        celula = meta.query_selector("td.preenchimento")
        alvo_barra = esperado["proporcao_barra_meta"] * 100
        if celula is None:
            if alvo_barra > 0:
                falhas.append("Meta sem barra preenchida")
        else:
            obtido = float(celula.get_attribute("data-percentual"))
            if not _quase_igual(obtido, alvo_barra, TOLERANCIA_PERCENTUAL):
                falhas.append(
                    f"Barra da meta em {obtido:.1f}% vs {alvo_barra:.1f}% esperado"
                )

    contribuicao = pagina.query_selector(
        'tr[data-bloco="contribuicao"][data-grafico="contribuicao"]'
    )
    if contribuicao is None:
        falhas.append("Bloco HTML da contribuicao ausente")
        return
    if not contribuicao.is_visible():
        falhas.append("Bloco da contribuicao oculto")

    if contribuicao.query_selector("table.empilhada") is not None:
        falhas.append("Barra empilhada ainda presente (estilo abandonado)")

    texto_contrib = contribuicao.inner_text().replace("\u00a0", " ")
    if "MesR$" in texto_contrib or "MêsR$" in texto_contrib:
        falhas.append("Rotulo do mes colado ao valor em reais")
    if formatar_moeda(esperado["total_mes"]) not in texto_contrib:
        falhas.append("Total do mes ausente abaixo do donut")

    linhas = contribuicao.query_selector_all("tr.participacao")
    if len(linhas) != len(esperado["participacoes"]):
        falhas.append(
            f"{len(linhas)} linha(s) por colaborador; "
            f"esperado {len(esperado['participacoes'])}"
        )
    for linha in linhas:
        nome = linha.get_attribute("data-nome")
        if nome not in esperado["participacoes"]:
            falhas.append(f"Linha de colaborador inesperada: {nome}")
            continue
        if not linha.is_visible():
            falhas.append(f"Linha de {nome} invisivel")
        texto = linha.inner_text().replace("\u00a0", " ")
        if nome not in texto:
            falhas.append(f"Nome de {nome} ausente na linha")
        percentual = esperado["participacoes"][nome]
        if f"{percentual:.1f}%" not in texto:
            falhas.append(f"Percentual de {nome} ausente na linha")


def checar_sem_svg(pagina, esperado, falhas):
    """Simula o cliente que remove SVG: o HTML precisa continuar completo."""
    from email_relatorio import formatar_moeda

    pagina.evaluate("document.querySelectorAll('svg').forEach(el => el.remove())")

    if pagina.query_selector("svg") is not None:
        falhas.append("SVG ainda presente apos a remocao simulada")

    # Com o SVG removido, o container pode ficar; o total e o ranking bastam.
    for nome, percentual in esperado["participacoes"].items():
        alvo = pagina.query_selector(f'tr.participacao[data-nome="{nome}"]')
        if alvo is None or not alvo.is_visible():
            falhas.append(f"Sem SVG, {nome} sumiu do relatorio")
            continue
        texto = alvo.inner_text().replace("\u00a0", " ")
        if f"{percentual:.1f}%" not in texto:
            falhas.append(f"Sem SVG, o percentual de {nome} nao aparece")

    corpo = _texto_normalizado(pagina)
    if formatar_moeda(esperado["total_mes"]) not in corpo:
        falhas.append("Sem SVG, o total do mes sumiu")
    if esperado["meta_mes"]:
        percentual = f"{esperado['percentual_meta']:.1f}%"
        if percentual not in corpo:
            falhas.append("Sem SVG, o progresso da meta nao aparece em texto")


# O rotulo e o mesmo nos dois estados de proposito (ver metas_consultores.status);
# quem distingue abaixo de atingida e o marcador, entao ele tambem e checado.
ROTULO_STATUS = "PROJEÇÃO DA META"
MARCADOR_STATUS = {"abaixo": "▼", "atingida": "▲"}


def _checar_cartao_meta(cartao, alvo, falhas, rotulo):
    """Confere um cartao do relatorio de metas contra os numeros esperados."""
    from email_relatorio import formatar_moeda

    if not cartao.is_visible():
        falhas.append(f"{rotulo}: cartao oculto")

    # A barra do cartao mede projecao sobre meta, e a do topo mede realizado
    # sobre meta. Sem o rotulo as duas teriam a mesma cara medindo coisas
    # diferentes, entao ele e obrigatorio.
    texto_barra = (
        f"Projeção {formatar_moeda(alvo['projecao'])} de "
        f"{formatar_moeda(alvo['meta'])}"
    )
    if texto_barra not in cartao.inner_text().replace("\u00a0", " "):
        falhas.append(f"{rotulo}: barra sem o rotulo '{texto_barra}'")

    status = cartao.get_attribute("data-status")
    if status != alvo["status"]:
        falhas.append(
            f"{rotulo}: status '{status}' vs '{alvo['status']}' esperado "
            f"(% = {alvo['percentual']:.1f})"
        )

    obtido = float(cartao.get_attribute("data-percentual"))
    if not _quase_igual(obtido, alvo["percentual"], TOLERANCIA_PERCENTUAL):
        falhas.append(
            f"{rotulo}: {obtido:.1f}% no cartao vs {alvo['percentual']:.1f}% esperado"
        )

    texto = cartao.inner_text().replace("\u00a0", " ")
    selo = f"{MARCADOR_STATUS[alvo['status']]} {ROTULO_STATUS}"
    if selo not in texto:
        falhas.append(f"{rotulo}: selo '{selo}' ausente")
    marcador_errado = MARCADOR_STATUS[
        "atingida" if alvo["status"] == "abaixo" else "abaixo"
    ]
    if marcador_errado in texto:
        falhas.append(f"{rotulo}: marcador '{marcador_errado}' nao deveria aparecer")

    for campo in ("meta", "realizado", "projecao", "falta", "por_dia"):
        valor = formatar_moeda(alvo[campo])
        if valor not in texto:
            falhas.append(f"{rotulo}: {campo} '{valor}' ausente no cartao")

    if f"{alvo['percentual']:.1f}%" not in texto:
        falhas.append(f"{rotulo}: percentual '{alvo['percentual']:.1f}%' ausente")

    barra = cartao.query_selector("td.preenchimento")
    alvo_barra = min(alvo["percentual"], 100)
    if barra is None:
        if alvo_barra > 0:
            falhas.append(f"{rotulo}: barra de progresso sem preenchimento")
    else:
        largura = float(barra.get_attribute("data-percentual"))
        if not _quase_igual(largura, alvo_barra, TOLERANCIA_PERCENTUAL):
            falhas.append(
                f"{rotulo}: barra em {largura:.1f}% vs {alvo_barra:.1f}% esperado"
            )


def checar_metas(pagina, esperado, falhas):
    """Relatorio de metas: numeros, flag do % e o rodape de dias uteis."""
    from email_relatorio import formatar_moeda
    from metas_consultores import formatar_dias

    barra_topo = pagina.query_selector('tr[data-bloco="meta"]')
    if barra_topo is None:
        falhas.append("Barra de progresso do total ausente")
    else:
        texto_topo = (
            f"Realizado {formatar_moeda(esperado['total']['realizado'])} de "
            f"{formatar_moeda(esperado['total']['meta'])}"
        )
        if texto_topo not in barra_topo.inner_text().replace("\u00a0", " "):
            falhas.append(f"Barra do total sem o rotulo '{texto_topo}'")

    cartoes = pagina.query_selector_all('tr[data-bloco="meta-consultor"]')
    if len(cartoes) != len(esperado["linhas"]):
        falhas.append(
            f"{len(cartoes)} cartao(oes) de consultor; "
            f"esperado {len(esperado['linhas'])}"
        )

    vistos = []
    for cartao in cartoes:
        nome = cartao.get_attribute("data-nome")
        alvo = esperado["linhas"].get(nome)
        if alvo is None:
            falhas.append(f"Cartao de consultor inesperado: {nome}")
            continue
        vistos.append(nome)
        _checar_cartao_meta(cartao, alvo, falhas, nome)

    # Pior % primeiro: quem precisa de atencao nao pode cair no fim da lista.
    ordenado = sorted(vistos, key=lambda nome: esperado["linhas"][nome]["percentual"])
    if vistos != ordenado:
        falhas.append(f"Cartoes fora de ordem por %: {vistos} (esperado {ordenado})")

    total = pagina.query_selector('tr[data-bloco="meta-total"]')
    if total is None:
        falhas.append("Cartao do total da filial ausente")
    else:
        # Se o % do total virasse media dos percentuais individuais, este
        # cenario acusaria: os numeros foram escolhidos para divergirem.
        _checar_cartao_meta(total, esperado["total"], falhas, "Total")

    rodape = pagina.query_selector('tr[data-bloco="dias-uteis"]')
    if rodape is None:
        falhas.append("Rodape de dias uteis ausente")
    else:
        dias = esperado["dias"]
        for campo in ("total", "passados", "restantes"):
            obtido = float(rodape.get_attribute(f"data-{campo}"))
            if not _quase_igual(obtido, dias[campo], 0.01):
                falhas.append(
                    f"Rodape: dias {campo} = {obtido:g} vs {dias[campo]:g} esperado"
                )
        texto = rodape.inner_text().replace("\u00a0", " ")
        for campo in ("total", "passados", "restantes"):
            if formatar_dias(dias[campo]) not in texto:
                falhas.append(f"Rodape sem os dias uteis {campo} em texto")

    # O relatorio de metas nao usa SVG, entao nao ha o que quebrar no Gmail.
    if pagina.query_selector("svg") is not None:
        falhas.append("Relatorio de metas nao deveria ter SVG")

    corpo = _texto_normalizado(pagina)
    for colado in ("metaR$", "METAR$", "%R$"):
        if colado in corpo:
            falhas.append(f"Texto colado: '{colado}'")


def validar_cenario(pagina, cenario, destino, ver=False):
    metas = cenario.get("tipo") == "metas"
    html, esperado = montar_html_metas(cenario) if metas else montar_html(cenario)
    arquivo = destino / f"test_email_{cenario['nome']}.html"
    arquivo.write_text(html, encoding="utf-8")

    falhas = []
    pagina.goto(arquivo.as_uri())
    pagina.wait_for_load_state("load")

    if metas:
        checar_metas(pagina, esperado, falhas)
    else:
        checar_svg(pagina, esperado, falhas)
        checar_html(pagina, esperado, falhas)
        checar_textos(pagina, esperado, falhas)

    pagina.screenshot(
        path=str(destino / f"test_grafico_{cenario['nome']}.png"), full_page=True
    )

    if not metas:
        checar_sem_svg(pagina, esperado, falhas)
        checar_textos(pagina, esperado, falhas)
        pagina.screenshot(
            path=str(destino / f"test_grafico_{cenario['nome']}_sem_svg.png"),
            full_page=True,
        )

    if ver:
        print(f"    HTML: {arquivo}")
    return falhas


def executar(tentativas, ver):
    from playwright.sync_api import sync_playwright

    destino = RAIZ
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 700, "height": 1200})

        restantes = cenarios() + cenarios_metas()
        for tentativa in range(1, tentativas + 1):
            print(f"Tentativa {tentativa}/{tentativas}")
            falharam = []
            for cenario in restantes:
                falhas = validar_cenario(pagina, cenario, destino, ver=ver)
                if falhas:
                    falharam.append(cenario)
                    print(f"  [FALHA] {cenario['nome']}")
                    for falha in falhas:
                        print(f"    - {falha}")
                else:
                    print(f"  [OK] {cenario['nome']}")

            if not falharam:
                navegador.close()
                print("\nTodos os cenarios passaram.")
                return 0
            restantes = falharam

        navegador.close()

    print(
        f"\n{len(restantes)} cenario(s) ainda falhando apos {tentativas} tentativa(s)."
    )
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Valida os graficos do e-mail com Playwright."
    )
    parser.add_argument(
        "--tentativas",
        type=int,
        default=3,
        help="Quantas vezes repetir os cenarios que falharem (padrao: 3).",
    )
    parser.add_argument(
        "--ver",
        action="store_true",
        help="Mostra o caminho do HTML gerado em cada cenario.",
    )
    args = parser.parse_args(argv)
    return executar(args.tentativas, args.ver)


if __name__ == "__main__":
    sys.exit(main())
