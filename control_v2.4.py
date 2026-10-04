# -*- coding: utf-8 -*-
"""
Control del motor por numero de onda.

- El Arduino recibe setpoints POS mediante el comando T<POS>.
- El Arduino devuelve posiciones por serial con lineas tipo:
      POS:512
      POS:512,ERR:3,SP:520
- Las conversiones POS <-> numero de onda usan la calibracion cuadratica.
- La funcion de barrido va primero a numero de onda A y luego mide desde A hasta B.
  Durante ese segundo movimiento reconstruye el eje espectral,
  corrige el piso del ADC y, si esta disponible respuesta_pmt.csv,
  aplica la correccion relativa de respuesta espectral del PMT.
"""

import csv
import math
import time
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import serial

# -------------------------------------------------------------------
# Configuracion serial
# -------------------------------------------------------------------
PUERTO = "COM3"
BAUDRATE = 115200
TIMEOUT = 0.1
TIEMPO_INTEGRACION = 500
# Carpeta donde se guardan los CSV de barrido.
CARPETA_MEDICIONES = Path("mediciones")

# -------------------------------------------------------------------
# Correcciones de los datos
# -------------------------------------------------------------------
# Curva de respuesta espectral del PMT.
# Se esperan dos columnas: longitud de onda [nm] y respuesta relativa.
ARCHIVO_RESPUESTA_PMT = Path("respuesta_pmt.csv")
LONGITUD_ONDA_REFERENCIA_NM = 585.25

# El piso del ADC se estima como la moda de la señal adquirida.
CORREGIR_OFFSET_ADC = True

# Suavizado/correccion del eje espectral:
# se ajusta numero_onda(t) linealmente y solamente se reemplazan los
# puntos cuyo residuo supera esta tolerancia.
CORREGIR_EJE_ESPECTRAL = True
TOLERANCIA_EJE_CM1 = 5.0


# -------------------------------------------------------------------
# Calibracion cuadratica
# -------------------------------------------------------------------
# POS = A*u^2 + B*u + C
# u = (numero_onda - NUM_ONDA_0) / NUM_ONDA_ESCALA
# numero_onda en cm-1.
# -------------------------------------------------------------------
A_POS = 2.281024
B_POS = 47.194962
C_POS = 190.828864

NUM_ONDA_0 = 11037.0
NUM_ONDA_MIN = 11037.0
NUM_ONDA_MAX = 21997.0
NUM_ONDA_ESCALA = 1000.0

POS_MIN = 0
POS_MAX = 1023


# -------------------------------------------------------------------
# Utilidades numericas y conversiones
# -------------------------------------------------------------------
def limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def pos_float_para_numero_onda(numero_onda):
    """Calcula POS como float para un numero de onda dado."""
    u = (float(numero_onda) - NUM_ONDA_0) / NUM_ONDA_ESCALA
    return A_POS * u**2 + B_POS * u + C_POS


POTE_CAL_MIN = pos_float_para_numero_onda(NUM_ONDA_MIN)
POTE_CAL_MAX = pos_float_para_numero_onda(NUM_ONDA_MAX)


def numero_onda_a_pos(numero_onda):
    """Convierte numero de onda [cm-1] a setpoint POS entero para Arduino."""
    numero_onda = limitar(float(numero_onda), NUM_ONDA_MIN, NUM_ONDA_MAX)
    pos = pos_float_para_numero_onda(numero_onda)
    pos = limitar(pos, POS_MIN, POS_MAX)
    return int(round(pos))


def pos_a_numero_onda(pos):
    """Convierte POS recibido desde Arduino a numero de onda [cm-1]."""
    pos = limitar(float(pos), POTE_CAL_MIN, POTE_CAL_MAX)
    discriminante = B_POS**2 - 4 * A_POS * (C_POS - pos)

    if discriminante < 0:
        discriminante = 0.0

    u = (-B_POS + math.sqrt(discriminante)) / (2 * A_POS)
    numero_onda = NUM_ONDA_0 + NUM_ONDA_ESCALA * u
    return limitar(numero_onda, NUM_ONDA_MIN, NUM_ONDA_MAX)


