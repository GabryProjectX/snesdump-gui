import os
import sys
import serial
import signal
import struct
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial.tools.list_ports

puerto = None
baud = 2000000

comandos = {
    'CTRL': bytes([0]),
    'READSECTION': bytes([1]),
    'WRITESECTION': bytes([2])
}

paises = [
    'Japón (NTSC)', 'EE. UU. (NTSC)', 'Europa, Oceanía, Asia (PAL)', 'Suecia (PAL)',
    'Finlandia (PAL)', 'Dinamarca (PAL)', 'Francia (PAL)', 'Holanda (PAL)',
    'España (PAL)', 'Alemania, Austria, Suiza (PAL)', 'Italia (PAL)',
    'Hong Kong, China (PAL)', 'Indonesia (PAL)', 'Corea (PAL)'
]

def conectar_puerto(event=None):
    nombre_puerto = combobox_puerto.get()
    etiqueta_estado.config(text="Intentando abrir el puerto: " + nombre_puerto, fg="orange")
    try:
        global puerto
        puerto = serial.Serial(nombre_puerto, baud)
        puerto.read(1)
        etiqueta_estado.config(text="Conectado a " + nombre_puerto, fg="green")
        boton_conectar.pack_forget()
        boton_desconectar.pack()
        combobox_puerto.config(state="disabled")
        boton_info_cartucho.config(state="normal")
        boton_volcar_rom.config(state="normal")
        boton_volcar_sram.config(state="normal")
        boton_escribir_sram.config(state="normal")
        
    except (OSError, serial.SerialException) as e:
        messagebox.showerror("Error", "Error al abrir el puerto:" + nombre_puerto)
        etiqueta_estado.config(text="Error: No se pudo abrir el puerto serial", fg="red")

def desconectar_puerto():
    puerto.close()
    etiqueta_estado.config(text="No conectado", fg="red")
    boton_conectar.pack()
    boton_desconectar.pack_forget()
    combobox_puerto.config(state="readonly")
    boton_info_cartucho.config(state="disabled")
    boton_volcar_rom.config(state="disabled")
    boton_volcar_sram.config(state="disabled")
    boton_escribir_sram.config(state="disabled")
   
def mostrar_info_cartucho():
    encabezado = obtener_encabezado()
    if not verificar_encabezado(encabezado):
        messagebox.showerror("Error", "No se pudo leer el encabezado del cartucho!")
        etiqueta_estado.config(text="Error: No se pudo leer el encabezado del cartucho!", fg="red")
        return

    titulo = encabezado[:21].decode('utf-8').strip()
    layout = "HiROM" if (encabezado[21] & 1) else "LoROM"
    tamano_rom = (1 << encabezado[23]) * 1024
    tamano_sram = encabezado[24] * 2048
    codigo_pais = encabezado[25]
    pais = paises[codigo_pais] if codigo_pais < len(paises) else str(codigo_pais)
    version = encabezado[27]
    checksum = (encabezado[30] << 8) | encabezado[31]
    info = "Título: {}\nLayout: {}\nTamaño ROM: {} KB\nTamaño SRAM: {} KB\nPaís: {}\nVersión: {}\nChecksum: 0x{:02X}".format(titulo, layout, tamano_rom, tamano_sram, pais, version, checksum)
    etiqueta_info.config(text=info)

def obtener_encabezado():
    set_ctrl_lines(False, True, False, True)
    puerto.write(comandos['READSECTION'])
    puerto.write(bytes([0]))  # Escribir número de banco
    write_addr(0xffc0)
    write_addr(0xffdf)
    datos = puerto.read(32)
    return bytearray(datos)

def verificar_encabezado(encabezado):
    return not all(v == 0 for v in encabezado)

def escribir_a_archivo(datos, nombre_archivo):
    with open(nombre_archivo, 'wb') as f:
        f.write(datos)

