from generador_intermedio import GeneradorCodigoIntermedio
from interprete_referencia import interpretar


def test_resolver_lineal_emite_mostrar():
    codigo = "ecu e1: 2*x + 5 = 15\nresolver e1 para x\n"
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    cuadruplos = resultado["cuadruplos"]
    assert any(c["op"] == "mostrar" and c["arg1"] == '"x = 5"' for c in cuadruplos)
    assert interpretar(cuadruplos).strip() == "x = 5"


def test_resolver_cuadratica_dos_raices():
    codigo = "ecu e1: x elevado_a 2 - 5*x + 6 = 0\nresolver e1 para x\n"
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    cuadruplos = resultado["cuadruplos"]
    assert any(c["op"] == "mostrar" and c["arg1"] == '"x = 3, x = 2"' for c in cuadruplos)
    assert interpretar(cuadruplos).strip() == "x = 3, x = 2"


def test_resolver_cuadratica_raices_cero_y_uno():
    codigo = "ecu e1: -(x elevado_a 2) + x = 0\nresolver e1 para x\n"
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    cuadruplos = resultado["cuadruplos"]
    assert any(c["op"] == "mostrar" and c["arg1"] == '"x = 1, x = 0"' for c in cuadruplos)
    assert interpretar(cuadruplos).strip() == "x = 1, x = 0"


def test_resolver_lineal_decimal():
    codigo = "ecu e1: 2*x = 5\nresolver e1 para x\n"
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    cuadruplos = resultado["cuadruplos"]
    assert any(c["op"] == "mostrar" and c["arg1"] == '"x = 2.5"' for c in cuadruplos)
    assert interpretar(cuadruplos).strip() == "x = 2.5"


def test_dos_resolver_conservan_orden():
    codigo = (
        "ecu e1: 2*x + 5 = 15\n"
        "resolver e1 para x\n"
        "ecu e2: 2*z = 5\n"
        "resolver e2 para z\n"
    )
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    cuadruplos = resultado["cuadruplos"]
    assert [c["arg1"] for c in cuadruplos if c["op"] == "mostrar"] == ['"x = 5"', '"x = 2.5"']
    assert interpretar(cuadruplos).strip() == "x = 5\nx = 2.5"


def test_resolver_no_altera_orden_de_salidas():
    codigo = (
        "num a = 1\n"
        "mostrar a\n"
        "ecu e1: 2*x + 5 = 15\n"
        "resolver e1 para x\n"
        "mostrar a + 1\n"
    )
    resultado = GeneradorCodigoIntermedio().compilar_programa(codigo)
    cuadruplos = resultado["cuadruplos"]
    assert interpretar(cuadruplos).strip() == "1\nx = 5\n2"


def test_compilar_programa_no_duplica_salida_del_resolver(capsys):
    GeneradorCodigoIntermedio().compilar_programa(
        "ecu e1: 2*x + 5 = 15\nresolver e1 para x\n"
    )
    assert capsys.readouterr().out == ""