def numero_onda_valido(numero_onda):
    return NUM_ONDA_MIN <= numero_onda <= NUM_ONDA_MAX



# -------------------------------------------------------------------
# Correccion del eje espectral y de la respuesta del PMT
# -------------------------------------------------------------------
def corregir_eje_espectral(tiempos_ms, numeros_onda, tolerancia=TOLERANCIA_EJE_CM1):
    """
    Ajusta numero de onda vs. tiempo con una recta, aprovechando que el
    barrido mecanico es aproximadamente lineal en numero de onda.

    Solo reemplaza por el valor del ajuste los puntos que se apartan mas
    de 'tolerancia' cm-1. Los demas valores medidos se conservan.
    """
    t = np.asarray(tiempos_ms, dtype=float)
    nu = np.asarray(numeros_onda, dtype=float)

    if len(t) < 2:
        return nu.copy()

    coef = np.polyfit(t, nu, 1)
    nu_ajuste = np.polyval(coef, t)
    residuo = nu - nu_ajuste

    nu_corregido = nu.copy()
    mascara = np.abs(residuo) > tolerancia
    nu_corregido[mascara] = nu_ajuste[mascara]

    return nu_corregido


def estimar_offset_adc(senal):
    """
    Estima el piso del ADC como la moda de los valores adquiridos.
    Como senal_ADC contiene cuentas enteras, bincount permite obtener
    directamente el valor mas frecuente.
    """
    valores = np.rint(np.asarray(senal, dtype=float)).astype(int)

    if len(valores) == 0:
        return 0.0

    minimo = valores.min()
    desplazados = valores - minimo
    moda = np.bincount(desplazados).argmax() + minimo

    return float(moda)


def cargar_respuesta_pmt(ruta=ARCHIVO_RESPUESTA_PMT):
    """
    Lee la curva de respuesta del PMT.

    Acepta un CSV con encabezados. Si existen columnas llamadas
    longitud_onda_nm y respuesta_PMT las usa; en caso contrario usa
    las primeras dos columnas.
    """
    tabla = pd.read_csv(ruta)

    if {"longitud_onda_nm", "respuesta_PMT"}.issubset(tabla.columns):
        lambda_nm = tabla["longitud_onda_nm"].to_numpy(dtype=float)
        respuesta = tabla["respuesta_PMT"].to_numpy(dtype=float)
    else:
        lambda_nm = tabla.iloc[:, 0].to_numpy(dtype=float)
        respuesta = tabla.iloc[:, 1].to_numpy(dtype=float)

    orden = np.argsort(lambda_nm)
    return lambda_nm[orden], respuesta[orden]


def corregir_respuesta_pmt(numeros_onda, senal_sin_offset,
                           ruta=ARCHIVO_RESPUESTA_PMT):
    """
    Corrige la respuesta espectral relativa del PMT.

        lambda[nm] = 1e7 / numero_onda[cm-1]

        I_corr = I_neta * R(585.25 nm) / R(lambda)

    La normalizacion a 585.25 nm mantiene la correccion en unidades
    relativas comparables con las cuentas ADC netas.
    """
    nu = np.asarray(numeros_onda, dtype=float)
    senal = np.asarray(senal_sin_offset, dtype=float)

    lambda_nm = 1.0e7 / nu

    lambda_tabla, respuesta_tabla = cargar_respuesta_pmt(ruta)

    respuesta_interp = np.interp(
        lambda_nm,
        lambda_tabla,
        respuesta_tabla,
        left=np.nan,
        right=np.nan
    )

    respuesta_ref = np.interp(
        LONGITUD_ONDA_REFERENCIA_NM,
        lambda_tabla,
        respuesta_tabla
    )

    factor = np.full_like(respuesta_interp, np.nan, dtype=float)
    validos = np.isfinite(respuesta_interp) & (respuesta_interp > 0)
    factor[validos] = respuesta_ref / respuesta_interp[validos]

    senal_corregida = senal * factor

    return lambda_nm, respuesta_interp, factor, senal_corregida


# -------------------------------------------------------------------
# Comunicacion serial
# -------------------------------------------------------------------
def abrir_serial():
    ser = serial.Serial(PUERTO, BAUDRATE, timeout=TIMEOUT)
    time.sleep(2)
    limpiar_buffer_entrada(ser)
    return ser


