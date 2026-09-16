from flask import Flask, jsonify, render_template
import serial
import serial.tools.list_ports
import time
import re
import sqlite3
import threading
import json
import os
from datetime import datetime

# ============================================================
# CONFIGURACIÓN
# ============================================================

app = Flask(__name__)

BAUDRATE = 115200
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "npk_smart_soil.db")

PUERTO_ESP32 = "/dev/ttyUSB0"


# ============================================================
# VARIABLES GLOBALES
# ============================================================

esp32 = None

datos_actuales = {
    "humedad": 0,
    "temperatura": 0,
    "conductividad": 0,
    "ph": 0,
    "nitrogeno": 0,
    "fosforo": 0,
    "potasio": 0
}

estado_esp32 = {
    "conectado": False,
    "puerto": None
}

lock_datos = threading.Lock()
secuencia_activa = False
secuencia_terminada = False

# ============================================================
# BASE DE DATOS
# ============================================================

def crear_base_datos():

    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()

    # ==========================================
    # TABLA DE MEDICIONES DEL SENSOR
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mediciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            humedad REAL,
            temperatura REAL,
            conductividad INTEGER,
            ph REAL,
            nitrogeno INTEGER,
            fosforo INTEGER,
            potasio INTEGER
        )
    """)

    # ==========================================
    # TABLA DE ACCIONES DE LA MÁQUINA
    # ==========================================
    # El proyecto usa la columna "resultado".
    # Si existe una base antigua con "estado", se migra automáticamente.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS acciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            accion TEXT NOT NULL,
            resultado TEXT NOT NULL
        )
    """)

    cursor.execute("PRAGMA table_info(acciones)")
    columnas_acciones = {fila[1] for fila in cursor.fetchall()}

    if "resultado" not in columnas_acciones:
        if "estado" in columnas_acciones:
            cursor.execute(
                "ALTER TABLE acciones ADD COLUMN resultado TEXT"
            )
            cursor.execute("""
                UPDATE acciones
                SET resultado = estado
                WHERE resultado IS NULL
            """)
        else:
            cursor.execute("""
                ALTER TABLE acciones
                ADD COLUMN resultado TEXT NOT NULL DEFAULT 'OK'
            """)

    conexion.commit()
    conexion.close()

    print("Base de datos preparada.")

# ============================================================
# GUARDAR MEDICIÓN
# ============================================================

def guardar_medicion(datos):

    try:

        conexion = sqlite3.connect(DB_NAME)
        cursor = conexion.cursor()
        fecha_hora = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        

        cursor.execute("""
            INSERT INTO mediciones (

                fecha_hora,
                humedad,
                temperatura,
                conductividad,
                ph,
                nitrogeno,
                fosforo,
                potasio

            )
        

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        """, (

            fecha_hora,

            datos["humedad"],
            datos["temperatura"],
            datos["conductividad"],
            datos["ph"],
            datos["nitrogeno"],
            datos["fosforo"],
            datos["potasio"]

        ))
        conexion.commit()
        conexion.close()
        print("✓ Medición guardada en SQLite.")
    except Exception as error:

        print(
            "Error guardando medición:",
            error
        )

def guardar_accion(accion, resultado):

    try:

        conexion = sqlite3.connect(DB_NAME)
        cursor = conexion.cursor()

        fecha_hora = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute("""
            INSERT INTO acciones (
                fecha_hora,
                accion,
                resultado
            )
            VALUES (?, ?, ?)
        """, (
            fecha_hora,
            accion.upper(),
            resultado
        ))

        conexion.commit()
        conexion.close()

        print(
            f"✓ Acción guardada: "
            f"{accion.upper()} - {resultado}"
        )

    except Exception as error:

        print(
            "Error guardando acción:",
            error
        )

# ============================================================
# DETECTAR ESP32
# ============================================================

def buscar_esp32():

    global esp32

    print()
    print("==============================")
    print("       BUSCANDO ESP32")
    print("==============================")
    print()

    try:

        print(f"Conectando a {PUERTO_ESP32}...")

        ser = serial.Serial(
            PUERTO_ESP32,
            BAUDRATE,
            timeout=1
        )

        # El ESP32 puede reiniciarse al abrir el puerto
        time.sleep(3)

        ser.reset_input_buffer()

        estado_esp32["conectado"] = True
        estado_esp32["puerto"] = PUERTO_ESP32

        esp32 = ser

        print()
        print("==============================")
        print("       ESP32 CONECTADO")
        print("==============================")
        print(f"Puerto: {PUERTO_ESP32}")
        print()

        return ser

    except Exception as error:

        print()
        print("No se pudo conectar con el ESP32.")
        print(error)
        print()

        estado_esp32["conectado"] = False
        estado_esp32["puerto"] = None

        return None
    
