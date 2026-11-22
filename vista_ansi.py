"""Interpreta colores ANSI TrueColor y bloques de terminal sin dependencias externas.

La salida de Numlang es texto UTF-8 y codigos ANSI. Tkinter no interpreta
esos codigos por si solo, asi que esta vista los dibuja como pixeles 2D.
"""

from __future__ import annotations

import re
import tkinter as tk

PATRON_SGR = re.compile(r"\x1b\[([0-9;]*)m")
BLOQUES = {"█", "▀", "▄"}
NEGRO = "#000000"
BLANCO = "#FFFFFF"


def tiene_dibujo_ansi(texto: str) -> bool:
    """Detecta la salida a color de un programa .src (no texto comun)."""
    return "\x1b[" in texto and any(caracter in texto for caracter in BLOQUES)


def sin_codigos_ansi(texto: str) -> str:
    """Convierte secuencias ANSI a texto legible en un cuadro sin soporte ANSI."""
    return PATRON_SGR.sub("", texto)


def _hexadecimal(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _actualizar_colores(codigos: str, fg: str, bg: str) -> tuple[str, str]:
    valores = [int(item) for item in codigos.split(";") if item] if codigos else [0]
    i = 0
    while i < len(valores):
        n = valores[i]
        if n == 0:
            fg, bg = BLANCO, NEGRO
        elif n == 39:
            fg = BLANCO
        elif n == 49:
            bg = NEGRO
        elif n in (38, 48) and i + 4 < len(valores) and valores[i + 1] == 2:
            rgb = _hexadecimal(*valores[i + 2:i + 5])
            if n == 38:
                fg = rgb
            else:
                bg = rgb
            i += 4
        i += 1
    return fg, bg


def convertir_a_celdas(texto: str) -> list[list[tuple[str, str]]]:
    """Cada caracter produce dos medios pixeles: (color superior, inferior)."""
    filas = []
    fg, bg = BLANCO, NEGRO
    for linea in texto.splitlines():
        celdas: list[tuple[str, str]] = []
        ultimo = 0
        for secuencia in PATRON_SGR.finditer(linea):
            for caracter in linea[ultimo:secuencia.start()]:
                celdas.append(_colores_de_caracter(caracter, fg, bg))
            fg, bg = _actualizar_colores(secuencia.group(1), fg, bg)
            ultimo = secuencia.end()
        for caracter in linea[ultimo:]:
            celdas.append(_colores_de_caracter(caracter, fg, bg))
        filas.append(celdas)
    # La salida puede terminar con un salto de linea; no es un pixel extra.
    return filas


def _colores_de_caracter(caracter: str, fg: str, bg: str) -> tuple[str, str]:
    if caracter == "▀":
        return fg, bg
    if caracter == "▄":
        return bg, fg
    if caracter == "█":
        return fg, fg
    if caracter == " ":
        return bg, bg
    # Cualquier caracter visible en el dibujo se trata como pixel en primer plano.
    return fg, fg


class LienzoAnsi(tk.Canvas):
    """Muestra el dibujo completo, centrado y escalado sin recortar su contenido."""

    def __init__(self, master, **kwargs):
        super().__init__(master, background=NEGRO, highlightthickness=0, **kwargs)
        self._celdas: list[list[tuple[str, str]]] = []
        self._pendiente = None
        self.bind("<Configure>", self._al_redimensionar)

    def mostrar(self, texto: str) -> None:
        self._celdas = convertir_a_celdas(texto)
        self._redibujar_pronto()

    def _al_redimensionar(self, _evento) -> None:
        self._redibujar_pronto()

    def _redibujar_pronto(self) -> None:
        if self._pendiente is not None:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after_idle(self._dibujar)

    def _dibujar(self) -> None:
        self._pendiente = None
        self.delete("all")
        if not self._celdas:
            self.create_text(
                self.winfo_width() / 2, self.winfo_height() / 2,
                text="Compila un .src con salida ANSI a color para verla aqui.",
                fill="#bdbdbd", font=("Segoe UI", 11), anchor="center"
            )
            return
        columnas = max(map(len, self._celdas))
        filas = len(self._celdas)
        if not columnas or not filas:
            return
        ancho = max(1, self.winfo_width())
        alto = max(1, self.winfo_height())
        # Un caracter de terminal tiene dos medios bloques cuadrados.
        escala = max(0.1, min((ancho - 18) / columnas, (alto - 18) / (filas * 2)))
        x0 = (ancho - columnas * escala) / 2
        y0 = (alto - filas * 2 * escala) / 2
        # Dibujar tramos contiguos del mismo color reduce el numero de objetos.
        for y, fila in enumerate(self._celdas):
            for mitad in (0, 1):
                anterior = None
                inicio = 0
                for x in range(len(fila) + 1):
                    actual = fila[x][mitad] if x < len(fila) else None
                    if actual != anterior:
                        if anterior and anterior != NEGRO:
                            self.create_rectangle(
                                x0 + inicio * escala,
                                y0 + (y * 2 + mitad) * escala,
                                x0 + x * escala + 0.2,
                                y0 + (y * 2 + mitad + 1) * escala + 0.2,
                                fill=anterior, outline="", tags="pixel",
                            )
                        anterior = actual
                        inicio = x