def limpiar_buffer_entrada(ser):
    while ser.in_waiting:
        ser.readline()


def enviar(ser, comando):
    ser.write((comando + "\n").encode("ascii"))

    """
    Envía al Arduino el tiempo de integración para la medición.
    Espera la respuesta ACK:I:<valor>.
    """
def configurar_tiempo_integracion(ser, tiempo_ms):

    limpiar_buffer_entrada(ser)
    enviar(ser, f"I{int(tiempo_ms)}")
    inicio = time.monotonic()

    while time.monotonic() - inicio < 2.0:
        linea = leer_linea(ser)
        if not linea:
            continue
        if linea.startswith("ACK:I:"):
            print(f"Arduino: {linea}")
            return True
        print("Arduino:", linea)
    print("No se recibió ACK del Arduino.")
    return False

def leer_linea(ser):
    try:
        return ser.readline().decode(errors="ignore").strip()
    except serial.SerialException:
        raise
    except Exception:
        return ""


"""
 Parsea lineas del tipo:
     POS:512
     POS:512,ERR:3,SP:520

 Retorna un diccionario, por ejemplo:
     {"POS": 512, "ERR": 3, "SP": 520}
 """
def parsear_posicion(linea):
   
    if not linea.upper().startswith("POS:"):
        return None
    datos = {}
    for parte in linea.split(","):
        if ":" not in parte:
            continue
        clave, valor = parte.split(":", 1)
        clave = clave.strip().upper()
        valor = valor.strip()
        try:
            datos[clave] = int(float(valor))
        except ValueError:
            pass
    return datos if "POS" in datos else None

"""
Parsea líneas del tipo:

    SIG:512,T:12345

Devuelve:
    {"SIG":512, "T":12345}
"""
def parsear_senial(linea):
    
    if not linea.upper().startswith("SIG:"):
        return None
    datos = {}
    for parte in linea.split(","):
        if ":" not in parte:
            continue
        clave, valor = parte.split(":", 1)
        try:
            datos[clave.strip().upper()] = int(valor)
        except ValueError:
            pass
    if "SIG" not in datos:
        return None
    return datos

"""Devuelve POS final si la linea es DONE:<POS>; si no, devuelve None."""
def parsear_done(linea):
    
    if not linea.upper().startswith("DONE:"):
        return None
    try:
        return int(float(linea.split(":", 1)[1].strip()))
    except (IndexError, ValueError):
        return None


# -------------------------------------------------------------------
# Operaciones basicas
# -------------------------------------------------------------------
def pedir_posicion(ser):
    
    limpiar_buffer_entrada(ser)
    enviar(ser, "P")
    inicio = time.monotonic()
    while time.monotonic() - inicio < 2.0:
        linea = leer_linea(ser)
        if not linea:
            continue
        datos = parsear_posicion(linea)
        if datos:
            pos = datos["POS"]
            numero_onda = pos_a_numero_onda(pos)
            print(f"POS={pos} | Numero de onda={numero_onda:.1f} cm-1")
            return pos
        print("Arduino:", linea)
    print("No se recibio posicion del Arduino.")
    return None


def imprimir_estado(datos, numero_onda_objetivo=None):
    
    pos = datos.get("POS")
    err = datos.get("ERR")
    sp = datos.get("SP")
    numero_onda = pos_a_numero_onda(pos)
    partes = [f"POS: {pos:4d}",f"Numero de onda: {numero_onda:8.1f} cm-1",]
    if err is not None:
        partes.insert(1, f"ERR: {err:4d}")
    if sp is not None:
        partes.append(f"SP: {sp:4d}")
    if numero_onda_objetivo is not None:
        partes.append(f"Objetivo: {numero_onda_objetivo:.1f} cm-1")
    print(" | ".join(partes))



"""
Mueve el motor a un setpoint POS.

Si registrar_csv no es None, debe ser un csv.writer. En ese caso guarda
una fila por cada POS recibido desde Arduino:
    tiempo_s, POS, numero_onda_cm-1

Como el Arduino entrega datos cada 1 s, tiempo_s se calcula como indice
de muestra: 0, 1, 2, ...
"""

