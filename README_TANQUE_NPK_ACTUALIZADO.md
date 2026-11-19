# NPK SMART SOIL 🌱

Sistema de monitoreo agrícola basado en IoT que integra un sensor de suelo NPK de 7 parámetros, un microcontrolador ESP32 y aplicaciones de visualización y control. El proyecto permite consultar variables del suelo, visualizar mediciones desde una interfaz web y accionar un motor mediante un controlador L298N Mini.

El repositorio reúne el firmware del ESP32 y los programas Python asociados al dashboard, almacenamiento de mediciones y control de la plataforma Transbot.

## Características principales

- Lectura de siete parámetros del suelo: humedad, temperatura, conductividad eléctrica, pH, nitrógeno, fósforo y potasio.
- Comunicación entre el sensor y el ESP32 mediante UART1 (interfaz serial utilizada para el sensor RS485).
- Servidor web integrado en el ESP32 mediante Wi-Fi en modo punto de acceso.
- Consulta de mediciones en formato JSON.
- Interfaz web alojada directamente en el ESP32.
- Control de motor mediante un puente H L298N Mini.
- Aplicación Python/Flask para integración serial, dashboard e historial local.
- Programa complementario para control de Transbot, joystick y brazo robótico.

> Las funciones disponibles dependen del hardware conectado y de la configuración del entorno. El firmware y los programas Python son componentes relacionados, pero ejecutables de manera independiente según su propósito.

## Arquitectura general: comunicación dual simultánea

El ESP32 trabaja con dos canales de comunicación activos al mismo tiempo:

1. **USB / Serial:** conecta el ESP32 con el computador. A través de este canal, Python/Flask recibe las lecturas que el firmware imprime por el puerto serial y puede enviar comandos al ESP32.
2. **Wi-Fi / servidor web integrado:** el ESP32 crea su propia red inalámbrica en modo Access Point y atiende directamente las solicitudes HTTP de los dispositivos conectados a esa red.

El canal UART1 está dedicado a la comunicación con el sensor NPK. Por tanto, el sensor, el puerto USB y el servidor Wi-Fi cumplen funciones distintas dentro del mismo controlador.

```text
       SENSOR DE SUELO NPK 7 EN 1
     Humedad · Temperatura · EC · pH
             N · P · K
                  |
          Interfaz / transceptor RS485
                  |
                  v
              ESP32
       UART1: RX 16 / TX 17
                  |
        +---------+----------------+
        |                          |
        v                          v
  USB / Serial                 Wi-Fi Access Point
  115200 baudios               SSID: NPK-SUELO
        |                      IP: 192.168.4.1
        |                          |
        v                          v
  Python + PySerial          Servidor HTTP ESP32
        |                          |
        v                          +--> Página web /
  Flask + SQLite              +--> JSON /datos
        |                      +--> /adelante
        v                      +--> /atras
  Dashboard e historial       +--> /detener

        ESP32
          |
          v
   Puente H L298N Mini
   IN1: GPIO 18
   IN2: GPIO 5

  Control complementario:
  Transbot + joystick + brazo
          |
  Programa Tanque_PUCHO.py
```

### Flujo de datos y comandos

- El sensor entrega sus registros al ESP32 por la interfaz RS485 conectada a UART1.
- El ESP32 procesa las mediciones y las muestra por USB/Serial; Flask lee ese flujo mediante PySerial.
- Flask almacena y presenta las mediciones mediante la aplicación web y SQLite.
- Flask también puede enviar comandos por el mismo puerto USB/Serial; el firmware interpreta los comandos de movimiento recibidos.
- De manera paralela, un teléfono o computador conectado a la red Wi-Fi `NPK-SUELO` puede abrir la interfaz alojada en el ESP32 y consultar `/datos` o utilizar las rutas de control del motor.

**Importante:** la interfaz web del ESP32 y el dashboard Flask son dos interfaces diferentes. La primera se sirve directamente desde el microcontrolador por Wi-Fi; la segunda se ejecuta en el computador mediante Flask.

## Hardware identificado

| Componente | Función / configuración |
|---|---|
| ESP32 | Lectura de datos, servidor web y control de motor |
| Sensor NPK 7 en 1 | Medición de siete variables del suelo |
| Interfaz RS485 del sensor | Comunicación con el ESP32 a través de UART1 |
| Puente H L298N Mini | Control de dirección del motor |
| Motor | Accionamiento controlado por el puente H |
| Transbot | Plataforma robótica utilizada por el programa complementario |

