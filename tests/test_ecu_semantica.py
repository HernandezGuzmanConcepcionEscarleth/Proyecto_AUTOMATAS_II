"""Pruebas semánticas de DefEcu (P0.3.b): incógnita, grado y coeficientes."""

from analizador_semantico import analizar_codigo


def ecu(codigo):
    resultado = analizar_codigo(codigo)
    assert resultado["valido"], resultado["errores"]
    return resultado["tabla_simbolos"]["e1"]


def falla(codigo, fragmento):
    resultado = analizar_codigo(codigo)
    assert not resultado["valido"]
    assert any(fragmento in error.lower() for error in resultado["errores"])


def test_01_grado_1():
    simbolo = ecu("ecu e1: 2*x + 5 = 15\n")
    assert simbolo["incognita"] == "x"
    assert simbolo["grado"] == 1
    assert simbolo["coefs"] == (0.0, 2.0, -10.0)


def test_02_grado_2():
    simbolo = ecu("ecu e1: x elevado_a 2 - 4 = 0\n")
    assert simbolo["incognita"] == "x"
    assert simbolo["grado"] == 2
    assert simbolo["coefs"] == (1.0, 0.0, -4.0)


def test_03_mas_de_una_incognita():
    falla("ecu e1: x + y = 10\n", "más de una incógnita")


def test_04_grado_mayor_a_2():
    falla("ecu e1: x elevado_a 3 = 8\n", "grado mayor a 2")


def test_05_sin_incognita():
    falla("ecu e1: 2 + 3 = 5\n", "no hay incógnita")


def test_06_ecuacion_degenerada():
    falla("ecu e1: 2*x - 2*x = 0\n", "ecuación degenerada")


def test_07_tipos_no_num():
    falla("ecu e1: verdadero = falso\n", "tipos no num")


def test_08_incognita_repetida_se_deduplica():
    simbolo = ecu("ecu e1: 2*x = x + 5\n")
    assert simbolo["incognita"] == "x"
    assert simbolo["grado"] == 1
    assert simbolo["coefs"] == (0.0, 1.0, -5.0)


def test_09_cancelacion_cuadratica():
    simbolo = ecu("ecu e1: x elevado_a 2 - x elevado_a 2 + x = 6\n")
    assert simbolo["grado"] == 1
    assert simbolo["coefs"] == (0.0, 1.0, -6.0)


def test_10_coeficiente_cuadratico_cero():
    simbolo = ecu("ecu e1: 0*x elevado_a 2 + 3*x = 6\n")
    assert simbolo["grado"] == 1
    assert simbolo["coefs"] == (0.0, 3.0, -6.0)


def test_11_factor_cancelado():
    simbolo = ecu("ecu e1: (x - x)*x elevado_a 2 + x = 6\n")
    assert simbolo["grado"] == 1
    assert simbolo["coefs"] == (0.0, 1.0, -6.0)
