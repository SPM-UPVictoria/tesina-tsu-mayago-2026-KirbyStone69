from dotenv import load_dotenv
load_dotenv()

import os
import json
import base64
import time
import threading
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ZONA_LOCAL = ZoneInfo("America/Mexico_City")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

estado_lock = threading.Lock()


def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje})
        resp.raise_for_status()
        return resp.json()["result"]["message_id"]
    except Exception as e:
        print(f"  !! No se pudo enviar a Telegram: {e}")
        return None


def borrar_mensaje_telegram(message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    try:
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id})
        resp.raise_for_status()
    except Exception as e:
        print(f"  !! No se pudo borrar el mensaje de Telegram: {e}")


def avisar_inicio_bot():
    message_id = enviar_telegram("🤖 Bot de monitoreo iniciado")
    if message_id is not None:
        time.sleep(2)
        borrar_mensaje_telegram(message_id)


def formatear_hora_local(dt_utc):
    return dt_utc.astimezone(ZONA_LOCAL).strftime("%b %d, %Y %I:%M:%S %p")


MUTE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muted.json")
MUTE_DURACION_MINUTOS = 60

muted_soluciones = {}

soluciones_conocidas = {}


def cargar_mutes():
    global muted_soluciones
    if not os.path.exists(MUTE_FILE):
        return

    try:
        with open(MUTE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  !! No se pudo leer {MUTE_FILE}: {e}")
        return

    ahora = datetime.now(timezone.utc)
    vigentes = {}
    for codigo, expiracion_iso in data.get("codigos", {}).items():
        try:
            expiracion = datetime.fromisoformat(expiracion_iso)
        except Exception:
            continue
        if expiracion > ahora:
            vigentes[codigo] = expiracion

    with estado_lock:
        muted_soluciones = vigentes

    if vigentes:
        print(f"Mutes cargados desde disco: {list(vigentes.keys())}")


def guardar_mutes():
    data = {
        "codigos": {
            codigo: expiracion.isoformat()
            for codigo, expiracion in sorted(muted_soluciones.items())
        }
    }
    try:
        with open(MUTE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  !! No se pudo guardar {MUTE_FILE}: {e}")


def limpiar_mutes_vencidos():
    ahora = datetime.now(timezone.utc)
    vencidos = [codigo for codigo, expiracion in muted_soluciones.items() if expiracion <= ahora]
    for codigo in vencidos:
        del muted_soluciones[codigo]
    if vencidos:
        guardar_mutes()


def es_muteada(nombre_solucion):
    nombre_upper = nombre_solucion.strip().upper()
    with estado_lock:
        limpiar_mutes_vencidos()
        return any(nombre_upper.startswith(codigo) for codigo in muted_soluciones)


def buscar_nombres_por_codigo(codigo):
    resultados = []
    with estado_lock:
        for org_nombre, nombre in soluciones_conocidas.values():
            if nombre.strip().upper().startswith(codigo):
                resultados.append((org_nombre, nombre))
    return resultados


SCRIBESOFT_USER = os.environ["SCRIBESOFT_USER"]
SCRIBESOFT_PASS = os.environ["SCRIBESOFT_PASS"]

credenciales = base64.b64encode(f"{SCRIBESOFT_USER}:{SCRIBESOFT_PASS}".encode("utf-8")).decode("ascii")

scribesoft_session = requests.Session()
scribesoft_session.headers["Authorization"] = f"Basic {credenciales}"

ORGANIZACIONES = [
    {"id": "CLIENTE_1_ID", "nombre": "CLIENTE_1"},
    {"id": "CLIENTE_2_ID", "nombre": "CLIENTE_2"},
]

LIMIT_HISTORIAL = 25
INTERVALO_SCRIBESOFT_SEGUNDOS = 240

ESTADO_OK = "CompletedSuccessfully"

REGLAS = {
    "InProgress":          {"tipo": "conteo_y_tiempo", "limite": 10, "limite_min": 10},
    "CompletedWithErrors": {"tipo": "conteo",  "limite": 10},
}

COLORES = {
    "CompletedSuccessfully": "🟢 CompletedSuccessfully",
    "InProgress": "⚪ InProgress",
    "CompletedWithErrors": "🟡 CompletedWithErrors",
    "FatalError": "🟥 FatalError",
}

rachas_activas = {}

fatal_errors_reportados = {}
FATAL_ERROR_REPORT_TTL_MINUTOS = 60 * 24

fatal_error_primera_pasada = set()


def obtener_soluciones(org_id):
    resp = scribesoft_session.get(f"https://api.scribesoft.com/v1/orgs/{org_id}/solutions")
    resp.raise_for_status()
    return resp.json()


def obtener_historial(org_id, sol_id):
    resp = scribesoft_session.get(
        f"https://api.scribesoft.com/v1/orgs/{org_id}/solutions/{sol_id}/history",
        params={
            "offset": 0,
            "limit": LIMIT_HISTORIAL,
            "executionHistoryColumnSort": 0,
            "laterThanDate": "1753-01-01",
            "sortOrder": "desc",
        },
    )
    resp.raise_for_status()
    return resp.json()


def calcular_racha(historial):
    if not historial:
        return None, None

    estado_actual = historial[0]["result"]

    if estado_actual == ESTADO_OK:
        return None, None

    racha = []
    for item in historial:
        if item["result"] == estado_actual:
            racha.append(item)
        else:
            break

    mas_viejo_de_la_racha = racha[-1]
    inicio = datetime.fromisoformat(mas_viejo_de_la_racha["start"].replace("Z", "+00:00"))

    return estado_actual, inicio


def limpiar_fatal_errors_vencidos():
    limite = datetime.now(timezone.utc) - timedelta(minutes=FATAL_ERROR_REPORT_TTL_MINUTOS)
    vencidos = [k for k, momento in fatal_errors_reportados.items() if momento < limite]
    for k in vencidos:
        del fatal_errors_reportados[k]


def reportar_fatal_errors_del_historial(org_nombre, nombre, clave, historial):
    limpiar_fatal_errors_vencidos()

    es_primera_pasada = clave not in fatal_error_primera_pasada
    fatal_error_primera_pasada.add(clave)

    for item in historial:
        if item["result"] != "FatalError":
            continue

        clave_evento = f"{clave}|{item['start']}"
        if clave_evento in fatal_errors_reportados:
            continue

        fatal_errors_reportados[clave_evento] = datetime.now(timezone.utc)

        if es_primera_pasada:
            continue

        if es_muteada(nombre):
            continue

        inicio = datetime.fromisoformat(item["start"].replace("Z", "+00:00"))
        reportar_scribesoft(f"[{org_nombre}] {nombre}", "FatalError", inicio)


def umbral_para_empezar_a_vigilar(estado):
    regla = REGLAS.get(estado)
    if regla is None:
        return None

    if "limite" in regla:
        return regla["limite"]

    return 1


def contar_racha(historial, estado):
    cantidad = 0
    for item in historial:
        if item["result"] == estado:
            cantidad += 1
        else:
            break
    return cantidad


def debe_reportar(estado, inicio, cantidad_en_racha):
    regla = REGLAS.get(estado)

    if regla is None:
        return False

    if regla["tipo"] == "conteo":
        return cantidad_en_racha >= regla["limite"]

    if regla["tipo"] == "tiempo":
        ahora = datetime.now(timezone.utc)
        minutos_transcurridos = (ahora - inicio).total_seconds() / 60
        return minutos_transcurridos >= regla["limite_min"]

    if regla["tipo"] == "conteo_y_tiempo":
        ahora = datetime.now(timezone.utc)
        minutos_transcurridos = (ahora - inicio).total_seconds() / 60
        cumple_conteo = cantidad_en_racha >= regla["limite"]
        cumple_tiempo = minutos_transcurridos >= regla["limite_min"]
        return cumple_conteo and cumple_tiempo

    return False


def reportar_scribesoft(nombre, estado, inicio):
    color = COLORES.get(estado, f"❓ {estado}")
    mensaje = f"🚨 '{nombre}' posiblemente caída -- en {color} desde {formatear_hora_local(inicio)}"
    print(f"\n{mensaje}\n")
    enviar_telegram(mensaje)


def revisar_scribesoft():
    print(f"\n=== Revisión Scribesoft: {datetime.now(ZONA_LOCAL).strftime('%b %d, %Y %I:%M:%S %p')} ===")

    resumen_rachas = []

    for org in ORGANIZACIONES:
        org_id = org["id"]
        org_nombre = org["nombre"]

        print(f"\n########## Organización: {org_nombre} ##########")

        soluciones = obtener_soluciones(org_id)

        for sol in soluciones:
            nombre = sol.get("name", "(sin nombre)")
            sol_id = sol["id"]
            clave = f"{org_id}:{sol_id}"

            with estado_lock:
                soluciones_conocidas[clave] = (org_nombre, nombre)

            print(f"\n[{org_nombre} / {nombre}]")

            historial = obtener_historial(org_id, sol_id)

            if not historial:
                print("  (sin historial)")
                continue

            for j, item in enumerate(historial, start=1):
                estado_item = item["result"]
                color_item = COLORES.get(estado_item, f"❓ SIN MAPEAR ({estado_item})")
                dt_item = datetime.fromisoformat(item["start"].replace("Z", "+00:00"))
                print(f"  {j}. {color_item}  -  {formatear_hora_local(dt_item)}")

            reportar_fatal_errors_del_historial(org_nombre, nombre, clave, historial)

            estado_actual, inicio_racha = calcular_racha(historial)

            if estado_actual is None:
                if clave in rachas_activas:
                    del rachas_activas[clave]
                continue

            cantidad = contar_racha(historial, estado_actual)
            umbral = umbral_para_empezar_a_vigilar(estado_actual)

            if umbral is None or cantidad < umbral:
                if clave in rachas_activas:
                    del rachas_activas[clave]
                continue

            if clave not in rachas_activas or rachas_activas[clave]["inicio"] != inicio_racha:
                rachas_activas[clave] = {"estado": estado_actual, "inicio": inicio_racha, "reportado": False}

            info = rachas_activas[clave]
            color = COLORES.get(estado_actual, f"❓ {estado_actual}")
            muteada = es_muteada(nombre)
            tag_mute = "  🔇 (muteada, no se manda alerta)" if muteada else ""
            resumen_rachas.append(
                f"  [{org_nombre}] {nombre}: {color} -- {cantidad} seguidos, desde {formatear_hora_local(info['inicio'])}{tag_mute}"
            )

            if not muteada and not info["reportado"] and debe_reportar(estado_actual, info["inicio"], cantidad):
                reportar_scribesoft(f"[{org_nombre}] {nombre}", estado_actual, info["inicio"])
                info["reportado"] = True

    print("\n" + "=" * 60)
    print("RESUMEN DE EJECUCIONES ACTIVAS")
    if resumen_rachas:
        for linea in resumen_rachas:
            print(linea)
    else:
        print("  (ninguna, todo en orden)")


def loop_scribesoft():
    while True:
        try:
            revisar_scribesoft()
        except Exception as e:
            print(f"!! Error durante la revisión de Scribesoft: {e}")
        time.sleep(INTERVALO_SCRIBESOFT_SEGUNDOS)


def procesar_comando(texto, responder):
    partes = texto.strip().split(maxsplit=1)
    comando = partes[0].lower()

    if comando == "/mute":
        if len(partes) < 2 or not partes[1].strip():
            responder("Uso: /mute <codigo> [horas]  (ej. /mute 008B  o  /mute 008B 3)")
            return

        codigo_y_resto = partes[1].strip().split(maxsplit=1)
        codigo = codigo_y_resto[0].strip().upper()

        if len(codigo_y_resto) > 1:
            try:
                horas = float(codigo_y_resto[1].strip().replace(",", "."))
                if horas <= 0:
                    raise ValueError
            except ValueError:
                responder("Número de horas inválido. Uso: /mute <codigo> [horas]  (ej. /mute 008B 3)")
                return
            duracion_minutos = horas * 60
        else:
            duracion_minutos = MUTE_DURACION_MINUTOS

        expiracion = datetime.now(timezone.utc) + timedelta(minutes=duracion_minutos)

        with estado_lock:
            muted_soluciones[codigo] = expiracion
            guardar_mutes()

        hora_local = formatear_hora_local(expiracion)
        matches = buscar_nombres_por_codigo(codigo)

        mensaje = f"🔇 Muteado '{codigo}' hasta las {hora_local}."
        if matches:
            mensaje += "\nSolutions que matchean ahora mismo:\n" + "\n".join(
                f"  - [{org}] {nombre}" for org, nombre in matches
            )
        else:
            mensaje += "\n(No encontré ninguna solution con ese código todavía; se aplicará en cuanto aparezca en una revisión.)"

        responder(mensaje)

    elif comando == "/unmute":
        if len(partes) < 2 or not partes[1].strip():
            responder("Uso: /unmute <codigo>  (ej. /unmute 008B)")
            return

        codigo = partes[1].strip().upper()

        with estado_lock:
            existia = codigo in muted_soluciones
            if existia:
                del muted_soluciones[codigo]
                guardar_mutes()

        if existia:
            responder(f"🔊 '{codigo}' ya no está muteado.")
        else:
            responder(f"'{codigo}' no estaba muteado.")

    elif comando == "/muted":
        with estado_lock:
            limpiar_mutes_vencidos()
            copia = dict(muted_soluciones)

        if not copia:
            responder("No hay mutes activos.")
            return

        lineas = ["🔇 Mutes activos:"]
        for codigo, expiracion in sorted(copia.items()):
            hora_local = formatear_hora_local(expiracion)
            matches = buscar_nombres_por_codigo(codigo)
            nombres = ", ".join(nombre for _, nombre in matches) if matches else "sin match todavía"
            lineas.append(f"  - {codigo} (hasta {hora_local}) -> {nombres}")

        responder("\n".join(lineas))

    elif comando.startswith("/"):
        responder(
            "Comandos disponibles:\n"
            "/mute <codigo> [horas] - silencia alertas de esa solution (1 hora por default, ej. /mute 008B 3)\n"
            "/unmute <codigo> - quita el mute antes de que expire\n"
            "/muted - lista los mutes activos"
        )


TELEGRAM_POLL_BACKOFF_INICIAL_SEGUNDOS = 5
TELEGRAM_POLL_BACKOFF_MAXIMO_SEGUNDOS = 60


def escuchar_comandos_telegram():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    offset = None
    backoff = TELEGRAM_POLL_BACKOFF_INICIAL_SEGUNDOS

    poll_session = requests.Session()

    print("Escuchando comandos de Telegram (/mute, /unmute, /muted)...")

    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset

            resp = poll_session.get(url, params=params, timeout=35)
            resp.raise_for_status()
            data = resp.json()

            backoff = TELEGRAM_POLL_BACKOFF_INICIAL_SEGUNDOS

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                mensaje = update.get("message")
                if not mensaje or "text" not in mensaje:
                    continue

                chat_id = mensaje.get("chat", {}).get("id")
                if str(chat_id) != str(TELEGRAM_CHAT_ID):
                    continue

                texto = mensaje["text"]
                if not texto.startswith("/"):
                    continue

                print(f"  << comando recibido: {texto}")
                procesar_comando(texto, enviar_telegram)

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError) as e:
            print(f"!! Error de red escuchando comandos de Telegram (reintentando en {backoff}s): {e}")
            poll_session.close()
            poll_session = requests.Session()
            time.sleep(backoff)
            backoff = min(backoff * 2, TELEGRAM_POLL_BACKOFF_MAXIMO_SEGUNDOS)
        except Exception as e:
            print(f"!! Error escuchando comandos de Telegram (reintentando en {backoff}s): {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, TELEGRAM_POLL_BACKOFF_MAXIMO_SEGUNDOS)


def main():
    print("Bot de monitoreo iniciado. Ctrl+C para detener.\n")

    cargar_mutes()
    avisar_inicio_bot()

    threading.Thread(target=loop_scribesoft, daemon=True).start()

    escuchar_comandos_telegram()


if __name__ == "__main__":
    main()
