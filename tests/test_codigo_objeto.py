"""Pruebas end-to-end del backend NASM win32 de Numlang."""

from pathlib import Path

import pytest

from asignador_registros import AsignadorRegistros
from generador_objeto import (
    NasmWin32Backend,
    compilar_cuadruplos,
    ensamblar_enlazar_ejecutar,
    localizar_herramienta,
)
from gestor_memoria import GestorMemoria
from interprete_referencia import interpretar

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"

PROGRAMAS_VALIDOS = [
    "programa.src",
    "operaciones.src",
    "correcto.src",
    "prueba_while.src",
    "prueba_for.src",
    "prueba_motor.src",
]

SALIDAS_ESPERADAS = {
    "programa.src": "mayor\n",
    "operaciones.src": "25\n15\n100\n4\n",
    "correcto.src": "10\n",
    "prueba_while.src": "0\n1\n2\n",
    "prueba_for.src": "1\n2\n3\n4\n5\n",
    "prueba_motor.src": "10\n",
}

requiere_toolchain = pytest.mark.skipif(
    localizar_herramienta("nasm") is None or localizar_herramienta("gcc") is None,
    reason="Faltan nasm o gcc con soporte -m32 (MinGW-w64 i686); instala NASM y MinGW para ejecutar estas pruebas",
)


def normalizar(texto: str) -> str:
    return texto.replace("\r\n", "\n").rstrip("\n")


def escribir_asm(destino: Path, cuadruplos, simbolos, direcciones) -> str:
    asignador = AsignadorRegistros(cuadruplos, simbolos, direcciones)
    gestor = GestorMemoria(simbolos, direcciones, bytes_spills=asignador.bytes_spills)
    backend = NasmWin32Backend()
    asm = backend.generar(
        cuadruplos,
        {"asignador": asignador, "gestor": gestor, "simbolos": simbolos},
    )
    with destino.open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(asm)
    return asm


def compilar_y_preparar(ruta: Path, tmp_path: Path, optimizar: bool, sufijo: str):
    cuadruplos, resultado, analisis = compilar_cuadruplos(ruta, optimizar)
    simbolos = resultado["tabla_simbolos_semantica"]
    destino = tmp_path / f"{ruta.stem}_{sufijo}.asm"
    escribir_asm(destino, cuadruplos, simbolos, analisis["tabla_direcciones"])
    esperado = interpretar(cuadruplos, simbolos)
    return destino, esperado


@pytest.mark.parametrize("nombre", PROGRAMAS_VALIDOS)
def test_interprete_coincide_con_valores_conocidos(nombre):
    ruta = SRC / nombre
    cuadruplos, resultado, _ = compilar_cuadruplos(ruta, True)
    salida = interpretar(cuadruplos, resultado["tabla_simbolos_semantica"])
    assert normalizar(salida) == normalizar(SALIDAS_ESPERADAS[nombre])


@pytest.mark.parametrize("nombre", PROGRAMAS_VALIDOS)
@requiere_toolchain
def test_programas_src_generan_asm_y_coinciden_con_el_interprete(nombre, tmp_path):
    destino, esperado = compilar_y_preparar(SRC / nombre, tmp_path, True, "opt")
    correcto, salida = ensamblar_enlazar_ejecutar(destino)
    assert correcto, salida
    assert normalizar(salida) == normalizar(esperado)


@pytest.mark.parametrize("nombre", PROGRAMAS_VALIDOS)
@requiere_toolchain
def test_optimizado_y_sin_optimizar_producen_la_misma_salida(nombre, tmp_path):
    ruta = SRC / nombre
    asm_opt, esperado_opt = compilar_y_preparar(ruta, tmp_path, True, "opt")
    asm_sin, esperado_sin = compilar_y_preparar(ruta, tmp_path, False, "sinopt")

    correcto_opt, salida_opt = ensamblar_enlazar_ejecutar(asm_opt)
    correcto_sin, salida_sin = ensamblar_enlazar_ejecutar(asm_sin)
    assert correcto_opt, salida_opt
    assert correcto_sin, salida_sin
    assert normalizar(salida_opt) == normalizar(salida_sin)
    assert normalizar(salida_opt) == normalizar(esperado_opt) == normalizar(esperado_sin)


