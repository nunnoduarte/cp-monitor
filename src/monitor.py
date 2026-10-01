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
LEMBRETE_MIN = 20       # lembrete (estado + lotação + linha) X min antes de cada comboio; 0 = desligado

# Significado dos níveis de lotação da API (valores assumidos, por confirmar
# na app da CP). Valores desconhecidos aparecem como "nível N".
OCUPACAO = {0: "baixa", 1: "média", 2: "alta", 3: "muito alta"}

# vista: DEPARTURES (partidas da estação) ou ARRIVALS (chegadas à estação)
# destino/origem: código da estação para filtrar (None = sem filtro)
# inicio/fim: janela horária (se alteraste as tuas, mantém os teus valores)
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
        "nome": "Sao Frutuoso > Braga",
        "estacao": "94-4051",           # São Frutuoso (apeadeiro; código deduzido, confirmar no teste)
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


def lotacao(paragem):
    o = paragem.get("occupancy")
    if o is None:
        return ""
    return OCUPACAO.get(o, f"nível {o}")


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
    # TESTE=1: ignora fins de semana e janelas e avisa de todos os comboios
    teste = os.environ.get("TESTE") == "1"
    if agora.weekday() >= 5 and not teste:  # sábado/domingo
        return

    hoje = agora.strftime("%Y-%m-%d")
    # mantém só os alertas de hoje
    estado = {k: v for k, v in carregar_estado().items() if k.startswith(hoje)}

    for t in TRAJETOS:
        ini, fim = hora(t["inicio"], agora), hora(t["fim"], agora)
        if not teste and not (ini - timedelta(minutes=ANTECEDENCIA_MIN) <= agora <= fim):
            continue

        campo_hora, _ = campos(t["vista"])
        try:
            paragens = obter_paragens(t, agora)
        except Exception as e:  # avisa uma vez por dia e trajeto
            chave = f"{hoje}|{t['nome']}|erro"
            if chave not in estado:
                enviar("Monitor com erro", f"{t['nome']}: {e!r}", "high", "warning")
                estado[chave] = "1"
            continue

        encontrados = 0
        for p in paragens:
            h = p.get(campo_hora)
            if not h or not (ini <= hora(h, agora) <= fim):
                continue
            if t["destino"] and (p.get("trainDestination") or {}).get("code") != t["destino"]:
                continue
            if t["origem"] and (p.get("trainOrigin") or {}).get("code") != t["origem"]:
                continue

            encontrados += 1
            print(json.dumps(p, ensure_ascii=False))  # fica no log do Actions

            num = p.get("trainNumber")
            occ = lotacao(p)
            plat = p.get("platform")
            extra = (f" | lotação {occ}" if occ else "") + (f" | linha {plat}" if plat else "")

            if suprimido(p):
                situacao, prioridade, tags = "suprimido", "urgent", "rotating_light"
                texto = f"{h} (comboio {num}) SUPRIMIDO"
            else:
                atraso = atraso_min(p, t["vista"])
                if atraso >= ATRASO_MIN_ALERTA:
                    # blocos de 5 min: evita repetir o alerta a cada minuto
                    situacao = f"atraso{atraso // 5 * 5}"
                    prioridade, tags = "high", "warning"
                    texto = f"{h} (comboio {num}) com {atraso} min de atraso{extra}"
                else:
                    faltam = (hora(h, agora) - agora).total_seconds() / 60
                    if not teste and not (LEMBRETE_MIN > 0 and -2 <= faltam <= LEMBRETE_MIN):
                        continue
                    situacao, prioridade, tags = "lembrete", "default", "train"
                    estado_txt = "a horas" if atraso <= 0 else f"{atraso} min de atraso"
                    texto = f"{h} (comboio {num}) {estado_txt}{extra}"

            chave = f"{hoje}|{num}|{situacao}"
            if chave in estado and not teste:
                continue

            enviar(("[TESTE] " if teste else "") + t["nome"], texto, prioridade, tags)
            if not teste:
                estado[chave] = "1"

        if encontrados == 0 and not teste:
            chave = f"{hoje}|{t['nome']}|vazio"
            if chave not in estado:
                enviar(
                    "Monitor sem comboios",
                    f"{t['nome']}: nenhum comboio encontrado na janela "
                    "(feriado ou alteração na API?)",
                    "default",
                    "warning",
                )
                estado[chave] = "1"

    if not teste:
        guardar_estado(estado)


if __name__ == "__main__":
    main()




            
