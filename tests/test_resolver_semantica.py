"""Pruebas semánticas de resolver ID para ID (P0.3.c)."""

from analizador_semantico import analizar_codigo


def valido(codigo):
    resultado = analizar_codigo(codigo)
    assert resultado["valido"], resultado["errores"]
    return resultado


def falla(codigo, fragmento):
    resultado = analizar_codigo(codigo)
    assert not resultado["valido"]
    assert any(fragmento in error.lower() for error in resultado["errores"])


def test_01_resolver_valido():
    resultado = valido("ecu e1: 2*x + 5 = 15\nresolver e1 para x\n")
    assert any(
        nodo["instruccion"] == "resolver" and nodo.get("valida") is True
        for nodo in resultado["arboles"]
    )


def test_02_incognita_no_coincide():
    falla(
        "ecu e1: 2*x + 5 = 15\nresolver e1 para y\n",
        "no es la incógnita",
    )


def test_03_no_es_ecuacion():
    falla(
        "num a = 5\nresolver a para x\n",
        "no es una ecuación",
    )


def test_04_ecuacion_no_declarada():
    falla(
        "resolver e_inexistente para x\n",
        "no está declarada",
    )


def test_05_grado_2_tambien_valido():
    valido("ecu e2: x elevado_a 2 - 4 = 0\nresolver e2 para x\n")
