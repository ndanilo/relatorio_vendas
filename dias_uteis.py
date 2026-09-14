#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calendario de dias uteis do Brasil, usado pelo relatorio de metas.

O peso de cada dia segue a regra da planilha de referencia: segunda a sexta
conta 1 dia, sabado conta meio dia (a academia abre pela manha), domingo e
feriado nao contam. Com isso setembro/2026 fecha em 23 dias uteis - o mesmo
numero que a planilha usa - em vez dos 21 dias uteis "de escritorio".

Os feriados nacionais sao calculados, nao listados: a Sexta-feira Santa
depende da Pascoa e mudaria de data todo ano. Feriados municipais/estaduais
e pontos facultativos entram por configuracao ("dias_uteis.feriados_extras"),
porque variam por cidade e por ramo.

Dependencias: nenhuma. Apenas a biblioteca padrao.

Uso avulso (conferencia rapida, sem tocar na API do EVO):
    py dias_uteis.py            # mes atual
    py dias_uteis.py 2026-09    # mes especifico
"""

import calendar
import sys
from datetime import date, timedelta

PESO_SABADO_PADRAO = 0.5

# Palavras-chave aceitas em feriados_extras para as datas moveis. Carnaval e
# Corpus Christi nao sao feriados nacionais (ponto facultativo), mas fecham a
# casa em boa parte do setor, entao ficam disponiveis por nome - o usuario nao
# precisa descobrir a data de cada ano.
DESLOCAMENTO_MOVEIS = {
    "carnaval": (-48, -47),  # segunda e terca de carnaval
    "corpus-christi": (60,),
}

# O calendario e remontado a cada consulta (mes, decorridos, restantes), entao
# um item invalido seria avisado varias vezes por filial; aqui sai uma vez.
_EXTRAS_INVALIDOS = set()


def pascoa(ano):
    """Domingo de Pascoa pelo algoritmo de Meeus/Butcher (calendario gregoriano)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    n = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * n) // 451
    mes, dia = divmod(h + n - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados_nacionais(ano):
    """Feriados nacionais do ano, incluindo o movel derivado da Pascoa."""
    domingo_pascoa = pascoa(ano)
    return {
        date(ano, 1, 1): "Confraternização Universal",
        domingo_pascoa - timedelta(days=2): "Sexta-feira Santa",
        date(ano, 4, 21): "Tiradentes",
        date(ano, 5, 1): "Dia do Trabalho",
        date(ano, 9, 7): "Independência",
        date(ano, 10, 12): "Nossa Senhora Aparecida",
        date(ano, 11, 2): "Finados",
        date(ano, 11, 15): "Proclamação da República",
        # Nacional desde a Lei 14.759/2023.
        date(ano, 11, 20): "Consciência Negra",
        date(ano, 12, 25): "Natal",
    }


def _datas_extra(ano, item):
    """Converte um item de feriados_extras nas datas que ele representa.

    Aceita "MM-DD" (repete todo ano), "AAAA-MM-DD" (so naquele ano) e as
    palavras-chave de DESLOCAMENTO_MOVEIS.
    """
    texto = str(item).strip().lower()
    if not texto:
        return []

    if texto in DESLOCAMENTO_MOVEIS:
        domingo_pascoa = pascoa(ano)
        return [
            domingo_pascoa + timedelta(days=dias)
            for dias in DESLOCAMENTO_MOVEIS[texto]
        ]

    partes = texto.split("-")
    try:
        if len(partes) == 2:
            return [date(ano, int(partes[0]), int(partes[1]))]
        if len(partes) == 3:
            data = date(int(partes[0]), int(partes[1]), int(partes[2]))
            return [data] if data.year == ano else []
    except ValueError:
        pass

    if texto not in _EXTRAS_INVALIDOS:
        _EXTRAS_INVALIDOS.add(texto)
        print(
            f'[AVISO] Ignorando dias_uteis.feriados_extras invalido: "{item}". '
            'Use "MM-DD", "AAAA-MM-DD" ou '
            f"{'/'.join(sorted(DESLOCAMENTO_MOVEIS))}."
        )
    return []


def _cfg(config):
    return (config or {}).get("dias_uteis") or {}


def peso_sabado(config):
    return float(_cfg(config).get("peso_sabado", PESO_SABADO_PADRAO))


def feriados(ano, config=None):
    """Feriados nacionais + os extras configurados, como {data: nome}."""
    calendario = feriados_nacionais(ano)
    for item in _cfg(config).get("feriados_extras") or []:
        for data in _datas_extra(ano, item):
            calendario.setdefault(data, str(item))
    return calendario


def peso_dia(data, calendario_feriados, sabado=PESO_SABADO_PADRAO):
    """Quanto o dia vale: 1 em dia de semana, `sabado` no sabado, 0 no resto."""
    if data in calendario_feriados:
        return 0.0
    dia_semana = data.weekday()
    if dia_semana < 5:
        return 1.0
    if dia_semana == 5:
        return sabado
    return 0.0


def contar_dias_uteis(inicio, fim, config=None):
    """Soma o peso dos dias no intervalo fechado [inicio, fim]."""
    if fim < inicio:
        return 0.0
    sabado = peso_sabado(config)
    calendario = feriados(inicio.year, config)
    if fim.year != inicio.year:
        calendario = dict(calendario, **feriados(fim.year, config))

    total = 0.0
    data = inicio
    while data <= fim:
        total += peso_dia(data, calendario, sabado)
        data += timedelta(days=1)
    return total


def calcular_dias_uteis(periodo_inicio, ontem, config=None):
    """Dias uteis do mes do relatorio, divididos em decorridos e restantes.

    `periodo_inicio` e o dia 1 do mes coberto pelo relatorio (no dia 1 o
    script olha o mes anterior, entao o mes vem daqui e nao de date.today()).
    Os decorridos vao do dia 1 ate `ontem` - a mesma janela das vendas -,
    de modo que decorridos + restantes = total.
    """
    ultimo_dia = calendar.monthrange(periodo_inicio.year, periodo_inicio.month)[1]
    fim_mes = periodo_inicio.replace(day=ultimo_dia)

    total = contar_dias_uteis(periodo_inicio, fim_mes, config)
    passados = contar_dias_uteis(periodo_inicio, min(ontem, fim_mes), config)

    return {
        "total": total,
        "passados": passados,
        "restantes": total - passados,
        "peso_sabado": peso_sabado(config),
    }


def _mes_de(argv):
    if len(argv) > 1:
        ano, mes = argv[1].split("-")[:2]
        return date(int(ano), int(mes), 1)
    hoje = date.today()
    return hoje.replace(day=1)


def main(argv=None):
    """Conferencia manual: imprime o calendario do mes e os tres totais."""
    argv = argv if argv is not None else sys.argv
    # O console do Windows abre em cp1252 e quebraria "Independência". Feito
    # aqui, e nao via gerar_relatorio_vendas.configurar_saida_utf8, para este
    # modulo nao depender do script que o consome.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    inicio = _mes_de(argv)
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    if ontem < inicio:
        ontem = inicio

    calendario = feriados(inicio.year)
    sabado = PESO_SABADO_PADRAO
    ultimo_dia = calendar.monthrange(inicio.year, inicio.month)[1]

    print(f"Dias uteis de {inicio.strftime('%m/%Y')} (sabado = {sabado})")
    for dia in range(1, ultimo_dia + 1):
        data = inicio.replace(day=dia)
        nome = calendario.get(data, "")
        print(
            f"  {data.strftime('%d/%m')} {'seg ter qua qui sex sab dom'.split()[data.weekday()]}"
            f"  {peso_dia(data, calendario, sabado):>3}  {nome}"
        )

    dias = calcular_dias_uteis(inicio, ontem)
    print(
        f"\nAte {ontem.strftime('%d/%m/%Y')} -> total {dias['total']:g} | "
        f"passados {dias['passados']:g} | restantes {dias['restantes']:g}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
