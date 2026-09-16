#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================
# CONTROL COMPLETO DE TRANSBOT
# Movimiento + brazo + rutina automática con botón B
#
# Arquitectura:
#   - Este programa controla el Transbot por /dev/ttyAMA0
#   - Flask controla el ESP32 por /dev/ttyUSB0
#   - El botón B solicita a Flask iniciar la secuencia automática
# ============================================================

import os
import sys
import time
import threading
import pygame
import requests

from Transbot_Lib import Transbot
from arm_transbot import Transbot_ARM


# ============================================================
# CONFIGURACIÓN FLASK
# ============================================================

# Flask está ejecutándose en la misma Raspberry Pi
FLASK_URL = "http://127.0.0.1:5000"


# ============================================================
# CONFIGURACIÓN TRANBOT
# ============================================================

sys.path.append('/home/pi/.local/lib/python2.7/site-packages')
sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')
sys.path.append('/opt/ros/melodic/bin')
sys.path.append("/home/pi/transbot_ws/src/transbot_program/scripts")
sys.path.append("/home/pi/transbot_ws/src/transbot_bringup/scripts")


import rospy
from Device import *


# ============================================================
# DEBUG
# ============================================================

g_debug = False

if len(sys.argv) > 1 and sys.argv[1] == "debug":
    g_debug = True

print("Debug mode:", g_debug)


# ============================================================
# INICIALIZAR TRANBOT
# ============================================================

g_arm = Transbot_ARM(debug=g_debug)

g_arm_offset = g_arm.get_arm_offset()

g_bot = Transbot(com="/dev/ttyAMA0")


# ============================================================
# POSICIONES DEL BRAZO
# ============================================================

POSICION_BAJA = [120, 0, 0]

POSICION_ALTA = [135, 135, 135]

ultima_posicion = [90, 90, 90]


# ============================================================
# ESTADO DE LA RUTINA AUTOMÁTICA
# ============================================================

rutina_activa = False


# ============================================================
# CONFIGURACIÓN DE LA RUTA AUTOMÁTICA
# ============================================================

# Tiempo aproximado para avanzar unos 3 pasos.
# Se puede ajustar después de hacer la primera prueba.

RUTINA_AVANCE = 1.5

# Tiempo que gira el Transbot

RUTINA_GIRO = 1.0

# Velocidad de avance

RUTINA_VELOCIDAD = 0.25

# Velocidad de giro

RUTINA_VELOCIDAD_GIRO = 1.0


# ============================================================
# CONFIGURACIÓN DE BOTONES
# ============================================================

# Botón B
BOTON_B = 1

# Botones originales del programa

BOTON_BRAZO_BAJA = 1
BOTON_BRAZO_SUBE = 0
BOTON_PARADA = 2
BOTON_SALIR = 7


# ============================================================
# POSICIONAMIENTO SUAVE DEL BRAZO
# ============================================================

def mover_suave(pos_objetivo):

    global ultima_posicion

    delay = 0.01
    paso = 1

    for i in range(3):

        servo_id = i + 7

        inicio = ultima_posicion[i]
        fin = pos_objetivo[i]

        if inicio < fin:

            rango = range(
                inicio,
                fin + paso,
                paso
            )

        else:

            rango = range(
                inicio,
                fin - paso,
                -paso
            )

        for angulo in rango:

            g_bot.set_uart_servo_angle(
                servo_id,
                angulo
            )

            time.sleep(delay)

        ultima_posicion[i] = fin


# ============================================================
# CONFIGURAR JOYSTICK
# ============================================================

def init_joystick():

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:

        print()
        print("⚠️ No se detectó ningún joystick.")
        print()

        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)

    joystick.init()

    print()
    print("🎮 Joystick conectado:")
    print(joystick.get_name())
    print()

    return joystick


# ============================================================
# MAPEAR VALORES DEL JOYSTICK
# ============================================================

MAX_LINEAR_SPEED = 0.45

MAX_ANGULAR_SPEED = 1.5


def map_value(
    x,
    in_min,
    in_max,
    out_min,
    out_max
):

    return out_min + (
        float(x - in_min)
        * (out_max - out_min)
        / (in_max - in_min)
    )


# ============================================================
# AVANZAR DURANTE UN TIEMPO
# ============================================================