### Conexiones del ESP32

| Señal | GPIO ESP32 |
|---|---:|
| RX del sensor (UART1) | 16 |
| TX del sensor (UART1) | 17 |
| IN1 del L298N Mini | 18 |
| IN2 del L298N Mini | 5 |

**Importante:** la tabla refleja los pines declarados en el firmware compartido. Verifica el cableado físico, la alimentación, la referencia GND común y la conexión del transceptor RS485 según el módulo utilizado. No conectes directamente las líneas diferenciales A/B del sensor a los pines UART del ESP32; se requiere la interfaz/transceptor RS485 correspondiente.

## Firmware ESP32

Ubicación:

```text
firmware/
└── A_read_sensor_npk7in1_esp32/
    └── A_read_sensor_npk7in1_esp32.ino
```

### Configuración del firmware

| Parámetro | Valor definido |
|---|---|
| Comunicación con el sensor | UART1 |
| Velocidad UART del sensor | 9600 baudios |
| Formato serial | 8N1 |
| Pines UART1 | RX 16 / TX 17 |
| Monitor serial USB | 115200 baudios |
| Intervalo de lectura | 3000 ms |
| Servidor HTTP | Puerto 80 |
| Modo Wi-Fi | Punto de acceso (SoftAP) |
| SSID configurado | `NPK-SUELO` |
| IP del ESP32 | `192.168.4.1` |

La contraseña Wi-Fi está definida en el código fuente. Cámbiala antes de desplegar el equipo y evita publicar credenciales reales en el repositorio.

El firmware utiliza dos interfaces seriales con propósitos diferentes:

- `Serial`: puerto USB del ESP32, configurado a 115200 baudios. Se utiliza para imprimir el estado y las mediciones, y para recibir comandos desde el programa Python.
- `SerialSensor`: UART1, configurado a 9600 baudios en RX 16 y TX 17. Se utiliza para consultar el sensor NPK mediante el transceptor RS485.

El servidor Wi-Fi y el servidor HTTP se inicializan en el mismo firmware. En el ciclo principal se atienden las solicitudes web y se procesa la comunicación serial, mientras se realizan las lecturas periódicas del sensor.

### Variables obtenidas

| Campo JSON | Variable del firmware | Descripción |
|---|---|---|
| `humedad` | `soilHumidity` | Humedad del suelo |
| `temperatura` | `soilTemperature` | Temperatura |
| `conductividad` | `soilConductivity` | Conductividad eléctrica |
| `ph` | `soilPH` | pH |
| `nitrogeno` | `nitrogen` | Nitrógeno |
| `fosforo` | `phosphorus` | Fósforo |
| `potasio` | `potassium` | Potasio |

El firmware escala humedad, temperatura y pH dividiendo la lectura recibida entre 10. La unidad de las lecturas N, P y K debe documentarse de acuerdo con la ficha técnica del sensor.

### Rutas HTTP del ESP32

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Página web de monitoreo y control |
| GET | `/datos` | Devuelve las siete variables en JSON |
| GET | `/adelante` | Acciona el motor hacia adelante |
| GET | `/atras` | Acciona el motor hacia atrás |
| GET | `/detener` | Detiene el motor |

Ejemplo de respuesta de `/datos` (valores ilustrativos):

```json
{
  "humedad": 35.6,
  "temperatura": 24.8,
  "conductividad": 420,
  "ph": 6.5,
  "nitrogeno": 18,
  "fosforo": 25,
  "potasio": 30
}
```

Los valores del ejemplo son demostrativos y no corresponden a una medición real.

### Cómo cargar el firmware

1. Instala Arduino IDE.
2. Configura el soporte de placas ESP32 en Arduino IDE.
3. Abre `A_read_sensor_npk7in1_esp32.ino`.
4. Selecciona la placa ESP32 correspondiente y el puerto USB correcto.
5. Compila y carga el programa.
6. Abre el Monitor Serie a 115200 baudios.
7. Conecta el computador o dispositivo a la red Wi-Fi `NPK-SUELO`.
8. Abre `http://192.168.4.1` en el navegador.