def volcar_rom():
    encabezado = obtener_encabezado()
    if not verificar_encabezado(encabezado):
        messagebox.showerror("Error", "No se pudo leer el encabezado del cartucho!")
        etiqueta_estado.config(text="Error: No se pudo leer el encabezado del cartucho!", fg="red")
        return

    nombre_archivo = filedialog.asksaveasfilename(defaultextension=".smc", filetypes=[("Archivos SMC", "*.smc"), ("Archivos ROM", "*.rom")])
    if nombre_archivo:
        tamano_rom = (1 << encabezado[23]) * 1024
        set_ctrl_lines(False, True, False, True)
        bytes_totales_leidos = 0
        with open(nombre_archivo, 'wb') as f:
            for banco in range((tamano_rom + 0xffff) // 0x10000):
                puerto.write(comandos['READSECTION'])
                puerto.write(bytes([banco]))
                write_addr(0x0 if (encabezado[21] & 1) else 0x8000)
                write_addr(0xffff)
                datos = puerto.read(0x10000)
                f.write(datos)
                bytes_totales_leidos += len(datos)
                etiqueta_estado.config(text="Volcando ROM: {0:,}/{1:,} bytes".format(bytes_totales_leidos, tamano_rom), fg="green")
        etiqueta_estado.config(text="Volcado guardado en " + nombre_archivo, fg="green")

def volcar_sram():
    encabezado = obtener_encabezado()
    if not verificar_encabezado(encabezado):
        messagebox.showerror("Error", "No se pudo leer el encabezado del cartucho!")
        etiqueta_estado.config(text="Error: No se pudo leer el encabezado del cartucho!", fg="red")
        return

    tamano_sram = encabezado[24] * 2048
    if tamano_sram == 0:
        messagebox.showerror("Error", "El juego no tiene SRAM!")
        etiqueta_estado.config(text="Error: El juego no tiene SRAM!", fg="red")
        return

    nombre_archivo = filedialog.asksaveasfilename(defaultextension=".sram", filetypes=[("Archivos SRAM", "*.sram"), ("Todos los archivos", "*.*")])
    if nombre_archivo:
        set_ctrl_lines(False, True, (encabezado[21] & 1), True)
        write_addr(0x6000 if (encabezado[21] & 1) else 0x8000)
        write_addr(0x6000 + tamano_sram - 1)
        datos = puerto.read(tamano_sram)
        escribir_a_archivo(datos, nombre_archivo)
        etiqueta_estado.config(text="Volcado guardado en " + nombre_archivo, fg="green")

def escribir_sram():
    encabezado = obtener_encabezado()
    if not verificar_encabezado(encabezado):
        messagebox.showerror("Error", "No se pudo leer el encabezado del cartucho!")
        etiqueta_estado.config(text="Error: No se pudo leer el encabezado del cartucho!", fg="red")
        return

    tamano_sram = encabezado[24] * 2048
    if tamano_sram == 0:
        messagebox.showerror("Error", "El juego no tiene SRAM!")
        etiqueta_estado.config(text="Error: ¡El juego no tiene SRAM!", fg="red")
        return

    nombre_archivo = filedialog.askopenfilename(filetypes=[("Archivos SRAM", "*.sram"), ("Todos los archivos", "*.*")])
    if nombre_archivo:
        tamano_archivo = os.path.getsize(nombre_archivo)
        if tamano_archivo != tamano_sram:
            messagebox.showerror("Error", "La cantidad de bytes del archivo no coincide con la SRAM del juego!")
            etiqueta_estado.config(text="Error: La cantidad de bytes del archivo no coincide con la SRAM del juego! Archivo: {}, SRAM: {}".format(tamano_archivo, tamano_sram), fg="red")
            return

        set_ctrl_lines(True, False, (encabezado[21] & 1), True)
        write_addr(0x6000 if (encabezado[21] & 1) else 0x8000)
        write_addr(0x6000 + tamano_sram - 1)
        with open(nombre_archivo, 'rb') as f:
            bytes_totales_escritos = 0
            while bytes_totales_escritos < tamano_archivo:
                este_byte = f.read(1)
                puerto.write(este_byte)
                bytes_totales_escritos += 1
                time.sleep(0.001)  # Agregar un pequeño retraso
                etiqueta_estado.config(text="Escribiendo SRAM: {}/{} bytes".format(bytes_totales_escritos, tamano_sram), fg="green")

def set_ctrl_lines(leer, escribir, cartucho, reiniciar):
    valor = (leer << 3) | (escribir << 2) | (cartucho << 1) | reiniciar
    puerto.write(comandos['CTRL'])
    puerto.write(bytes([valor]))

def write_addr(addr):
    puerto.write(bytes([addr >> 8 & 0xff]))
    puerto.write(bytes([addr & 0xff]))

def sigint_handler(signum, frame):
    signal.signal(signal.SIGINT, sigint)
    if puerto is not None:
        puerto.close()
    sys.exit(1)
    signal.signal(signal.SIGINT, sigint_handler) 

if __name__ == '__main__':
    sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, sigint_handler)

    raiz = tk.Tk()
    raiz.title("SnesDump GUI")

    frame_puerto = tk.Frame(raiz)
    frame_puerto.pack(padx=10, pady=10)

    tk.Label(frame_puerto, text="Seleccionar Puerto:").pack()

    combobox_puerto = ttk.Combobox(frame_puerto, state="readonly")
    combobox_puerto.pack()

    puertos_disponibles = [puerto.device for puerto in serial.tools.list_ports.comports()]

    combobox_puerto['values'] = puertos_disponibles

    if puertos_disponibles:
        combobox_puerto.current(0)

    boton_conectar = tk.Button(frame_puerto, text="Conectar", command=conectar_puerto)
    boton_conectar.pack()
    
    boton_desconectar = tk.Button(frame_puerto, text="Desconectar", command=desconectar_puerto)
    boton_desconectar.pack_forget()

    etiqueta_estado = tk.Label(raiz, text="No conectado", fg="red")
    etiqueta_estado.pack(pady=5)

    boton_info_cartucho = tk.Button(raiz, text="Información del Cartucho", command=mostrar_info_cartucho, state="disabled")
    boton_info_cartucho.pack(pady=5)

    etiqueta_info = tk.Label(raiz, text="", fg="blue")
    etiqueta_info.pack(pady=5)

    frame_botones = tk.Frame(raiz)
    frame_botones.pack(pady=10)

    boton_volcar_rom = tk.Button(frame_botones, text="Volcar ROM", command=volcar_rom, state="disabled")
    boton_volcar_rom.pack(side="left", padx=5)

    boton_volcar_sram = tk.Button(frame_botones, text="Volcar SRAM", command=volcar_sram, state="disabled")
    boton_volcar_sram.pack(side="left", padx=5)

    boton_escribir_sram = tk.Button(frame_botones, text="Escribir SRAM", command=escribir_sram, state="disabled")
    boton_escribir_sram.pack(side="left", padx=5)
    
    info = tk.Label(raiz, text="< GUI by @GabryProject | SnesDump by cthill >")
    info.pack()
    
    raiz.mainloop()
