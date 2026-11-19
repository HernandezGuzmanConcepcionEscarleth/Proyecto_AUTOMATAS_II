"""Generacion de codigo objeto NASM x86-32 para Windows desde cuadruplos Numlang."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Mapping

from analizador_semantico import analizar_codigo, ErrorNumlang
from asignador_registros import AsignadorRegistros
from generador_intermedio import GeneradorCodigoIntermedio
from gestor_memoria import GestorMemoria, entero_nasm
from motor_optimizacion import MotorOptimizacion

REGISTROS_SCRATCH = ("eax", "ecx", "edx")
PATRON_NUMERO = re.compile(r"^-?\d+(?:\.\d+)?$")

OPERADORES_BASICOS = {"+", "-", "*"}
OPERADORES_DIVISION = {"/", "%", "residuo_de"}
OPERADORES_RELACIONALES = {
    "<": "setl",
    ">": "setg",
    "<=": "setle",
    ">=": "setge",
    "==": "sete",
    "!=": "setne",
    "igual_a": "sete",
    "diferente_de": "setne",
    "menor_que": "setl",
    "mayor_que": "setg",
}
OPERADORES_LOGICOS = {"y", "o"}
OPERADORES_POTENCIA = {"elevado_a", "**"}


def texto_entre_comillas(valor: str) -> str | None:
    """Extrae el contenido de un literal de cadena de Numlang."""
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
        return valor[1:-1]
    return None


def ascii_seguro(texto: object) -> str:
    """Deja solo ASCII para comentarios del .asm (NASM no acepta BOM ni acentos)."""
    limpio = str(texto).replace("\r", " ").replace("\n", " ")
    return "".join(caracter if 32 <= ord(caracter) <= 126 else "?" for caracter in limpio)


def sanitizar_etiqueta(nombre: str) -> str:
    """Convierte un nombre de etiqueta de Numlang a un identificador NASM valido."""
    return re.sub(r"[^A-Za-z0-9_]", "_", nombre)


class TargetBackend(ABC):
    """Interfaz para generadores de codigo objeto (solo NASM win32 implementado)."""

    nombre: str = "base"
    extension: str = ".asm"

    @abstractmethod
    def generar(
        self,
        cuadruplos: list[dict[str, str]],
        contexto: Mapping[str, object],
    ) -> str:
        """Devuelve el codigo objeto como texto."""


class NasmWin32Backend(TargetBackend):
    """Traduce cuadruplos optimizados a NASM x86-32 con CRT de MinGW."""

    nombre = "nasm-win32"
    extension = ".asm"

    def __init__(self) -> None:
        self.codigo: list[str] = []
        self.asignador: AsignadorRegistros | None = None
        self.gestor: GestorMemoria | None = None
        self.tipos: dict[str, str] = {}
        self.etiquetas: dict[str, str] = {}
        self.parametros_pendientes: list[str] = []
        self.contador_local = 0

    def generar(
        self,
        cuadruplos: list[dict[str, str]],
        contexto: Mapping[str, object],
    ) -> str:
        self.codigo = []
        self.parametros_pendientes = []
        self.tipos = {}
        self.asignador = contexto["asignador"]
        self.gestor = contexto["gestor"]

        simbolos = contexto.get("simbolos", {})
        for nombre, info in dict(simbolos).items():
            self.tipos[nombre] = str(dict(info).get("tipo", "num"))

        self._registrar_etiquetas(cuadruplos)
        self._registrar_cadenas_y_tipos(cuadruplos)
        self._emitir_prologo()

        for cuad in cuadruplos:
            self.codigo.append(self._comentario(cuad))
            self._traducir(cuad)

        self.codigo.append("    mov eax, 0")
        self._emitir_epilogo()
        return self.gestor.generar_secciones(self.codigo)

    def _nueva_etiqueta_local(self, base: str) -> str:
        self.contador_local += 1
        return f".L_{base}_{self.contador_local}"

    def _registrar_etiquetas(self, cuadruplos: Iterable[dict[str, str]]) -> None:
        for cuad in cuadruplos:
            op = cuad["op"]
            if op in ("etiqueta", "goto", "if_false") and cuad["res"] != "-":
                nombre = cuad["res"]
                if nombre not in self.etiquetas:
                    self.etiquetas[nombre] = f"L_{sanitizar_etiqueta(nombre)}"
            if op == "llamar" and cuad["arg1"] != "-":
                nombre = cuad["arg1"]
                if nombre not in self.etiquetas:
                    destino = f"func_{nombre}"
                    self.etiquetas[nombre] = self.etiquetas.get(
                        destino, f"L_{sanitizar_etiqueta(nombre)}"
                    )

    def _registrar_cadenas_y_tipos(self, cuadruplos: Iterable[dict[str, str]]) -> None:
        for cuad in cuadruplos:
            op, arg1, arg2, res = cuad["op"], cuad["arg1"], cuad["arg2"], cuad["res"]
            for valor in (arg1, arg2):
                texto = texto_entre_comillas(valor)
                if texto is not None:
                    self.gestor.agregar_cadena(texto)
                    self.tipos[valor] = "msj"
            if valor_es_booleano(arg1):
                self.tipos[arg1] = "bool"
            if valor_es_booleano(arg2):
                self.tipos[arg2] = "bool"

            if op == "=" and res != "-":
                self.tipos[res] = self.tipos.get(arg1, "num")
            elif op in OPERADORES_RELACIONALES or op in OPERADORES_LOGICOS:
                self.tipos[res] = "num"
            elif op in ("neg", "no") and res != "-":
                self.tipos[res] = "num"
            elif op in OPERADORES_BASICOS | OPERADORES_DIVISION | OPERADORES_POTENCIA:
                self.tipos[res] = "num"
            elif op == "llamar" and res != "-":
                self.tipos[res] = "num"

    @staticmethod
    def _comentario(cuad: Mapping[str, str]) -> str:
        campos = [cuad.get(clave, "-") for clave in ("op", "arg1", "arg2", "res")]
        return "    ; (" + ", ".join(ascii_seguro(campo) for campo in campos) + ")"

    def _emitir(self, instruccion: str) -> None:
        self.codigo.append("    " + instruccion)

    def _emitir_prologo(self) -> None:
        self.codigo.append("_main:")
        self._emitir("; --- prologo de _main ---")
        self._emitir("push ebp")
        self._emitir("mov ebp, esp")
        self._emitir("push ebx")
        self._emitir("push esi")
        self._emitir("push edi")
        if self.gestor.bytes_spills:
            self._emitir(f"sub esp, {self.gestor.bytes_spills}")
        self._emitir("")

    def _emitir_epilogo(self) -> None:
        self._emitir("")
        self._emitir("; --- epilogo de _main ---")
        self._emitir("mov esp, ebp")
        self._emitir("sub esp, 12")
        self._emitir("pop edi")
        self._emitir("pop esi")
        self._emitir("pop ebx")
        self._emitir("pop ebp")
        self._emitir("ret")

    def _operando(self, valor: str) -> str:
        if valor in REGISTROS_SCRATCH or valor in ("ebx", "esi", "edi"):
            return valor
        if valor in self.asignador.tabla:
            return self.asignador.ubicacion_asm(valor)
        texto = texto_entre_comillas(valor)
        if texto is not None:
            return self.gestor.agregar_cadena(texto)
        if valor_es_booleano(valor):
            return "1" if valor == "verdadero" else "0"
        if PATRON_NUMERO.match(valor):
            return str(entero_nasm(valor))
        if valor in self.gestor.variables:
            return f"[{self.gestor.etiqueta_variable(valor)}]"
        return f"[{self.gestor.asegurar_variable(valor)}]"

    def _destino(self, nombre: str) -> str | None:
        if nombre == "-":
            return None
        if nombre in self.asignador.tabla:
            return self.asignador.ubicacion_asm(nombre)
        return f"[{self.gestor.asegurar_variable(nombre)}]"

    def _cargar(self, registro: str, valor: str) -> None:
        self._emitir(f"mov {registro}, {self._operando(valor)}")

    def _guardar(self, nombre: str, registro: str = "eax") -> None:
        destino = self._destino(nombre)
        if destino is not None:
            self._emitir(f"mov {destino}, {registro}")

    def _empujar(self, valor: str) -> None:
        fuente = self._operando(valor)
        if fuente in REGISTROS_SCRATCH or fuente in ("ebx", "esi", "edi"):
            self._emitir(f"push {fuente}")
        else:
            self._emitir(f"push dword {fuente}")

    def _alinear_para_call(self, numero_argumentos: int) -> None:
        padding = (16 - (numero_argumentos * 4) % 16) % 16
        self._emitir("; alineacion de pila: se reconstruye desde EBP")
        self._emitir("mov esp, ebp")
        self._emitir(f"sub esp, {self.gestor.tamano_frame}")
        self._emitir("and esp, -16")
        if padding:
            self._emitir(f"sub esp, {padding}")

    def _restaurar_tras_call(self) -> None:
        self._emitir("; llamador limpia argumentos cdecl")
        self._emitir("mov esp, ebp")
        self._emitir(f"sub esp, {self.gestor.tamano_frame}")

    def _formato_para(self, valor: str) -> str:
        return "fmt_str" if self.tipos.get(valor) == "msj" or texto_entre_comillas(valor) else "fmt_int"

    def _traducir(self, cuad: Mapping[str, str]) -> None:
        op = cuad["op"]
        arg1, arg2, res = cuad["arg1"], cuad["arg2"], cuad["res"]

        if op == "=":
            self._cargar("eax", arg1)
            self._guardar(res)
        elif op in OPERADORES_BASICOS:
            self._traducir_aritmetica(op, arg1, arg2, res)
        elif op in OPERADORES_DIVISION:
            self._traducir_division(op, arg1, arg2, res)
        elif op in OPERADORES_RELACIONALES:
            self._cargar("eax", arg1)
            self._emitir(f"cmp eax, {self._operando(arg2)}")
            self._emitir(OPERADORES_RELACIONALES[op] + " al")
            self._emitir("movzx eax, al")
            self._guardar(res)
        elif op in OPERADORES_LOGICOS:
            self._traducir_logico(op, arg1, arg2, res)
        elif op == "no":
            self._cargar("eax", arg1)
            self._emitir("test eax, eax")
            self._emitir("setz al")
            self._emitir("movzx eax, al")
            self._guardar(res)
        elif op == "neg":
            self._cargar("eax", arg1)
            self._emitir("neg eax")
            self._guardar(res)
        elif op in OPERADORES_POTENCIA:
            self._traducir_potencia(arg1, arg2, res)
        elif op == "etiqueta":
            self.codigo[-1] = "    ; (" + ", ".join(
                ascii_seguro(cuad.get(clave, "-")) for clave in ("op", "arg1", "arg2", "res")
            ) + ")"
            self.codigo.append(f"{self.etiquetas[res]}:")
        elif op == "goto":
            self._emitir(f"jmp {self.etiquetas[res]}")
        elif op == "if_false":
            self._cargar("eax", arg1)
            self._emitir("test eax, eax")
            self._emitir(f"jz {self.etiquetas[res]}")
        elif op == "mostrar":
            self._alinear_para_call(2)
            self._empujar(arg1)
            self._emitir(f"push dword {self._formato_para(arg1)}")
            self._emitir("call _printf")
            self._restaurar_tras_call()
        elif op == "param":
            self.parametros_pendientes.append(arg1)
        elif op == "llamar":
            self._traducir_llamada(arg1, arg2, res)
        elif op == "retornar":
            self._cargar("eax", arg1)
            self._emitir_epilogo()
        elif op in ("campo_estructura", "param_recibir"):
            self._emitir("; operacion resuelta en tiempo de compilacion")
        else:
            raise ErrorNumlang(f"Operador no soportado por el backend NASM: {op}")

    def _traducir_aritmetica(self, op: str, arg1: str, arg2: str, res: str) -> None:
        self._cargar("eax", arg1)
        fuente = self._operando(arg2)
        if op == "+":
            self._emitir(f"add eax, {fuente}")
        elif op == "-":
            self._emitir(f"sub eax, {fuente}")
        else:
            self._emitir(f"imul eax, {fuente}")
        self._guardar(res)

    def _traducir_division(self, op: str, arg1: str, arg2: str, res: str) -> None:
        self._cargar("eax", arg1)
        self._emitir("cdq")
        self._cargar("ecx", arg2)
        self._emitir("idiv ecx")
        if op in ("%", "residuo_de"):
            self._emitir("mov eax, edx")
        self._guardar(res)

    def _traducir_logico(self, op: str, arg1: str, arg2: str, res: str) -> None:
        self._cargar("eax", arg1)
        self._emitir("test eax, eax")
        self._emitir("setne al")
        self._emitir("movzx eax, al")
        self._cargar("ecx", arg2)
        self._emitir("test ecx, ecx")
        self._emitir("setne cl")
        self._emitir("movzx ecx, cl")
        self._emitir("and al, cl" if op == "y" else "or al, cl")
        self._emitir("movzx eax, al")
        self._guardar(res)

    def _traducir_potencia(self, arg1: str, arg2: str, res: str) -> None:
        self._cargar("eax", arg1)
        self._cargar("ecx", arg2)
        self._emitir("mov edx, 1")
        etiqueta = self._nueva_etiqueta_local("pow")
        fin = self._nueva_etiqueta_local("pow_fin")
        self.codigo.append(f"{etiqueta}:")
        self._emitir("test ecx, ecx")
        self._emitir(f"jle {fin}")
        self._emitir("imul edx, eax")
        self._emitir("dec ecx")
        self._emitir(f"jmp {etiqueta}")
        self.codigo.append(f"{fin}:")
        self._emitir("mov eax, edx")
        self._guardar(res)

    def _traducir_llamada(self, nombre: str, numero_argumentos: str, res: str) -> None:
        cantidad = entero_nasm(numero_argumentos)
        argumentos = self.parametros_pendientes[-cantidad:] if cantidad else []
        self.parametros_pendientes = []
        self._alinear_para_call(len(argumentos))
        for argumento in reversed(argumentos):
            self._empujar(argumento)
        destino = self.etiquetas.get(nombre, f"L_{sanitizar_etiqueta(nombre)}")
        self._emitir(f"call {destino}")
        self._restaurar_tras_call()
        self._guardar(res)


def valor_es_booleano(valor: str) -> bool:
    """Reconoce los literales booleanos de Numlang."""
    return valor in ("verdadero", "falso", "True", "False")


def localizar_herramienta(nombre: str) -> Path | None:
    """Busca una herramienta con shutil.which y rutas tipicas de Windows."""
    encontrado = shutil.which(nombre)
    if encontrado:
        return Path(encontrado)

    candidatos: list[Path] = []
    if nombre.lower() == "nasm":
        program_files = Path(os.environ.get("ProgramFiles", "C:") + os.sep)
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:") + os.sep)
        local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        candidatos.extend(
            [
                program_files / "NASM" / "nasm.exe",
                program_files_x86 / "NASM" / "nasm.exe",
                program_files_x86 / "SASM" / "NASM" / "nasm.exe",
                Path("C:") / "nasm" / "nasm.exe",
                local_appdata / "Programs" / "NASM" / "nasm.exe",
                Path.home() / "scoop" / "apps" / "nasm" / "current" / "nasm.exe",
            ]
        )
        paquetes = local_appdata / "Microsoft" / "WinGet" / "Packages"
        if paquetes.is_dir():
            candidatos.extend(sorted(paquetes.rglob("nasm.exe")))

    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


def citar_ruta(ruta: Path) -> str:
    """Cita una ruta de Windows si contiene espacios."""
    texto = str(ruta)
    return f'"{texto}"' if " " in texto else texto


def comandos_manuales(asm: Path, obj: Path, exe: Path) -> list[str]:
    """Comandos Windows equivalentes a los que ejecuta --ejecutar."""
    return [
        f"nasm -f win32 {citar_ruta(asm)} -o {citar_ruta(obj)}",
        f"gcc -m32 {citar_ruta(obj)} -o {citar_ruta(exe)}",
        citar_ruta(exe),
    ]


def ensamblar_enlazar_ejecutar(asm: Path) -> tuple[bool, str]:
    """Ensambla con NASM, enlaza con gcc -m32 y ejecuta el .exe resultante."""
    nasm = localizar_herramienta("nasm")
    gcc = localizar_herramienta("gcc")
    obj = asm.with_suffix(".obj")
    exe = asm.with_suffix(".exe")

    if nasm is None or gcc is None:
        faltantes = []
        if nasm is None:
            faltantes.append("nasm")
        if gcc is None:
            faltantes.append("gcc (MinGW con soporte -m32)")
        lineas = ["Herramientas no encontradas: " + ", ".join(faltantes)]
        lineas.append("Instala NASM y MinGW-w64 i686 (gcc -m32), o ejecuta manualmente:")
        lineas.extend("  " + comando for comando in comandos_manuales(asm, obj, exe))
        return False, "\n".join(lineas)

    asm.parent.mkdir(parents=True, exist_ok=True)
    pasos = [
        [str(nasm), "-f", "win32", str(asm), "-o", str(obj)],
        [str(gcc), "-m32", str(obj), "-o", str(exe)],
    ]
    for paso in pasos:
        resultado = subprocess.run(paso, capture_output=True, text=True, shell=False)
        if resultado.returncode != 0:
            return False, "Fallo al ejecutar: " + " ".join(paso) + "\n" + resultado.stderr.strip()

    resultado = subprocess.run([str(exe)], capture_output=True, text=True, shell=False)
    salida = resultado.stdout.replace("\r\n", "\n")
    if resultado.stderr:
        salida += "\n" + resultado.stderr.replace("\r\n", "\n")
    return resultado.returncode == 0, salida.rstrip("\n")


def compilar_cuadruplos(ruta: Path, optimizar: bool) -> tuple[list[dict[str, str]], dict, dict]:
    """Ejecuta analisis, generacion intermedia y optimizacion."""
    codigo = ruta.read_text(encoding="utf-8")
    analisis = analizar_codigo(codigo)
    if not analisis["valido"]:
        raise ErrorNumlang("Errores semanticos: " + "; ".join(analisis["errores"]))

    generador = GeneradorCodigoIntermedio()
    resultado = generador.compilar_programa(codigo)
    cuadruplos = resultado["cuadruplos"]
    if optimizar:
        motor = MotorOptimizacion(cuadruplos)
        cuadruplos = motor.ejecutar_optimizaciones()["cuadruplos_optimizados"]
    return cuadruplos, resultado, analisis


def generar_archivo_objeto(
    ruta: Path,
    salida: Path,
    optimizar: bool = True,
    reporte_registros: bool = False,
    reporte_memoria: bool = False,
    ejecutar: bool = False,
) -> int:
    """Flujo completo de la CLI de generacion de codigo objeto."""
    try:
        cuadruplos, resultado, analisis = compilar_cuadruplos(ruta, optimizar)
    except (OSError, ErrorNumlang) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    simbolos = resultado["tabla_simbolos_semantica"]
    direcciones = analisis["tabla_direcciones"]
    asignador = AsignadorRegistros(cuadruplos, simbolos, direcciones)
    gestor = GestorMemoria(
        simbolos, direcciones, bytes_spills=asignador.bytes_spills
    )
    backend = NasmWin32Backend()
    asm = backend.generar(
        cuadruplos,
        {
            "asignador": asignador,
            "gestor": gestor,
            "simbolos": simbolos,
            "cuadruplos": cuadruplos,
        },
    )

    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(asm)

    if reporte_registros:
        print("\n" + asignador.reporte())
    if reporte_memoria:
        print("\n" + gestor.reporte())
    print(f"ASM generado: {salida}")

    if ejecutar:
        correcto, salida_ejecucion = ensamblar_enlazar_ejecutar(salida)
        if not correcto:
            print(salida_ejecucion, file=sys.stderr)
            return 1
        print("Salida del ejecutable:")
        print(salida_ejecucion)
    return 0


def construir_parser() -> argparse.ArgumentParser:
    """CLI del backend de codigo objeto."""
    parser = argparse.ArgumentParser(
        description="Genera codigo objeto NASM win32 desde un programa Numlang."
    )
    parser.add_argument(
        "archivo", type=Path, nargs="?", help="archivo fuente .src de Numlang"
    )
    parser.add_argument(
        "-o", "--salida", type=Path, default=Path("build") / "salida.asm",
        help="archivo .asm de salida",
    )
    parser.add_argument("--sin-optimizar", action="store_true", help="usa cuadruplos sin optimizar")
    parser.add_argument("--reporte-registros", action="store_true", help="muestra asignacion de registros")
    parser.add_argument("--reporte-memoria", action="store_true", help="muestra mapa de memoria")
    parser.add_argument("--ejecutar", action="store_true", help="ensambla, enlaza y ejecuta")
    parser.add_argument("--gui", action="store_true", help="abre la interfaz grafica de Numlang")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la CLI."""
    parser = construir_parser()
    argumentos = parser.parse_args(argv)
    if argumentos.gui:
        from interfaz_grafica import main as main_gui

        return main_gui([str(argumentos.archivo)] if argumentos.archivo else [])
    if argumentos.archivo is None:
        parser.error("se requiere un archivo .src o la opcion --gui")
    return generar_archivo_objeto(
        argumentos.archivo,
        argumentos.salida,
        optimizar=not argumentos.sin_optimizar,
        reporte_registros=argumentos.reporte_registros,
        reporte_memoria=argumentos.reporte_memoria,
        ejecutar=argumentos.ejecutar,
    )


if __name__ == "__main__":
    sys.exit(main())
