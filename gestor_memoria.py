from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass
class EntradaMemoria:

    etiqueta: str
    contenido: str
    tamano: int
    detalle: str = ""


def cadena_nasm(texto: str) -> str:
    datos = texto.encode("utf-8")
    imprimible = all(32 <= byte <= 126 for byte in datos)
    if imprimible and '"' not in texto and "\\" not in texto:
        return f'db "{texto}", 0'
    partes = [f"0x{byte:02X}" for byte in datos]
    partes.append("0")
    return "db " + ", ".join(partes)


def entero_nasm(valor: object) -> int:
    if isinstance(valor, bool):
        return 1 if valor else 0
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0


class GestorMemoria:

    def __init__(
        self,
        simbolos: Mapping[str, Mapping[str, object]] | None = None,
        direcciones: Mapping[str, str] | None = None,
        bytes_spills: int = 0,
    ) -> None:
        self.simbolos = dict(simbolos or {})
        self.direcciones = dict(direcciones or {})
        self.bytes_spills = bytes_spills
        self.registros_preservados = 12
        self.entradas_data: list[EntradaMemoria] = []
        self.entradas_bss: list[EntradaMemoria] = []
        self.cadenas: dict[str, str] = {}
        self.variables: dict[str, dict[str, object]] = {}

        self._agregar_formatos()
        self._agregar_variables()

    def _agregar_formatos(self) -> None:
        self.entradas_data.extend(
            [
                EntradaMemoria("fmt_int", 'db "%d", 10, 0', 4, "salida entera"),
                EntradaMemoria("fmt_str", 'db "%s", 10, 0', 4, "salida de cadena"),
            ]
        )

    @staticmethod
    def _etiqueta_desde(nombre: str, prefijo: str) -> str:
        limpio = re.sub(r"[^A-Za-z0-9_]", "_", nombre)
        return f"{prefijo}_{limpio}"

    def _agregar_variables(self) -> None:
        def clave(nombre: str) -> tuple[int, str]:
            direccion = self.direcciones.get(nombre, "")
            try:
                return (int(str(direccion), 0), nombre)
            except ValueError:
                return (0xFFFFFFFF, nombre)

        for nombre in sorted(self.simbolos, key=clave):
            info = self.simbolos[nombre]
            tipo = str(info.get("tipo", "num"))
            valor = info.get("valor")
            etiqueta = self._etiqueta_desde(nombre, "v")
            direccion = str(self.direcciones.get(nombre, "sin direccion"))

            if valor is None:
                self.entradas_bss.append(
                    EntradaMemoria(etiqueta, "resb 8", 8, f"{nombre} ({tipo})")
                )
                segmento = "bss"
                offset = len([e for e in self.entradas_bss]) - 1
            elif tipo == "msj" and isinstance(valor, str):
                etiqueta_cadena = self.agregar_cadena(valor)
                self.entradas_data.append(
                    EntradaMemoria(
                        etiqueta, f"dd {etiqueta_cadena}\n    times 4 db 0", 8,
                        f"{nombre} (msj)",
                    )
                )
                segmento = "data"
                offset = -1
            else:
                self.entradas_data.append(
                    EntradaMemoria(
                        etiqueta, f"dd {entero_nasm(valor)}\n    times 4 db 0", 8,
                        f"{nombre} ({tipo})",
                    )
                )
                segmento = "data"
                offset = -1

            self.variables[nombre] = {
                "etiqueta": etiqueta,
                "tipo": tipo,
                "segmento": segmento,
                "direccion_declarada": direccion,
                "indice_bss": offset,
            }

    def agregar_cadena(self, texto: str) -> str:
        """Registra un literal de cadena y devuelve su etiqueta NASM."""
        if texto in self.cadenas:
            return self.cadenas[texto]
        etiqueta = f"cad_{len(self.cadenas) + 1}"
        self.cadenas[texto] = etiqueta
        self.entradas_data.append(
            EntradaMemoria(etiqueta, cadena_nasm(texto), len(texto.encode("utf-8")) + 1, "literal")
        )
        return etiqueta

    def asegurar_variable(self, nombre: str, tipo: str = "num") -> str:
        """Crea una variable global si el cuadruplo la usa sin declaracion previa."""
        if nombre in self.variables:
            return str(self.variables[nombre]["etiqueta"])
        etiqueta = self._etiqueta_desde(nombre, "v")
        self.entradas_bss.append(EntradaMemoria(etiqueta, "resb 8", 8, f"{nombre} ({tipo})"))
        self.variables[nombre] = {
            "etiqueta": etiqueta,
            "tipo": tipo,
            "segmento": "bss",
            "direccion_declarada": "sin direccion",
            "indice_bss": len(self.entradas_bss) - 1,
        }
        return etiqueta

    def etiqueta_variable(self, nombre: str) -> str:
        """Etiqueta NASM de una variable de usuario."""
        return str(self.variables[nombre]["etiqueta"])

    def tipo_variable(self, nombre: str) -> str | None:
        """Tipo declarado de una variable, o None si no existe."""
        info = self.variables.get(nombre)
        return str(info["tipo"]) if info else None

    def _offsets(self) -> dict[str, tuple[str, int, int]]:
        resultado: dict[str, tuple[str, int, int]] = {}
        offset = 0
        for entrada in self.entradas_data:
            resultado[entrada.etiqueta] = ("data", offset, entrada.tamano)
            offset += entrada.tamano
        offset = 0
        for entrada in self.entradas_bss:
            resultado[entrada.etiqueta] = ("bss", offset, entrada.tamano)
            offset += entrada.tamano
        return resultado

    @property
    def tamano_data(self) -> int:
        return sum(entrada.tamano for entrada in self.entradas_data)

    @property
    def tamano_bss(self) -> int:
        return sum(entrada.tamano for entrada in self.entradas_bss)

    @property
    def tamano_frame(self) -> int:
        return self.registros_preservados + self.bytes_spills

    def generar_secciones(self, codigo: Iterable[str]) -> str:
        """Devuelve el archivo .asm completo con los tres segmentos."""
        lineas = [
            "; Numlang -> codigo objeto NASM x86-32 win32",
            "; CRT de MinGW: _main, _printf; sin syscalls de Linux",
            f"; Frame de _main: {self.tamano_frame} bytes",
            "; [ebp+8] parametros; [ebp] viejo ebp; [ebp+4] retorno",
            "; [ebp-4] EBX; [ebp-8] ESI; [ebp-12] EDI",
            f"; [ebp-16..] spills ({self.bytes_spills} bytes)",
            "; Antes de cada call se realinea ESP a 16 bytes y se restaura desde EBP",
            "",
            "section .data",
        ]
        for entrada in self.entradas_data:
            lineas.append(f"{entrada.etiqueta}: {entrada.contenido}")
        lineas.extend(["", "section .bss"])
        for entrada in self.entradas_bss:
            lineas.append(f"{entrada.etiqueta}: {entrada.contenido}")
        lineas.extend(
            [
                "",
                "section .text",
                "global _main",
                "extern _printf",
                "",
            ]
        )
        lineas.extend(codigo)
        return "\n".join(lineas) + "\n"

    def reporte(self) -> str:
        """Reporte legible del mapa de memoria y del marco de pila."""
        offsets = self._offsets()
        lineas = [
            "MAPA DE MEMORIA (NASM x86-32 Windows)",
            f"  section .data : {self.tamano_data} bytes",
        ]
        for entrada in self.entradas_data:
            _, offset, _ = offsets[entrada.etiqueta]
            lineas.append(
                f"    {entrada.etiqueta:<24} offset={offset:<4} "
                f"tam={entrada.tamano:<3} {entrada.detalle}"
            )
        lineas.append(f"  section .bss  : {self.tamano_bss} bytes")
        for entrada in self.entradas_bss:
            _, offset, _ = offsets[entrada.etiqueta]
            lineas.append(
                f"    {entrada.etiqueta:<24} offset={offset:<4} "
                f"tam={entrada.tamano:<3} {entrada.detalle}"
            )
        lineas.extend(
            [
                "",
                "VARIABLES DE USUARIO:",
            ]
        )
        for nombre, info in self.variables.items():
            etiqueta = str(info["etiqueta"])
            segmento, offset, _ = offsets[etiqueta]
            lineas.append(
                f"  {nombre:<12} -> [{segmento}+{offset}] "
                f"direccion_declarada={info['direccion_declarada']}"
            )
        lineas.extend(
            [
                "",
                "MARCO DE PILA DE _main:",
                f"  tamanio total           : {self.tamano_frame} bytes",
                "  [ebp+8 ..]              : parametros (cdecl)",
                "  [ebp]                   : viejo EBP",
                "  [ebp+4]                 : direccion de retorno",
                "  [ebp-4] / -8 / -12      : EBX / ESI / EDI preservados",
                f"  [ebp-16 .. ebp-{15 + self.bytes_spills}] : spills",
                "  Alineacion: ESP se reajusta desde EBP antes de cada call",
            ]
        )
        return "\n".join(lineas)


def redondear_arriba(valor: int, multiplo: int = 16) -> int:
    """Utilidad para calcular padding de alineacion de pila."""
    return int(math.ceil(valor / multiplo) * multiplo)
