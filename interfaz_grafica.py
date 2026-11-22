"""Interfaz grafica de Numlang: editor de codigo, cuadruplos, ASM y ejecucion."""

from __future__ import annotations

import queue
import sys
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Iterable, Mapping

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from asignador_registros import AsignadorRegistros
from generador_objeto import (
    NasmWin32Backend,
    compilar_cuadruplos,
    ensamblar_enlazar_ejecutar,
)
from gestor_memoria import GestorMemoria
from diagnosticos_en_vivo import analizar_en_vivo, Diagnostico
from vista_ansi import LienzoAnsi, tiene_dibujo_ansi, sin_codigos_ansi

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
        self._id_validacion: str | None = None
        self._diagnosticos: list[Diagnostico] = []
        self._dibujo_ansi = ""
        self._ventana_dibujo: tk.Toplevel | None = None
        self._lienzo_grande: LienzoAnsi | None = None

        self._construir_interfaz()
        self.editor.bind("<<Modified>>", self._editor_modificado)
        self._cargar_ejemplos()
        self.cargar_archivo(RAIZ / "src" / "programa.src")
        self._establecer_estado("Listo. Escribe codigo Numlang y pulsa Compilar.")
        self._revisar_codigo()
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
        self.editor.tag_configure("error_en_vivo", foreground="#B91C1C", background="#FFF1F2", underline=True)
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

        marco_errores = ttk.LabelFrame(marco_editor, text=" Analizadores: errores en tiempo real (sin compilar) ", padding=4)
        marco_errores.pack(fill=tk.X, pady=(7, 0))
        self.resumen_errores = tk.StringVar(value="Sin errores detectados")
        ttk.Label(marco_errores, textvariable=self.resumen_errores).pack(anchor=tk.W, pady=(0, 3))
        columnas = ("fase", "linea", "detalle")
        self.lista_errores = ttk.Treeview(marco_errores, columns=columnas, show="headings", height=4)
        self.lista_errores.heading("fase", text="Analizador")
        self.lista_errores.heading("linea", text="Linea")
        self.lista_errores.heading("detalle", text="Error y sugerencia")
        self.lista_errores.column("fase", width=105, minwidth=80, stretch=False)
        self.lista_errores.column("linea", width=55, minwidth=50, stretch=False)
        self.lista_errores.column("detalle", width=650, minwidth=250, stretch=True)
        self.lista_errores.pack(fill=tk.X)
        self.lista_errores.bind("<<TreeviewSelect>>", self._ir_al_error)

        marco_resultados = ttk.LabelFrame(paned, text=" Resultados ", padding=6)
        self.notebook = ttk.Notebook(marco_resultados)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.texto_salida = self._agregar_pestana("Salida del programa")
        self.texto_cuadruplos = self._agregar_pestana("Cuadruplos")
        self.texto_asm = self._agregar_pestana("ASM generado")
        self.texto_reportes = self._agregar_pestana("Registros y memoria")

        marco_vista = ttk.Frame(self.notebook)
        fila_vista = ttk.Frame(marco_vista, padding=(8, 5))
        fila_vista.pack(fill=tk.X)
        ttk.Label(fila_vista, text="Salida 2D a color de Numlang (ajustada automaticamente)").pack(side=tk.LEFT)
        ttk.Button(fila_vista, text="Abrir en ventana grande", command=self._abrir_vista_grande).pack(side=tk.RIGHT)
        self.lienzo_2d = LienzoAnsi(marco_vista)
        self.lienzo_2d.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(marco_vista, text="Vista 2D a color")
        self.pestana_2d = marco_vista

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

    def _editor_modificado(self, _evento: object) -> None:
        """Cada cambio reprograma el chequeo (650 ms sin escribir)."""
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        if self._id_validacion is not None:
            self.after_cancel(self._id_validacion)
        self._id_validacion = self.after(650, self._revisar_codigo)

    def _revisar_codigo(self) -> None:
        """Valida el texto actual sin generar .asm ni ejecutar codigo."""
        if self._id_validacion is not None:
            self.after_cancel(self._id_validacion)
            self._id_validacion = None
        codigo = self.editor.get("1.0", "end-1c")
        self._diagnosticos = analizar_en_vivo(codigo)
        self.editor.tag_remove("error_en_vivo", "1.0", tk.END)
        for item in self.lista_errores.get_children():
            self.lista_errores.delete(item)
        for indice, diag in enumerate(self._diagnosticos):
            self.lista_errores.insert("", "end", iid=str(indice), values=(diag.fase, diag.linea, diag.mensaje))
            inicio = f"{diag.linea}.{max(0, diag.columna - 1)}"
            fin = f"{diag.linea}.{max(0, diag.columna - 1) + diag.longitud}"
            self.editor.tag_add("error_en_vivo", inicio, fin)
        if self._diagnosticos:
            fases = {fase: sum(1 for d in self._diagnosticos if d.fase == fase)
                     for fase in ("Lexico", "Sintactico", "Semantico")}
            self.resumen_errores.set(
                "Errores: " + str(len(self._diagnosticos)) + "  |  "
                + "  |  ".join(f"{clave}: {cantidad}" for clave, cantidad in fases.items())
                + "  (haz clic en un error para ir a la linea)"
            )
        else:
            self.resumen_errores.set("Sin errores detectados mientras escribes")

    def _ir_al_error(self, _evento: object) -> None:
        seleccion = self.lista_errores.selection()
        if not seleccion:
            return
        indice = int(seleccion[0])
        if indice >= len(self._diagnosticos):
            return
        diag = self._diagnosticos[indice]
        posicion = f"{diag.linea}.{max(0, diag.columna - 1)}"
        self.editor.mark_set(tk.INSERT, posicion)
        self.editor.see(posicion)
        self.editor.focus_set()

    def _abrir_vista_grande(self) -> None:
        """Abre una ventana independiente para ver el logo COMPLETO y a color."""
        if not self._dibujo_ansi:
            messagebox.showinfo("Vista 2D", "Primero compila y ejecuta un .src con salida ANSI a color.")
            return
        if self._ventana_dibujo is not None and self._ventana_dibujo.winfo_exists():
            self._ventana_dibujo.lift()
            self._ventana_dibujo.focus_force()
            return
        ventana = tk.Toplevel(self)
        ventana.title("Numlang - Dibujo 2D a color")
        ventana.geometry("940x800")
        ventana.minsize(360, 280)
        marco = ttk.Frame(ventana, padding=7)
        marco.pack(fill=tk.BOTH, expand=True)
        ttk.Label(marco, text="Imagen renderizada desde la salida .src (UTF-8 + ANSI TrueColor)").pack(anchor="w", pady=(0, 4))
        lienzo = LienzoAnsi(marco)
        lienzo.pack(fill=tk.BOTH, expand=True)
        lienzo.mostrar(self._dibujo_ansi)
        self._ventana_dibujo = ventana
        self._lienzo_grande = lienzo
        def cerrar() -> None:
            self._ventana_dibujo = None
            self._lienzo_grande = None
            ventana.destroy()
        ventana.protocol("WM_DELETE_WINDOW", cerrar)

    def _limpiar(self) -> None:
        self._dibujo_ansi = ""
        self.lienzo_2d.mostrar("")
        if self._lienzo_grande is not None and self._ventana_dibujo is not None and self._ventana_dibujo.winfo_exists():
            self._lienzo_grande.mostrar("")
        self._reemplazar_editor("")
        for widget in (
            self.texto_salida,
            self.texto_cuadruplos,
            self.texto_asm,
            self.texto_reportes,
        ):
            self._escribir_texto(widget, "")
        self._revisar_codigo()
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
        self._revisar_codigo()
        if self._diagnosticos:
            primera = self._diagnosticos[0]
            self.lista_errores.selection_set("0")
            self.lista_errores.see("0")
            self._establecer_estado(
                f"Compilacion detenida: {len(self._diagnosticos)} error(es). "
                f"Primer error: {primera.fase}, linea {primera.linea}."
            )
            return
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
        except Exception:
            self.cola.put(("error", traceback.format_exc()))
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
                salida = resultado["salida"]
                dibujo = tiene_dibujo_ansi(salida)
                # Evitar que Tk muestre los caracteres de control ANSI como basura.
                self._escribir_texto(self.texto_salida, sin_codigos_ansi(salida))
                if dibujo:
                    self._dibujo_ansi = salida
                    self.lienzo_2d.mostrar(salida)
                    self.notebook.select(self.pestana_2d)
                    self._abrir_vista_grande()
                else:
                    self._dibujo_ansi = ""
                    self.lienzo_2d.mostrar("")
                    if self._ventana_dibujo is not None and self._ventana_dibujo.winfo_exists():
                        self._ventana_dibujo.destroy()
                        self._ventana_dibujo = None
                        self._lienzo_grande = None
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
