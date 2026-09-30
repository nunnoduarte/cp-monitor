"""Monitor de comboios Braga <-> Porto-Campanhã com alertas via ntfy."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TOPIC = os.environ["NTFY_TOPIC"]  # definido como secret no GitHub
TZ = ZoneInfo("Europe/Lisbon")
ESTADO = Path("estado/alertas.json")

ANTECEDENCIA_MIN = 60   # começa a vigiar X minutos antes da janela
ATRASO_MIN_ALERTA = 5   # atraso (min) a partir do qual avisa
SO_PROBLEMAS = True     # True: só atrasos/supressões | False: todos os comboios da janela

TRAJETOS = [
    {
        "nome": "Braga > Porto-Campanhã",
        "origem": "Braga",
        "destino": "Porto-Campanhã",
        "inicio": "06:20",
        "fim": "06:40",
    },
    {
        "nome": "Porto-Campanhã > Braga",
        "origem": "Porto-Campanhã",
        "destino": "Braga",
        "inicio": "17:00",
        "fim": "18:15",
    },
]


def hora(texto, base):
    h, m = map(int, texto.split(":"))
    return base.replace(hour=h, minute=m, second=0, microsecond=0)


def obter_partidas(origem, destino, agora):
    """A IMPLEMENTAR: ligar à fonte de dados da CP.

    Deve devolver uma lista de dicionários, um por comboio:
        {"comboio": "15168", "hora": "06:35", "atraso_min": 0, "suprimido": False}
    """
    raise NotImplementedError("fonte de dados da CP ainda por ligar")


def enviar(titulo, mensagem, prioridade="default", tags="train"):
    # Nota: os valores dos cabeçalhos HTTP têm de ser ASCII/latin-1 (sem "→").
    r = requests.post(
        f"https://ntfy.sh/{TOPIC}",
        data=mensagem.encode("utf-8"),
        headers={"Title": titulo, "Priority": prioridade, "Tags": tags},
        timeout=10,
    )
    r.raise_for_status()


def carregar_estado():
    try:
        return json.loads(ESTADO.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_estado(estado):
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(estado))


def main():
    agora = datetime.now(TZ)
    if agora.weekday() >= 5:  # sábado/domingo
        return

    hoje = agora.strftime("%Y-%m-%d")
    # mantém só os alertas de hoje
    estado = {k: v for k, v in carregar_estado().items() if k.startswith(hoje)}

    for t in TRAJETOS:
        ini, fim = hora(t["inicio"], agora), hora(t["fim"], agora)
        if not (ini - timedelta(minutes=ANTECEDENCIA_MIN) <= agora <= fim):
            continue

        try:
            partidas = obter_partidas(t["origem"], t["destino"], agora)
        except Exception as e:  # avisa uma vez por dia e trajeto
            chave = f"{hoje}|{t['nome']}|erro"
            if chave not in estado:
                enviar("Monitor com erro", f"{t['nome']}: {e!r}", "low", "warning")
                estado[chave] = "1"
            continue

        for p in partidas:
            if not (ini <= hora(p["hora"], agora) <= fim):
                continue

            if p["suprimido"]:
                situacao, prioridade, tags = "suprimido", "urgent", "rotating_light"
                texto = f"{p['hora']} (comboio {p['comboio']}) SUPRIMIDO"
            elif p["atraso_min"] >= ATRASO_MIN_ALERTA:
                # agrupa em blocos de 5 min para não repetir alertas a cada minuto
                situacao = f"atraso{p['atraso_min'] // 5 * 5}"
                prioridade, tags = "high", "warning"
                texto = f"{p['hora']} (comboio {p['comboio']}) com {p['atraso_min']} min de atraso"
            else:
                if SO_PROBLEMAS:
                    continue
                situacao, prioridade, tags = "ok", "default", "white_check_mark"
                texto = f"{p['hora']} (comboio {p['comboio']}) a horas"

            chave = f"{hoje}|{p['comboio']}|{situacao}"
            if chave in estado:
                continue

            enviar(t["nome"], texto, prioridade, tags)
            estado[chave] = "1"

    guardar_estado(estado)


if __name__ == "__main__":
    main()
