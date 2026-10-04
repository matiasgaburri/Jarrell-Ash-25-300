==========================================================
CONTROL Y ADQUISICIÓN DEL ESPECTRÓMETRO JARRELL-ASH 25-300
==========================================================

Software de control y adquisición desarrollado para la puesta en funcionamiento y modernización del espectrómetro Jarrell-Ash 25-300 (monocromador doble Czerny-Turner) del Centro Atómico Constituyentes (CNEA), en el marco de la tesis de Licenciatura en Ciencias Físicas "Puesta en funcionamiento y modernización de un espectrómetro Jarrell-Ash 25-300" (FCEN-UBA).

El sistema permite:

- Posicionar las redes de difracción en un número de onda elegido.
- Realizar barridos espectrales automáticos entre dos números de onda.
- Registrar simultáneamente la posición de las redes y la señal del fotomultiplicador.
- Reconstruir el eje espectral, corregir el nivel de base y la respuesta espectral del detector.
- Guardar cada medición en un archivo CSV y graficar el espectro.

ÍNDICE
======

1. Contenido del repositorio
2. Cómo funciona el sistema
3. Requisitos
4. Conexiones
5. Instalación
6. Firmware del Arduino (controlv2_4.ino)
7. Script de Python (controlv2_4.py)
8. Procesamiento de los datos
9. Archivos de salida
10. Procedimiento de medición paso a paso
11. Recomendaciones de uso
12. Recalibración del eje espectral
13. Solución de problemas
14. Limitaciones conocidas
15. Créditos

1. CONTENIDO DEL REPOSITORIO
============================

  * controlv2_4.ino
      Descripción: Firmware para la placa Arduino. Controla el motor del sistema de barrido mediante relays, lee la posición de las redes (potenciómetro) y la señal del detector, y se comunica con la PC por puerto serie.
  * controlv2_4.py
      Descripción: Script de control para la PC. Ofrece una consola para mover las redes y hacer barridos, procesa los datos y guarda los resultados.
  * respuesta_pmt.csv
      Descripción: Curva de respuesta espectral relativa del fotomultiplicador (Hamamatsu R1414), usada para corregir la señal.
  * README.txt
      Descripción: Este documento.

2. CÓMO FUNCIONA EL SISTEMA
===========================

El sistema tiene dos partes que se comunican por USB (puerto serie): el firmware del Arduino y el script de Python.

Reparto de tareas:

- El Arduino es la interfaz con el hardware. Mide, promedia, marca cada medición con su instante de tiempo y enciende o apaga el motor según el setpoint recibido. No conoce números de onda: trabaja solo en cuentas del conversor A/D (0 a 1023).
- El script de Python es el que "piensa" en términos espectrales. Traduce números de onda a posiciones con la curva de calibración, decide qué movimiento pedir, recibe los datos, reconstruye el eje espectral y aplica las correcciones.

Idea central de la adquisición. Durante un barrido, la posición de las redes y la señal del detector se miden por separado y en instantes distintos, cada una con su marca temporal (reloj interno del Arduino, en ms). Al terminar, el script asigna a cada valor de señal la posición correspondiente interpolando en el tiempo. Esto es válido porque el mecanismo de desplazamiento cosecante del equipo produce un barrido lineal en número de onda.

3. REQUISITOS
=============

Hardware
--------

- Espectrómetro Jarrell-Ash 25-300 con el sistema de barrido original (motor, caja de velocidades y potenciómetro multivuelta acoplado al mecanismo cosecante).
- Placa Arduino (se utilizó un Arduino Nano, microcontrolador ATmega328).
- Circuito de relays para el motor (RY1: habilitación; RY2: sentido de giro), con su driver a transistores.
- Fotomultiplicador Hamamatsu R1414 con su fuente de alta tensión.
- Circuito de acondicionamiento de la señal, cuya salida debe estar entre 0 y 5 V.
- Cable USB entre el Arduino y la PC.

Software
--------

- Arduino IDE para cargar el firmware.
- Python 3 con las siguientes bibliotecas:

  Biblioteca | Uso
  -----------+-----------------------------------------
  pyserial   | Comunicación por puerto serie
  numpy      | Cálculos numéricos y ajustes
  pandas     | Lectura de la curva de respuesta del PMT
  matplotlib | Gráfico del espectro

