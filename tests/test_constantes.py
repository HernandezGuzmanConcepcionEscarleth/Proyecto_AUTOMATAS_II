"""Pruebas mínimas de constantes PI, Eu, verdadero y falso (P0.5)."""

import math

from analizador_semantico import AnalizadorSemantico, analizar_codigo
from generador_intermedio import GeneradorCodigoIntermedio
from interprete_referencia import interpretar


def test_mostrar_PI():
    codigo = "mostrar PI\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [math.pi]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "3.141592653589793"


def test_mostrar_Eu():
    codigo = "mostrar Eu\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [math.e]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "2.718281828459045"


def test_area_con_PI():
    codigo = "num area = PI * 4\nmostrar area\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [12.566370614359172]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "12.566370614359172"


def test_ecu_con_PI(capsys):
    codigo = "ecu e1: x * PI = 6\nresolver e1 para x\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert capsys.readouterr().out == f"x = {6 / math.pi}\n"


def test_PI_y_Eu_son_reservadas_pero_pi_y_e_no():
    resultado = analizar_codigo("num PI = 3\n")
    assert not resultado["valido"]
    assert any("palabra reservada" in error for error in resultado["errores"])
    assert not analizar_codigo("PI = 4\n")["valido"]

    reservadas = AnalizadorSemantico().palabras_reservadas
    assert "PI" in reservadas
    assert "Eu" in reservadas
    assert "pi" not in reservadas
    assert "e" not in reservadas


def test_verdadero_en_ambas_rutas():
    codigo = "bool b = verdadero\nmostrar b\nsi verdadero entonces\nmostrar 1\nfin\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [True, 1.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).splitlines() == ["1", "1"]
