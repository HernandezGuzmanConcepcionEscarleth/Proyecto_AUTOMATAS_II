"""Pruebas unitarias de precedencia entre menos unario y elevado_a."""

from analizador_semantico import analizar_codigo, crear_arbol
from generador_intermedio import GeneradorCodigoIntermedio
from interprete_referencia import interpretar


def test_menos_unario_precede_a_elevado_a():
    codigo = "mostrar -2 elevado_a 2\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [4.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "4"


def test_elevado_a_asocia_a_la_derecha():
    codigo = "mostrar 2 elevado_a 3 elevado_a 2\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [512.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "512"


def test_parentesis_explicitos_requieren_negacion_de_la_potencia():
    codigo = "mostrar -(2 elevado_a 2)\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [-4.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "-4"


def test_parentesis_explicitos_con_espacios_requieren_negacion_de_la_potencia():
    codigo = "mostrar - ( 2 elevado_a 2 )\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [-4.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "-4"


def test_suma_con_parentesis_explicitos_requiere_negacion_de_la_potencia():
    codigo = "mostrar (1 elevado_a 1) + -(2 elevado_a 2)\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [-3.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "-3"


def test_parentesis_solo_en_base_no_cambia_la_regresion():
    codigo = "mostrar -(2) elevado_a 2\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [4.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "4"


def test_exponente_negativo_entre_parentesis_respeta_agrupacion():
    codigo = "mostrar 2 elevado_a -(3 elevado_a 2)\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [0.001953125]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "0.001953125"


def test_exponente_negativo_sin_parentesis_usa_regresion():
    codigo = "mostrar 2 elevado_a -3 elevado_a 2\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [512.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "512"


def test_ecu_con_parentesis_explicitos_resuelve_raices_positivas(capsys):
    codigo = "ecu e1: -(x elevado_a 2) + x = 0\nresolver e1 para x\n"
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert capsys.readouterr().out == "x = 1, x = 0\n"


def test_caracter_no_ascii_antes_del_menos_no_rompe_parentesis():
    codigo = 'msj s = "ñ"\nmostrar -(2 elevado_a 2)\n'
    analisis = analizar_codigo(codigo)
    assert analisis["valido"], analisis["errores"]
    assert analisis["salidas"] == [-4.0]
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    assert interpretar(resultado["cuadruplos"]).strip() == "-4"

    arbol = crear_arbol('"ñ" + -(2 elevado_a 2)')
    assert arbol["derecha"] == {
        "tipo": "negativo",
        "expresion": {
            "tipo": "operacion",
            "operador": "elevado_a",
            "izquierda": {"tipo": "numero", "valor": 2.0},
            "derecha": {"tipo": "numero", "valor": 2.0},
        },
    }
