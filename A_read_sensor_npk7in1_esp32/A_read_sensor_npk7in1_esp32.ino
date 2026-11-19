#include <WiFi.h>
#include <WebServer.h>
#include <HardwareSerial.h>

HardwareSerial SerialSensor(1); // UART1 para el sensor NPK

// PINES

// Sensor NPK
const int SeriaSensor1RX = 16;
const int SeriaSensor1TX = 17;

// Puente H L298N Mini
const int MOTOR_IN1 = 18;
const int MOTOR_IN2 = 5;

// DATOS DEL SENSOR
float soilHumidity = 0;
float soilTemperature = 0;
int soilConductivity = 0;
float soilPH = 0;
int nitrogen = 0;
int phosphorus = 0;
int potassium = 0;
unsigned long ultimaLecturaSensor = 0;
const unsigned long intervaloSensor = 3000;

// SERVIDOR WIFI
WebServer server(80);
const char* ssid = "NPK-SUELO";
const char* password = "12345678";

// SETUP
void setup() {

  Serial.begin(115200);

  Serial.println("NPK_SMART_SOIL_ESP32");

  // UART del sensor NPK
  SerialSensor.begin(
    9600,
    SERIAL_8N1,
    SeriaSensor1RX,
    SeriaSensor1TX
  );

  // CONFIGURAR MOTOR
  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);

  // Motor detenido al arrancar
  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);

  // CREAR WIFI
  IPAddress local_IP(192, 168, 4, 1);
  IPAddress gateway(192, 168, 4, 1);
  IPAddress subnet(255, 255, 255, 0);

  WiFi.softAPConfig(
    local_IP,
    gateway,
    subnet
  );

  WiFi.softAP(
    ssid,
    password
  );

  Serial.println();
  Serial.println("==============================");
  Serial.println("       NPK SMART SOIL");
  Serial.println("==============================");

  Serial.println("WiFi iniciada");

  Serial.print("Nombre WiFi: ");
  Serial.println(ssid);

  Serial.print("IP: ");
  Serial.println(WiFi.softAPIP());


  server.on("/", handleRoot);

  server.on("/datos", []() {

  String json = "{";

  json += "\"humedad\":" + String(soilHumidity, 1) + ",";
  json += "\"temperatura\":" + String(soilTemperature, 1) + ",";
  json += "\"conductividad\":" + String(soilConductivity) + ",";
  json += "\"ph\":" + String(soilPH, 1) + ",";
  json += "\"nitrogeno\":" + String(nitrogen) + ",";
  json += "\"fosforo\":" + String(phosphorus) + ",";
  json += "\"potasio\":" + String(potassium);

  json += "}";

  server.send(200, "application/json", json);
});

  // CONTROL DEL MOTOR
  server.on("/adelante", []() {

    moverAdelante();

    server.send(
      200,
      "text/plain",
      "Motor adelante"
    );
  });


  server.on("/atras", []() {

    moverAtras();

    server.send(
      200,
      "text/plain",
      "Motor atras"
    );
  });


  server.on("/detener", []() {

    detenerMotor();

    server.send(
      200,
      "text/plain",
      "Motor detenido"
    );
  });

 // INICIAR SERVIDOR
 
  server.begin();

  Serial.println("Servidor iniciado");
  Serial.println();
}

// PAGINA WEB