def mover_a_setpoint(ser,setpoint,numero_onda_objetivo=None,registrar_csv=None,eje_x=None,
    eje_y=None,tiempos_signal=None,tiempos_pos=None,posiciones=None):
    
    limpiar_buffer_entrada(ser)
    enviar(ser, f"T{setpoint}")
    print("\nMoviendo. Presiona Ctrl+C para cancelar y frenar.")
    indice_muestra = 0
    ultimo_pos_guardado = None
    ultima_pos = None
    ultimo_numero_onda = None
    try:
        while True:
            linea = leer_linea(ser)
            if not linea:
                continue
            datos_pos = parsear_posicion(linea)
            if datos_pos:
                pos = datos_pos["POS"]
                t = datos_pos.get("T",0)
                if tiempos_pos is not None:
                    tiempos_pos.append(t)
                if posiciones is not None:
                    posiciones.append(pos)
                imprimir_estado(datos_pos, numero_onda_objetivo)
                continue
            pos_final = parsear_done(linea)
            datos_sig = parsear_senial(linea)
            if datos_sig:
               senial = datos_sig["SIG"]
               t = datos_sig["T"]
               if eje_y is not None:
                   eje_y.append(senial)
               if tiempos_signal is not None:
                   tiempos_signal.append(t)
               continue
            if pos_final is not None:
                numero_onda_final = pos_a_numero_onda(pos_final)
                print(
                    "Llegó al setpoint. " f"POS={pos_final} | "
                    f"Numero de onda={numero_onda_final:.1f} cm-1")
                return pos_final
            if linea.upper().startswith("DONE"):
                print("Llegó al setpoint.")
                return None
            print("Arduino:", linea)
    except KeyboardInterrupt:
        enviar(ser, "S")
        print("\nMovimiento cancelado. Motor frenado.")
        return None


def mover_a_numero_onda(ser, numero_onda):
    
    setpoint = numero_onda_a_pos(numero_onda)
    print(f"Numero de onda objetivo: {numero_onda:.1f} cm-1 | "
        f"Setpoint POS={setpoint}")
    return mover_a_setpoint(ser, setpoint, numero_onda_objetivo=numero_onda)


# -------------------------------------------------------------------
# Barrido con guardado CSV
# -------------------------------------------------------------------

"""
  Para cada medicion de señal interpola la posición utilizando
  las posiciones medidas por el potenciómetro y sus tiempos.

  Devuelve:
      posiciones_interpoladas
      numeros_onda
"""
def interpolar_numero_onda_tiempo(tiempos_pos, posiciones, tiempos_sig):
  
    posiciones_interpoladas = []
    numeros_onda = []
    for t in tiempos_sig:
        if t <= tiempos_pos[0]:
            pos_interp = float(posiciones[0])
        elif t >= tiempos_pos[-1]:
            pos_interp = float(posiciones[-1])
        else:   
            for i in range(len(tiempos_pos) - 1):
                t1 = tiempos_pos[i]
                t2 = tiempos_pos[i + 1]
                if t1 <= t <= t2:
                    p1 = posiciones[i]
                    p2 = posiciones[i + 1]
                    fraccion = (t - t1) / (t2 - t1)
                    pos_interp = p1 + fraccion * (p2 - p1)
                    break
        posiciones_interpoladas.append(pos_interp)
        numeros_onda.append(pos_a_numero_onda(pos_interp))
    return posiciones_interpoladas, numeros_onda


def pedir_numero_onda(etiqueta):
  
    entrada = input(f"Numero de onda {etiqueta} [{NUM_ONDA_MIN:.0f}-{NUM_ONDA_MAX:.0f} cm-1]: ").strip()
    try:
        numero_onda = float(entrada)
    except ValueError:
        print("Entrada invalida. Ingrese un numero.")
        return None
    if not numero_onda_valido(numero_onda):
        print(
            "Numero de onda fuera de rango. "
            f"Debe estar entre {NUM_ONDA_MIN:.0f} y {NUM_ONDA_MAX:.0f} cm-1.")
        return None
    return numero_onda


