"""Asignacion de registros para temporales del codigo intermedio de Numlang.

Registros scratch: EAX, ECX, EDX (caller-saved, no guardan temporales vivos).
Registros asignables: EBX, ESI, EDI (callee-saved, preservados por _main).
ESP y EBP quedan reservados para el marco de pila.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

REGISTROS_SCRATCH = ("eax", "ecx", "edx")
REGISTROS_TEMPORALES = ("ebx", "esi", "edi")
REGISTROS_RESERVADOS = ("esp", "ebp")
PATRON_TEMPORAL = re.compile(r"^t\d+$")


@dataclass
class Asignacion:
    """Ubicacion elegida para un temporal."""

    nombre: str
    inicio: int
    fin: int
    ubicacion: str
    tipo: str
    derramado: bool = False


class AsignadorRegistros:
    """Asigna EBX/ESI/EDI a temporales con linear scan y spill en [ebp-N]."""

    def __init__(
        self,
        cuadruplos: Iterable[Mapping[str, str]],
        simbolos: Mapping[str, Mapping[str, object]] | None = None,
        direcciones: Mapping[str, str] | None = None,
        base_spill: int = 16,
    ) -> None:
        self.cuadruplos = list(cuadruplos)
        self.simbolos = dict(simbolos or {})
        self.direcciones_declaradas = dict(direcciones or {})
        self.base_spill = base_spill
        self.tabla: dict[str, Asignacion] = {}
        self.siguiente_slot = base_spill
        self.slots_libres: list[int] = []
        self._asignar()

    def _intervalos(self) -> dict[str, tuple[int, int]]:
        """Devuelve inicio/fin (indice de cuadruplo) de cada temporal."""
        intervalos: dict[str, tuple[int, int]] = {}
        for indice, cuad in enumerate(self.cuadruplos):
            for campo in ("arg1", "arg2", "res"):
                nombre = str(cuad.get(campo, "-"))
                if not PATRON_TEMPORAL.match(nombre):
                    continue
                anterior = intervalos.get(nombre)
                if anterior is None:
                    intervalos[nombre] = (indice, indice)
                else:
                    intervalos[nombre] = (anterior[0], indice)
        return intervalos

    def _liberar(self, activos: dict[str, Asignacion], indice: int) -> None:
        """Devuelve registros y slots de los temporales que ya murieron."""
        for nombre in list(activos):
            asignacion = activos[nombre]
            if asignacion.fin >= indice:
                continue
            if asignacion.tipo == "registro":
                self.registros_libres.append(asignacion.ubicacion)
            else:
                offset = int(asignacion.ubicacion[5:-1])
                self.slots_libres.append(offset)
            del activos[nombre]

    def _asignar(self) -> None:
        self.registros_libres = list(REGISTROS_TEMPORALES)
        activos: dict[str, Asignacion] = {}

        for nombre, (inicio, fin) in sorted(
            self._intervalos().items(), key=lambda item: (item[1][0], item[1][1])
        ):
            self._liberar(activos, inicio)

            if self.registros_libres:
                registro = self.registros_libres.pop(0)
                asignacion = Asignacion(nombre, inicio, fin, registro, "registro")
            else:
                if self.slots_libres:
                    offset = self.slots_libres.pop(0)
                else:
                    offset = self.siguiente_slot
                    self.siguiente_slot += 4
                asignacion = Asignacion(
                    nombre, inicio, fin, f"[ebp-{offset}]", "memoria", True
                )

            activos[nombre] = asignacion
            self.tabla[nombre] = asignacion

    def tabla_asignacion(self) -> dict[str, str]:
        """Mapa nombre -> registro o direccion de memoria listo para mostrar."""
        resultado = {
            nombre: (
                asignacion.ubicacion.upper()
                if asignacion.tipo == "registro"
                else asignacion.ubicacion
            )
            for nombre, asignacion in self.tabla.items()
        }
        for nombre in self.simbolos:
            direccion = self.direcciones_declaradas.get(nombre)
            resultado[nombre] = (
                f"memoria global ({direccion})" if direccion else "memoria global"
            )
        return resultado

    def ubicacion_asm(self, nombre: str) -> str | None:
        """Devuelve el operando NASM de un temporal, o None si no es temporal."""
        asignacion = self.tabla.get(nombre)
        return asignacion.ubicacion if asignacion else None

    @property
    def bytes_spills(self) -> int:
        """Bytes reservados en el marco de pila para temporales derramados."""
        return max(0, self.siguiente_slot - self.base_spill)

    @property
    def registros_usados(self) -> list[str]:
        """Registros callee-saved que deben preservarse en el prologo."""
        usados = {
            a.ubicacion for a in self.tabla.values() if a.tipo == "registro"
        }
        return [r for r in REGISTROS_TEMPORALES if r in usados]

    def reporte(self) -> str:
        """Reporte legible de la asignacion de registros y memoria."""
        lineas = [
            "MAPA DE REGISTROS (NASM x86-32 Windows)",
            "  Scratch (caller-saved): " + ", ".join(r.upper() for r in REGISTROS_SCRATCH),
            "  Asignables (callee-saved): " + ", ".join(r.upper() for r in REGISTROS_TEMPORALES),
            "  Reservados: " + ", ".join(r.upper() for r in REGISTROS_RESERVADOS),
            "",
            "TEMPORALES:",
        ]
        if not self.tabla:
            lineas.append("  (ninguno)")
        for nombre, a in self.tabla.items():
            estado = "spill" if a.derramado else "registro"
            destino = a.ubicacion.upper() if a.tipo == "registro" else a.ubicacion
            lineas.append(
                f"  {nombre:<6} -> {destino:<10} [{a.inicio}..{a.fin}] {estado}"
            )
        lineas.extend(
            [
                "",
                "VARIABLES DE USUARIO (siempre en memoria):",
            ]
        )
        if not self.simbolos:
            lineas.append("  (ninguna)")
        for nombre, info in self.simbolos.items():
            direccion = self.direcciones_declaradas.get(nombre, "sin direccion")
            lineas.append(
                f"  {nombre:<12} tipo={info.get('tipo', '?'):<4} "
                f"direccion_declarada={direccion}"
            )
        lineas.append(f"\nBYTES DE SPILL RESERVADOS: {self.bytes_spills}")
        return "\n".join(lineas)