def cerrar_conexion_esp32():
    global esp32

    try:
        if esp32 is not None and esp32.is_open:
            esp32.close()
    except Exception:
        pass

    esp32 = None

    estado_esp32["conectado"] = False
    estado_esp32["puerto"] = None

    print("ESP32 desconectado.")

# ============================================================
# CONVERTIR DATOS
# ============================================================

def convertir_datos(lineas):

    datos = {

        "humedad": None,
        "temperatura": None,
        "conductividad": None,
        "ph": None,
        "nitrogeno": None,
        "fosforo": None,
        "potasio": None

    }
    for linea in lineas:
        if "Humedad:" in linea:
            valor = re.search(
                r"[-+]?\d*\.?\d+",
                linea
            )
            if valor:
                datos["humedad"] = float(
                    valor.group()
                )

        elif "Temperatura:" in linea:
            valor = re.search(
                r"[-+]?\d*\.?\d+",
                linea
            )
            if valor:
                datos["temperatura"] = float(
                    valor.group()
                )


        elif "Conductividad:" in linea:
            valor = re.search(
                r"[-+]?\d+",
                linea
            )

            if valor:
                datos["conductividad"] = int(
                    valor.group()
                )


        elif "pH:" in linea:
            valor = re.search(
                r"[-+]?\d*\.?\d+",
                linea
            )

            if valor:
                datos["ph"] = float(
                    valor.group()
                )


        elif "Nitrogen:" in linea:
            valor = re.search(
                r"[-+]?\d+",
                linea

            )

            if valor:
                datos["nitrogeno"] = int(
                    valor.group()
                )


        elif "Phosphorus:" in linea:
            valor = re.search(
                r"[-+]?\d+",
                linea

            )

            if valor:
                datos["fosforo"] = int(
                    valor.group()
                )


        elif "Potassium:" in linea:
            valor = re.search(
                r"[-+]?\d+",
                linea
            )

            if valor:
                datos["potasio"] = int(
                    valor.group()
                )
                
    

    return datos


# ============================================================
# HILO DE LECTURA DEL ESP32
# ============================================================

def leer_esp32():

    global esp32
    while True:

        # ----------------------------------------------------
        # SI NO HAY ESP32, BUSCARLO
        # ----------------------------------------------------

        if esp32 is None or not esp32.is_open:
            estado_esp32["conectado"] = False
            estado_esp32["puerto"] = None
            esp32 = buscar_esp32()
            if esp32 is None:

                print(
                    "Esperando ESP32..."
                )

                time.sleep(5)
                continue


        # ----------------------------------------------------
        # LEER SERIAL
        # ----------------------------------------------------

        medicion = []

        try:

            while True:
                if esp32.in_waiting:
                    linea = esp32.readline().decode(
                        "utf-8",
                        errors="ignore"
                    ).strip()


                    if not linea:
                        continue


                    print(
                        f"[ESP32] {linea}"
                    )

                    medicion.append(linea)


                    # ----------------------------------------
                    # TERMINÓ UNA MEDICIÓN
                    # ----------------------------------------

                    if "------------------------" in linea:

                        datos = convertir_datos(
                            medicion
                        )


                        # ------------------------------------
                        # VERIFICAR QUE HAYA DATOS
                        # ------------------------------------

                        if (

                            datos["humedad"] is not None
                            or datos["temperatura"] is not None
                            or datos["ph"] is not None
                            or datos["nitrogeno"] is not None
                        ):


                            with lock_datos:
                                for clave in datos:
                                    if datos[clave] is not None:
                                        datos_actuales[clave] = datos[clave]


                            print()
                            print(
                                "========= DATOS ========="
                            )
                            print(
                                f"Humedad:       "
                                f"{datos['humedad']} %"
                            )

                            print(
                                f"Temperatura:   "
                                f"{datos['temperatura']} °C"
                            )

                            print(
                                f"Conductividad: "
                                f"{datos['conductividad']} uS/cm"
                            )

                            print(
                                f"pH:             "
                                f"{datos['ph']}"
                            )

                            print(
                                f"Nitrógeno:      "
                                f"{datos['nitrogeno']}"
                            )

                            print(
                                f"Fósforo:        "
                                f"{datos['fosforo']}"
                            )

                            print(
                                f"Potasio:        "
                                f"{datos['potasio']}"
                            )

                            print(
                                "========================="
                            )


                            # ------------------------------
                            # GUARDAR EN SQLITE
                            # ------------------------------

                            guardar_medicion(
                                datos
                            )


                        medicion = []


                else:

                    time.sleep(0.01)


        except (

            serial.SerialException,
            OSError
        ) as error:
            print()
            print(
                "Se perdió la conexión con ESP32:"
            )
            print(error)
            print()

            try:

                esp32.close()

            except:

                pass


            esp32 = None
            estado_esp32["conectado"] = False
            estado_esp32["puerto"] = None
            time.sleep(3)


