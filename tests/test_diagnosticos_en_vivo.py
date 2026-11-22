"""Pruebas de la revision de errores mientras se escribe."""
from pathlib import Path

from diagnosticos_en_vivo import analizar_en_vivo

BASE = Path(__file__).resolve().parents[1] / "src"


def test_los_tres_archivos_correctos_no_tienen_diagnosticos():
    for nombre in ("lexico_correcto.src", "sintactico_correcto.src", "semantico_correcto.src", "demo_correcto.src"):
        assert analizar_en_vivo((BASE / nombre).read_text(encoding="utf-8")) == [], nombre


def test_lexico_incorrecto_detecta_caracter_desconocido():
    resultado = analizar_en_vivo((BASE / "lexico_incorrecto.src").read_text(encoding="utf-8"))
    assert len(resultado) == 1
    assert resultado[0].fase == "Lexico" and resultado[0].linea == 4
    assert "@" in resultado[0].mensaje


def test_sintactico_incorrecto_detecta_dos_errores():
    resultado = analizar_en_vivo((BASE / "sintactico_incorrecto.src").read_text(encoding="utf-8"))
    assert len(resultado) == 2
    assert {x.fase for x in resultado} == {"Sintactico"}
    assert "mostrar" in resultado[-1].mensaje


def test_semantico_incorrecto_tiene_cuatro_errores():
    resultado = analizar_en_vivo((BASE / "semantico_incorrecto.src").read_text(encoding="utf-8"))
    assert len(resultado) == 4
    assert all(x.fase == "Semantico" for x in resultado)
    assert any("Division entre cero" in x.mensaje for x in resultado)


def test_demo_contiene_los_tres_analizadores():
    resultado = analizar_en_vivo((BASE / "demo_incorrecto.src").read_text(encoding="utf-8"))
    assert {x.fase for x in resultado} == {"Lexico", "Sintactico", "Semantico"}


def test_instruccion_sumar_se_explica_en_lugar_de_inventarla():
    diag = analizar_en_vivo("sumar a b")
    assert len(diag) == 1 and "'+'" in diag[0].mensaje


def test_error_linea_corresponde_fuente():
    diag = analizar_en_vivo("num a = 3\nnum b = 5 @ 1\nmostrar a")
    assert len(diag) == 1 and diag[0].linea == 2
