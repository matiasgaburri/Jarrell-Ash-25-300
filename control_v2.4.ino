const int relayEnable = 7;
const int relayDir    = 8;
const int pinPos      = A0;
const int pinSignal   = A1;

// Tiempo muerto al cambiar de direccion para proteger motor y relays
const unsigned long tiempoCambio = 300; // ms

// ------------------------------------------------------------
// Ajustes de control
// ------------------------------------------------------------

// Promedio usado para leer la posicion durante el control
const unsigned long tiempoPID = 20; // ms

// Tiempo de promedio de la señal. Python lo modifica con I<ms>
unsigned long tiempoMedicion = 500; // ms

// Tolerancia de llegada en cuentas ADC del potenciometro
const int tolerancia = 2;

// Si forward hace aumentar POS, dejar true
const bool forwardAumentaPosicion = true;

// Periodicidad con la que se informa la posicion durante el movimiento
const unsigned long periodoPosicion = 1000; // ms

// ------------------------------------------------------------
// Estado
// ------------------------------------------------------------
bool motorEncendido = false;
bool direccion = false;

bool controlActivo = false;
int setpoint = 0;

unsigned long ultimaPosicion = 0;
unsigned long ultimaSenial = 0;

String bufferSerie = "";

// ------------------------------------------------------------
// Motor
// ------------------------------------------------------------
void apagarMotor()
{
  digitalWrite(relayEnable, LOW);
  motorEncendido = false;
}

void encenderMotor()
{
  if (!motorEncendido)
  {
    digitalWrite(relayEnable, HIGH);
    motorEncendido = true;
  }
}

void cambiarDireccion(bool nuevaDireccion)
{
  if (direccion == nuevaDireccion)
    return;

  apagarMotor();
  delay(tiempoCambio);

  digitalWrite(relayDir, nuevaDireccion ? HIGH : LOW);
  direccion = nuevaDireccion;

  delay(tiempoCambio);
}

void moverForward()
{
  cambiarDireccion(false);
  encenderMotor();
}

void moverReverse()
{
  cambiarDireccion(true);
  encenderMotor();
}

// ------------------------------------------------------------
// Lecturas analogicas promediadas
// ------------------------------------------------------------
int leerPosicionPromedio(unsigned long tiempo)
{
  unsigned long inicio = millis();
  long suma = 0;
  long cantidad = 0;

  while (millis() - inicio < tiempo)
  {
    suma += analogRead(pinPos);
    cantidad++;
  }

  if (cantidad == 0)
    return analogRead(pinPos);

  return suma / cantidad;
}

int leerSenialPromedio(unsigned long tiempo)
{
  unsigned long inicio = millis();
  long suma = 0;
  long cantidad = 0;

  while (millis() - inicio < tiempo)
  {
    suma += analogRead(pinSignal);
    cantidad++;
  }

  if (cantidad == 0)
    return analogRead(pinSignal);

  return suma / cantidad;
}

// ------------------------------------------------------------
// Mensajes que espera Python
// ------------------------------------------------------------

void enviarPosicion(int pos, int error)
{
  unsigned long t = millis();

  Serial.print("POS:");
  Serial.print(pos);

  Serial.print(",ERR:");
  Serial.print(error);

  Serial.print(",SP:");
  Serial.print(setpoint);

  Serial.print(",T:");
  Serial.println(t);
}

void enviarSenial()
{
  // El promedio tarda tiempoMedicion ms. Se toma como timestamp
  // el centro temporal de la ventana de promedio.
  unsigned long tInicio = millis();
  int senial = leerSenialPromedio(tiempoMedicion);
  unsigned long tFin = millis();
  unsigned long tMedio = tInicio + (tFin - tInicio) / 2;

  Serial.print("SIG:");
  Serial.print(senial);

  Serial.print(",T:");
  Serial.println(tMedio);
}