# ============================================================
# RUTA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():

    return """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport"
content="width=device-width, initial-scale=1.0">
<title>NPK Smart Soil</title>
<style>
body{

    margin:0;
    padding:40px;
    background:#171a16;
    color:#eef0ea;
    font-family:'Segoe UI',Arial,sans-serif;

}

.contenedor{

    max-width:900px;
    margin:auto;

}

h1{

    letter-spacing:.08em;

}

.boton{

    display:inline-block;
    padding:14px 22px;
    margin-top:20px;
    background:#3c8a2e;
    color:white;
    text-decoration:none;
    border-radius:10px;
    font-weight:bold;

}

</style>
</head>
<body>
<div class="contenedor">
<h1>NPK SMART SOIL</h1>
<p>
Sistema de monitoreo y control.
</p>

<a
class="boton"
href="/historial">

Abrir Dashboard

</a>

</div>

</body>

</html>
"""
# ============================================================
# API DE ACCIONES
# ============================================================






@app.route("/api/acciones")
def api_acciones():

    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT
                id,
                fecha_hora,
                accion,
                resultado
            FROM acciones
            ORDER BY id DESC
            LIMIT 20
        """)

        acciones = cursor.fetchall()

        lista = []

        for accion in acciones:
            lista.append({
                "id": accion["id"],
                "fecha_hora": accion["fecha_hora"],
                "accion": accion["accion"],
                "resultado": accion["resultado"]
            })

        return jsonify(lista)

    except Exception as error:
        print("Error en /api/acciones:", error)
        return jsonify([]), 500

    finally:
        conexion.close()

# ============================================================
# API DE DATOS ACTUALES
# ============================================================

@app.route("/api/datos")
def api_datos():

    with lock_datos:

        datos = datos_actuales.copy()


    datos["esp32_conectado"] = (
        estado_esp32["conectado"]
    )

    datos["puerto"] = (
        estado_esp32["puerto"]
    )

    

    return jsonify(datos)


# ============================================================
# CONTROL DEL MOTOR
# ============================================================

def enviar_comando_motor(comando):
    global esp32

    try:
        # Si no hay conexión, intentar buscar el ESP32
        if esp32 is None or not esp32.is_open:
            print("ESP32 no conectado. Buscando nuevamente...")
            esp32 = buscar_esp32()

            if esp32 is None:
                print("No se encontró el ESP32.")
                return False

        mensaje = comando + "\n"

        esp32.write(mensaje.encode("utf-8"))
        esp32.flush()

        print(f"[USB → ESP32] {comando}")

        return True

    except (serial.SerialException, OSError) as error:
        print("Error leyendo ESP32:")
        print(error)

        cerrar_conexion_esp32()

        time.sleep(2)

@app.route("/motor/<accion>")
def motor(accion):

    acciones_permitidas = [
        "adelante",
        "atras",
        "detener"
    ]

    if accion not in acciones_permitidas:

        return jsonify({
            "ok": False,
            "mensaje": "Acción no permitida"
        }), 400

    comandos = {
        "adelante": "ADELANTE",
        "atras": "ATRAS",
        "detener": "DETENER"
    }

    comando = comandos[accion]

    enviado = enviar_comando_motor(comando)

    if enviado:

        guardar_accion(
            accion,
            "OK"
        )

        return jsonify({
            "ok": True,
            "mensaje": f"Motor: {accion.upper()}"
        })

    else:

        guardar_accion(
            accion,
            "SIN CONEXION"
        )

        return jsonify({
            "ok": False,
            "mensaje": "No se pudo comunicar con el ESP32 por USB"
        }), 500
        
                
def ejecutar_movimiento(accion, segundos):
    global secuencia_activa

    try:

        respuesta = requests.get(
            f"http://{ESP32_IP}/{accion}",
            timeout=3
        )

        if not respuesta.ok:

            guardar_accion(accion, "ERROR")
            return False

        guardar_accion(accion, "OK")

        print(
            f"Movimiento: {accion} "
            f"durante {segundos} segundos"
        )

        # Esperar comprobando si se activó
        # el paro de emergencia
        tiempo_inicio = time.time()

        while time.time() - tiempo_inicio < segundos:

            if not secuencia_activa:

                requests.get(
                    f"http://{ESP32_IP}/detener",
                    timeout=3
                )

                guardar_accion(
                    "detener",
                    "EMERGENCIA"
                )

                print("!!! PARO DE EMERGENCIA !!!")

                return False

            time.sleep(0.1)

        # Detener al terminar el movimiento
        requests.get(
            f"http://{ESP32_IP}/detener",
            timeout=3
        )

        guardar_accion(
            "detener",
            "OK"
        )
        
        secuencia_activa = False

        return True

    except requests.exceptions.RequestException as error:

        print("Error durante movimiento:")
        print(error)

        guardar_accion(
            accion,
            "SIN CONEXION"
        )
        
        secuencia_activa = False

        return False


    
def ejecutar_secuencia():

    global secuencia_activa
    global secuencia_terminada

    # La secuencia comienza activa
    secuencia_activa = True
    secuencia_terminada = False

    secuencia = [
        ("adelante", 5),
        ("detener", 2),
        ("atras", 5),
        ("detener", 2) 
        ]

    print()
    print("==============================")
    print("     INICIANDO SECUENCIA")
    print("==============================")

    for accion, duracion in secuencia:

        if not secuencia_activa:
            break

        print(
            f"SECUENCIA: "
            f"{accion.upper()} "
            f"durante {duracion} segundos"
        )

        comandos = {
            "adelante": "ADELANTE",
            "atras": "ATRAS",
            "detener": "DETENER"
        }

        comando = comandos[accion]

        enviado = enviar_comando_motor(comando)

        if not enviado:

            guardar_accion(
                accion,
                "SIN CONEXION"
            )

            secuencia_activa = False
            secuencia_terminada = True

            break

        guardar_accion(
            accion,
            "OK"
        )

        tiempo_inicio = time.time()

        while time.time() - tiempo_inicio < duracion:

            if not secuencia_activa:
                break

            time.sleep(0.1)

    # Asegurar que el motor quede detenido
    enviar_comando_motor("DETENER")

    guardar_accion(
        "detener",
        "OK"
    )

    secuencia_activa = False
    secuencia_terminada = True

    print()
    print("==============================")
    print("    SECUENCIA TERMINADA")
    print("==============================")




@app.route("/automatizar", methods=["POST"])
def automatizar():

    global secuencia_activa
    global secuencia_terminada

    if secuencia_activa:
        return jsonify({
            "ok": False,
            "mensaje": "La secuencia ya está funcionando"
        }), 409

    secuencia_terminada = False

    hilo = threading.Thread(
        target=ejecutar_secuencia,
        daemon=True
    )

    hilo.start()

    return jsonify({
        "ok": True,
        "mensaje": "Secuencia automática iniciada"
    })


@app.route("/api/secuencia")
def estado_secuencia():

    return jsonify({
        "activa": secuencia_activa,
        "terminada": secuencia_terminada
    })
def ejecutar_secuencia():

    global secuencia_activa
    global secuencia_terminada

    secuencia_activa = True
    secuencia_terminada = False

    secuencia = [
        ("adelante", 3),
        ("detener", 2),
        ("atras", 3),
        ("detener", 1)
    ]

    print()
    print("==============================")
    print("     INICIANDO SECUENCIA ESP32")
    print("==============================")
    print()

    comandos = {
        "adelante": "ADELANTE",
        "atras": "ATRAS",
        "detener": "DETENER"
    }

    try:

        for accion, duracion in secuencia:

            if not secuencia_activa:
                break

            comando = comandos[accion]

            print(
                f"ESP32: {comando} "
                f"durante {duracion} segundos"
            )

            enviado = enviar_comando_motor(comando)

            if not enviado:

                print(
                    f"No se pudo enviar: {comando}"
                )

                guardar_accion(
                    accion,
                    "SIN CONEXION"
                )

                secuencia_activa = False
                secuencia_terminada = True

                return

            guardar_accion(
                accion,
                "OK"
            )

            tiempo_inicio = time.time()

            while time.time() - tiempo_inicio < duracion:

                if not secuencia_activa:

                    enviar_comando_motor(
                        "DETENER"
                    )

                    print(
                        "SECUENCIA CANCELADA"
                    )

                    secuencia_terminada = True

                    return

                time.sleep(0.1)

        enviar_comando_motor(
            "DETENER"
        )

        guardar_accion(
            "detener",
            "OK"
        )

        print()
        print("==============================")
        print("    SECUENCIA ESP32 TERMINADA")
        print("==============================")
        print()

    except Exception as error:

        print(
            "Error en secuencia ESP32:"
        )

        print(error)

        try:
            enviar_comando_motor("DETENER")
        except Exception:
            pass

    finally:

        secuencia_activa = False
        secuencia_terminada = True


@app.route("/historial")
def historial():

    conexion = sqlite3.connect(DB_NAME)

    conexion.row_factory = sqlite3.Row

    cursor = conexion.cursor()


    cursor.execute("""

        SELECT
            id,
            fecha_hora,
            humedad,
            temperatura,
            conductividad,
            ph,
            nitrogeno,
            fosforo,
            potasio
        FROM mediciones
        ORDER BY id ASC

    """)


    mediciones = cursor.fetchall()

    conexion.close()


    # --------------------------------------------------------
    # DATOS PARA GRÁFICAS
    # --------------------------------------------------------
    fechas = []
    humedad = []
    temperatura = []
    conductividad = []
    ph = []
    nitrogeno = []
    fosforo = []
    potasio = []

    for medicion in mediciones:

        fechas.append(
            medicion["fecha_hora"]
        )

        humedad.append(
            medicion["humedad"]
        )

        temperatura.append(
            medicion["temperatura"]
        )

        conductividad.append(
            medicion["conductividad"]
        )

        ph.append(
            medicion["ph"]
        )

        nitrogeno.append(
            medicion["nitrogeno"]
        )

        fosforo.append(
            medicion["fosforo"]
        )

        potasio.append(
            medicion["potasio"]
        )


    # --------------------------------------------------------
    # ÚLTIMA MEDICIÓN
    # --------------------------------------------------------

    if mediciones:

        ultima = mediciones[-1]
        ultima_humedad = ultima["humedad"]
        ultima_temperatura = ultima["temperatura"]
        ultima_conductividad = ultima["conductividad"]
        ultima_ph = ultima["ph"]
        ultimo_n = ultima["nitrogeno"]
        ultimo_p = ultima["fosforo"]
        ultimo_k = ultima["potasio"]

    else:

        ultima_humedad = 0
        ultima_temperatura = 0
        ultima_conductividad = 0
        ultima_ph = 0
        ultimo_n = 0
        ultimo_p = 0
        ultimo_k = 0


    # --------------------------------------------------------
    # CREAR TABLA
    # --------------------------------------------------------

    filas = ""


    for medicion in reversed(mediciones):

        filas += f"""

