"""Interfaz grafica de Numlang: editor de codigo, cuadruplos, ASM y ejecucion."""

from __future__ import annotations

import queue
import re
import sys
import tempfile
import threading
from pathlib import Path
from typing import Iterable, Mapping

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from analizador_semantico import ErrorNumlang
from asignador_registros import AsignadorRegistros
from generador_objeto import (
    NasmWin32Backend,
    compilar_cuadruplos,
    ensamblar_enlazar_ejecutar,
)
from gestor_memoria import GestorMemoria

def formatear_error_compilacion(error: Exception) -> str:
    if not isinstance(error, ErrorNumlang):
        return f"Error interno: {type(error).__name__}: {error}"
    mensaje = str(error).strip()
    for encabezado in ("Errores semanticos:", "Errores semánticos detectados:"):
        if mensaje.startswith(encabezado):
            partes = [
                parte.strip()
                for parte in re.split(r"[;\n]", mensaje[len(encabezado):])
                if parte.strip()
            ]
            if partes:
                return "\n".join(["Error de compilación", *partes])
            return "Error de compilación"
    return f"Error de compilación\n{mensaje}"


RAIZ = Path(__file__).resolve().parent
DIRECTORIO_BUILD = RAIZ / "build"


def formatear_cuadruplos(cuadruplos: Iterable[Mapping[str, str]]) -> str:
    """Muestra los cuadruplos en forma de tabla de texto."""
    return "\n".join(
        f"{indice:>3}. ({cuad['op']}, {cuad['arg1']}, {cuad['arg2']}, {cuad['res']})"
        for indice, cuad in enumerate(cuadruplos, start=1)
    )