void handleRoot() {

  String html = "<!DOCTYPE html><html lang='es'><head>";
  html += "<meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>NPK Smart Soil</title>";

  html += "<style>";
  html += R"=====(
    :root{
      --bg:#171a16;
      --card:#1f241d;
      --card-edge:#333a2f;
      --text:#eef0ea;
      --muted:#8e9788;
    }
    *{box-sizing:border-box;}
    body{
      margin:0;
      background:radial-gradient(circle at 15% 0%, #1c2018 0%, var(--bg) 60%);
      font-family:'Segoe UI', sans-serif;
      color:var(--text);
      padding:32px 18px 60px;
    }
    h1{ font-size:22px; letter-spacing:.08em; text-transform:uppercase; margin:0 0 2px; }
    .subtitle{ color:var(--muted); font-size:13px; }
    h2{
      font-size:13px; color:var(--muted); text-transform:uppercase;
      letter-spacing:.1em; font-weight:500; margin:28px 0 14px;
      border-bottom:1px solid var(--card-edge); padding-bottom:8px;
    }
    .grid{
      display:grid;
      grid-template-columns:repeat(auto-fill, minmax(140px,1fr));
      gap:14px; max-width:640px;
    }
    .card{
      background:linear-gradient(160deg,#242a20,var(--card) 65%);
      border:1px solid var(--card-edge);
      border-radius:10px;
      padding:14px 16px;
    }
    .card .label{ font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }
    .card .value{ font-size:26px; font-weight:700; margin-top:4px; }
    .card .unit{ font-size:13px; color:var(--muted); font-weight:400; margin-left:3px; }
    .controls{ display:flex; gap:14px; flex-wrap:wrap; max-width:640px; }
    .btn{
      flex:1; min-width:140px; text-align:center; text-decoration:none;
      color:#fff; font-weight:700; font-size:16px; letter-spacing:.03em;
      padding:16px 20px; border-radius:12px; display:block;
      transition:transform .1s ease, box-shadow .1s ease;
    }
    .btn:active{ transform:translateY(4px); }
    .btn-go{
      background:linear-gradient(155deg,#6fd85c,#3c8a2e);
      box-shadow:0 6px 0 #235f1a,0 10px 18px rgba(0,0,0,.35);
    }
    .btn-go:active{ box-shadow:0 2px 0 #235f1a,0 4px 10px rgba(0,0,0,.25); }
    .btn-back{
      background:linear-gradient(155deg,#6fa8e0,#3568a8);
      box-shadow:0 6px 0 #1f4270,0 10px 18px rgba(0,0,0,.35);
    }
    .btn-back:active{ box-shadow:0 2px 0 #1f4270,0 4px 10px rgba(0,0,0,.25); }
    .btn-stop{
      background:linear-gradient(155deg,#ff5b5b,#c92a2a);
      box-shadow:0 6px 0 #7a1a1a,0 10px 18px rgba(0,0,0,.35);
    }
    .btn-stop:active{ box-shadow:0 2px 0 #7a1a1a,0 4px 10px rgba(0,0,0,.25); }
  )=====";

  html += R"=====(

   .historial{
     max-width:640px;
     background:#1f241d;
     border:1px solid #333a2f;
     border-radius:10px;
     overflow:hidden;
}

  .accion{
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding:14px 16px;
    border-bottom:1px solid #333a2f;
    font-size:15px;
}

  .accion:last-child{
   border-bottom:none;
}

  .numero{
   color:#8e9788;
   width:40px;
}

 .nombre-accion{
   flex:1;
   font-weight:700;
}

 .hora{
   color:#8e9788;
   font-size:12px;
}

 .sin-acciones{
   padding:20px;
   color:#8e9788;
   text-align:center;
}

)=====";

  html += "</style>";
  html += "</head><body>";

  html += "<h1>NPK Smart Soil</h1>";
  html += "<div class='subtitle'>Monitor de suelo en tiempo real</div>";

  // DATOS DEL SENSOR (en tarjetas)

  html += "<h2>Lecturas del sensor</h2>";
  html += "<div class='grid'>";

  html += "<div class='card'><div class='label'>Humedad</div><div class='value' id='humedad'>" + String(soilHumidity, 1) + "<span class='unit'>%</span></div></div>";

  html += "<div class='card'><div class='label'>Temperatura</div><div class='value' id='temperatura'>" + String(soilTemperature, 1) + "<span class='unit'>°C</span></div></div>";

  html += "<div class='card'><div class='label'>Conductividad</div><div class='value' id='conductividad'>" + String(soilConductivity) + "<span class='unit'>µS/cm</span></div></div>";

  html += "<div class='card'><div class='label'>pH</div><div class='value' id='ph'>" + String(soilPH, 1) + "</div></div>";

  html += "<div class='card'><div class='label'>Nitrógeno</div><div class='value' id='nitrogeno'>" + String(nitrogen) + "</div></div>";

  html += "<div class='card'><div class='label'>Fósforo</div><div class='value' id='fosforo'>" + String(phosphorus) + "</div></div>";

  html += "<div class='card'><div class='label'>Potasio</div><div class='value' id='potasio'>" + String(potassium) + "</div></div>";
  html += "</div>";

  // CONTROL DEL MOTOR

 html += "<div class='controls'>";

 html += "<button class='btn btn-go' onclick=\"controlMotor('/adelante')\">";
 html += "&#8593; ADELANTE";
 html += "</button>";

 html += "<button class='btn btn-back' onclick=\"controlMotor('/atras')\">";
 html += "&#8595; ATRÁS";
 html += "</button>";

 html += "<button class='btn btn-stop' onclick=\"controlMotor('/detener')\">";
 html += "&#9940; DETENER";
 html += "</button>";

 html += "</div>";

 html += "<h2>Historial de acciones</h2>";

html += "<div id='historial' class='historial'>";

html += "<div class='sin-acciones'>";
html += "No hay acciones registradas";
html += "</div>";

html += "</div>";

 html += "<div id='estado' style='margin-top:20px;font-weight:bold;'>";
 html += "Estado: DETENIDA";
 html += "</div>";

 html += "<script>";

 html += "let numeroAccion = 0;";

 html += "function controlMotor(ruta) {";

 html += "fetch(ruta)"
        ".then(response => response.text())"
        ".then(data => {";

 html += "document.getElementById('estado').innerText = 'Estado: ' + data;";

 html += "agregarAccion(data);";

 html += "})";

 html += ".catch(error => {";

 html += "document.getElementById('estado').innerText = 'Error de conexión';";

 html += "});";

 html += "}";


 html += "function agregarAccion(accion) {";

 html += "numeroAccion++;";

 html += "let historial = document.getElementById('historial');";

 html += "let sinAcciones = document.querySelector('.sin-acciones');";

 html += "if (sinAcciones) {";
 html += "sinAcciones.remove();";
 html += "}";

 html += "let ahora = new Date();";

 html += "let hora = ahora.toLocaleTimeString();";

 html += "let elemento = document.createElement('div');";

 html += "elemento.className = 'accion';";

 html += "elemento.innerHTML = "
        "\"<span class='numero'>#\" + numeroAccion + "
        "\"</span>\" + "
        "\"<span class='nombre-accion'>\" + accion + "
        "\"</span>\" + "
        "\"<span class='hora'>\" + hora + "
        "\"</span>\";";

 html += "historial.prepend(elemento);";

 html += "}";

 html += "</script>";

 html += "}";

 html += "</script>";
 html += "<script>";
 html += "function actualizarDatos() {";
 html += "fetch('/datos')";
 html += ".then(response => response.json())";
 html += ".then(data => {";
 html += "document.getElementById('humedad').innerHTML = data.humedad.toFixed(1) + \"<span class='unit'>%</span>\";";
 html += "document.getElementById('temperatura').innerHTML = data.temperatura.toFixed(1) + \"<span class='unit'>°C</span>\";";
 html += "document.getElementById('conductividad').innerHTML = data.conductividad + \"<span class='unit'>µS/cm</span>\";";
 html += "document.getElementById('ph').innerHTML = data.ph.toFixed(1);";
 html += "document.getElementById('nitrogeno').innerHTML = data.nitrogeno;";
 html += "document.getElementById('fosforo').innerHTML = data.fosforo;";
 html += "document.getElementById('potasio').innerHTML = data.potasio;";
 html += "})";
 html += ".catch(error => {";
 html += "console.log('Error actualizando sensores:', error);";
 html += "});";
 html += "}";
 html += "setInterval(actualizarDatos, 2000);";
 html += "actualizarDatos();";
 html += "</script>";
 html += "</body></html>";

  server.send(200, "text/html", html);
}

// MOTOR ADELANTE

void moverAdelante() {

  digitalWrite(
    MOTOR_IN1,
    HIGH
  );

  digitalWrite(
    MOTOR_IN2,
    LOW
  );

  Serial.println(
    "MOTOR: ADELANTE"
  );
}

// MOTOR ATRAS

void moverAtras() {

  digitalWrite(
    MOTOR_IN1,
    LOW
  );

  digitalWrite(
    MOTOR_IN2,
    HIGH
  );

  Serial.println(
    "MOTOR: ATRAS"
  );
}

// DETENER MOTOR

void detenerMotor() {

  digitalWrite(
    MOTOR_IN1,
    LOW
  );

  digitalWrite(
    MOTOR_IN2,
    LOW
  );

  Serial.println(
    "MOTOR: DETENIDO"
  );
}

// LOOP

void recibirComandoSerial() {

  if (Serial.available()) {

    String comando = Serial.readStringUntil('\n');

    comando.trim();

    if (comando == "ADELANTE") {

      moverAdelante();

      Serial.println("OK:ADELANTE");

    }
    else if (comando == "ATRAS") {

      moverAtras();

      Serial.println("OK:ATRAS");

    }
    else if (comando == "DETENER") {

      detenerMotor();

      Serial.println("OK:DETENIDO");

    }
  }
}

void loop() {

  server.handleClient();

  recibirComandoSerial();

  if (millis() - ultimaLecturaSensor >= intervaloSensor) {

    ultimaLecturaSensor = millis();

    soild_sensor_HTCpHNPK();

    if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();

    if (comando == "ADELANTE") {
        moverAdelante();
    }
    else if (comando == "ATRAS") {
        moverAtras();
    }
    else if (comando == "DETENER") {
        detenerMotor();
    }
}
  }
}
// SENSOR NPK

void soild_sensor_HTCpHNPK() {

  byte queryData[] = {
    0x01,
    0x03,
    0x00,
    0x00,
    0x00,
    0x07,
    0x04,
    0x08
  };

  byte receivedData[19];

  // Enviar consulta
  SerialSensor.write(
    queryData,
    sizeof(queryData)
  );

  // Enviar consulta
  SerialSensor.write(
  queryData,
  sizeof(queryData)
);

// Esperar brevemente la respuesta
  delay(100);


  if (
    SerialSensor.available()
    >= sizeof(receivedData)
  ) {

    SerialSensor.readBytes(
      receivedData,
      sizeof(receivedData)
    );

    // PROCESAR DATOS

    soilHumidity =
      ((receivedData[3] << 8)
      | receivedData[4]) / 10.0;

    soilTemperature =
      ((receivedData[5] << 8)
      | receivedData[6]) / 10.0;

    soilConductivity =
      (receivedData[7] << 8)
      | receivedData[8];

    soilPH =
      ((receivedData[9] << 8)
      | receivedData[10]) / 10.0;

    nitrogen =
      (receivedData[11] << 8)
      | receivedData[12];

    phosphorus =
      (receivedData[13] << 8)
      | receivedData[14];

    potassium =
      (receivedData[15] << 8)
      | receivedData[16];
   
       // MOSTRAR EN MONITOR SERIE
   
    Serial.println();
    Serial.println("------ SENSOR NPK ------");

    Serial.print("Humedad: ");
    Serial.print(soilHumidity, 1);
    Serial.println(" %");

    Serial.print("Temperatura: ");
    Serial.print(soilTemperature, 1);
    Serial.println(" °C");

    Serial.print("Conductividad: ");
    Serial.print(soilConductivity);
    Serial.println(" uS/cm");

    Serial.print("pH: ");
    Serial.println(soilPH, 1);

    Serial.print("Nitrogen: ");
    Serial.println(nitrogen);

    Serial.print("Phosphorus: ");
    Serial.println(phosphorus);

    Serial.print("Potassium: ");
    Serial.println(potassium);

    Serial.println("------------------------");
  }
}

// void soild_sensor_HTCpHNPK(){
//     byte queryData[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x07, 0x04, 0x08};
//   byte receivedData[19];

//   SerialSensor.write(queryData, sizeof(queryData));  // Send the query data to the NPK sensor
//   delay(1000);  // Wait for 1 second

//   if (SerialSensor.available() >= sizeof(receivedData)) {  // Check if there are enough bytes available to read
//     SerialSensor.readBytes(receivedData, sizeof(receivedData));  // Read the received data into the receivedData array

//     // Parse and print the received data in decimal format
//     unsigned int soilHumidity = (receivedData[3] << 8) | receivedData[4];
//     unsigned int soilTemperature = (receivedData[5] << 8) | receivedData[6];
//     unsigned int soilConductivity = (receivedData[7] << 8) | receivedData[8];
//     unsigned int soilPH = (receivedData[9] << 8) | receivedData[10];    
//     unsigned int nitrogen = (receivedData[11] << 8) | receivedData[12];
//     unsigned int phosphorus = (receivedData[13] << 8) | receivedData[14];
//     unsigned int potassium = (receivedData[15] << 8) | receivedData[16];

//     Serial.print("Soil Humidity: ");
//     Serial.println((float)soilHumidity / 10.0);
//     Serial.print("Soil Temperature: ");
//     Serial.println((float)soilTemperature / 10.0);
//     Serial.print("Soil Conductivity: ");
//     Serial.println(soilConductivity);
//     Serial.print("Soil pH: ");
//     Serial.println((float)soilPH / 10.0);
//     Serial.print("Nitrogen: ");
//     Serial.println(nitrogen);
//     Serial.print("Phosphorus: ");
//     Serial.println(phosphorus);
//     Serial.print("Potassium: ");
//     Serial.println(potassium);
//     Serial.println();
//   }
// }