4. CONEXIONES
=============

  * D7
      Conexión: Driver del relay RY1
      Función: Enciende / apaga el motor
  * D8
      Conexión: Driver del relay RY2
      Función: Selecciona el sentido de giro
  * A0
      Conexión: Cursor del potenciómetro (divisor de tensión entre 5 V y GND)
      Función: Posición de las redes
  * A1
      Conexión: Salida del circuito de acondicionamiento
      Función: Señal del detector
  * 5V, GND
      Conexión: Alimentación del potenciómetro y de las bobinas de los relays
      Función: —

  Nota: el firmware usa los pines D7 y D8 para los relays. Verificar que el cableado coincida; en la descripción del circuito de la tesis los relays figuran en D2 y D3. Si se usan otros pines, modificar las constantes relayEnable y relayDir al comienzo del firmware.

  Importante: la entrada A1 del Arduino admite como máximo 5 V. Ajustar la ganancia del circuito de acondicionamiento (preset R7) para que la señal más intensa que se espera medir no supere ese valor.

5. INSTALACIÓN
==============

1. Cargar el firmware. Abrir controlv2_4.ino en el Arduino IDE, seleccionar la placa y el puerto correspondientes y cargarlo.
2. Comprobar el firmware (opcional). Abrir el Monitor Serie del IDE a 115200 baudios. Al reiniciarse la placa deben aparecer las líneas:
   
   LISTO
   Comandos: T<num>, I<ms>, P, S, F, R
   
   Se puede escribir P y presionar Enter para recibir la posición actual. Cerrar el Monitor Serie antes de usar el script de Python: el puerto no puede estar abierto en dos programas a la vez.
3. Instalar las bibliotecas de Python:
   bash
   pip install pyserial numpy pandas matplotlib
   
4. Configurar el puerto. Editar la constante PUERTO al comienzo del script ("COM3" por defecto en Windows; en Linux será algo como "/dev/ttyUSB0" y en macOS "/dev/tty.usbserial-...").
5. Colocar respuesta_pmt.csv en la misma carpeta desde la que se ejecuta el script.
6. Ejecutar:
   bash
   python controlv2_4.py
   

6. FIRMWARE DEL ARDUINO
=======================

6.1 Parámetros configurables
----------------------------

Están definidos como constantes al comienzo del archivo:

  * relayEnable
      Valor: 7
      Descripción: Pin del relay de encendido del motor (RY1).
  * relayDir
      Valor: 8
      Descripción: Pin del relay de sentido de giro (RY2).
  * pinPos
      Valor: A0
      Descripción: Entrada analógica del potenciómetro.
  * pinSignal
      Valor: A1
      Descripción: Entrada analógica de la señal del detector.
  * tiempoCambio
      Valor: 300 ms
      Descripción: Tiempo muerto al cambiar el sentido de giro. El motor se apaga, se espera este tiempo, se conmuta el relay de dirección y se vuelve a esperar. Protege al motor y a los contactos de los relays.
  * tiempoPID
      Valor: 20 ms
      Descripción: Ventana de promediado de la posición durante el control. Es una lectura corta, para poder decidir con frecuencia si ya se llegó al setpoint.
  * tiempoMedicion
      Valor: 500 ms
      Descripción: Ventana de promediado de la señal. El script de Python la modifica con el comando I<ms> antes de cada barrido.
  * tolerancia
      Valor: 2 cuentas
      Descripción: Zona de llegada: el movimiento termina cuando |setpoint − posición| ≤ 2 cuentas del ADC.
  * forwardAumentaPosicion
      Valor: true
      Descripción: Indica si el giro "forward" hace aumentar la lectura del potenciómetro. Si en el mecanismo ocurre al revés, cambiar a false y el control invierte el sentido automáticamente.
  * periodoPosicion
      Valor: 1000 ms
      Descripción: Cada cuánto se informa la posición a la PC durante un movimiento.

6.2 Lecturas analógicas
-----------------------

Ambas entradas se leen con el conversor A/D de 10 bits, que asigna a cada tensión entre 0 y 5 V un valor entero entre 0 y 1023 (≈ 4,9 mV por cuenta).

