"""Pruebas de semántica de DefFunc sin evaluación de llamadas (P0.4.b)."""

import math

from analizador_semantico import analizar_codigo


def _errores(codigo):
    resultado = analizar_codigo(codigo)
    assert not resultado["valido"], resultado
    return resultado["errores"]


def test_func_un_parametro_valida():
    resultado = analizar_codigo("func f(x) = x + 1\n")
    assert resultado["valido"], resultado["errores"]
    simbolo = resultado["tabla_simbolos"]["f"]
    assert simbolo["tipo"] == "func"
    assert simbolo["parametros"] == ["x"]
    assert simbolo["n_params"] == 1
    assert simbolo["expresion"]["operador"] == "+"
    assert simbolo["scope"] == "global"
    assert simbolo["valor"] is None


def test_func_cero_parametros_con_PI():
    resultado = analizar_codigo("func h() = PI * 2\n")
    assert resultado["valido"], resultado["errores"]
    simbolo = resultado["tabla_simbolos"]["h"]
    assert simbolo["parametros"] == []
    assert simbolo["n_params"] == 0
    assert simbolo["expresion"]["izquierda"] == {"tipo": "numero", "valor": math.pi}


def test_func_cuerpo_llama_funcion_previa():
    resultado = analizar_codigo("func f(x) = x + 1\nfunc g(z) = f(z) + 2\n")
    assert resultado["valido"], resultado["errores"]
    llamada = resultado["tabla_simbolos"]["g"]["expresion"]["izquierda"]
    assert llamada["nombre"] == "f"
    assert llamada["args"] == [{"tipo": "variable", "nombre": "z"}]


def test_param_sombrea_global():
    resultado = analizar_codigo("num x = 100\nfunc f(x) = x + 1\n")
    assert resultado["valido"], resultado["errores"]
    assert resultado["tabla_simbolos"]["f"]["parametros"] == ["x"]


def test_llamada_no_definida_en_cuerpo():
    errores = _errores("func g(x) = h(x) + 1\n")
    assert any("no definida" in error for error in errores)


def test_recursion_bloqueada():
    errores = _errores("func f(x) = f(x) + 1\n")
    assert any("recursi" in error for error in errores)


def test_global_en_cuerpo():
    errores = _errores("num g = 5\nfunc f(x) = x + g\n")
    assert any("global" in error for error in errores)


def test_variable_no_declarada_en_cuerpo():
    errores = _errores("func f(x) = x + y\n")
    assert any("no declarada" in error for error in errores)


def test_params_duplicados():
    errores = _errores("func f(x, x) = x\n")
    assert any("duplicad" in error for error in errores)


def test_param_reservado():
    errores = _errores("func f(PI) = PI\n")
    assert any("reservada" in error for error in errores)


def test_nombre_func_reservado():
    errores = _errores("func num(x) = x\n")
    assert any("reservada" in error for error in errores)


def test_func_redeclarada():
    errores = _errores("func f(x) = x\nfunc f(z) = z\n")
    assert any("ya fue declarada" in error for error in errores)


def test_colision_var_a_func():
    errores = _errores("num f = 1\nfunc f(x) = x\n")
    assert any("ya fue declarada" in error for error in errores)


def test_colision_func_a_var():
    errores = _errores("func f(x) = x\nnum f = 1\n")
    assert any("ya fue declarada" in error for error in errores)


def test_cuerpo_bool():
    errores = _errores("func f(x) = x > 3\n")
    assert any("NUM" in error for error in errores)


def test_cuerpo_cadena():
    errores = _errores('func f(x) = "hola"\n')
    assert any("NUM" in error for error in errores)


def test_cuerpo_booleano_literal():
    errores = _errores("func f(x) = verdadero\n")
    assert any("NUM" in error for error in errores)


def test_aridad_incorrecta_en_cuerpo():
    errores = _errores("func f(x) = x\nfunc g(z) = f(z, 2) + 1\n")
    assert any("aridad" in error for error in errores)


def test_param_y_reservado():
    errores = _errores("func g(x, y) = x + 1\n")
    assert any("reservada" in error for error in errores)