El sensor debe estar correctamente alimentado y conectado mediante su interfaz RS485 para obtener mediciones reales.

## Aplicación Python y dashboard

La carpeta principal contiene estos programas:

| Archivo | Descripción |
|---|---|
| `app.py` | Aplicación Flask principal, integración serial, endpoints y almacenamiento local |
| `app_dashboard_ligero_v2.py` | Implementación alternativa de dashboard e integración |
| `Tanque_PUCHO.py` | Programa complementario para control del Transbot, joystick y brazo robótico |
| `npk_smart_soil.db` | Base de datos SQLite incluida en el paquete recibido |

La aplicación Python utiliza Flask y PySerial para comunicarse con el ESP32 desde el computador. La base SQLite se utiliza para persistir datos e historial, según la implementación de la aplicación.

### Dependencias Python

Instala las dependencias principales:

```bash
pip install Flask pyserial
```

Para el programa complementario del Transbot también se utilizan:

```bash
pip install pygame requests
```

El entorno Transbot puede requerir bibliotecas adicionales del fabricante y configuración de ROS. Esas dependencias deben instalarse según el equipo robótico disponible.

### Configuración del puerto serial

La aplicación Python debe utilizar el puerto donde el ESP32 esté conectado por USB. Ejemplos:

- Windows: `COM3`, `COM4`, etc.
- Linux: `/dev/ttyUSB0` o `/dev/ttyACM0`.

Revisa la configuración de puerto y velocidad en el archivo Python antes de ejecutar. El firmware usa 115200 baudios para el monitor serial USB.

### Ejecución de Flask

Desde la carpeta del proyecto:

```bash
python app.py
```

Abre en el navegador la dirección local configurada por Flask, normalmente:

```text
http://127.0.0.1:5000
```

La dirección y el puerto pueden variar según la configuración de ejecución del archivo.

## Estructura recomendada del repositorio

```text
Tanque-NPK/
│
├── README.md
│
├── firmware/
│   └── A_read_sensor_npk7in1_esp32/
│       └── A_read_sensor_npk7in1_esp32.ino
│
├── backend/
│   ├── app.py
│   ├── app_dashboard_ligero_v2.py
│   ├── Tanque_PUCHO.py
│   └── requirements.txt
│
├── templates/
│   └── dashboard_verde_perla.html
│
├── static/
│   └── img/
│       ├── fondo-agro.jpg
│       └── logo-npk.png
│
├── docs/
│   ├── arquitectura.md
│   └── conexiones.md
│
└── images/
    └── (fotografías del prototipo y capturas)
```

Esta es una estructura propuesta para organizar los archivos. Al mover los programas Python a `backend/`, revisa las rutas relativas a `templates/`, `static/` y la base de datos para que Flask pueda encontrarlas correctamente.

## Observaciones antes de publicar

1. **Plantilla HTML:** en el paquete recibido, la plantilla disponible se llama `dashboard_verde_perla.html`. Verifica que `app.py` utilice exactamente ese nombre al renderizarla; una diferencia de nombre puede producir `TemplateNotFound`.
2. **Firmware:** el archivo `.ino` ya está identificado y debe incluirse en `firmware/`.
3. **Dependencias:** crea y valida `requirements.txt` en el entorno donde se ejecuta el proyecto. No se deben inventar versiones no probadas.
4. **Credenciales:** cambia la contraseña Wi-Fi de ejemplo y no publiques contraseñas, tokens ni datos privados.
5. **Base de datos:** revisa `npk_smart_soil.db` antes de publicarla. Si contiene datos de pruebas o información privada, exclúyela y documenta cómo se crea.
6. **Transbot:** documenta por separado las dependencias del robot y su entorno de ejecución.
7. **Protocolo del sensor:** confirma el modelo exacto, el mapa de registros, las unidades y el procedimiento de lectura con la documentación del fabricante.

## Tecnologías

`ESP32` · `Arduino IDE` · `C/C++` · `RS485` · `UART` · `Wi-Fi` · `Python` · `Flask` · `PySerial` · `SQLite` · `HTML` · `CSS` · `JavaScript` · `Transbot`

## Proyecto

**NPK SMART SOIL — Sistema inteligente de monitoreo agrícola.**

Proyecto de integración de sistemas embebidos, sensores, conectividad IoT, desarrollo web y control robótico para la supervisión de variables del suelo.