def avanzar_durante(duracion):

    print()
    print("🚜 Transbot avanzando...")

    g_bot.set_car_motion(
        RUTINA_VELOCIDAD,
        0
    )

    tiempo_inicio = time.time()

    while time.time() - tiempo_inicio < duracion:

        time.sleep(0.05)

    g_bot.set_car_motion(
        0,
        0
    )

    print("🛑 Transbot detenido.")


# ============================================================
# GIRAR DURANTE UN TIEMPO
# ============================================================

def girar_durante(duracion):

    print()
    print("↪️ Transbot girando...")

    g_bot.set_car_motion(
        0,
        RUTINA_VELOCIDAD_GIRO
    )

    tiempo_inicio = time.time()

    while time.time() - tiempo_inicio < duracion:

        time.sleep(0.05)

    g_bot.set_car_motion(
        0,
        0
    )

    print("🛑 Giro terminado.")


# ============================================================
# INICIAR SECUENCIA DE FLASK
# ============================================================

def iniciar_secuencia_flask():

    print()
    print("==============================")
    print(" SOLICITANDO SECUENCIA FLASK")
    print("==============================")
    print()

    try:

        respuesta = requests.post(
            FLASK_URL + "/automatizar",
            timeout=5
        )

        datos = respuesta.json()

        print(
            "Respuesta Flask:",
            datos
        )

        if not respuesta.ok:

            print()
            print(
                "❌ Flask no pudo iniciar la secuencia."
            )

            return False

        if not datos.get("ok", False):

            print()
            print(
                "❌ La secuencia no fue iniciada."
            )

            print(
                datos.get(
                    "mensaje",
                    "Error desconocido"
                )
            )

            return False

        print()
        print("✅ Secuencia Flask iniciada.")

        return True

    except Exception as error:

        print()
        print(
            "❌ Error conectando con Flask:"
        )

        print(error)

        return False


# ============================================================
# ESPERAR A QUE TERMINE LA SECUENCIA
# ============================================================

def esperar_secuencia_flask():

    print()
    print("==============================")
    print(" ESPERANDO SECUENCIA ESP32")
    print("==============================")
    print()

    tiempo_inicio = time.time()

    # Tiempo máximo de espera.
    # La secuencia actual dura aproximadamente 21 segundos,
    # pero dejamos margen suficiente.

    TIMEOUT_SECUENCIA = 120

    while True:

        try:

            respuesta = requests.get(
                FLASK_URL + "/api/secuencia",
                timeout=5
            )

            datos = respuesta.json()

            activa = datos.get(
                "activa",
                False
            )

            terminada = datos.get(
                "terminada",
                False
            )

            print(
                f"Secuencia -> "
                f"activa={activa}, "
                f"terminada={terminada}"
            )

            if terminada and not activa:

                print()
                print(
                    "✅ Secuencia ESP32 terminada."
                )

                return True

        except Exception as error:

            print(
                "⚠️ Error consultando Flask:",
                error
            )

        if time.time() - tiempo_inicio > TIMEOUT_SECUENCIA:

            print()
            print(
                "❌ Tiempo de espera agotado."
            )

            return False

        time.sleep(0.5)


# ============================================================
# RUTINA AUTOMÁTICA COMPLETA
# ============================================================

