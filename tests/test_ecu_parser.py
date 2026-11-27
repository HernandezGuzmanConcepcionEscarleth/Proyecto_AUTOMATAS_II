"""Pruebas del front-end de ecuaciones (P0.3.a)."""

from analizador_semantico import analizar_codigo
from generador_intermedio import GeneradorCodigoIntermedio


def test_defecu_parsea():
    codigo = "ecu e1: 2*x + 5 = 15\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    generado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert generado["valido"]


def test_resolver_parsea():
    codigo = "ecu e1: 2*x + 5 = 15\nresolver e1 para x\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    generado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert generado["valido"]


def test_multiplicacion_implicita_falla_en_parser():
    analisis = analizar_codigo("ecu e1: 2x + 5 = 15\n")
    assert not analisis["valido"]
    assert any("Expresión mal escrita" in error for error in analisis["errores"])
