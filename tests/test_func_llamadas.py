"""Semántica de llamadas ID(Args) (P0.4.c)."""

from analizador_semantico import analizar_codigo


def _errores(codigo):
    resultado = analizar_codigo(codigo)
    assert not resultado["valido"], resultado
    return resultado["errores"]


def _error(codigo, subcadena):
    errores = _errores(codigo)
    assert any(subcadena in error for error in errores)


def test_llamadas_no_lanzan_excepcion():
    resultado = analizar_codigo("func f(x) = x + 1\nmostrar f(3)\n")
    assert resultado["salidas"] == [4.0]
    assert isinstance(analizar_codigo("func f(x) = x + 1\nnum r = f(3)\n"), dict)


def test_llamada_sin_definir():
    _error("mostrar g(3)\n", "no definida")


def test_aridad_llamada():
    _error("func f(x) = x\nmostrar f(1, 2)\n", "aridad")
    _error("func f(x) = x\nmostrar f()\n", "aridad")


def test_argumentos_llamada():
    _error('func f(x) = x\nmostrar f("a")\n', "NUM")
    _error("func f(x) = x\nmostrar f(verdadero)\n", "NUM")
    _error("func f(x) = x\nmostrar f(w)\n", "no está declarada")


def test_callee_no_funcion():
    _error("num a = 1\nmostrar a(2)\n", "no es una función")
    _error("ecu e1: x = 1\nmostrar e1(2)\n", "no es una función")


def test_llamada_anidada_no_lanza():
    resultado = analizar_codigo("func f(x) = x + 1\nmostrar f(f(2))\n")
    assert resultado["salidas"] == [4.0]


def test_llamada_en_ecu():
    _error("func f(x) = x\necu e1: f(x) = 3\n", "llamadas a funciones no permitidas dentro de una ecuación")


def test_parametro_como_callee_en_cuerpo():
    _error("func f(x) = x\nfunc g(f) = f(2)\n", "parámetro")
