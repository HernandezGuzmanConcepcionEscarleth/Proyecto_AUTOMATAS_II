"""Numlang - Integrante 1: Analizador Semántico (Actualizado Fase 2)."""

import ast
import json
import math
import re
import sys
from pathlib import Path

# Coeficientes podados a 1e-12 en P0.3.b; 1e-9 distingue d==0 sin confundir d=1e-10.
TOL_DISCRIMINANTE = 1e-9


def _normalizar_operadores_verbones(expresion: str) -> str:
    """Traduce operadores verbales de Numlang a operadores de Python."""
    partes = re.split(r'("[^"]*"|\'[^\']*\')', expresion)
    for i in range(0, len(partes), 2):
        partes[i] = re.sub(r"\belevado_a\b", "**", partes[i])
    return "".join(partes)


def menos_unario_esta_parentizado(expresion: str, nodo: ast.UnaryOp) -> bool:
    """True si hay '(' entre el '-' y el operando, usando offsets UTF-8."""
    inicio = nodo.col_offset + 1
    fin = nodo.operand.col_offset
    return b"(" in expresion.encode("utf-8")[inicio:fin]


class ErrorNumlang(Exception):
    """Error de sintaxis o semántica de una instrucción de Numlang."""


def crear_arbol(expresion):
    """Convierte una expresión en un árbol simple (diccionarios)."""
    fuente = _normalizar_operadores_verbones(expresion)
    try:
        raiz = ast.parse(fuente, mode="eval").body
    except SyntaxError as exc:
        raise ErrorNumlang(f"Expresión mal escrita: '{expresion}'") from exc

    operaciones = {
        ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
        ast.Gt: ">", ast.Lt: "<", ast.GtE: ">=", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!=",
        ast.Pow: "elevado_a",
    }

    def convertir(nodo):
        if isinstance(nodo, ast.Call):
            if not isinstance(nodo.func, ast.Name) or nodo.keywords:
                raise ErrorNumlang("Llamada no soportada en la expresión")
            return {
                "tipo": "llamada",
                "nombre": nodo.func.id,
                "args": [convertir(arg) for arg in nodo.args],
            }
        if isinstance(nodo, ast.Constant):
            if type(nodo.value) in (int, float):
                return {"tipo": "numero", "valor": float(nodo.value)}
            if type(nodo.value) is str:
                return {"tipo": "cadena", "valor": nodo.value}
            if type(nodo.value) is bool:
                return {"tipo": "booleano", "valor": nodo.value}
        if isinstance(nodo, ast.Name):
            if nodo.id in ("verdadero", "falso"):
                return {"tipo": "booleano", "valor": nodo.id == "verdadero"}
            if nodo.id == "PI":
                return {"tipo": "numero", "valor": math.pi}
            if nodo.id == "Eu":
                return {"tipo": "numero", "valor": math.e}
            return {"tipo": "variable", "nombre": nodo.id}
        if isinstance(nodo, ast.BinOp) and type(nodo.op) in operaciones:
            return {
                "tipo": "operacion", "operador": operaciones[type(nodo.op)],
                "izquierda": convertir(nodo.left), "derecha": convertir(nodo.right),
            }
        if isinstance(nodo, ast.Compare):
            if len(nodo.ops) == 1 and type(nodo.ops[0]) in operaciones:
                return {
                    "tipo": "operacion", "operador": operaciones[type(nodo.ops[0])],
                    "izquierda": convertir(nodo.left), "derecha": convertir(nodo.comparators[0]),
                }
        if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, ast.USub):
            interno = convertir(nodo.operand)
            if (
                interno.get("tipo") == "operacion"
                and interno.get("operador") == "elevado_a"
                and not menos_unario_esta_parentizado(fuente, nodo)
            ):
                return {
                    "tipo": "operacion", "operador": "elevado_a",
                    "izquierda": {"tipo": "negativo", "expresion": interno["izquierda"]},
                    "derecha": interno["derecha"],
                }
            return {"tipo": "negativo", "expresion": interno}
        raise ErrorNumlang("Operación no soportada en la expresión")

    return convertir(raiz)