Para reducir el ruido, cada lectura es un promedio: la placa lee la entrada de forma continua durante una ventana de tiempo y devuelve el promedio de todas las muestras (leerPosicionPromedio y leerSenialPromedio).

- Posición: se promedia durante tiempoPID (20 ms).
- Señal: se promedia durante tiempoMedicion. Como el promedio dura un tiempo finito y las redes se siguen moviendo, el valor obtenido representa toda la ventana. Por eso, la marca temporal que se envía con la señal es el centro de la ventana de promediado (instante de inicio más la mitad de la duración), y no el instante en que empezó.

6.3 Lógica de control
---------------------

El control es de tipo encendido/apagado con zona de tolerancia:

1. La PC envía un setpoint T<POS>. El Arduino lo limita al rango 0–1023, activa el control y responde ACK:SP:<POS>.
2. En cada ciclo del programa, mientras el control está activo:
   - Se lee la posición (promedio de 20 ms) y se calcula el error setpoint − posición.
   - Si el error está dentro de la tolerancia: se apaga el motor, se envía una última línea de posición (sirve para cerrar la interpolación en la PC), se desactiva el control y se envía DONE:<POS>.
   - Si no: se elige el sentido de giro según el signo del error (teniendo en cuenta forwardAumentaPosicion) y se enciende el motor. Si hace falta invertir el sentido, se respeta el tiempo muerto.
   - Si pasó periodoPosicion desde el último envío, se manda la posición.
   - Si pasó tiempoMedicion desde la última medición de señal, se mide y se manda la señal.
3. La posición y la señal se envían en líneas separadas, que es como las interpreta el script de Python.

Como la medición de la señal dura exactamente tiempoMedicion, las ventanas de señal quedan prácticamente una a continuación de la otra: durante un movimiento, la señal se registra de forma casi continua.

  La señal solo se mide mientras hay un movimiento en curso (control activo). Con las redes quietas, el Arduino no envía señal.

6.4 Comandos que acepta
-----------------------

Los comandos se envían como texto terminado en salto de línea. Se ignoran los espacios y no se distingue mayúsculas de minúsculas. Si se reciben más de 30 caracteres sin un salto de línea, se descartan.

  * T<POS>
      Acción: Mover las redes hasta la posición <POS> (0–1023).
      Respuesta: ACK:SP:<POS>, luego líneas POS y SIG durante el movimiento y DONE:<POS> al llegar.
  * I<ms>
      Acción: Fijar la ventana de promediado de la señal. Se limita entre 1 y 2000 ms.
      Respuesta: ACK:I:<ms>
  * P
      Acción: Pedir la posición actual.
      Respuesta: POS:<POS>,T:<ms>
  * S
      Acción: Detener: apaga el motor y cancela el control.
      Respuesta: STOP
  * F
      Acción: Mover en sentido forward de forma continua, sin setpoint.
      Respuesta: FORWARD
  * R
      Acción: Mover en sentido reverse de forma continua, sin setpoint.
      Respuesta: REVERSE
  * otro
      Acción: —
      Respuesta: ERR:COMANDO_INVALIDO

  Precaución con F y R: el motor queda encendido hasta recibir S. Usarlos solo vigilando el equipo, para no llevar el mecanismo contra sus topes.

6.5 Mensajes que envía
----------------------

  * LISTO
      Significado: La placa terminó de inicializarse.
  * POS:<pos>,ERR:<err>,SP:<sp>,T:<ms>
      Significado: Posición durante un movimiento: lectura actual, error respecto del setpoint, setpoint y marca temporal.
  * SIG:<senal>,T:<ms>
      Significado: Señal promediada (cuentas ADC) y marca temporal del centro de la ventana.
  * DONE:<pos>
      Significado: Se llegó al setpoint.
  * ACK:SP:<sp> / ACK:I:<ms>
      Significado: Confirmación de los comandos T e I.

Las marcas temporales T son el reloj interno del Arduino (millis()), en ms desde que se encendió o reinició la placa.

7. SCRIPT DE PYTHON
===================

7.1 Parámetros configurables
----------------------------

