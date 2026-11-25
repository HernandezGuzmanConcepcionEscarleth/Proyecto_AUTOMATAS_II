"""Evaluación de llamadas con pila de scopes (P0.4.d)."""

import math

from analizador_semantico import analizar_codigo

def _salidas(codigo): return analizar_codigo(codigo)["salidas"]

def _errores(codigo): return analizar_codigo(codigo)["errores"]

def test_llamadas_basicas(): assert _salidas("func f(x) = x + 1\nmostrar f(3)\n") == [4.0]; assert _salidas("func f(x) = x + 1\nnum r = f(3)\nmostrar r\nr = f(r)\nmostrar r\n") == [4.0, 5.0]; assert _salidas("func f(x) = x + 1\nmostrar f(f(2))\n") == [4.0]

def test_funcion_llama_otra(): assert _salidas("func f(x) = x + 1\nfunc g(x) = f(x) * 2\nmostrar g(3)\n") == [8.0]

def test_scopes_y_parametros(): assert _salidas("num x = 100\nfunc f(x) = x + 1\nmostrar f(2)\nmostrar x\n") == [3.0, 100.0]; assert _salidas("num x = 5\nfunc f(x) = x * 2\nmostrar f(x + 1)\n") == [12.0]; assert _salidas("func h() = PI * 2\nmostrar h()\n") == [2 * math.pi]

def test_scope_no_colgado_tras_error(): codigo = "func f(x) = 1 / x\nmostrar f(0)\nnum k = 7\nmostrar k\n"; resultado = analizar_codigo(codigo); assert any("División entre cero" in error for error in resultado["errores"]); assert resultado["salidas"] == [7.0]

def test_argumento_expresion_no_declarada(): errores = _errores("func f(x) = x + 1\nmostrar f(w + 1)\n"); assert any("no está declarada" in error for error in errores)

def test_llamada_en_condicion(): codigo = "func f(x) = x + 1\nsi f(2) > 2 entonces\nmostrar 1\nfin\n"; resultado = analizar_codigo(codigo); assert resultado["valido"], resultado["errores"]; assert resultado["salidas"] == [1.0]

def test_pila_equivalente_a_expresion(): con = analizar_codigo("func f(x) = x + 1\nmostrar f(3)\n"); sin = analizar_codigo("mostrar 3 + 1\n"); assert con["historial_pila"][-2]["pila"] == sin["historial_pila"][-2]["pila"] == [4.0]

def test_orden_parametros(): assert _salidas("func h(a, b) = a - b\nmostrar h(10, 3)\n") == [7.0]; assert _salidas("func h(a, b) = a - b\nmostrar h(3, 10)\n") == [-7.0]

def test_scope_exterior_restaurado(): assert _salidas("func f(x) = x + 1\nfunc g(x) = f(x * 10) + x\nmostrar g(2)\n") == [23.0]
