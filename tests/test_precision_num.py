"""Pruebas de representacion float de doble precision para num."""

from analizador_semantico import AnalizadorSemantico, analizar_codigo
from generador_intermedio import GeneradorCodigoIntermedio
from interprete_referencia import interpretar


def test_literal_entero_se_almacena_como_float():
    resultado = analizar_codigo("num x = 5\n")
    assert resultado["valido"], resultado["errores"]
    valor = resultado["tabla_simbolos"]["x"]["valor"]
    assert isinstance(valor, float)
    assert valor == 5.0


def test_suma_decimal_sin_perdida_en_todo_el_pipeline():
    codigo = "num x = 5\nmostrar x + 0.1\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [5.1]
    generado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert generado["cuadruplos"][0]["arg1"] == "5.0"
    assert generado["cuadruplos"][1]["arg2"] == "0.1"
    assert interpretar(generado["cuadruplos"], generado["tabla_simbolos_semantica"]).strip() == "5.1"


def test_salida_entera_permanece_consistente():
    codigo = "num x = 5\nmostrar x\n"
    semantico = AnalizadorSemantico()
    for linea in codigo.splitlines():
        semantico.ejecutar_instruccion(linea)
    assert semantico.salidas == [5.0]
    generado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(generado["cuadruplos"], generado["tabla_simbolos_semantica"]).strip() == "5"