Al comienzo del script:

  * PUERTO
      Valor: "COM3"
      Descripción: Puerto serie del Arduino.
  * BAUDRATE
      Valor: 115200
      Descripción: Debe coincidir con el del firmware.
  * TIMEOUT
      Valor: 0.1 s
      Descripción: Tiempo máximo de espera de cada lectura del puerto.
  * TIEMPO_INTEGRACION
      Valor: 500 ms
      Descripción: Ventana de promediado de la señal que se envía al Arduino antes de cada barrido.
  * CARPETA_MEDICIONES
      Valor: mediciones
      Descripción: Carpeta donde se guardan los CSV. Se crea automáticamente.
  * ARCHIVO_RESPUESTA_PMT
      Valor: respuesta_pmt.csv
      Descripción: Curva de respuesta espectral del PMT.
  * LONGITUD_ONDA_REFERENCIA_NM
      Valor: 585.25 nm
      Descripción: Longitud de onda a la que se normaliza la corrección del PMT (línea intensa del neón).
  * CORREGIR_OFFSET_ADC
      Valor: True
      Descripción: Activa la sustracción del nivel de base.
  * CORREGIR_EJE_ESPECTRAL
      Valor: True
      Descripción: Activa la corrección de puntos anómalos del eje espectral.
  * TOLERANCIA_EJE_CM1
      Valor: 5.0 cm⁻¹
      Descripción: Umbral para considerar anómalo un punto del eje espectral.
  * A_POS, B_POS, C_POS
      Valor: —
      Descripción: Coeficientes de la calibración posición ↔ número de onda (ver 7.2).
  * NUM_ONDA_MIN, NUM_ONDA_MAX
      Valor: 11037 / 21997 cm⁻¹
      Descripción: Rango útil del sistema de barrido.

7.2 Calibración posición ↔ número de onda
-----------------------------------------

La lectura del potenciómetro (POS, en cuentas ADC) se relaciona con el número de onda mediante un ajuste cuadrático, obtenido al barrer el rango completo del equipo:

    POS = A·u² + B·u + C,     con   u = (ν̄ − 11037 cm⁻¹) / 1000 cm⁻¹
    
    A = 2,281024     B = 47,194962     C = 190,828864

- De número de onda a posición (numero_onda_a_pos): el número de onda se limita al rango útil, se evalúa el polinomio y se redondea al entero más cercano. Es el valor que se envía como setpoint.
- De posición a número de onda (pos_a_numero_onda): se invierte el polinomio resolviendo la ecuación cuadrática y tomando la raíz positiva. La posición se limita primero al rango cubierto por la calibración (≈ 191 a 982 cuentas).

Como el rango de ~11000 cm⁻¹ se cubre con ~790 cuentas, cada cuenta equivale en promedio a unos 14 cm⁻¹. El eje espectral final se reconstruye con mejor precisión que eso gracias al promediado y a la interpolación temporal (sección 8).

7.3 Uso de la consola
---------------------

Al ejecutar el script se abre el puerto (con una espera de 2 s, porque el Arduino se reinicia al abrir la conexión) y aparece el menú:

    Numero de onda 11037-21997 cm-1 | P=posicion | B=barrido A->B | S=stop | Q=salir:

  Entrada                      | Acción
  -----------------------------+-----------------------------------------------------------------
  Un número (por ej. 16500)    | Mueve las redes hasta ese número de onda, mostrando el progreso.
  P                            | Muestra la posición actual en cuentas y en número de onda.
  B                            | Inicia un barrido con guardado de datos (ver 7.4).
  S                            | Detiene el motor.
  Q                            | Detiene el motor y cierra el programa.
  Ctrl+C durante un movimiento | Cancela el movimiento y frena el motor.

Durante un movimiento se imprime una línea por cada posición recibida:

    POS:  612 | ERR:   35 | Numero de onda:  18240.3 cm-1 | SP:  647 | Objetivo: 18500.0 cm-1

Al salir del programa, por cualquier motivo, el script envía siempre la orden de detener el motor antes de cerrar el puerto.

7.4 Barrido
-----------

Al elegir B:

1. El script pide el número de onda inicial A y el final B, y muestra las posiciones correspondientes.
2. Envía al Arduino el tiempo de integración (I500 por defecto) y espera la confirmación. Si no la recibe en 2 s, cancela el barrido.
3. Mueve las redes hasta A sin registrar datos.
4. Mueve las redes desde A hasta B registrando: guarda por separado cada posición con su tiempo y cada valor de señal con su tiempo.
5. Al llegar a B, procesa los datos (sección 8), guarda el CSV, muestra el gráfico y escribe en consola el nivel de base estimado y la ruta del archivo.

Si al terminar no hay al menos un valor de señal y dos posiciones, el script avisa que no hay datos suficientes y no guarda nada.

  La velocidad del barrido no se controla por software. La fija el selector de velocidad del panel frontal del monocromador (caja de engranajes). El software solo enciende y apaga el motor y elige el sentido de giro.

8. PROCESAMIENTO DE LOS DATOS
=============================

Al terminar el barrido, los datos pasan por cuatro etapas.

8.1 Reconstrucción del eje espectral
------------------------------------

Posición y señal se miden en instantes distintos. Para cada valor de señal, tomado en el instante t (centro de su ventana de promediado), se busca entre qué dos posiciones registradas cae ese instante y se interpola linealmente:

    P(t) = P₁ + (t − t₁)/(t₂ − t₁) · (P₂ − P₁)

Si t queda antes de la primera posición o después de la última, se usa la posición del extremo. Luego la posición interpolada se convierte a número de onda con la calibración.

8.2 Corrección de puntos anómalos del eje
-----------------------------------------

A pesar del promediado, alguna lectura del potenciómetro puede salir anómala y producir un salto en el eje espectral. Como el barrido es aproximadamente lineal en número de onda, se ajusta una recta ν̄(t) a todos los puntos. Solo los puntos que se apartan de la recta más de TOLERANCIA_EJE_CM1 (5 cm⁻¹) se reemplazan por el valor del ajuste; el resto se conserva tal como se midió.

8.3 Sustracción del nivel de base
---------------------------------

La electrónica de acondicionamiento introduce un nivel de base aproximadamente constante (offset), al que se suma la corriente oscura del fotomultiplicador. Se estima como la moda de los valores de señal: el valor que más se repite. Esto funciona bien cuando la mayor parte del barrido es fondo y las líneas espectrales ocupan una fracción pequeña del rango.

El offset se resta a toda la señal, y los valores que quedan negativos (por fluctuaciones) se llevan a cero.

8.4 Corrección por la respuesta espectral del PMT
-------------------------------------------------

La sensibilidad del fotomultiplicador depende de la longitud de onda: una misma intensidad de luz produce más o menos señal según la región del espectro. Para compensarlo:

1. Se convierte cada número de onda a longitud de onda: λ [nm] = 10⁷ / ν̄ [cm⁻¹].
2. Se interpola la respuesta R(λ) a partir de respuesta_pmt.csv.
3. Se corrige la señal normalizando a 585,25 nm:

    I_corregida = I_neta · R(585,25 nm) / R(λ)

La normalización hace que la señal corregida quede en unidades comparables con las cuentas ADC netas: en 585,25 nm la corrección vale exactamente 1.

- Los puntos cuya longitud de onda cae fuera del rango de la tabla quedan sin corrección (celdas vacías en el CSV).
- Si no se encuentra respuesta_pmt.csv, el script avisa, guarda la medición sin esta corrección y grafica la señal sin offset.

Formato de respuesta_pmt.csv:

Un CSV con encabezado y dos columnas: longitud de onda en nm y respuesta relativa. Si las columnas se llaman longitud_onda_nm y respuesta_PMT se usan por nombre; si no, se toman las dos primeras columnas en ese orden. No hace falta que esté ordenado.

    longitud_onda_nm,respuesta_PMT
    450.0,62.1
    500.0,55.3
    ...

  Tener en cuenta que dividir por R(λ) amplifica el ruido donde la respuesta del PMT es baja (por encima de ~600 nm para el R1414).

9. ARCHIVOS DE SALIDA
=====================

Cada barrido genera un archivo en la carpeta mediciones/:

    mediciones/medicion_<A>_a_<B>_<AAAAMMDD>_<HHMMSS>.csv