// ------------------------------------------------------------
// Control por setpoint
// ------------------------------------------------------------
void activarSetpoint(int nuevoSetpoint)
{
  setpoint = constrain(nuevoSetpoint, 0, 1023);
  controlActivo = true;

  ultimaPosicion = 0;
  ultimaSenial = 0;

  Serial.print("ACK:SP:");
  Serial.println(setpoint);
}

void actualizarControl()
{
  if (!controlActivo)
    return;

  // Lectura corta para decidir continuamente si se llego al setpoint
  int pos = leerPosicionPromedio(tiempoPID);
  int error = setpoint - pos;

  if (abs(error) <= tolerancia)
  {
    apagarMotor();

    // Una ultima posicion antes de DONE ayuda a cerrar la interpolacion.
    enviarPosicion(pos, error);

    controlActivo = false;

    Serial.print("DONE:");
    Serial.println(pos);
    return;
  }

  bool usarForward;

  if (forwardAumentaPosicion)
    usarForward = (error > 0);
  else
    usarForward = (error < 0);

  if (usarForward)
    moverForward();
  else
    moverReverse();

  unsigned long ahora = millis();

  // Posicion y señal se mandan en lineas SEPARADAS porque asi las
  // parsea el script de Python.
  if (ahora - ultimaPosicion >= periodoPosicion)
  {
    ultimaPosicion = ahora;
    enviarPosicion(pos, error);
  }

  if (ahora - ultimaSenial >= tiempoMedicion)
  {
    ultimaSenial = millis();
    enviarSenial();
  }
}

// ------------------------------------------------------------
// Recepcion serie
// ------------------------------------------------------------
void procesarComando(String comando)
{
  comando.trim();
  comando.toUpperCase();

  if (comando.length() == 0)
    return;

  char tipo = comando.charAt(0);

  // T<POS> : mover a setpoint
  if (tipo == 'T')
  {
    int nuevoSetpoint = comando.substring(1).toInt();
    activarSetpoint(nuevoSetpoint);
    return;
  }

  // I<ms> : tiempo de promedio de señal
  if (tipo == 'I')
  {
    unsigned long tiempo = comando.substring(1).toInt();

    if (tiempo < 1)
      tiempo = 1;

    if (tiempo > 2000)
      tiempo = 2000;

    tiempoMedicion = tiempo;

    Serial.print("ACK:I:");
    Serial.println(tiempoMedicion);
    return;
  }

  switch (tipo)
  {
    case 'P':
    {
      int pos = leerPosicionPromedio(tiempoPID);

      Serial.print("POS:");
      Serial.print(pos);
      Serial.print(",T:");
      Serial.println(millis());
      break;
    }

    case 'S':
      controlActivo = false;
      apagarMotor();
      Serial.println("STOP");
      break;

    case 'F':
      controlActivo = false;
      moverForward();
      Serial.println("FORWARD");
      break;

    case 'R':
      controlActivo = false;
      moverReverse();
      Serial.println("REVERSE");
      break;

    default:
      Serial.println("ERR:COMANDO_INVALIDO");
      break;
  }
}

void leerComandosSerie()
{
  while (Serial.available() > 0)
  {
    char c = Serial.read();

    if (c == '\n' || c == '\r')
    {
      if (bufferSerie.length() > 0)
      {
        procesarComando(bufferSerie);
        bufferSerie = "";
      }
    }
    else
    {
      bufferSerie += c;

      if (bufferSerie.length() > 30)
        bufferSerie = "";
    }
  }
}

// ------------------------------------------------------------
// Setup / loop
// ------------------------------------------------------------
void setup()
{
  Serial.begin(115200);

  pinMode(relayEnable, OUTPUT);
  pinMode(relayDir, OUTPUT);

  apagarMotor();
  digitalWrite(relayDir, LOW);

  Serial.println("LISTO");
  Serial.println("Comandos: T<num>, I<ms>, P, S, F, R");
}

void loop()
{
  leerComandosSerie();
  actualizarControl();
}