<tr>

<td>{medicion['id']}</td>
<td>{medicion['fecha_hora']}</td>
<td>{medicion['humedad']} %</td>
<td>{medicion['temperatura']} °C</td>
<td>{medicion['conductividad']} µS/cm</td>
<td>{medicion['ph']}</td>
<td>{medicion['nitrogeno']}</td>
<td>{medicion['fosforo']}</td>
<td>{medicion['potasio']}</td>
</tr>

"""


    # ========================================================
    # HTML
    # ========================================================


    return render_template(
    "dashboard.html",
    fechas=fechas,
    humedad=humedad,
    temperatura=temperatura,
    conductividad=conductividad,
    ph=ph,
    nitrogeno=nitrogeno,
    fosforo=fosforo,
    potasio=potasio,
    filas=filas
)


# ============================================================
# INICIO
# ============================================================

if __name__ == "__main__":

    print()

    print("==============================")
    print("       NPK SMART SOIL")
    print("==============================")

    print()

    print("Preparando base de datos...")

    crear_base_datos()

    print()

    print(
        "Iniciando lector del ESP32..."
    )


    # --------------------------------------------------------
    # HILO PARA SERIAL
    # --------------------------------------------------------

    hilo_serial = threading.Thread(

        target=leer_esp32,

        daemon=True

    )

    hilo_serial.start()


    time.sleep(1)


    print()

    print(
        "Servidor Flask iniciado."
    )

    print()

    print(
        "Dashboard:"
    )

    print(
        "http://127.0.0.1:5000/historial"
    )

    print()

    print(
        "Control del ESP32:"
    )

    print()

    print(
        "Presiona CTRL+C para detener."
    )

    print()



    # --------------------------------------------------------
    # FLASK
    # --------------------------------------------------------

    app.run(

        host="127.0.0.1",

        port=5000,

        debug=False,

        use_reloader=False

    )