def test_asignador_derrama_cuando_hay_mas_de_tres_temporales_vivos():
    cuadruplos = [{"op": "=", "arg1": "1", "arg2": "-", "res": "a"}]
    cuadruplos += [
        {"op": "+", "arg1": "a", "arg2": str(numero), "res": f"t{numero}"}
        for numero in range(1, 7)
    ]
    cuadruplos += [
        {"op": "=", "arg1": f"t{numero}", "arg2": "-", "res": f"r{numero}"}
        for numero in range(1, 7)
    ]
    asignador = AsignadorRegistros(cuadruplos)
    ubicaciones = asignador.tabla_asignacion()
    derramados = [valor for valor in ubicaciones.values() if str(valor).startswith("[ebp-")]
    assert len(derramados) >= 3
    assert asignador.bytes_spills >= 12


@requiere_toolchain
def test_spill_se_ejecuta_correctamente(tmp_path):
    cuadruplos = [{"op": "=", "arg1": "1", "arg2": "-", "res": "a"}]
    cuadruplos += [
        {"op": "+", "arg1": "a", "arg2": str(numero), "res": f"t{numero}"}
        for numero in range(1, 7)
    ]
    cuadruplos += [
        {"op": "=", "arg1": f"t{numero}", "arg2": "-", "res": f"r{numero}"}
        for numero in range(1, 7)
    ]
    cuadruplos += [
        {"op": "mostrar", "arg1": f"r{numero}", "arg2": "-", "res": "-"}
        for numero in range(1, 7)
    ]
    simbolos = {"a": {"tipo": "num", "valor": 1}}
    destino = tmp_path / "spill.asm"
    asm = escribir_asm(destino, cuadruplos, simbolos, {})
    assert "[ebp-" in asm

    correcto, salida = ensamblar_enlazar_ejecutar(destino)
    assert correcto, salida
    assert normalizar(salida) == normalizar("2\n3\n4\n5\n6\n7\n")
    assert normalizar(salida) == normalizar(interpretar(cuadruplos, simbolos))


@requiere_toolchain
def test_negativos_y_division_entera(tmp_path):
    fuente = tmp_path / "negativos.src"
    fuente.write_text(
        "num a = -7\nnum b = a / 2\nmostrar a\nmostrar b\n",
        encoding="utf-8",
    )
    destino, esperado = compilar_y_preparar(fuente, tmp_path, True, "negativos")
    correcto, salida = ensamblar_enlazar_ejecutar(destino)
    assert correcto, salida
    assert normalizar(salida) == normalizar(esperado)
    assert normalizar(salida) == "-7\n-3"


@requiere_toolchain
def test_bucle_con_paso_negativo(tmp_path):
    fuente = tmp_path / "paso_negativo.src"
    fuente.write_text(
        "para i = 5 hasta 1 paso -1 hacer\n    mostrar i\nfin\n",
        encoding="utf-8",
    )
    destino, esperado = compilar_y_preparar(fuente, tmp_path, True, "paso_neg")
    correcto, salida = ensamblar_enlazar_ejecutar(destino)
    assert correcto, salida
    assert normalizar(salida) == normalizar(esperado)
    assert normalizar(salida) == "5\n4\n3\n2\n1"


def test_procesar_codigo_genera_asm_y_reportes_sin_ejecutar(tmp_path):
    from interfaz_grafica import procesar_codigo

    resultado = procesar_codigo(
        "num x = 5\nmostrar x\n",
        ejecutar=False,
        ruta_asm=tmp_path / "interfaz.asm",
    )
    assert "section .text" in resultado["asm"]
    assert "global _main" in resultado["asm"]
    assert "mostrar" in resultado["cuadruplos"]
    assert "MAPA DE REGISTROS" in resultado["reporte"]
    assert "MAPA DE MEMORIA" in resultado["reporte"]


@requiere_toolchain
def test_procesar_codigo_ejecuta_desde_la_interfaz(tmp_path):
    from interfaz_grafica import procesar_codigo

    resultado = procesar_codigo(
        "num x = 5\nmostrar x\n",
        ejecutar=True,
        ruta_asm=tmp_path / "interfaz.asm",
    )
    assert normalizar(resultado["salida"]) == "5"