def rutina_automatica():

    global rutina_activa

    if rutina_activa:

        print(
            "⚠️ La rutina automática ya está activa."
        )

        return

    rutina_activa = True

    print()
    print("========================================")
    print("       INICIANDO RUTINA AUTOMÁTICA")
    print("========================================")
    print()

    try:

        # ----------------------------------------------------
        # 1. DETENER EL TRANSBOT
        # ----------------------------------------------------

        print("🛑 Preparando Transbot...")

        g_bot.set_car_motion(
            0,
            0
        )

        time.sleep(0.5)


        # ----------------------------------------------------
        # 2. AVANZAR APROXIMADAMENTE 3 PASOS
        # ----------------------------------------------------

        avanzar_durante(
            RUTINA_AVANCE
        )

        time.sleep(0.5)


        # ----------------------------------------------------
        # 3. GIRAR
        # ----------------------------------------------------

        girar_durante(
            RUTINA_GIRO
        )

        time.sleep(0.5)


        # ----------------------------------------------------
        # 4. DETENER
        # ----------------------------------------------------

        g_bot.set_car_motion(
            0,
            0
        )

        print()
        print("🛑 Transbot detenido.")
        print()


        # ----------------------------------------------------
        # 5. BAJAR BRAZO
        # ----------------------------------------------------

        print("↓ Bajando brazo...")

        mover_suave(
            POSICION_BAJA
        )

        print("✅ Brazo abajo.")

        time.sleep(1)


        # ----------------------------------------------------
        # 6. PEDIR A FLASK QUE INICIE LA SECUENCIA
        # ----------------------------------------------------

        secuencia_iniciada = iniciar_secuencia_flask()

        if not secuencia_iniciada:

            print()
            print(
                "❌ No se pudo iniciar la secuencia ESP32."
            )

            print(
                "Subiendo el brazo por seguridad..."
            )

            mover_suave(
                POSICION_ALTA
            )

            return


        # ----------------------------------------------------
        # 7. ESPERAR A QUE TERMINE EL ESP32
        # ----------------------------------------------------

        secuencia_terminada = esperar_secuencia_flask()

        if not secuencia_terminada:

            print()
            print(
                "⚠️ La secuencia no terminó correctamente."
            )


        # ----------------------------------------------------
        # 8. SUBIR BRAZO
        # ----------------------------------------------------

        print()
        print("↑ Subiendo brazo...")

        mover_suave(
            POSICION_ALTA
        )

        print("✅ Brazo en posición inicial.")


        # ----------------------------------------------------
        # 9. ASEGURAR DETENCIÓN
        # ----------------------------------------------------

        g_bot.set_car_motion(
            0,
            0
        )

        print()
        print("========================================")
        print("       RUTINA AUTOMÁTICA TERMINADA")
        print("========================================")
        print()


    except Exception as error:

        print()
        print("❌ ERROR EN RUTINA AUTOMÁTICA:")
        print(error)
        print()

        # Seguridad:
        # detener el Transbot

        try:

            g_bot.set_car_motion(
                0,
                0
            )

        except:

            pass

        # Intentar devolver brazo a posición alta

        try:

            mover_suave(
                POSICION_ALTA
            )

        except:

            pass


    finally:

        rutina_activa = False

        # Última orden de seguridad

        try:

            g_bot.set_car_motion(
                0,
                0
            )

        except:

            pass


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    joystick = init_joystick()

    # --------------------------------------------------------
    # Posición inicial del Transbot
    # --------------------------------------------------------

    g_bot.set_car_motion(
        0,
        0
    )

    print()
    print("==============================")
    print("       TRANSBOT LISTO")
    print("==============================")
    print()
    print("Joystick izquierdo:")
    print("  ↑ ↓  Movimiento")
    print("  ← →  Giro")
    print()
    print("Botón 1: bajar brazo")
    print("Botón 0: subir brazo")
    print("Botón 2: parada manual")
    print("Botón B: rutina automática")
    print("Botón 7: salir")
    print()


    # ========================================================
    # ESTADO ANTERIOR DEL BOTÓN B
    # ========================================================

    boton_b_anterior = False


    try:

        while True:

            pygame.event.pump()


            # =================================================
            # BOTÓN B
            # Detectamos solamente el momento de PRESIONAR.
            # Así mantener B pulsado no inicia muchas rutinas.
            # =================================================

            boton_b_actual = joystick.get_button(
                BOTON_B
            )


            if (
                boton_b_actual
                and not boton_b_anterior
                and not rutina_activa
            ):

                print()
                print(
                    "🔵 BOTÓN B PRESIONADO"
                )

                print(
                    "Iniciando rutina automática..."
                )

                # Detener inmediatamente el movimiento manual

                g_bot.set_car_motion(
                    0,
                    0
                )

                hilo_rutina = threading.Thread(
                    target=rutina_automatica,
                    daemon=True
                )

                hilo_rutina.start()


            boton_b_anterior = boton_b_actual


            # =================================================
            # SI LA RUTINA AUTOMÁTICA ESTÁ ACTIVA
            # =================================================

            if rutina_activa:

                # No ejecutar el control manual
                # porque podría interferir con la rutina.

                time.sleep(0.05)

                continue


            # =================================================
            # CONTROL MANUAL DEL JOYSTICK
            # =================================================

            axis_y = -joystick.get_axis(1)

            axis_x = joystick.get_axis(0)


            line_speed = map_value(
                axis_y,
                -1,
                1,
                -MAX_LINEAR_SPEED,
                MAX_LINEAR_SPEED
            )


            angular_speed = map_value(
                axis_x,
                1,
                -1,
                -MAX_ANGULAR_SPEED,
                MAX_ANGULAR_SPEED
            )


            # -------------------------------------------------
            # ZONA MUERTA
            # -------------------------------------------------

            if abs(line_speed) < 0.05:

                line_speed = 0


            if abs(angular_speed) < 0.05:

                angular_speed = 0


            # -------------------------------------------------
            # MOVER TRANSBOT
            # -------------------------------------------------

            g_bot.set_car_motion(
                line_speed,
                angular_speed
            )


            # =================================================
            # BRAZO ABAJO
            # =================================================

            if joystick.get_button(
                BOTON_BRAZO_BAJA
            ):

                print(
                    "↓ Bajando brazo..."
                )

                mover_suave(
                    POSICION_BAJA
                )

                time.sleep(0.5)


            # =================================================
            # BRAZO ARRIBA
            # =================================================

            elif joystick.get_button(
                BOTON_BRAZO_SUBE
            ):

                print(
                    "↑ Subiendo brazo..."
                )

                mover_suave(
                    POSICION_ALTA
                )

                time.sleep(0.5)


            # =================================================
            # PARADA MANUAL
            # =================================================

            if joystick.get_button(
                BOTON_PARADA
            ):

                g_bot.set_car_motion(
                    0,
                    0
                )

                print(
                    "🛑 Parada manual"
                )

                time.sleep(0.2)


            # =================================================
            # SALIR
            # =================================================

            if joystick.get_button(
                BOTON_SALIR
            ):

                print()
                print(
                    "🛑 Saliendo del programa."
                )

                break


            time.sleep(0.05)


    except KeyboardInterrupt:

        print()
        print(
            "🛑 Programa detenido por el usuario."
        )


    finally:

        # ----------------------------------------------------
        # SEGURIDAD
        # ----------------------------------------------------

        print()
        print(
            "Deteniendo Transbot..."
        )

        try:

            g_bot.set_car_motion(
                0,
                0
            )

        except:

            pass


        pygame.quit()

        print(
            "Programa finalizado."
        )