class AnalizadorSemantico:
    def __init__(self, mostrar_resolucion=True):
        self.mostrar_resolucion = mostrar_resolucion
        self.simbolos = {}
        self.direcciones = {}
        self.pila = []
        self.historial_pila = []
        self.arboles = []
        self.errores = []
        self.salidas = []
        self._scopes = []
        self.linea = 0
        self._lineas = []
        # Lista de palabras reservadas del lenguaje
        self.palabras_reservadas = {
            "num", "msj", "bool", "mostrar", "si", "si_no", "entonces", 
            "mientras", "para", "hasta", "paso", "hacer", "fin", 
            "ecu", "resolver", "y", "o", "no", "verdadero", "falso", "PI", "Eu", "func", "funcion", "retornar", 
            "estructura", "const"
        }

    def registrar_pila(self, accion):
        self.historial_pila.append({
            "linea": self.linea, "accion": accion, "pila": self.pila.copy()
        })

    @staticmethod
    def _sin_cero_negativo(valor):
        return 0.0 if valor == 0 else valor

    @staticmethod
    def _formatear_num(valor):
        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))
        return str(valor)

    def _registrar_texto_resolucion(self, nodo, texto):
        nodo["texto"] = texto
        self.salidas.append(texto)
        if self.mostrar_resolucion:
            print(texto)

    def _evaluar_resolucion(self, nodo):
        """Resuelve una ecuación ya validada por P0.3.c y registra su salida."""
        simbolo = self.simbolos[nodo["destino"]]
        a, b, c = simbolo["coefs"]
        grado = simbolo["grado"]

        if grado == 1:
            if b == 0:
                raise ErrorNumlang("ecuación degenerada en evaluación")
            x = self._sin_cero_negativo(-c / b)
            self._registrar_texto_resolucion(nodo, f"x = {self._formatear_num(x)}")
            return x

        if grado == 2:
            discriminante = b * b - 4 * a * c
            if abs(discriminante) <= TOL_DISCRIMINANTE:
                x = self._sin_cero_negativo(-b / (2 * a))
                self._registrar_texto_resolucion(nodo, f"x = {self._formatear_num(x)}")
                return x
            if discriminante < -TOL_DISCRIMINANTE:
                raise ErrorNumlang("la ecuación no tiene soluciones reales")
            raiz = math.sqrt(discriminante)
            x1 = (-b + raiz) / (2 * a)
            x2 = (-b - raiz) / (2 * a)
            if x1 < x2:
                x1, x2 = x2, x1
            x1 = self._sin_cero_negativo(x1)
            x2 = self._sin_cero_negativo(x2)
            self._registrar_texto_resolucion(
                nodo, f"x = {self._formatear_num(x1)}, x = {self._formatear_num(x2)}"
            )
            return x1, x2

        raise ErrorNumlang(f"grado no soportado en evaluación: {grado}")

    def evaluar(self, nodo):
        """Evalúa un nodo del árbol verificando tipos y usando la pila."""
        if nodo.get("instruccion") == "resolver":
            if nodo.get("valida") is not True:
                return "num", None
            self._evaluar_resolucion(nodo)
            return "num", None
        tipo_nodo = nodo["tipo"]
        if tipo_nodo == "numero":
            valor = nodo["valor"]
            self.pila.append(valor)
            self.registrar_pila(f"PUSH {valor:g}")
            return "num", valor
        if tipo_nodo == "cadena":
            valor = nodo["valor"]
            self.pila.append(valor)
            self.registrar_pila(f'PUSH "{valor}"')
            return "msj", valor
        if tipo_nodo == "booleano":
            valor = nodo["valor"]
            self.pila.append(valor)
            self.registrar_pila(f"PUSH {valor}")
            return "bool", valor
        if tipo_nodo == "variable":
            nombre = nodo["nombre"]
            if self._scopes:
                if nombre not in self._scopes[-1]:
                    raise ErrorNumlang("variable fuera de alcance")
                valor = self._scopes[-1][nombre]
                self.pila.append(valor)
                self.registrar_pila(f"PUSH {nombre}")
                return "num", valor
            if nombre not in self.simbolos:
                raise ErrorNumlang(f"La variable '{nombre}' no está declarada")
            valor = self.simbolos[nombre]["valor"]
            self.pila.append(valor)
            self.registrar_pila(f"PUSH {nombre}")
            return self.simbolos[nombre]["tipo"], valor
        if tipo_nodo == "negativo":
            tipo, _ = self.evaluar(nodo["expresion"])
            if tipo != "num":
                raise ErrorNumlang("El signo negativo requiere un número")
            valor = -self.pila.pop()
            self.pila.append(valor)
            self.registrar_pila("NEG")
            return "num", valor

        if tipo_nodo == "llamada":
            if not self._scopes:
                self._validar_llamada(nodo)
            simbolo = self.simbolos[nodo["nombre"]]
            valores = []
            for argumento in nodo["args"]:
                self.evaluar(argumento)
                valores.append(self.pila.pop())
                self.registrar_pila("Consumir argumento")
            self._scopes.append(dict(zip(simbolo["parametros"], valores)))
            self.registrar_pila(f"PUSH scope {nodo['nombre']}")
            try:
                self.evaluar(simbolo["expresion"])
                resultado = self.pila.pop()
                self.registrar_pila("Consumir resultado de función")
            finally:
                self._scopes.pop()
                self.registrar_pila("POP scope")
            valor = float(resultado)
            self.pila.append(valor)
            self.registrar_pila(f"PUSH resultado {nodo['nombre']}")
            return "num", valor

        tipo_izq, _ = self.evaluar(nodo["izquierda"])
        tipo_der, _ = self.evaluar(nodo["derecha"])
        
        op = nodo["operador"]
        
        if op in ("+", "-", "*", "/", "elevado_a"):
            if tipo_izq != "num" or tipo_der != "num":
                raise ErrorNumlang(f"Tipos incompatibles: la operación '{op}' requiere 'num'")
            b = self.pila.pop()
            a = self.pila.pop()
            if op == "+": valor = a + b
            elif op == "-": valor = a - b
            elif op == "*": valor = a * b
            elif op == "elevado_a": valor = a ** b
            else:
                if b == 0: raise ErrorNumlang("División entre cero")
                valor = a / b
            self.pila.append(valor)
            self.registrar_pila(f"{a:g} {op} {b:g}")
            return "num", valor
            
        elif op in (">", "<", ">=", "<=", "==", "!="):
            if tipo_izq != tipo_der:
                raise ErrorNumlang(f"Tipos incompatibles en comparación: {tipo_izq} vs {tipo_der}")
            b = self.pila.pop()
            a = self.pila.pop()
            if op == ">": valor = a > b
            elif op == "<": valor = a < b
            elif op == ">=": valor = a >= b
            elif op == "<=": valor = a <= b
            elif op == "==": valor = a == b
            elif op == "!=": valor = a != b
            self.pila.append(valor)
            self.registrar_pila(f"{a} {op} {b}")
            return "bool", valor

        raise ErrorNumlang(f"Operador desconocido: {op}")

    def _validar_llamada(self, nodo):
        callee = nodo["nombre"]
        simbolo = self.simbolos.get(callee)
        if simbolo is None: raise ErrorNumlang(f"Función '{callee}' no definida")
        if simbolo.get("tipo") != "func": raise ErrorNumlang(f"'{callee}' no es una función")
        if len(nodo["args"]) != simbolo["n_params"]: raise ErrorNumlang(f"aridad incorrecta en la llamada a '{callee}'")
        for arg in nodo["args"]:
            if arg["tipo"] == "variable" and arg["nombre"] not in self.simbolos: raise ErrorNumlang(f"La variable '{arg['nombre']}' no está declarada")
            if self._tipo_arbol(arg) != "num": raise ErrorNumlang("los argumentos de la llamada deben ser NUM")
        return "num"

    def _tipo_arbol(self, nodo):
        """Tipo Numlang de un nodo, sin evaluar la expresión."""
        tipo = nodo["tipo"]
        if tipo == "numero":
            return "num"
        if tipo == "cadena":
            return "msj"
        if tipo == "booleano":
            return "bool"
        if tipo == "variable":
            simbolo = self.simbolos.get(nodo["nombre"])
            return simbolo["tipo"] if simbolo else "num"
        if tipo == "negativo":
            return "num"
        if tipo == "operacion":
            if nodo["operador"] in (">", "<", ">=", "<=", "==", "!="):
                return "bool"
            return "num"
        if tipo == "llamada":
            return self._validar_llamada(nodo)
        raise ErrorNumlang("Tipo de nodo desconocido en la ecuación")

    def _incognitas_en_arbol(self, nodo, encontradas):
        """Recorre E1/E2 y acumula IDs no declarados, deduplicados por nombre."""
        tipo = nodo["tipo"]
        if tipo == "variable":
            if nodo["nombre"] not in self.simbolos:
                encontradas.add(nodo["nombre"])
            return
        if tipo == "negativo":
            self._incognitas_en_arbol(nodo["expresion"], encontradas)
            return
        if tipo == "operacion":
            self._incognitas_en_arbol(nodo["izquierda"], encontradas)
            self._incognitas_en_arbol(nodo["derecha"], encontradas)

    @staticmethod
    def _podar(polinomio):
        """Elimina coeficientes con |c| < 1e-12."""
        return {grado: c for grado, c in polinomio.items() if abs(c) >= 1e-12}

    @staticmethod
    def _sumar_polinomios(a, b):
        resultado = dict(a)
        for grado, coef in b.items():
            resultado[grado] = resultado.get(grado, 0.0) + coef
        return AnalizadorSemantico._podar(resultado)

    @staticmethod
    def _restar_polinomios(a, b):
        resultado = dict(a)
        for grado, coef in b.items():
            resultado[grado] = resultado.get(grado, 0.0) - coef
        return AnalizadorSemantico._podar(resultado)

    @classmethod
    def _multiplicar_polinomios(cls, a, b):
        resultado = {}
        for ga, ca in a.items():
            for gb, cb in b.items():
                grado = ga + gb
                resultado[grado] = resultado.get(grado, 0.0) + ca * cb
        return cls._podar(resultado)

    def _coeficientes(self, nodo, incognita):
        """Devuelve {grado: coeficiente} del polinomio en `incognita`."""
        tipo = nodo["tipo"]

        if tipo == "numero":
            return self._podar({0: float(nodo["valor"])})

        if tipo == "booleano":
            return self._podar({0: 1.0 if nodo["valor"] else 0.0})

        if tipo == "variable":
            nombre = nodo["nombre"]
            if nombre == incognita:
                return {1: 1.0}
            simbolo = self.simbolos.get(nombre)
            if simbolo is None:
                raise ErrorNumlang(
                    f"El símbolo '{nombre}' no está declarado en la ecuación"
                )
            return self._podar({0: float(simbolo.get("valor") or 0.0)})

        if tipo == "negativo":
            interno = self._coeficientes(nodo["expresion"], incognita)
            return self._podar({g: -c for g, c in interno.items()})

        if tipo == "operacion":
            op = nodo["operador"]
            izq = self._coeficientes(nodo["izquierda"], incognita)
            der = self._coeficientes(nodo["derecha"], incognita)

            if op == "+":
                return self._sumar_polinomios(izq, der)
            if op == "-":
                return self._restar_polinomios(izq, der)
            if op == "*":
                return self._multiplicar_polinomios(izq, der)
            if op == "/":
                if set(der) != {0} or der.get(0, 0.0) == 0.0:
                    raise ErrorNumlang(
                        "El divisor no puede depender de la incógnita ni ser cero"
                    )
                divisor = der[0]
                return self._podar({g: c / divisor for g, c in izq.items()})
            if op == "elevado_a":
                if set(der) != {0}:
                    raise ErrorNumlang("El exponente no puede depender de la incógnita")
                exponente = der[0]
                if not exponente.is_integer() or exponente < 0:
                    raise ErrorNumlang("El exponente debe ser entero no negativo")
                resultado = {0: 1.0}
                for _ in range(int(exponente)):
                    resultado = self._multiplicar_polinomios(resultado, izq)
                return resultado

        raise ErrorNumlang(
            f"Operación no soportada en la ecuación: {nodo.get('operador', tipo)}"
        )

    def ejecutar_instruccion(self, texto):
        texto = texto.strip().removesuffix(";").strip()
        if not texto or texto.startswith("nota:"):
            return

        declaracion = re.fullmatch(r"(num|msj|bool)\s+([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(.+)", texto)
        asignacion = re.fullmatch(r"([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(.+)", texto)
        salida = re.fullmatch(r"mostrar\s+(.+)", texto)
        definicion_func = re.fullmatch(r"func\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*=\s*(.+)", texto)
        definicion_ecu = re.fullmatch(r"ecu\s+([a-zA-Z_]\w*)\s*:\s*([^=]+?)\s*=\s*(.+)", texto)
        resolucion = re.fullmatch(r"resolver\s+([a-zA-Z_]\w*)\s+para\s+([a-zA-Z_]\w*)", texto)

        if declaracion:
            tipo_var, nombre, expresion = declaracion[1], declaracion[2], declaracion[3]
            
            # --- VERIFICACIÓN DE PALABRAS RESERVADAS ---
            if nombre in self.palabras_reservadas:
                raise ErrorNumlang(f"'{nombre}' es una palabra reservada y no puede usarse como nombre de variable")
            
            if nombre in self.simbolos:
                raise ErrorNumlang(f"La variable '{nombre}' ya fue declarada")
            arbol = crear_arbol(expresion)
            tipo_expr, valor = self.evaluar(arbol)
            self.pila.pop()
            self.registrar_pila("Consumir resultado")
            
            if tipo_var != tipo_expr:
                raise ErrorNumlang(f"Tipos incompatibles: se esperaba {tipo_var}, se recibió {tipo_expr}")
            if tipo_var == "num":
                valor = float(valor)
            
            self.direcciones[nombre] = hex(0x1000 + len(self.direcciones) * 8)
            self.simbolos[nombre] = {"tipo": tipo_var, "valor": valor, "scope": "global"}
            self.arboles.append({"linea": self.linea, "instruccion": "declaracion", "destino": nombre, "expresion": arbol})

        elif definicion_func:
            nombre, params_str, cuerpo_str = definicion_func.groups()
            params = [p.strip() for p in params_str.split(",")] if params_str.strip() else []
            for param in params:
                if not re.fullmatch(r"[a-zA-Z_]\w*", param):
                    raise ErrorNumlang(f"Parámetro inválido: '{param}'")
                if param in self.palabras_reservadas:
                    raise ErrorNumlang(f"El parámetro '{param}' es una palabra reservada")
            if len(set(params)) != len(params):
                raise ErrorNumlang("parámetros duplicados en la definición de función")
            if nombre in self.palabras_reservadas:
                raise ErrorNumlang(f"'{nombre}' es una palabra reservada y no puede usarse como nombre de función")
            if nombre in self.simbolos:
                raise ErrorNumlang(f"'{nombre}' ya fue declarada")
            arbol = crear_arbol(cuerpo_str)

            def validar(nodo):
                tipo = nodo["tipo"]
                if tipo == "numero":
                    return "num"
                if tipo == "variable":
                    nombre_var = nodo["nombre"]
                    if nombre_var in params:
                        return "num"
                    if nombre_var in self.simbolos:
                        raise ErrorNumlang("globales no permitidas en el cuerpo de la función")
                    raise ErrorNumlang(f"Variable '{nombre_var}' no declarada")
                if tipo == "negativo":
                    return validar(nodo["expresion"])
                if tipo == "operacion":
                    if nodo["operador"] in (">", "<", ">=", "<=", "==", "!="):
                        raise ErrorNumlang("cuerpo de función debe ser NUM")
                    validar(nodo["izquierda"])
                    validar(nodo["derecha"])
                    return "num"
                if tipo == "llamada":
                    callee = nodo["nombre"]
                    if callee in params: raise ErrorNumlang(f"'{callee}' es un parámetro, no una función")
                    if callee == nombre:
                        raise ErrorNumlang("recursión no permitida en la definición de función")
                    simbolo = self.simbolos.get(callee)
                    if simbolo is None or simbolo.get("tipo") != "func":
                        raise ErrorNumlang(f"Función '{callee}' no definida")
                    if len(nodo["args"]) != simbolo["n_params"]:
                        raise ErrorNumlang(f"aridad incorrecta en la llamada a '{callee}'")
                    for arg in nodo["args"]:
                        validar(arg)
                    return "num"
                raise ErrorNumlang("cuerpo de función debe ser NUM")

            validar(arbol)
            self.simbolos[nombre] = {
                "tipo": "func",
                "parametros": params,
                "n_params": len(params),
                "expresion": arbol,
                "scope": "global",
                "valor": None,
            }
            self.arboles.append({
                "linea": self.linea,
                "instruccion": "func",
                "destino": nombre,
                "parametros": params,
                "expresion": arbol,
            })

        elif definicion_ecu:
            nombre, expr_izq, expr_der = definicion_ecu.groups()
            if nombre in self.palabras_reservadas:
                raise ErrorNumlang(f"'{nombre}' es una palabra reservada y no puede usarse como nombre de ecuación")

            arbol_izq = crear_arbol(expr_izq)
            arbol_der = crear_arbol(expr_der)

            pila_nodos = [arbol_izq, arbol_der]
            while pila_nodos:
                nodo = pila_nodos.pop()
                if nodo["tipo"] == "llamada": raise ErrorNumlang("llamadas a funciones no permitidas dentro de una ecuación")
                if nodo["tipo"] == "negativo": pila_nodos.append(nodo["expresion"])
                elif nodo["tipo"] == "operacion": pila_nodos.extend((nodo["izquierda"], nodo["derecha"]))

            tipo_izq = self._tipo_arbol(arbol_izq)
            tipo_der = self._tipo_arbol(arbol_der)
            if tipo_izq != "num" or tipo_der != "num":
                raise ErrorNumlang(
                    f"tipos no NUM en la ecuación: {tipo_izq} = {tipo_der}"
                )

            incognitas = set()
            self._incognitas_en_arbol(arbol_izq, incognitas)
            self._incognitas_en_arbol(arbol_der, incognitas)
            if not incognitas:
                raise ErrorNumlang("no hay incógnita en la ecuación")
            if len(incognitas) > 1:
                raise ErrorNumlang(
                    "la ecuación tiene más de una incógnita: "
                    + ", ".join(sorted(incognitas))
                )
            incognita = next(iter(incognitas))

            diferencia = {
                "tipo": "operacion",
                "operador": "-",
                "izquierda": arbol_izq,
                "derecha": arbol_der,
            }
            polinomio = self._podar(self._coeficientes(diferencia, incognita))
            if not polinomio:
                raise ErrorNumlang("ecuación degenerada")

            grado = max(polinomio)
            if grado > 2:
                raise ErrorNumlang(f"grado mayor a 2: {grado}")

            coefs = (
                polinomio.get(2, 0.0),
                polinomio.get(1, 0.0),
                polinomio.get(0, 0.0),
            )
            self.simbolos[nombre] = {
                "tipo": "ecu",
                "incognita": incognita,
                "grado": grado,
                "coefs": coefs,
                "lado_izq": expr_izq,
                "lado_der": expr_der,
                "scope": "global",
                "valor": None,
            }
            self.direcciones[nombre] = hex(0x1000 + len(self.direcciones) * 8)
            self.arboles.append({
                "linea": self.linea,
                "instruccion": "ecu",
                "destino": nombre,
                "expresion": {"izquierda": arbol_izq, "derecha": arbol_der},
            })
            
        elif resolucion:
            id_ecu, id_incognita = resolucion.groups()
            if id_ecu in self.palabras_reservadas:
                raise ErrorNumlang("La resolución no puede usar palabras reservadas como identificadores")
            if id_ecu not in self.simbolos:
                raise ErrorNumlang(f"la ecuación '{id_ecu}' no está declarada")
            simbolo_ecu = self.simbolos[id_ecu]
            if simbolo_ecu.get("tipo") != "ecu":
                raise ErrorNumlang(f"'{id_ecu}' no es una ecuación")
            if id_incognita != simbolo_ecu.get("incognita"):
                raise ErrorNumlang(
                    f"'{id_incognita}' no es la incógnita de '{id_ecu}' "
                    f"(la incógnita es '{simbolo_ecu.get('incognita')}')"
                )
            if id_incognita in self.palabras_reservadas:
                raise ErrorNumlang("La resolución no puede usar palabras reservadas como identificadores")
            nodo_resolver = {
                "linea": self.linea,
                "instruccion": "resolver",
                "destino": id_ecu,
                "expresion": id_incognita,
                "valida": True,
            }
            self.arboles.append(nodo_resolver)
            self.evaluar(nodo_resolver)
            
        elif asignacion:
            nombre, expresion = asignacion[1], asignacion[2]
            if nombre not in self.simbolos:
                raise ErrorNumlang(f"La variable '{nombre}' no está declarada")
            arbol = crear_arbol(expresion)
            tipo_expr, valor = self.evaluar(arbol)
            self.pila.pop()
            self.registrar_pila("Consumir resultado")
            if self.simbolos[nombre]["tipo"] != tipo_expr:
                raise ErrorNumlang(f"Tipos incompatibles en asignación: {nombre} es {self.simbolos[nombre]['tipo']}, se recibió {tipo_expr}")
            if self.simbolos[nombre]["tipo"] == "num":
                valor = float(valor)
            self.simbolos[nombre]["valor"] = valor
            self.arboles.append({"linea": self.linea, "instruccion": "asignacion", "destino": nombre, "expresion": arbol})
            
        elif salida:
            expresion = salida[1]
            arbol = crear_arbol(expresion)
            tipo_expr, valor = self.evaluar(arbol)
            self.pila.pop()
            self.registrar_pila("Consumir resultado")
            self.salidas.append(valor)
            self.arboles.append({"linea": self.linea, "instruccion": "mostrar", "destino": None, "expresion": arbol})
        else:
            raise ErrorNumlang(f"Instrucción no reconocida: '{texto}'")

    def analizar(self, codigo):
        self._lineas = []
        for num, texto in enumerate(codigo.splitlines(), start=1):
            limpia = texto.strip().removesuffix(";").strip()
            if limpia and not limpia.startswith("nota:"):
                self._lineas.append((num, limpia))
        
        self._procesar_bloque(0, len(self._lineas))
        
        return {
            "valido": not self.errores,
            "arboles": self.arboles,
            "tabla_simbolos": self.simbolos,
            "tabla_direcciones": self.direcciones,
            "historial_pila": self.historial_pila,
            "salidas": self.salidas,
            "errores": self.errores,
        }

    def _procesar_bloque(self, inicio, fin):
        i = inicio
        while i < fin:
            num_linea, texto = self._lineas[i]
            self.linea = num_linea
            
            # 1. Estructura condicional (si)
            m_si = re.fullmatch(r"si\s+(.+?)(?:\s+entonces)?", texto)
            if m_si:
                cond_str = m_si.group(1)
                idx_sino, idx_fin = self._buscar_cierre(i)
                try:
                    arbol_cond = crear_arbol(cond_str)
                    tipo, _ = self.evaluar(arbol_cond)
                    self.pila.pop() 
                    self.registrar_pila("Consumir condicion")
                    if tipo != "bool":
                        raise ErrorNumlang(f"La condición del 'si' debe ser booleana, se recibió {tipo}")
                except ErrorNumlang as e:
                    self.errores.append(f"Línea {num_linea}: {e}")
                
                self._procesar_bloque(i + 1, idx_sino if idx_sino != -1 else idx_fin)
                if idx_sino != -1:
                    self._procesar_bloque(idx_sino + 1, idx_fin)
                
                i = idx_fin + 1
                continue

            # 2. Ciclo mientras
            m_mientras = re.fullmatch(r"mientras\s+(.+?)(?:\s+hacer)?", texto)
            if m_mientras:
                cond_str = m_mientras.group(1)
                _, idx_fin = self._buscar_cierre(i)
                try:
                    arbol_cond = crear_arbol(cond_str)
                    tipo, _ = self.evaluar(arbol_cond)
                    self.pila.pop()
                    self.registrar_pila("Consumir condicion mientras")
                    if tipo != "bool":
                        raise ErrorNumlang(f"La condición del 'mientras' debe ser booleana, se recibió {tipo}")
                except ErrorNumlang as e:
                    self.errores.append(f"Línea {num_linea}: {e}")
                
                self._procesar_bloque(i + 1, idx_fin)
                i = idx_fin + 1
                continue

            # 3. Ciclo para
            m_para = re.fullmatch(r"para\s+(?:num\s+)?([a-zA-Z_]\w*)\s*=\s*(.+?)\s+hasta\s+(.+?)(?:\s+paso\s+(.+?))?(?:\s+hacer)?", texto)
            if m_para:
                var_ctrl, ini_str, lim_str, paso_str = m_para.groups()
                
                # --- VERIFICACIÓN DE PALABRAS RESERVADAS EN CICLO PARA ---
                if var_ctrl in self.palabras_reservadas:
                    self.errores.append(f"Línea {num_linea}: '{var_ctrl}' es una palabra reservada y no puede usarse como variable")
                    # Saltamos el bloque para evitar más errores en cascada
                    _, idx_fin = self._buscar_cierre(i)
                    i = idx_fin + 1
                    continue
                
                _, idx_fin = self._buscar_cierre(i)
                try:
                    arbol_ini = crear_arbol(ini_str)
                    tipo_ini, val_ini = self.evaluar(arbol_ini)
                    self.pila.pop()
                    self.registrar_pila("Consumir inicio para")
                    if tipo_ini != "num":
                        raise ErrorNumlang(f"El inicio del 'para' debe ser num, se recibió {tipo_ini}")
                    
                    arbol_lim = crear_arbol(lim_str)
                    tipo_lim, val_lim = self.evaluar(arbol_lim)
                    self.pila.pop()
                    self.registrar_pila("Consumir limite para")
                    if tipo_lim != "num":
                        raise ErrorNumlang(f"El límite del 'para' debe ser num, se recibió {tipo_lim}")
                    
                    if var_ctrl not in self.simbolos:
                        self.direcciones[var_ctrl] = hex(0x1000 + len(self.direcciones) * 8)
                        self.simbolos[var_ctrl] = {"tipo": "num", "valor": val_ini, "scope": "global"}
                    else:
                        if self.simbolos[var_ctrl]["tipo"] != "num":
                            raise ErrorNumlang(f"La variable de control '{var_ctrl}' debe ser de tipo num")
                        self.simbolos[var_ctrl]["valor"] = val_ini

                    if paso_str:
                        arbol_paso = crear_arbol(paso_str)
                        tipo_paso, _ = self.evaluar(arbol_paso)
                        self.pila.pop()
                        self.registrar_pila("Consumir paso para")
                        if tipo_paso != "num":
                            raise ErrorNumlang(f"El paso del 'para' debe ser num, se recibió {tipo_paso}")
                except ErrorNumlang as e:
                    self.errores.append(f"Línea {num_linea}: {e}")
                
                self._procesar_bloque(i + 1, idx_fin)
                i = idx_fin + 1
                continue

            # 4. Instrucciones simples
            try:
                self.ejecutar_instruccion(texto)
            except ErrorNumlang as e:
                self.errores.append(f"Línea {num_linea}: {e}")
                self.pila.clear()
            i += 1

    def _buscar_cierre(self, indice_inicio):
        nivel = 1
        idx_sino = -1
        APERTURAS = ("si ", "mientras ", "para ")
        for i in range(indice_inicio + 1, len(self._lineas)):
            _, texto = self._lineas[i]
            if any(texto.startswith(pref) for pref in APERTURAS):
                nivel += 1
            elif texto == "si_no" and nivel == 1:
                idx_sino = i
            elif texto == "fin":
                nivel -= 1
                if nivel == 0:
                    return idx_sino, i
        raise ErrorNumlang(f"Bloque sin 'fin' en línea {self._lineas[indice_inicio][0]}")


def analizar_codigo(codigo, mostrar_resolucion=True):
    return AnalizadorSemantico(mostrar_resolucion=mostrar_resolucion).analizar(codigo)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analizador_semantico.py <archivo.src> [--json]")
        sys.exit(1)
    archivo = Path(sys.argv[1])
    try:
        programa = archivo.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"No se pudo leer el archivo: {exc}")
        sys.exit(1)
        
    resultado = analizar_codigo(programa)
    if len(sys.argv) == 3 and sys.argv[2] == "--json":
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        print("ESTADO:", "CORRECTO" if resultado["valido"] else "CON ERRORES")
        if resultado["errores"]:
            print("\nERRORES:")
            for e in resultado["errores"]: print(" -", e)
        else:
            print("\nTABLA DE SIMBOLOS:")
            for n, info in resultado["tabla_simbolos"].items():
                print(f"  {n}: {info['tipo']} = {info['valor']}, scope={info['scope']}")
            print("SALIDAS:", resultado["salidas"])
    sys.exit(0 if resultado["valido"] else 1)