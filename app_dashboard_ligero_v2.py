from flask import Flask, jsonify
import serial
import serial.tools.list_ports
import time
import re
import sqlite3
import threading
import requests
import subprocess
from datetime import datetime


# ============================================================
# CONFIGURACIÓN
# ============================================================

app = Flask(__name__)

BAUDRATE = 115200
DB_NAME = "npk_smart_soil.db"

ESP32_IP = "192.168.4.1"


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


# ============================================================
# BASE DE DATOS
# ============================================================

def crear_base_datos():

    conexion = sqlite3.connect(DB_NAME)

    cursor = conexion.cursor()

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

    puertos = serial.tools.list_ports.comports()

    if not puertos:

        print("No se encontraron puertos COM.")

        return None


    for puerto in puertos:

        print(
            f"Probando {puerto.device}..."
        )

        try:

            ser = serial.Serial(

                puerto.device,

                BAUDRATE,

                timeout=1

            )

            # El ESP32 puede reiniciarse al abrir COM

            time.sleep(3)

            ser.reset_input_buffer()

            encontrado = False

            inicio = time.time()


            while time.time() - inicio < 5:

                if ser.in_waiting:

                    linea = ser.readline().decode(

                        "utf-8",

                        errors="ignore"

                    ).strip()


                    if linea:

                        print(
                            f"  → {linea}"
                        )


                    if (

                        "SENSOR NPK" in linea

                        or "Humedad:" in linea

                        or "Temperatura:" in linea

                        or "Conductividad:" in linea

                        or "Phosphorus:" in linea

                        or "Potassium:" in linea

                    ):

                        encontrado = True


            if encontrado:

                print()

                print("==============================")
                print("       ESP32 ENCONTRADO")
                print("==============================")

                print(
                    f"Puerto: {puerto.device}"
                )

                print()

                estado_esp32["conectado"] = True

                estado_esp32["puerto"] = puerto.device

                esp32 = ser

                return ser


            ser.close()


        except (

            serial.SerialException,

            PermissionError

        ) as error:

            print(
                f"  No disponible: {error}"
            )


    print()

    print(
        "No se encontró el ESP32."
    )

    return None


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

📊 Abrir Dashboard

</a>

</div>

</body>

</html>
"""


# ============================================================
# API DE DATOS ACTUALES
# ============================================================

def estado_transbot():

    try:
        resultado = subprocess.run(
            ["systemctl", "is-active", "npk-transbot.service"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            timeout=1
        )
        return resultado.stdout.strip() == "active"
    except Exception:
        return False


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

    datos["transbot_activo"] = estado_transbot()

    return jsonify(datos)


# ============================================================
# CONTROL DEL MOTOR
# ============================================================

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


    try:

        respuesta = requests.get(

            f"http://{ESP32_IP}/{accion}",

            timeout=3

        )


        return jsonify({

            "ok": respuesta.ok,

            "mensaje": respuesta.text

        }), respuesta.status_code


    except requests.exceptions.RequestException as error:

        print()

        print(
            "Error conectando con ESP32 por Wi-Fi:"
        )

        print(error)

        print()


        return jsonify({

            "ok": False,

            "mensaje":
            "No se pudo conectar con el ESP32"

        }), 500


# ============================================================
# DASHBOARD / HISTORIAL
# ============================================================

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

        FROM (
            SELECT
                id, fecha_hora, humedad, temperatura, conductividad,
                ph, nitrogeno, fosforo, potasio
            FROM mediciones
            ORDER BY id DESC
            LIMIT 40
        )

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

    html = """

<!DOCTYPE html>

<html lang="es">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>NPK Smart Soil</title>

<script
src="https://cdn.jsdelivr.net/npm/chart.js">
</script>