def nombre_archivo_medicion(numero_onda_a, numero_onda_b):
    
    CARPETA_MEDICIONES.mkdir(exist_ok=True)
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    a_txt = f"{numero_onda_a:.0f}"
    b_txt = f"{numero_onda_b:.0f}"
    return CARPETA_MEDICIONES / f"medicion_{a_txt}_a_{b_txt}_{marca_tiempo}.csv"


def medir_desde_a_hasta_b(ser):

    print("\nBarrido con guardado CSV")
    print("Primero se mueve hasta A sin guardar. Luego mide desde A hasta B.")

    numero_onda_a = pedir_numero_onda("A")
    if numero_onda_a is None:
        return

    numero_onda_b = pedir_numero_onda("B")
    if numero_onda_b is None:
        return

    setpoint_a = numero_onda_a_pos(numero_onda_a)
    setpoint_b = numero_onda_a_pos(numero_onda_b)

    print(
        f"\nA = {numero_onda_a:.1f} cm-1 -> POS={setpoint_a}\n"
        f"B = {numero_onda_b:.1f} cm-1 -> POS={setpoint_b}"
    )

    print("\nConfigurando tiempo de integración...")
    if not configurar_tiempo_integracion(ser, TIEMPO_INTEGRACION):
        return

    print("\nYendo primero hasta A...")
    mover_a_setpoint(
        ser,
        setpoint_a,
        numero_onda_objetivo=numero_onda_a
    )

    ruta_csv = nombre_archivo_medicion(numero_onda_a, numero_onda_b)
    print(f"\nMidiendo desde A hasta B. Guardando en: {ruta_csv}")

    senal = []
    tiempos_signal = []
    tiempos_pos = []
    posiciones = []

    mover_a_setpoint(
        ser,
        setpoint_b,
        numero_onda_objetivo=numero_onda_b,
        eje_y=senal,
        tiempos_signal=tiempos_signal,
        tiempos_pos=tiempos_pos,
        posiciones=posiciones
    )

    if len(senal) == 0 or len(tiempos_pos) < 2:
        print("No hay suficientes datos para reconstruir el espectro.")
        return

    # ---------------------------------------------------------------
    # 1) Reconstruccion de posicion y numero de onda
    # ---------------------------------------------------------------
    posiciones_interpoladas, numero_onda_raw = interpolar_numero_onda_tiempo(
        tiempos_pos,
        posiciones,
        tiempos_signal
    )

    numero_onda_raw = np.asarray(numero_onda_raw, dtype=float)

    # Correccion mas reciente del eje:
    # ajuste lineal nu(t) y reemplazo de outliers > tolerancia.
    if CORREGIR_EJE_ESPECTRAL:
        numero_onda = corregir_eje_espectral(
            tiempos_signal,
            numero_onda_raw,
            TOLERANCIA_EJE_CM1
        )
    else:
        numero_onda = numero_onda_raw.copy()

    # ---------------------------------------------------------------
    # 2) Correccion del piso/offset del ADC
    # ---------------------------------------------------------------
    senal_raw = np.asarray(senal, dtype=float)

    if CORREGIR_OFFSET_ADC:
        offset_adc = estimar_offset_adc(senal_raw)
    else:
        offset_adc = 0.0

    senal_sin_offset = senal_raw - offset_adc

    # No se permiten valores negativos despues de quitar el piso.
    senal_sin_offset[senal_sin_offset < 0] = 0.0

    # ---------------------------------------------------------------
    # 3) Correccion por respuesta espectral del PMT
    # ---------------------------------------------------------------
    try:
        (
            longitud_onda_nm,
            respuesta_pmt,
            factor_pmt,
            senal_corregida
        ) = corregir_respuesta_pmt(numero_onda, senal_sin_offset)

        correccion_pmt_disponible = True

    except FileNotFoundError:
        print(
            f"\nADVERTENCIA: no se encontro {ARCHIVO_RESPUESTA_PMT}. "
            "Se guardara la medicion sin correccion espectral del PMT."
        )

        longitud_onda_nm = 1.0e7 / numero_onda
        respuesta_pmt = np.full(len(numero_onda), np.nan)
        factor_pmt = np.ones(len(numero_onda))
        senal_corregida = senal_sin_offset.copy()

        correccion_pmt_disponible = False

    # ---------------------------------------------------------------
    # 4) Guardado
    # ---------------------------------------------------------------
    with ruta_csv.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)

        escritor.writerow([
            "tiempo_ms",
            "POS",
            "numero_onda_raw_cm-1",
            "numero_onda_cm-1",
            "longitud_onda_nm",
            "senal_ADC",
            "offset_ADC",
            "senal_ADC_sin_offset",
            "respuesta_PMT",
            "factor_correccion_PMT",
            "senal_ADC_corregida"
        ])

        for (
            t,
            pos_interp,
            nu_raw,
            nu,
            lam,
            sig_raw,
            sig_neta,
            resp,
            factor,
            sig_corr
        ) in zip(
            tiempos_signal,
            posiciones_interpoladas,
            numero_onda_raw,
            numero_onda,
            longitud_onda_nm,
            senal_raw,
            senal_sin_offset,
            respuesta_pmt,
            factor_pmt,
            senal_corregida
        ):
            escritor.writerow([
                t,
                f"{pos_interp:.6f}",
                f"{nu_raw:.6f}",
                f"{nu:.6f}",
                f"{lam:.6f}",
                f"{sig_raw:.6f}",
                f"{offset_adc:.6f}",
                f"{sig_neta:.6f}",
                f"{resp:.8g}" if np.isfinite(resp) else "",
                f"{factor:.8g}" if np.isfinite(factor) else "",
                f"{sig_corr:.6f}" if np.isfinite(sig_corr) else ""
            ])

    # ---------------------------------------------------------------
    # 5) Grafico
    # ---------------------------------------------------------------
    plt.figure(figsize=(10, 5))

    if correccion_pmt_disponible:
        plt.plot(numero_onda, senal_corregida)
        plt.ylabel("Señal corregida (u.a.)")
    else:
        plt.plot(numero_onda, senal_sin_offset)
        plt.ylabel("Señal ADC sin offset")

    plt.xlabel("Número de onda (cm⁻¹)")
    plt.title(
        f"Espectro - integración {TIEMPO_INTEGRACION} ms"
    )
    plt.grid(True)
    plt.gca().invert_xaxis()
    plt.tight_layout()
    plt.show()

    print(f"\nOffset ADC estimado: {offset_adc:.1f} cuentas")
    print(f"Medicion guardada: {ruta_csv.resolve()}")