def procesar_codigo(
    codigo: str,
    ejecutar: bool = False,
    optimizar: bool = True,
    ruta_asm: Path | None = None,
) -> dict[str, str]:
    """Compila el codigo de la interfaz y devuelve todo lo que debe mostrar."""
    destino = ruta_asm or (DIRECTORIO_BUILD / "interfaz.asm")

    with tempfile.TemporaryDirectory(prefix="numlang_gui_") as temporal:
        fuente = Path(temporal) / "programa.src"
        with fuente.open("w", encoding="utf-8", newline="\n") as archivo:
            archivo.write(codigo)
        cuadruplos, resultado, analisis = compilar_cuadruplos(fuente, optimizar)

    simbolos = resultado["tabla_simbolos_semantica"]
    direcciones = analisis["tabla_direcciones"]
    asignador = AsignadorRegistros(cuadruplos, simbolos, direcciones)
    gestor = GestorMemoria(simbolos, direcciones, bytes_spills=asignador.bytes_spills)
    asm = NasmWin32Backend().generar(
        cuadruplos,
        {"asignador": asignador, "gestor": gestor, "simbolos": simbolos},
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(asm)

    if ejecutar:
        correcto, salida = ensamblar_enlazar_ejecutar(destino)
        texto_salida = salida if correcto else "No se pudo ejecutar:\n" + salida
    else:
        texto_salida = "(Activa 'Ejecutar .exe' para ver la salida del programa)"

    reporte = asignador.reporte() + "\n\n" + gestor.reporte()
    return {
        "asm": asm,
        "cuadruplos": formatear_cuadruplos(cuadruplos),
        "salida": texto_salida,
        "reporte": reporte,
        "ruta_asm": str(destino),
    }


class AplicacionNumlang(tk.Tk):
    """Ventana principal del compilador Numlang."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Numlang - Compilador y codigo objeto")
        self.geometry("1120x760")
        self.minsize(900, 620)

        self.cola: queue.Queue[tuple[str, object]] = queue.Queue()
        self.botones: list[ttk.Button] = []
        self.ejemplos: dict[str, Path] = {}
        self.variable_optimizar = tk.BooleanVar(value=True)
        self.variable_ejecutar = tk.BooleanVar(value=True)

        self._construir_interfaz()
        self._cargar_ejemplos()
        self.cargar_archivo(RAIZ / "src" / "programa.src")
        self._establecer_estado("Listo. Escribe codigo Numlang y pulsa Compilar.")
        self.after(100, self._procesar_cola)

    def _construir_interfaz(self) -> None:
        principal = ttk.Frame(self, padding=8)
        principal.pack(fill=tk.BOTH, expand=True)

        cabecera = ttk.Frame(principal)
        cabecera.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(cabecera, text="Ejemplo:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self.combo_ejemplos = ttk.Combobox(cabecera, state="readonly", width=26)
        self.combo_ejemplos.pack(side=tk.LEFT, padx=(6, 8))
        self.combo_ejemplos.bind("<<ComboboxSelected>>", self._al_seleccionar_ejemplo)

        paned = ttk.PanedWindow(principal, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        marco_editor = ttk.LabelFrame(paned, text=" Codigo Numlang ", padding=6)
        self.editor = scrolledtext.ScrolledText(
            marco_editor, wrap=tk.WORD, font=("Consolas", 11), height=12
        )
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.bind("<Control-Return>", lambda _evento: self._iniciar_compilacion())

        barra = ttk.Frame(marco_editor)
        barra.pack(fill=tk.X, pady=(6, 0))
        self.boton_compilar = ttk.Button(
            barra, text="Compilar y ejecutar", command=self._iniciar_compilacion
        )
        self.boton_compilar.pack(side=tk.LEFT)
        self.boton_asm = ttk.Button(
            barra, text="Solo generar .asm", command=lambda: self._iniciar_compilacion(False)
        )
        self.boton_asm.pack(side=tk.LEFT, padx=6)
        self.boton_limpiar = ttk.Button(barra, text="Limpiar", command=self._limpiar)
        self.boton_limpiar.pack(side=tk.LEFT)
        self.botones = [self.boton_compilar, self.boton_asm, self.boton_limpiar]

        ttk.Checkbutton(
            barra, text="Optimizar", variable=self.variable_optimizar
        ).pack(side=tk.LEFT, padx=(14, 4))
        ttk.Checkbutton(
            barra, text="Ejecutar .exe", variable=self.variable_ejecutar
        ).pack(side=tk.LEFT)

        marco_resultados = ttk.LabelFrame(paned, text=" Resultados ", padding=6)
        self.notebook = ttk.Notebook(marco_resultados)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.texto_salida = self._agregar_pestana("Salida del programa")
        self.texto_cuadruplos = self._agregar_pestana("Cuadruplos")
        self.texto_asm = self._agregar_pestana("ASM generado")
        self.texto_reportes = self._agregar_pestana("Registros y memoria")

        paned.add(marco_editor, weight=1)
        paned.add(marco_resultados, weight=1)

        self.etiqueta_estado = ttk.Label(principal, text="", anchor=tk.W)
        self.etiqueta_estado.pack(fill=tk.X, pady=(6, 0))

        self._construir_menu()

    def _construir_menu(self) -> None:
        menu = tk.Menu(self)
        self.config(menu=menu)
        menu_archivo = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Archivo", menu=menu_archivo)
        menu_archivo.add_command(label="Abrir .src...", command=self._abrir_archivo)
        menu_archivo.add_command(label="Guardar codigo...", command=self._guardar_archivo)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self.destroy)
        menu_ayuda = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Ayuda", menu=menu_ayuda)
        menu_ayuda.add_command(label="Acerca de", command=self._mostrar_acerca_de)

    def _agregar_pestana(self, titulo: str) -> scrolledtext.ScrolledText:
        marco = ttk.Frame(self.notebook)
        texto = scrolledtext.ScrolledText(
            marco, wrap=tk.NONE, font=("Consolas", 10), state="disabled"
        )
        texto.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(marco, text=titulo)
        return texto

    def _cargar_ejemplos(self) -> None:
        directorio = RAIZ / "src"
        if not directorio.is_dir():
            return
        archivos = sorted(directorio.glob("*.src"), key=lambda ruta: ruta.name)
        self.ejemplos = {archivo.name: archivo for archivo in archivos}
        self.combo_ejemplos["values"] = list(self.ejemplos)

    def cargar_archivo(self, ruta: Path) -> None:
        """Carga un programa Numlang en el editor."""
        try:
            contenido = ruta.read_text(encoding="utf-8")
        except OSError as error:
            messagebox.showerror("Error", f"No se pudo leer {ruta}:\n{error}")
            return
        self._reemplazar_editor(contenido)
        if ruta.name in self.ejemplos:
            self.combo_ejemplos.set(ruta.name)
        self._establecer_estado(f"Archivo cargado: {ruta}")

    def _reemplazar_editor(self, contenido: str) -> None:
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", contenido)

    def _al_seleccionar_ejemplo(self, _evento: object) -> None:
        nombre = self.combo_ejemplos.get()
        if nombre in self.ejemplos:
            self.cargar_archivo(self.ejemplos[nombre])

    @staticmethod
    def _escribir_texto(widget: scrolledtext.ScrolledText, contenido: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", contenido)
        widget.see("1.0")
        widget.configure(state="disabled")

    def _establecer_estado(self, mensaje: str) -> None:
        self.etiqueta_estado.configure(text=mensaje)

    def _limpiar(self) -> None:
        self._reemplazar_editor("")
        for widget in (
            self.texto_salida,
            self.texto_cuadruplos,
            self.texto_asm,
            self.texto_reportes,
        ):
            self._escribir_texto(widget, "")
        self._establecer_estado("Editor y resultados limpios.")

    def _abrir_archivo(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Abrir programa Numlang",
            filetypes=[("Numlang", "*.src"), ("Todos", "*.*")],
        )
        if ruta:
            self.cargar_archivo(Path(ruta))

    def _guardar_archivo(self) -> None:
        ruta = filedialog.asksaveasfilename(
            title="Guardar programa Numlang",
            defaultextension=".src",
            filetypes=[("Numlang", "*.src"), ("Todos", "*.*")],
        )
        if not ruta:
            return
        try:
            with Path(ruta).open("w", encoding="utf-8", newline="\n") as archivo:
                archivo.write(self.editor.get("1.0", tk.END))
        except OSError as error:
            messagebox.showerror("Error", f"No se pudo guardar:\n{error}")
        else:
            self._establecer_estado(f"Codigo guardado: {ruta}")

    @staticmethod
    def _mostrar_acerca_de() -> None:
        messagebox.showinfo(
            "Acerca de",
            "Numlang GUI\nAnalisis semantico + codigo intermedio + optimizacion + NASM win32.",
        )

    def _iniciar_compilacion(self, ejecutar: bool | None = None) -> None:
        if ejecutar is None:
            ejecutar = self.variable_ejecutar.get()
        codigo = self.editor.get("1.0", tk.END)
        if not codigo.strip():
            messagebox.showwarning("Numlang", "Escribe instrucciones Numlang primero.")
            return

        self._escribir_texto(self.texto_salida, "Compilando...")
        self._establecer_estado("Compilando...")
        for boton in self.botones:
            boton.configure(state="disabled")

        hilo = threading.Thread(
            target=self._trabajar,
            args=(codigo, ejecutar, self.variable_optimizar.get()),
            daemon=True,
        )
        hilo.start()

    def _trabajar(self, codigo: str, ejecutar: bool, optimizar: bool) -> None:
        try:
            resultado = procesar_codigo(codigo, ejecutar, optimizar)
        except Exception as error:
            self.cola.put(("error", formatear_error_compilacion(error)))
            return
        self.cola.put(("ok", resultado))

    def _procesar_cola(self) -> None:
        try:
            tipo, datos = self.cola.get_nowait()
        except queue.Empty:
            pass
        else:
            for boton in self.botones:
                boton.configure(state="normal")
            if tipo == "ok":
                resultado = dict(datos)
                self._escribir_texto(self.texto_salida, resultado["salida"])
                self._escribir_texto(self.texto_cuadruplos, resultado["cuadruplos"])
                self._escribir_texto(self.texto_asm, resultado["asm"])
                self._escribir_texto(self.texto_reportes, resultado["reporte"])
                self._establecer_estado(f"Listo | ASM: {resultado['ruta_asm']}")
            else:
                mensaje = str(datos)
                self._escribir_texto(self.texto_salida, mensaje)
                self._establecer_estado("Error de compilacion.")
                messagebox.showerror("Error de compilacion", mensaje[-1200:])
        self.after(100, self._procesar_cola)


def main(argv: list[str] | None = None) -> int:
    """Abre la ventana; acepta un archivo .src opcional como argumento."""
    argumentos = list(sys.argv[1:] if argv is None else argv)
    aplicacion = AplicacionNumlang()
    if argumentos:
        aplicacion.cargar_archivo(Path(argumentos[0]))
    aplicacion.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