<style>
:root{
    --bg:#eaf5e4;
    --panel:#f7fbf5;
    --green:#2f7d32;
    --green-dark:#1f5d24;
    --green-soft:#dfeeda;
    --line:#b9d2b7;
    --text:#19321b;
    --muted:#5b735d;
    --danger:#b33a2c;
    --blue:#2e6ea6;
}
*{box-sizing:border-box;}
body{
    margin:0;
    padding:24px 14px 50px;
    background:var(--bg);
    color:var(--text);
    font-family:Arial,Helvetica,sans-serif;
}
.contenedor{max-width:1180px;margin:auto;}
.encabezado{
    display:flex;align-items:center;justify-content:space-between;
    gap:16px;flex-wrap:wrap;margin-bottom:18px;
}
.marca{display:flex;align-items:center;gap:12px;}
.logo-npk{
    font-size:30px;font-weight:900;letter-spacing:.06em;
    color:var(--green-dark);line-height:1;
}
.titulo{font-size:25px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;}
.subtitulo{color:var(--muted);margin-top:3px;font-size:13px;}
.estados{display:flex;gap:8px;flex-wrap:wrap;}
.estado{padding:8px 11px;border-radius:999px;background:var(--panel);border:1px solid var(--line);font-size:12px;font-weight:700;}
.seccion{margin-top:20px;}
.seccion h2{font-size:14px;margin:0 0 10px;color:var(--green-dark);text-transform:uppercase;letter-spacing:.08em;}
.tarjetas{display:grid;grid-template-columns:repeat(7,minmax(120px,1fr));gap:10px;}
.tarjeta{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;box-shadow:0 2px 7px rgba(38,70,35,.05);}
.nombre{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;}
.valor{font-size:24px;font-weight:800;margin-top:5px;}
.unidad{font-size:11px;color:var(--muted);font-weight:400;}
.graficas{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;}
.grafica{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;}
.grafica h3{margin:0 0 8px;font-size:13px;}
.canvas-container{position:relative;height:190px;}
.controles{display:flex;gap:10px;flex-wrap:wrap;}
.boton{flex:1;min-width:160px;border:0;padding:14px 16px;border-radius:10px;color:#fff;font-size:15px;font-weight:800;cursor:pointer;}
.boton:active{transform:translateY(1px);}
.boton-adelante{background:var(--green);}
.boton-atras{background:var(--blue);}
.boton-detener{background:var(--danger);}
.estado-motor{margin-top:10px;padding:10px 12px;background:var(--panel);border:1px solid var(--line);border-radius:8px;color:var(--muted);font-size:13px;}
.tabla-contenedor{overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px;}
table{width:100%;min-width:900px;border-collapse:collapse;}
th{padding:10px;background:var(--green-soft);color:var(--green-dark);font-size:10px;text-transform:uppercase;}
td{padding:9px;text-align:center;border-top:1px solid #d9e7d7;font-size:12px;}
.boton-historial{display:inline-block;padding:11px 15px;border-radius:8px;background:var(--green);color:#fff;text-decoration:none;font-weight:700;font-size:13px;}
@media(max-width:900px){.tarjetas{grid-template-columns:repeat(4,1fr);}.graficas{grid-template-columns:1fr;}}
@media(max-width:580px){body{padding:16px 10px 35px;}.tarjetas{grid-template-columns:repeat(2,1fr);}.titulo{font-size:21px;}.logo-npk{font-size:25px;}}
</style>

</head>


<body>


<div class="contenedor">


<div class="encabezado">
  <div>
    <div class="marca">
      <div class="logo-npk">NPK</div>
      <div>
        <div class="titulo">SMART SOIL</div>
        <div class="subtitulo">Dashboard de monitoreo y control</div>
      </div>
    </div>
  </div>
  <div class="estados">
    <div id="estadoESP32" class="estado">ESP32: buscando...</div>
    <div id="estadoTransbot" class="estado">Transbot: buscando...</div>
  </div>
</div>




<!-- ====================================================== -->
<!-- ÚLTIMA MEDICIÓN -->
<!-- ====================================================== -->

<div class="seccion">

<h2>Última medición</h2>


<div class="tarjetas">


<div class="tarjeta">

<div class="nombre">
Humedad
</div>

<div id="humedad"
class="valor">

0

<span class="unidad">
%
</span>

</div>

</div>


<div class="tarjeta">

<div class="nombre">
Temperatura
</div>

<div id="temperatura"
class="valor">

0

<span class="unidad">
°C
</span>

</div>

</div>


<div class="tarjeta">

<div class="nombre">
Conductividad
</div>

<div id="conductividad"
class="valor">

0

<span class="unidad">
µS/cm
</span>

</div>

</div>


<div class="tarjeta">

<div class="nombre">
pH
</div>

<div id="ph"
class="valor">

0

</div>

</div>


<div class="tarjeta">

<div class="nombre">
Nitrógeno
</div>

<div id="nitrogeno"
class="valor">

0

</div>

</div>


<div class="tarjeta">

<div class="nombre">
Fósforo
</div>

<div id="fosforo"
class="valor">

0

</div>

</div>


<div class="tarjeta">

<div class="nombre">
Potasio
</div>

<div id="potasio"
class="valor">

0

</div>

</div>


</div>

</div>


<!-- ====================================================== -->
<!-- CONTROL DEL MOTOR -->
<!-- ====================================================== -->

<div class="seccion">

<h2>Control de máquina</h2>


<div class="controles">


<button
class="boton boton-adelante"
onclick="controlMotor('adelante')">

↑ ADELANTE

</button>


<button
class="boton boton-atras"
onclick="controlMotor('atras')">

↓ ATRÁS

</button>


<button
class="boton boton-detener"
onclick="controlMotor('detener')">

⏹ DETENER

</button>


</div>


<div id="estadoMotor"
class="estado-motor">

Motor detenido

</div>

</div>


<!-- ====================================================== -->
<!-- GRÁFICAS -->
<!-- ====================================================== -->

<div class="seccion">

<h2>Gráficas</h2>


<div class="graficas">


<div class="grafica">

<h3> Humedad</h3>

<div class="canvas-container">

<canvas id="graficaHumedad"></canvas>

</div>

</div>


<div class="grafica">

<h3> Temperatura</h3>

<div class="canvas-container">

<canvas id="graficaTemperatura"></canvas>

</div>

</div>


<div class="grafica">

<h3> pH</h3>

<div class="canvas-container">

<canvas id="graficaPH"></canvas>

</div>

</div>


<div class="grafica">

<h3> Conductividad</h3>

<div class="canvas-container">

<canvas id="graficaConductividad"></canvas>

</div>

</div>


<div class="grafica">

<h3> NPK</h3>

<div class="canvas-container">

<canvas id="graficaNPK"></canvas>

</div>

</div>


</div>

</div>


<!-- ====================================================== -->
<!-- HISTORIAL -->
<!-- ====================================================== -->

<div class="seccion">

<h2>Historial de mediciones</h2>


<div class="tabla-contenedor">

<table>

<thead>

<tr>

<th>ID</th>

<th>Fecha / Hora</th>

<th>Humedad</th>

<th>Temperatura</th>

<th>Conductividad</th>

<th>pH</th>

<th>N</th>

<th>P</th>

<th>K</th>

</tr>

</thead>


<tbody>

""" + filas + """

</tbody>

</table>

</div>


</div>


</div>


<script>


// ==========================================================
// DATOS PARA LAS GRÁFICAS
// ==========================================================

const fechas = """ + repr(fechas) + """;

const humedadHistorica = """ + repr(humedad) + """;

const temperaturaHistorica = """ + repr(temperatura) + """;

const conductividadHistorica = """ + repr(conductividad) + """;

const phHistorico = """ + repr(ph) + """;

const nitrogenoHistorico = """ + repr(nitrogeno) + """;

const fosforoHistorico = """ + repr(fosforo) + """;

const potasioHistorico = """ + repr(potasio) + """;


// ==========================================================
// OPCIONES DE CHART
// ==========================================================

const opciones = {

    responsive:true,

    maintainAspectRatio:false,

    interaction:{mode:'index',intersect:false},

    animation:false,

    plugins:{

        legend:{

            labels:{

                color:'#eef0ea'

            }

        }

    },

    scales:{

        x:{

            ticks:{

                color:'#8e9788',

                maxTicksLimit:8

            },

            grid:{

                color:'#333a2f'

            }

        },

        y:{

            ticks:{

                color:'#8e9788'

            },

            grid:{

                color:'#333a2f'

            }

        }

    }

};


// ==========================================================
// CREAR GRÁFICAS
// ==========================================================

function crearGrafica(

    elemento,

    nombre,

    datos

){

    new Chart(

        document.getElementById(elemento),

        {

            type:'line',

            data:{

                labels:fechas,

                datasets:[{

                    label:nombre,

                    data:datos,

                    borderWidth:2,

                    pointRadius:0,

                    tension:0.15,

                    fill:false

                }]

            },

            options:opciones

        }

    );

}


crearGrafica(

    'graficaHumedad',

    'Humedad (%)',

    humedadHistorica

);


crearGrafica(

    'graficaTemperatura',

    'Temperatura (°C)',

    temperaturaHistorica

);


crearGrafica(

    'graficaPH',

    'pH',

    phHistorico

);


crearGrafica(

    'graficaConductividad',

    'Conductividad (µS/cm)',

    conductividadHistorica

);


// ==========================================================
// GRÁFICA NPK
// ==========================================================

new Chart(

    document.getElementById('graficaNPK'),

    {

        type:'line',

        data:{

            labels:fechas,

            datasets:[

                {

                    label:'Nitrógeno',

                    data:nitrogenoHistorico,

                    borderWidth:2,

                    tension:0.3

                },

                {

                    label:'Fósforo',

                    data:fosforoHistorico,

                    borderWidth:2,

                    tension:0.3

                },

                {

                    label:'Potasio',

                    data:potasioHistorico,

                    borderWidth:2,

                    tension:0.3

                }

            ]

        },

        options:opciones

    }

);


// ==========================================================
// ACTUALIZAR DATOS DEL SENSOR
// ==========================================================

async function actualizarDatos(){

    try{

        const respuesta =
            await fetch('/api/datos');

        const datos =
            await respuesta.json();


        document.getElementById(
            'humedad'
        ).innerHTML =
            datos.humedad +
            '<span class="unidad">%</span>';


        document.getElementById(
            'temperatura'
        ).innerHTML =
            datos.temperatura +
            '<span class="unidad">°C</span>';


        document.getElementById(
            'conductividad'
        ).innerHTML =
            datos.conductividad +
            '<span class="unidad">µS/cm</span>';


        document.getElementById(
            'ph'
        ).innerText =
            datos.ph;


        document.getElementById(
            'nitrogeno'
        ).innerText =
            datos.nitrogeno;


        document.getElementById(
            'fosforo'
        ).innerText =
            datos.fosforo;


        document.getElementById(
            'potasio'
        ).innerText =
            datos.potasio;


        const estado =
            document.getElementById(
                'estadoESP32'
            );


        if(datos.esp32_conectado){
            estado.innerText = 'ESP32: conectado - ' + datos.puerto;
        }else{
            estado.innerText = 'ESP32: no conectado';
        }

        const estadoTransbot = document.getElementById('estadoTransbot');
        estadoTransbot.innerText = datos.transbot_activo
            ? 'Transbot: activo'
            : 'Transbot: detenido';


    }catch(error){

        console.error(
            'Error obteniendo datos:',
            error
        );

    }

}


// ==========================================================
// CONTROL DEL MOTOR
// ==========================================================

async function controlMotor(accion){

    const estado =
        document.getElementById(
            'estadoMotor'
        );


    estado.innerText =
        'Enviando comando...';


    try{

        const respuesta =
            await fetch(
                '/motor/' + accion
            );


        const datos =
            await respuesta.json();


        if(datos.ok){

            estado.innerText =
                datos.mensaje;

        }else{

            estado.innerText =
                'Error: ' +
                datos.mensaje;

        }


    }catch(error){

        estado.innerText =
            'No se pudo conectar con Flask';

        console.error(error);

    }

}


// ==========================================================
// ACTUALIZACIÓN AUTOMÁTICA
// ==========================================================

actualizarDatos();


// Actualiza cada 3 segundos para reducir carga en la Raspberry
setInterval(
    actualizarDatos,
    3000
);


</script>


</body>

</html>

"""


    return html


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

    print(
        f"http://{ESP32_IP}"
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