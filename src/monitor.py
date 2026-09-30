"""Monitor de comboios Braga <-> Porto-Campanhã com alertas via ntfy.

Fonte de dados: API usada pelo site da CP (não oficial, pode mudar).
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TOPIC = os.environ["NTFY_TOPIC"]  # definido como secret no GitHub
TZ = ZoneInfo("Europe/Lisbon")
ESTADO = Path("estado/alertas.json")

API = "https://api-gateway.cp.pt/cp/services/travel-api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.cp.pt",
    "Referer": "https://www.cp.pt/",
    # Credenciais do cliente web da CP: guardar como secrets, nunca no código.
    "X-Api-Key": os.environ["CP_API_KEY"],
    "X-Cp-Connect-Id": os.environ["CP_CONNECT_ID"],
    "X-Cp-Connect-Secret": os.environ["CP_CONNECT_SECRET"],
}

ANTECEDENCIA_MIN = 60   # começa a vigiar X minutos antes da janela
ATRASO_MIN_ALERTA = 5   # atraso (min) a partir do qual avisa
SO_PROBLEMAS = True     # True: só atrasos/supressões | False: todos os comboios da janela

# vista: DEPARTURES (partidas da estação) ou ARRIVALS (chegadas à estação)
# destino/origem: código da estação para filtrar (None = sem filtro)
TRAJETOS = [
    {
        "nome": "Braga > Porto-Campanhã",
        "estacao": "94-29157",          # Braga (todos os comboios daqui vão para o Porto)
        "vista": "DEPARTURES",
        "destino": None,
        "origem": None,
        "inicio": "06:20",
        "fim": "06:40",
    },
    {
        "nome": "Porto-Campanhã > Braga",
        "estacao": "94-2006",           # Porto-Campanhã (confirmar abrindo o URL no browser)
        "vista": "DEPARTURES",
        "destino": "94-29157",          # só comboios com destino final Braga
        "origem": None,
        "inicio": "17:00",
        "fim": "18:15",
    },
]


def minutos(hhmm):
    h, m = map(int, hhmm[:5].split(":"))
    return h * 60 + m


def hora(texto, base):
    h, m = map(int, texto[:5].split(":"))
    return base.replace(hour=h, minute=m, second=0, microsecond=0)


def obter_paragens(trajeto, agora):
    """Pede à API da CP as paragens da estação a partir do início da janela."""
    url = f"{API}/stations/{trajeto['estacao']}/timetable/{agora:%Y-%m-%d}"
    r = requests.get(
        url,
        params={"view": trajeto["vista"], "start": trajeto["inicio"]},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("stationStops", [])


def campos(vista):
    # (hora prevista, hora estimada)
    if vista == "ARRIVALS":
        return "arrivalTime", "ETA"
    return "departureTime", "ETD"


def atraso_min(paragem, vista):
    campo_hora, campo_est = campos(vista)
    d = paragem.get("delay")
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        return int(d)
    if isinstance(d, str) and d.strip().lstrip("-").isdigit():
        return int(d.strip())
    est, prev = paragem.get(campo_est), paragem.get(campo_hora)
    if est and prev:
        return minutos(est) - minutos(prev)
    return 0


def suprimido(paragem):
    s = paragem.get("supression")  # (sic) assim vem na API
    if s is None or s is False or s == 0:
        return False
    if isinstance(s, str) and s.strip().lower() in ("", "false", "no", "0"):
        return False
    return True


def enviar(titulo, mensagem, prioridade="default", tags="train"):
    # Os valores dos cabeçalhos HTTP têm de ser latin-1 (sem "→").
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
    estado = {k: v for k, v in carregar_estado().items() if k.startswith(hoje)}

    for t in TRAJETOS:
        ini, fim = hora(t["inicio"], agora), hora(t["fim"], agora)
        if not (ini - timedelta(minutes=ANTECEDENCIA_MIN) <= agora <= fim):
            continue

        campo_hora, _ = campos(t["vista"])
        try:
            paragens = obter_paragens(t, agora)
        except Exception as e:  # avisa uma vez por dia e trajeto
            chave = f"{hoje}|{t['nome']}|erro"
            if chave not in estado:
                enviar("Monitor com erro", f"{t['nome']}: {e!r}", "low", "warning")
                estado[chave] = "1"
            continue

        for p in paragens:
            h = p.get(campo_hora)
            if not h or not (ini <= hora(h, agora) <= fim):
                continue
            if t["destino"] and (p.get("trainDestination") or {}).get("code") != t["destino"]:
                continue
            if t["origem"] and (p.get("trainOrigin") or {}).get("code") != t["origem"]:
                continue

            print(json.dumps(p, ensure_ascii=False))  # fica no log do Actions

            num = p.get("trainNumber")
            if suprimido(p):
                situacao, prioridade, tags = "suprimido", "urgent", "rotating_light"
                texto = f"{h} (comboio {num}) SUPRIMIDO"
            else:
                atraso = atraso_min(p, t["vista"])
                if atraso >= ATRASO_MIN_ALERTA:
                    # blocos de 5 min: evita repetir o alerta a cada minuto
                    situacao = f"atraso{atraso // 5 * 5}"
                    prioridade, tags = "high", "warning"
                    texto = f"{h} (comboio {num}) com {atraso} min de atraso"
                elif SO_PROBLEMAS:
                    continue
                else:
                    situacao, prioridade, tags = "ok", "default", "white_check_mark"
                    texto = f"{h} (comboio {num}) a horas"

            chave = f"{hoje}|{num}|{situacao}"
            if chave in estado:
                continue

            enviar(t["nome"], texto, prioridade, tags)
            estado[chave] = "1"

    guardar_estado(estado)


if __name__ == "__main__":
    main()
