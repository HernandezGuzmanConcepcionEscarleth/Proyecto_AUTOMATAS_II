from analizador_semantico import ErrorNumlang
from interfaz_grafica import formatear_error_compilacion


def test_error_numlang_con_prefijo_una_linea_por_error():
    mensaje = formatear_error_compilacion(
        ErrorNumlang("Errores semanticos: Línea 2: A; Línea 3: B")
    )
    assert mensaje.splitlines() == [
        "Error de compilación",
        "Línea 2: A",
        "Línea 3: B",
    ]


def test_error_numlang_sin_prefijo_una_sola_linea():
    mensaje = formatear_error_compilacion(
        ErrorNumlang("Instrucción no reconocida: 'func f(x) = x'")
    )
    assert mensaje.splitlines() == [
        "Error de compilación",
        "Instrucción no reconocida: 'func f(x) = x'",
    ]


def test_excepcion_interna_incluye_tipo_y_mensaje():
    mensaje = formatear_error_compilacion(Exception("boom"))
    assert "Error interno" in mensaje
    assert "boom" in mensaje