Por ejemplo: medicion_15500_a_17750_20260915_143210.csv. Contiene una fila por cada medición de señal, con las siguientes columnas:

  * tiempo_ms
      Unidad: ms
      Contenido: Instante de la medición (centro de la ventana de promediado), según el reloj del Arduino.
  * POS
      Unidad: cuentas ADC
      Contenido: Posición interpolada de las redes.
  * numero_onda_raw_cm-1
      Unidad: cm⁻¹
      Contenido: Número de onda obtenido directamente de la calibración.
  * numero_onda_cm-1
      Unidad: cm⁻¹
      Contenido: Número de onda tras la corrección de puntos anómalos. Es el eje a usar.
  * longitud_onda_nm
      Unidad: nm
      Contenido: 10⁷ / número de onda.
  * senal_ADC
      Unidad: cuentas ADC
      Contenido: Señal medida, sin procesar.
  * offset_ADC
      Unidad: cuentas ADC
      Contenido: Nivel de base estimado (mismo valor en todas las filas).
  * senal_ADC_sin_offset
      Unidad: cuentas ADC
      Contenido: Señal menos el nivel de base.
  * respuesta_PMT
      Unidad: relativa
      Contenido: Respuesta del PMT interpolada en esa longitud de onda.
  * factor_correccion_PMT
      Unidad: —
      Contenido: R(585,25 nm) / R(λ).
  * senal_ADC_corregida
      Unidad: u.a.
      Contenido: Señal final, corregida por la respuesta del PMT.

El gráfico que aparece al final muestra la señal corregida (o la señal sin offset, si no hubo corrección del PMT) en función del número de onda, con el eje horizontal invertido.

10. PROCEDIMIENTO DE MEDICIÓN PASO A PASO
=========================================

1. Encender el equipo. Alimentar el espectrómetro, la fuente del fotomultiplicador (se usó 1200 V) y el circuito de acondicionamiento. Con la luz de la sala controlada, esperar unos minutos a que se estabilicen.
2. Montar la fuente o la muestra frente a la rendija de entrada y enfocarla sobre ella.
3. Elegir las aperturas de las rendijas según el compromiso buscado: rendijas más cerradas dan mejor resolución pero menos señal.
4. Elegir la velocidad de barrido con el selector del panel frontal.
5. Conectar el Arduino a la PC y ejecutar el script.
6. Verificar la posición con P.
7. Ajustar la ganancia (opcional). Llevar las redes a una zona con señal intensa y, haciendo un barrido corto, comprobar que la señal no sature (que no llegue a 1023 cuentas).
8. Hacer el barrido con B, ingresando A y B.
9. Revisar el gráfico y anotar el nombre del archivo junto con las condiciones de la medición: velocidad, rendijas, tensión del PMT, tiempo de integración y muestra.

11. RECOMENDACIONES DE USO
==========================

- Barrer siempre en el mismo sentido, preferentemente en sentido creciente de número de onda (A < B). El mecanismo de barrido introduce un corrimiento sistemático que depende del sentido del movimiento: con una lámpara de neón se midió una diferencia de ~25 cm⁻¹ entre barridos en sentidos opuestos. Los barridos crecientes mostraron mejor acuerdo con la referencia (~5 cm⁻¹). Como el script primero lleva las redes hasta A, eligiendo A < B la llegada a la zona medida siempre se hace en el mismo sentido.
- Elegir el tiempo de integración según la velocidad de barrido. Durante una ventana de promediado las redes se desplazan velocidad × tiempo. Por ejemplo, a 500 cm⁻¹/min con 100 ms, cada punto abarca ~0,8 cm⁻¹. Ventanas más largas reducen el ruido pero ensanchan las líneas; en la tesis se buscó que cada punto abarcara del orden de 1 cm⁻¹. Para cambiarlo, modificar TIEMPO_INTEGRACION en el script.
- Cuidar la entrada A1. Una tensión mayor a 5 V puede dañar la placa.
- No abrir el Monitor Serie del Arduino IDE mientras corre el script.

12. RECALIBRACIÓN DEL EJE ESPECTRAL
===================================

Si se modifica el acople del potenciómetro, se reemplaza alguna pieza del mecanismo o se detecta un corrimiento sistemático, conviene recalibrar:

1. Identificar las posiciones extremas del barrido y sus números de onda en el contador del panel frontal.
2. Hacer un barrido completo a velocidad constante, registrando la lectura del potenciómetro en función del tiempo.
3. Asignar números de onda interpolando linealmente entre los extremos (el barrido es lineal en número de onda).
4. Ajustar un polinomio de segundo grado POS(u), con u = (ν̄ − ν̄₀)/1000, y reemplazar A_POS, B_POS, C_POS y, si cambian, NUM_ONDA_0, NUM_ONDA_MIN y NUM_ONDA_MAX.
5. Verificar el resultado midiendo una lámpara con líneas de posición conocida (por ejemplo, neón) y comparando con valores tabulados (NIST).

13. SOLUCIÓN DE PROBLEMAS
=========================

  * No se pudo abrir el puerto COM3
      Causa probable: Puerto equivocado, Arduino desconectado o puerto ocupado por otro programa.
      Qué hacer: Revisar PUERTO; cerrar el Monitor Serie del IDE.
  * No se recibió ACK del Arduino
      Causa probable: El firmware no está cargado o la velocidad no coincide.
      Qué hacer: Volver a cargar el firmware; verificar 115200 baudios.
  * El motor gira hacia el lado equivocado y nunca llega
      Causa probable: Sentido de giro invertido respecto del potenciómetro.
      Qué hacer: Cambiar forwardAumentaPosicion a false en el firmware.
  * El motor no se mueve
      Causa probable: Relays sin alimentación, pines mal conectados o selector del panel en una posición sin salida.
      Qué hacer: Revisar conexiones y la caja de velocidades; probar con F/R y S.
  * Un movimiento no termina nunca
      Causa probable: El setpoint queda fuera del recorrido mecánico o el potenciómetro no responde.
      Qué hacer: Cancelar con Ctrl+C; verificar con P que la posición cambie al moverse.
  * No hay suficientes datos para reconstruir el espectro
      Causa probable: Barrido demasiado corto o A y B demasiado cercanos.
      Qué hacer: Aumentar el rango del barrido.
  * La señal está siempre en 1023
      Causa probable: Saturación del ADC.
      Qué hacer: Reducir la ganancia del acondicionamiento, cerrar rendijas o atenuar la fuente.
  * Espectro plano o solo ruido
      Causa probable: Señal por debajo de la sensibilidad, PMT apagado o fuente mal enfocada.
      Qué hacer: Verificar alta tensión, alineación y apertura de rendijas.
  * ADVERTENCIA: no se encontro respuesta_pmt.csv
      Causa probable: El archivo no está en la carpeta de ejecución.
      Qué hacer: Copiarlo junto al script, o usar la columna sin corrección.
  * Celdas vacías en las columnas del PMT
      Causa probable: La longitud de onda cae fuera del rango de la tabla.
      Qué hacer: Es esperable fuera del rango de la curva; usar senal_ADC_sin_offset.

14. LIMITACIONES CONOCIDAS
==========================

- Señales de baja intensidad. En la configuración actual no fue posible registrar espectros Raman ni de fotoluminiscencia: la señal no superó el nivel de ruido. El sistema funciona bien con fuentes intensas, como lámparas de descarga o LEDs.
- Precisión de posicionamiento. La tolerancia de llegada es de ±2 cuentas, del orden de ±30 cm⁻¹. Esto afecta solo a dónde se detienen las redes, no al eje espectral de las mediciones, que se reconstruye a partir de las posiciones efectivamente registradas.
- Medición bloqueante. Mientras el Arduino promedia la señal no lee la posición. Con ventanas largas y velocidades altas, la detención puede demorarse hasta un tiempo de integración y pasarse levemente del setpoint.
- Corrimiento según el sentido de barrido. Ver sección 11.
- Rango de la corrección del PMT. Limitado al rango de la curva incluida en respuesta_pmt.csv.

15. CRÉDITOS
============

Desarrollado por Matías Javier Gaburri como parte de su tesis de Licenciatura en Ciencias Físicas (Facultad de Ciencias Exactas y Naturales, Universidad de Buenos Aires) y por Diego Mirarchi en su pasantía de Iingeniería Electrónica en el Laboratorio de Espectroscopía Vibracional del Departamento de Física de la Materia Condensada, Centro Atómico Constituyentes (CNEA) 

Directora: Dra. Paula Giudici.
