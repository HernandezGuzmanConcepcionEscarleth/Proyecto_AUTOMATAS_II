"""Pruebas del front-end de DefFunc y llamadas (P0.4.a)."""

from analizador_semantico import AnalizadorSemantico, analizar_codigo, crear_arbol


def test_01_func_un_parametro():
    r = analizar_codigo("func f(x) = x elevado_a 2 + 1\n")
    assert r["valido"], r["errores"]
    nodo = r["arboles"][0]
    assert nodo["instruccion"] == "func"
    assert nodo["destino"] == "f"
    assert nodo["parametros"] == ["x"]
    assert nodo["expresion"]["operador"] == "+"


def test_02_func_dos_parametros():
    r = analizar_codigo("func g(x, z) = x + z\n")
    assert r["valido"], r["errores"]
    assert r["arboles"][0]["parametros"] == ["x", "z"]


def test_03_func_cero_parametros():
    r = analizar_codigo("func h() = 42\n")
    assert r["valido"], r["errores"]
    assert r["arboles"][0]["parametros"] == []
    assert r["arboles"][0]["expresion"] == {"tipo": "numero", "valor": 42.0}


def test_04_llamada_en_primario():
    assert crear_arbol("f(3, x + 1)") == {
        "tipo": "llamada",
        "nombre": "f",
        "args": [
            {"tipo": "numero", "valor": 3.0},
            {
                "tipo": "operacion",
                "operador": "+",
                "izquierda": {"tipo": "variable", "nombre": "x"},
                "derecha": {"tipo": "numero", "valor": 1.0},
            },
        ],
    }


def test_05_cuerpo_puede_contener_llamada():
    r = analizar_codigo("func f(x) = x\nfunc g(x) = f(x) + 1\n")
    assert r["valido"], r["errores"]
    llamada = r["arboles"][1]["expresion"]["izquierda"]
    assert llamada["tipo"] == "llamada"
    assert llamada["nombre"] == "f"


def test_06_func_reservada():
    assert "func" in AnalizadorSemantico().palabras_reservadas


def test_07_falta_parentesis():
    assert not analizar_codigo("func f(x = x + 1\n")["valido"]


def test_08_falta_igual():
    assert not analizar_codigo("func f(x) x + 1\n")["valido"]


def test_09_parametro_invalido():
    r = analizar_codigo("func f(x,) = x\n")
    assert not r["valido"]
    assert any("Parámetro inválido" in e for e in r["errores"])
