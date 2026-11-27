"""Pruebas del evaluador numérico de resolver (P0.3.d)."""

from analizador_semantico import AnalizadorSemantico, analizar_codigo


def salida(codigo, capsys):
    resultado = analizar_codigo(codigo)
    assert resultado["valido"], resultado["errores"]
    return capsys.readouterr().out


def falla(codigo, fragmento):
    resultado = analizar_codigo(codigo)
    assert not resultado["valido"]
    assert any(fragmento in error.lower() for error in resultado["errores"])


def test_01_grado_1(capsys):
    assert salida("ecu e1: 2*x + 5 = 15\nresolver e1 para x\n", capsys) == "x = 5\n"


def test_02_grado_1_b_negativo(capsys):
    assert salida("ecu e1: -2*x + 4 = 0\nresolver e1 para x\n", capsys) == "x = 2\n"


def test_03_grado_1_c_cero(capsys):
    assert salida("ecu e1: 3*x = 0\nresolver e1 para x\n", capsys) == "x = 0\n"


def test_04_grado_2_dos_soluciones(capsys):
    assert salida("ecu e2: x elevado_a 2 - 4 = 0\nresolver e2 para x\n", capsys) == "x = 2, x = -2\n"


def test_05_grado_2_doble(capsys):
    assert salida("ecu e3: x elevado_a 2 - 4*x + 4 = 0\nresolver e3 para x\n", capsys) == "x = 2\n"


def test_06_sin_soluciones_reales(capsys):
    falla("ecu e4: x elevado_a 2 + 1 = 0\nresolver e4 para x\n", "no tiene soluciones reales")
    capsys.readouterr()


def test_07_grado_2_a_negativo(capsys):
    assert salida("ecu e5: 0 - x elevado_a 2 + 4 = 0\nresolver e5 para x\n", capsys) == "x = 2, x = -2\n"


def test_08_cancelacion_simbolica(capsys):
    assert salida("ecu e6: (x-x)*x elevado_a 2 + x = 6\nresolver e6 para x\n", capsys) == "x = 6\n"


def test_09_ignora_nodos_no_validos(capsys):
    analizador = AnalizadorSemantico()
    analizador.simbolos["e1"] = {
        "tipo": "ecu", "incognita": "x", "grado": 1,
        "coefs": (0.0, 2.0, -10.0), "valor": None,
    }
    analizador.evaluar({"instruccion": "resolver", "destino": "e1", "expresion": "x"})
    analizador.evaluar({"instruccion": "resolver", "destino": "e1", "expresion": "x", "valida": False})
    assert capsys.readouterr().out == ""


def test_10_resolver_dos_veces(capsys):
    assert salida(
        "ecu e1: 2*x + 5 = 15\nresolver e1 para x\nresolver e1 para x\n",
        capsys,
    ) == "x = 5\nx = 5\n"


def test_11_resolver_aparece_en_salidas(capsys):
    codigo = (
        "num a = 1\n"
        "mostrar a\n"
        "ecu e1: 2*x + 5 = 15\n"
        "resolver e1 para x\n"
        "mostrar a + 1\n"
    )
    resultado = analizar_codigo(codigo)
    assert resultado["valido"], resultado["errores"]
    assert resultado["salidas"] == [1.0, "x = 5", 2.0]
    assert capsys.readouterr().out == "x = 5\n"