# -------------------------------------------------------------------
# Interfaz de usuario
# -------------------------------------------------------------------
def leer_comando_usuario():
    
    entrada = input(f"\nNumero de onda {NUM_ONDA_MIN:.0f}-{NUM_ONDA_MAX:.0f} cm-1 | "
        "P=posicion | B=barrido A->B | S=stop | Q=salir: ").strip().upper()
    if entrada in {"P", "B", "S", "Q"}:
        return entrada
    try:
        numero_onda = float(entrada)
    except ValueError:
        print("Entrada invalida. Ingrese un numero de onda o P/B/S/Q.")
        return None
    if not numero_onda_valido(numero_onda):
        print("Numero de onda fuera de rango. "
            f"Debe estar entre {NUM_ONDA_MIN:.0f} y {NUM_ONDA_MAX:.0f} cm-1.")
        return None
    return numero_onda


def main():
    print("\nControl del motor por numero de onda")
    print("-----------------------------------")
    print(f"Puerto: {PUERTO} | Baudrate: {BAUDRATE}")

    try:
        ser = abrir_serial()
    except serial.SerialException as exc:
        print(f"No se pudo abrir el puerto {PUERTO}: {exc}")
        return

    try:
        while True:
            comando = leer_comando_usuario()

            if comando is None:
                continue

            if comando == "Q":
                enviar(ser, "S")
                break

            if comando == "S":
                enviar(ser, "S")
                print("Motor frenado.")
                continue

            if comando == "P":
                pedir_posicion(ser)
                continue

            if comando == "B":
                medir_desde_a_hasta_b(ser)
                continue

            mover_a_numero_onda(ser, comando)

    finally:
        try:
            enviar(ser, "S")
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
