"""Diagnosticos preliminares de Numlang mientras se edita un archivo .src.

No ejecuta ni genera codigo. Revisa el subconjunto de instrucciones aceptadas
por el proyecto: declaraciones, asignaciones, mostrar y bloques simples.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any

from generador_intermedio import crear_arbol_extendido
from analizador_semantico import ErrorNumlang


@dataclass(frozen=True)
class Diagnostico:
    fase: str
    linea: int
    columna: int
    longitud: int
    mensaje: str


IDENTIFICADOR = r"[a-zA-Z_][a-zA-Z_0-9]*"
DECLARACION = re.compile(rf"(?:(const)\s+)?(num|msj|bool)\s+({IDENTIFICADOR})\s*=\s*(.+)")
ASIGNACION = re.compile(rf"({IDENTIFICADOR}(?:\.{IDENTIFICADOR})?)\s*=\s*(.+)")
SALIDA = re.compile(r"mostrar\s+(.+)")
RETORNO = re.compile(r"retornar\s+(.+)")
LLAMAR = re.compile(rf"llamar\s+({IDENTIFICADOR})\s*\((.*)\)")
PARA = re.compile(rf"para\s+(?:num\s+)?({IDENTIFICADOR})\s*=\s*(.+?)\s+hasta\s+(.+?)(?:\s+paso\s+(.+?))?(?:\s+hacer)?")
FUNCION = re.compile(rf"funcion\s+({IDENTIFICADOR})\s*\((.*?)\)")
ESTRUCTURA = re.compile(rf"estructura\s+({IDENTIFICADOR})")
TOKEN = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r'[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|'
    r'==|!=|<=|>=|\*\*|[+\-*/%=<>():,.;.]'
)
RESERVADAS = {
    "num", "bool", "msj", "mostrar", "si", "entonces", "si_no", "fin",
    "mientras", "hacer", "para", "hasta", "paso", "funcion", "retornar",
    "estructura", "const", "llamar", "y", "o", "no", "verdadero", "falso",
    "elevado_a", "residuo_de", "igual_a", "diferente_de", "menor_que", "mayor_que",
}
PRIMERAS = (
    "num", "bool", "msj", "mostrar", "si", "si_no", "fin", "mientras",
    "para", "funcion", "estructura", "const", "retornar", "llamar",
)


def _tipo_expresion(nodo: dict[str, Any], simbolos: dict[str, str]) -> tuple[str, float | None]:
    """Devuelve el tipo, y el valor si es constante numerica."""
    clase = nodo["tipo"]
    if clase == "numero":
        return "num", float(nodo["valor"])
    if clase == "cadena":
        return "msj", None
    if clase == "booleano":
        return "bool", None
    if clase == "variable":
        nombre = nodo["nombre"]
        if nombre not in simbolos:
            raise ValueError(f"La variable '{nombre}' no esta declarada")
        return simbolos[nombre], None
    if clase == "llamada_funcion":
        for arg in nodo["argumentos"]:
            _tipo_expresion(arg, simbolos)
        # El analizador en vivo no ejecuta funciones ni infiere su retorno.
        return "desconocido", None
    if clase == "negativo":
        tipo, valor = _tipo_expresion(nodo["expresion"], simbolos)
        if tipo not in ("num", "desconocido"):
            raise ValueError("El signo negativo requiere un numero")
        return tipo, (-valor if valor is not None else None)
    if clase == "negacion_logica":
        tipo, _ = _tipo_expresion(nodo["expresion"], simbolos)
        if tipo not in ("bool", "desconocido"):
            raise ValueError("La negacion 'no' requiere un valor bool")
        return "bool", None
    if clase != "operacion":
        return "desconocido", None
    izq, valor_izq = _tipo_expresion(nodo["izquierda"], simbolos)
    der, valor_der = _tipo_expresion(nodo["derecha"], simbolos)
    op = nodo["operador"]
    if op in {"+", "-", "*", "/", "residuo_de", "elevado_a"}:
        if izq not in ("num", "desconocido") or der not in ("num", "desconocido"):
            raise ValueError(f"La operacion '{op}' necesita operandos num, no {izq} y {der}")
        if op in {"/", "residuo_de"} and valor_der == 0:
            raise ValueError("Division entre cero")
        if valor_izq is not None and valor_der is not None:
            try:
                valor = {
                    "+": lambda: valor_izq + valor_der,
                    "-": lambda: valor_izq - valor_der,
                    "*": lambda: valor_izq * valor_der,
                    "/": lambda: valor_izq / valor_der,
                    "residuo_de": lambda: valor_izq % valor_der,
                    "elevado_a": lambda: valor_izq ** valor_der,
                }[op]()
                return "num", float(valor) if isinstance(valor, (float, int, complex)) and not isinstance(valor, complex) else None
            except (ZeroDivisionError, OverflowError, ValueError):
                return "num", None
        return "num", None
    if op in {"<", ">", "<=", ">="}:
        if izq not in ("num", "desconocido") or der not in ("num", "desconocido"):
            raise ValueError(f"La comparacion '{op}' requiere numeros")
        return "bool", None
    if op in {"==", "!="}:
        if izq != der and "desconocido" not in (izq, der):
            raise ValueError("Los valores comparados deben tener el mismo tipo")
        return "bool", None
    if op in {"y", "o"}:
        if izq not in ("bool", "desconocido") or der not in ("bool", "desconocido"):
            raise ValueError(f"El operador '{op}' requiere valores bool")
        return "bool", None
    return "desconocido", None


def analizar_en_vivo(codigo: str) -> list[Diagnostico]:
    """Analiza sin alterar archivos ni ejecutar el programa; ordena por linea/fase."""
    diagnosticos: list[Diagnostico] = []
    simbolos: dict[str, str] = {}
    funciones: set[str] = set()
    bloques: list[tuple[str, int]] = []
    lineas = codigo.splitlines()

    def anadir(fase: str, numero: int, linea: str, mensaje: str, buscar: str = "") -> None:
        indice = linea.find(buscar) if buscar else -1
        if indice < 0:
            indice = len(linea) - len(linea.lstrip())
            longitud = len(linea.strip())
        else:
            longitud = len(buscar)
        diagnosticos.append(Diagnostico(fase, numero, indice + 1, max(1, longitud), mensaje))

    # Las funciones se conocen antes de comprobar sus llamadas.
    for raw in lineas:
        coincidencia = FUNCION.fullmatch(raw.strip().removesuffix(";").strip())
        if coincidencia:
            funciones.add(coincidencia.group(1))

    for numero, original in enumerate(lineas, start=1):
        linea = original.strip().removesuffix(";").strip()
        if not linea or linea.startswith("nota:"):
            continue

        # 1) Analisis lexico: detectar caracteres que no forman tokens.
        posicion = 0
        error_lexico = False
        while posicion < len(linea):
            if linea[posicion].isspace():
                posicion += 1
                continue
            coincidencia = TOKEN.match(linea, posicion)
            if coincidencia:
                posicion = coincidencia.end()
                continue
            resto = linea[posicion:]
            if resto.startswith(('"', "'")):
                mensaje = "Cadena sin comillas de cierre"
            elif linea[posicion].isnumeric() or linea[posicion].isalpha():
                mensaje = f"Caracter no admitido en un identificador: '{linea[posicion]}'"
            else:
                mensaje = f"Caracter no reconocido por Numlang: '{linea[posicion]}'"
            anadir("Lexico", numero, original, mensaje, resto[:1])
            error_lexico = True
            break
        if error_lexico:
            continue

        # 2) Analisis sintactico: estructura de cada sentencia y expresion.
        declaracion = DECLARACION.fullmatch(linea)
        asignacion = ASIGNACION.fullmatch(linea)
        salida = SALIDA.fullmatch(linea)
        retorno = RETORNO.fullmatch(linea)
        llamada = LLAMAR.fullmatch(linea)
        inicio_funcion = FUNCION.fullmatch(linea)
        inicio_estructura = ESTRUCTURA.fullmatch(linea)
        inicio_para = PARA.fullmatch(linea)
        inicio_si = re.fullmatch(r"si\s+(.+?)\s+entonces", linea)
        inicio_mientras = re.fullmatch(r"mientras\s+(.+?)\s+hacer", linea)
        expresiones: list[str] = []
        declarada: tuple[str, str] | None = None
        asignada: str | None = None

        if linea == "fin":
            if not bloques:
                anadir("Sintactico", numero, original, "Se encontro 'fin' sin bloque abierto", "fin")
            else:
                bloques.pop()
            continue
        if linea == "si_no":
            if not bloques or bloques[-1][0] != "si":
                anadir("Sintactico", numero, original, "'si_no' necesita un bloque 'si'", "si_no")
            continue
        if inicio_si:
            expresiones.append(inicio_si.group(1))
            bloques.append(("si", numero))
        elif inicio_mientras:
            expresiones.append(inicio_mientras.group(1))
            bloques.append(("mientras", numero))
        elif inicio_para:
            identificador, comienzo, limite, paso = inicio_para.groups()
            if identificador in RESERVADAS:
                anadir("Semantico", numero, original, f"'{identificador}' es una palabra reservada", identificador)
            else:
                simbolos.setdefault(identificador, "num")
            expresiones.extend([comienzo, limite])
            if paso:
                expresiones.append(paso)
            bloques.append(("para", numero))
        elif inicio_funcion:
            bloques.append(("funcion", numero))
            # Sus parametros son locales en compiladores completos; este chequeo
            # preliminar no intenta inferir el cuerpo de la funcion.
        elif inicio_estructura:
            bloques.append(("estructura", numero))
        elif declaracion:
            prefijo_const, tipo, nombre, expr = declaracion.groups()
            if prefijo_const:
                anadir("Semantico", numero, original, "El analizador semantico actual no admite declaraciones 'const'", "const")
            expresiones.append(expr)
            declarada = (tipo, nombre)
        elif asignacion:
            asignada, expr = asignacion.groups()
            expresiones.append(expr)
        elif salida:
            expresiones.append(salida.group(1))
        elif retorno:
            expresiones.append(retorno.group(1))
        elif llamada:
            nombre, argumentos = llamada.groups()
            if nombre not in funciones:
                anadir("Semantico", numero, original, f"Funcion '{nombre}' no definida", nombre)
            if argumentos.strip():
                expresiones.extend(parte.strip() for parte in argumentos.split(","))
        else:
            primera = linea.split()[0] if linea.split() else linea
            posible = get_close_matches(primera, PRIMERAS, n=1, cutoff=0.62)
            if primera == "sumar":
                mensaje = "Numlang utiliza el operador '+' para sumar, no la instruccion 'sumar'"
            elif posible:
                mensaje = f"Instruccion no reconocida '{primera}'. ¿Quisiste escribir '{posible[0]}'?"
            elif re.match(r"^(num|bool|msj|mostrar|si|mientras|para|funcion|llamar|const)\b", primera):
                mensaje = "Instruccion incompleta o mal formada; revisa la sintaxis"
            else:
                mensaje = f"Instruccion no reconocida o incompleta: '{primera}'"
            anadir("Sintactico", numero, original, mensaje, primera)
            continue

        tipos: list[str] = []
        fallo_sintactico = False
        for expresion in expresiones:
            try:
                arbol = crear_arbol_extendido(expresion)
            except (ErrorNumlang, SyntaxError, ValueError) as error:
                anadir("Sintactico", numero, original, str(error), expresion)
                fallo_sintactico = True
                break
            try:
                tipo, _ = _tipo_expresion(arbol, simbolos)
                tipos.append(tipo)
            except ValueError as error:
                anadir("Semantico", numero, original, str(error), expresion)
                tipos.append("desconocido")
        if fallo_sintactico:
            continue
        if declarada:
            tipo_esperado, nombre = declarada
            if nombre in RESERVADAS:
                anadir("Semantico", numero, original, f"'{nombre}' es una palabra reservada", nombre)
            elif nombre in simbolos:
                anadir("Semantico", numero, original, f"La variable '{nombre}' ya fue declarada", nombre)
            elif tipos and tipos[0] not in (tipo_esperado, "desconocido"):
                anadir("Semantico", numero, original, f"Tipo incompatible: '{nombre}' es {tipo_esperado} y la expresion es {tipos[0]}", nombre)
            else:
                simbolos[nombre] = tipo_esperado
        elif asignada:
            if asignada not in simbolos and "." not in asignada:
                anadir("Semantico", numero, original, f"La variable '{asignada}' no esta declarada", asignada)
            elif asignada in simbolos and tipos and tipos[0] not in (simbolos[asignada], "desconocido"):
                anadir("Semantico", numero, original, f"Tipo incompatible al asignar a '{asignada}'", asignada)
        elif (inicio_si or inicio_mientras) and tipos and tipos[0] not in ("bool", "desconocido"):
            anadir("Semantico", numero, original, "La condicion debe producir un valor bool", expresiones[0])

    for tipo, inicio in bloques:
        anadir("Sintactico", inicio, lineas[inicio - 1], f"Falta 'fin' para cerrar el bloque '{tipo}'")
    orden = {"Lexico": 0, "Sintactico": 1, "Semantico": 2}
    return sorted(diagnosticos, key=lambda d: (d.linea, orden[d.fase], d.columna))