# ============================================================
# INICIO DEL PROGRAMA
# ============================================================

if __name__ == '__main__':

    # Primero colocamos el brazo arriba

    print()
    print(
        "Colocando brazo en posición inicial..."
    )

    mover_suave(
        POSICION_ALTA
    )

    print(
        "Brazo listo."
    )

    # Iniciar control

    main()

#pi@Transbot:~/Desktop/proyecto$ python3 app.py

==============================
       NPK SMART SOIL
==============================

Preparando base de datos...
Base de datos preparada.

Iniciando lector del ESP32...

==============================
       BUSCANDO ESP32
==============================

Conectando a /dev/ttyUSB0...

Servidor Flask iniciado.

Dashboard:
http://127.0.0.1:5000/historial

Control del ESP32:

Presiona CTRL+C para detener.

 * Serving Flask app 'app' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
Traceback (most recent call last):
  File "app.py", line 2334, in <module>
    use_reloader=False
  File "/home/pi/.local/lib/python3.6/site-packages/flask/app.py", line 920, in run
    run_simple(t.cast(str, host), port, self, **options)
  File "/home/pi/.local/lib/python3.6/site-packages/werkzeug/serving.py", line 1010, in run_simple
    inner()
  File "/home/pi/.local/lib/python3.6/site-packages/werkzeug/serving.py", line 959, in inner
    fd=fd,
  File "/home/pi/.local/lib/python3.6/site-packages/werkzeug/serving.py", line 783, in make_server
    host, port, app, request_handler, passthrough_errors, ssl_context, fd=fd
  File "/home/pi/.local/lib/python3.6/site-packages/werkzeug/serving.py", line 688, in __init__
    super().__init__(server_address, handler)  # type: ignore
  File "/usr/lib/python3.6/socketserver.py", line 456, in __init__
    self.server_bind()
  File "/usr/lib/python3.6/http/server.py", line 136, in server_bind
    socketserver.TCPServer.server_bind(self)
  File "/usr/lib/python3.6/socketserver.py", line 470, in server_bind
    self.socket.bind(self.server_address)
OSError: [Errno 98] Address already in use

