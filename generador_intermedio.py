"""Numlang - Integrante 2: Generador de Código Intermedio (Tres Direcciones).

Integrado con el analizador semántico del Integrante 1.
"""

import ast
import json
import re
import sys
from pathlib import Path

# IMPORTACIÓN DEL INTEGRANTE 1
from analizador_semantico import analizar_codigo, ErrorNumlang

# =====================================================================
# 1. CONVERSIÓN DE NOTACIONES (INFIJA, PREFIJA Y POSTFIJA)
# =====================================================================

PRECEDENCIA = {
    "o": 1, "y": 2, "no": 3,
    "==": 4, "!=": 4, "<": 4, ">": 4, "<=": 4, ">=": 4,
    "igual_a": 4, "diferente_de": 4, "menor_que": 4, "mayor_que": 4,
    "+": 5, "-": 5, "*": 6, "/": 6, "residuo_de": 6, "%": 6,
    "elevado_a": 7, "**": 7, "NEG": 8,
}
ASOCIATIVIDAD_DERECHA = {"elevado_a", "**", "no", "NEG"}


def tokenizar_expresion(expresion: str) -> list[str]:
    """Divide una expresión de Numlang en tokens respetando palabras clave y cadenas."""
    patron = (
        r'"[^"]*"|\'[^\']*\'|'
        r'\b(?:elevado_a|residuo_de|igual_a|diferente_de|menor_que|mayor_que|y|o|no)\b|'
        r'<=|>=|==|!=|\*\*|'
        r'[a-zA-Z_][a-zA-Z_0-9]*(?:\.[a-zA-Z_][a-zA-Z_0-9]*)?|'
        r'\d+(?:\.\d+)?|'
        r'[+\-*/%<>()]'
    )
    return re.findall(patron, expresion)


def infija_a_postfija(expresion: str) -> str:
    """Convierte una expresión infija a notación Postfija (Polaca Inversa) con Shunting-Yard."""
    tokens = tokenizar_expresion(expresion)
    salida = []
    pila_ops = []

    for i, token in enumerate(tokens):
        if token == "-" and (i == 0 or tokens[i - 1] in PRECEDENCIA or tokens[i - 1] == "("):
            token = "NEG"

        if token not in PRECEDENCIA and token not in ("(", ")"):
            salida.append(token)
        elif token == "(":
            pila_ops.append(token)
        elif token == ")":
            while pila_ops and pila_ops[-1] != "(":
                salida.append(pila_ops.pop())
            if not pila_ops:
                raise ErrorNumlang("Paréntesis desbalanceados en la expresión")
            pila_ops.pop()
        else:
            while (
                pila_ops
                and pila_ops[-1] != "("
                and (
                    PRECEDENCIA[pila_ops[-1]] > PRECEDENCIA[token]
                    or (
                        PRECEDENCIA[pila_ops[-1]] == PRECEDENCIA[token]
                        and token not in ASOCIATIVIDAD_DERECHA
                    )
                )
            ):
                salida.append(pila_ops.pop())
            pila_ops.append(token)

    while pila_ops:
        op = pila_ops.pop()
        if op in ("(", ")"):
            raise ErrorNumlang("Paréntesis desbalanceados en la expresión")
        salida.append(op)

    return " ".join(salida)


def infija_a_prefija(expresion: str) -> str:
    """Convierte una expresión infija a notación Prefija (Polaca)."""
    tokens = tokenizar_expresion(expresion)
    pila_ops = []
    pila_operandos = []

    def construir_subexpresion():
        op = pila_ops.pop()
        if op in ("no", "NEG"):
            operando = pila_operandos.pop()
            simbolo = "-" if op == "NEG" else op
            pila_operandos.append(f"{simbolo} {operando}")
        else:
            der = pila_operandos.pop()
            izq = pila_operandos.pop()
            pila_operandos.append(f"{op} {izq} {der}")

    for i, token in enumerate(tokens):
        if token == "-" and (i == 0 or tokens[i - 1] in PRECEDENCIA or tokens[i - 1] == "("):
            token = "NEG"

        if token not in PRECEDENCIA and token not in ("(", ")"):
            pila_operandos.append(token)
        elif token == "(":
            pila_ops.append(token)
        elif token == ")":
            while pila_ops and pila_ops[-1] != "(":
                construir_subexpresion()
            pila_ops.pop()
        else:
            while (
                pila_ops
                and pila_ops[-1] != "("
                and (
                    PRECEDENCIA[pila_ops[-1]] > PRECEDENCIA[token]
                    or (
                        PRECEDENCIA[pila_ops[-1]] == PRECEDENCIA[token]
                        and token not in ASOCIATIVIDAD_DERECHA
                    )
                )
            ):
                construir_subexpresion()
            pila_ops.append(token)

    while pila_ops:
        construir_subexpresion()

    return pila_operandos[-1] if pila_operandos else ""


def postfija_a_infija(postfija: str) -> str:
    """Reconstruye una expresión infija a partir de su representación postfija."""
    pila = []
    for token in postfija.split():
        if token in ("no", "NEG"):
            op1 = pila.pop()
            pila.append(f"(-{op1})" if token == "NEG" else f"(no {op1})")
        elif token in PRECEDENCIA:
            der = pila.pop()
            izq = pila.pop()
            pila.append(f"({izq} {token} {der})")
        else:
            pila.append(token)
    return pila[0] if pila else ""


def convertir_notaciones(expresion: str) -> dict:
    """Devuelve las tres representaciones (infija, prefija y postfija) de una expresión."""
    return {
        "infija": expresion.strip(),
        "prefija": infija_a_prefija(expresion),
        "postfija": infija_a_postfija(expresion),
    }


# =====================================================================
# 2. ÁRBOL SINTÁCTICO EXTENDIDO PARA NUMLANG
# =====================================================================

REEMPLAZOS_OPERADORES = [
    (r"\belevado_a\b", "**"),
    (r"\bresiduo_de\b", "%"),
    (r"\bigual_a\b", "=="),
    (r"\bdiferente_de\b", "!="),
    (r"\bmenor_que\b", "<"),
    (r"\bmayor_que\b", ">"),
    (r"\by\b", "and"),
    (r"\bo\b", "or"),
    (r"\bno\b", "not"),
    (r"\bverdadero\b", "True"),
    (r"\bfalso\b", "False"),
]

MAPEO_INVERSO_OP = {
    "**": "elevado_a",
    "%": "residuo_de",
    "and": "y",
    "or": "o",
    "not": "no",
}


def normalizar_expresion_numlang(expr: str) -> str:
    """Traduce operadores verbales de Numlang a operadores válidos para el parser AST."""
    partes = re.split(r'("[^"]*"|\'[^\']*\')', expr)
    for i in range(0, len(partes), 2):
        for patron, reemplazo in REEMPLAZOS_OPERADORES:
            partes[i] = re.sub(patron, reemplazo, partes[i])
    return "".join(partes)


def crear_arbol_extendido(expresion: str) -> dict:
    """Construye el árbol de expresión compatible con el formato del Integrante 1."""
    expr_limpia = normalizar_expresion_numlang(expresion.strip())
    try:
        raiz = ast.parse(expr_limpia, mode="eval").body
    except SyntaxError as exc:
        raise ErrorNumlang(f"Expresión mal escrita: '{expresion}'") from exc

    op_binarias = {
        ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
        ast.Mod: "residuo_de", ast.Pow: "elevado_a",
    }
    op_relacionales = {
        ast.Gt: ">", ast.Lt: "<", ast.GtE: ">=", ast.LtE: "<=",
        ast.Eq: "==", ast.NotEq: "!=",
    }
    op_logicas = {ast.And: "y", ast.Or: "o"}

    def convertir(nodo):
        if isinstance(nodo, ast.Constant):
            if isinstance(nodo.value, bool):
                return {"tipo": "booleano", "valor": "verdadero" if nodo.value else "falso"}
            if isinstance(nodo.value, (int, float)):
                return {"tipo": "numero", "valor": float(nodo.value)}
            if isinstance(nodo.value, str):
                return {"tipo": "cadena", "valor": nodo.value}
        if isinstance(nodo, ast.Name):
            return {"tipo": "variable", "nombre": nodo.id}
        if isinstance(nodo, ast.Attribute) and isinstance(nodo.value, ast.Name):
            return {"tipo": "variable", "nombre": f"{nodo.value.id}.{nodo.attr}"}
        if isinstance(nodo, ast.BinOp) and type(nodo.op) in op_binarias:
            return {
                "tipo": "operacion",
                "operador": op_binarias[type(nodo.op)],
                "izquierda": convertir(nodo.left),
                "derecha": convertir(nodo.right),
            }
        if isinstance(nodo, ast.Compare) and len(nodo.ops) == 1:
            op_tipo = type(nodo.ops[0])
            if op_tipo in op_relacionales:
                return {
                    "tipo": "operacion",
                    "operador": op_relacionales[op_tipo],
                    "izquierda": convertir(nodo.left),
                    "derecha": convertir(nodo.comparators[0]),
                }
        if isinstance(nodo, ast.BoolOp) and type(nodo.op) in op_logicas:
            actual = convertir(nodo.values[0])
            for siguiente in nodo.values[1:]:
                actual = {
                    "tipo": "operacion",
                    "operador": op_logicas[type(nodo.op)],
                    "izquierda": actual,
                    "derecha": convertir(siguiente),
                }
            return actual
        if isinstance(nodo, ast.UnaryOp):
            if isinstance(nodo.op, ast.USub):
                return {"tipo": "negativo", "expresion": convertir(nodo.operand)}
            if isinstance(nodo.op, ast.Not):
                return {"tipo": "negacion_logica", "expresion": convertir(nodo.operand)}
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            return {
                "tipo": "llamada_funcion",
                "nombre": nodo.func.id,
                "argumentos": [convertir(arg) for arg in nodo.args],
            }
        raise ErrorNumlang(f"Operación no soportada en la expresión: {expresion}")

    return convertir(raiz)


# =====================================================================
# 3. GENERADOR DE CÓDIGO INTERMEDIO (CUÁDRUPLOS, TRIPLETAS Y CÓDIGO P)
# =====================================================================

class GeneradorCodigoIntermedio:
    """Genera código de tres direcciones en cuádrupletas, tripletas y código P."""

    def __init__(self):
        self.cuadruplos = []
        self.contador_temp = 0
        self.contadores_etiquetas = {}
        self.notaciones_registradas = []
        self.estructuras = {}

    def nuevoTemp(self) -> str:
        """Genera una nueva variable temporal (t1, t2, t3, ...)."""
        self.contador_temp += 1
        return f"t{self.contador_temp}"

    def nuevaEtiqueta(self, base: str = "L") -> str:
        """Genera etiquetas semánticas (Lfalso, Lfin, Linicio, ...)."""
        conteo = self.contadores_etiquetas.get(base, 0) + 1
        self.contadores_etiquetas[base] = conteo
        return base if conteo == 1 else f"{base}{conteo}"

    def gen(self, op: str, arg1: str = "-", arg2: str = "-", res: str = "-", descripcion: str = "") -> int:
        """Emite una cuádrupleta (op, arg1, arg2, res) y la almacena en la tabla."""
        indice = len(self.cuadruplos) + 1
        equivalente = self._formatear_equivalente(op, str(arg1), str(arg2), str(res))
        self.cuadruplos.append({
            "num": indice,
            "op": str(op),
            "arg1": str(arg1),
            "arg2": str(arg2),
            "res": str(res),
            "instruccion_equivalente": equivalente,
            "descripcion": descripcion or equivalente,
        })
        return indice

    @staticmethod
    def _formatear_equivalente(op: str, arg1: str, arg2: str, res: str) -> str:
        if op == "=":
            return f"{res} = {arg1}"
        if op in ("neg", "no"):
            simbolo = "-" if op == "neg" else "no "
            return f"{res} = {simbolo}{arg1}"
        if op == "if_false":
            return f"if_false {arg1} goto {res}"
        if op == "goto":
            return f"goto {res}"
        if op == "etiqueta":
            return f"{res}:"
        if op == "mostrar":
            return f"mostrar {arg1}"
        if op == "param":
            return f"param {arg1}"
        if op == "param_recibir":
            return f"recibir_param {res}"
        if op == "llamar":
            return f"{res} = llamar {arg1}, {arg2}" if res != "-" else f"llamar {arg1}, {arg2}"
        if op == "retornar":
            return f"retornar {arg1}"
        if op == "campo_estructura":
            return f"{res}.{arg1} ({arg2})"
        return f"{res} = {arg1} {op} {arg2}"

    def _registrar_notacion(self, expresion_str: str):
        try:
            self.notaciones_registradas.append(convertir_notaciones(expresion_str))
        except ErrorNumlang:
            pass

    def generar_expresion(self, nodo: dict) -> str:
        """Recorre el árbol de expresión en postorden emitiendo cuádrupletas."""
        tipo = nodo["tipo"]
        if tipo == "numero":
            return f"{nodo['valor']:g}"
        if tipo == "cadena":
            return f'"{nodo["valor"]}"'
        if tipo == "booleano":
            return nodo["valor"]
        if tipo == "variable":
            return nodo["nombre"]
        if tipo == "negativo":
            lugar = self.generar_expresion(nodo["expresion"])
            temp = self.nuevoTemp()
            self.gen("neg", lugar, "-", temp, f"Cambio de signo -{lugar}")
            return temp
        if tipo == "negacion_logica":
            lugar = self.generar_expresion(nodo["expresion"])
            temp = self.nuevoTemp()
            self.gen("no", lugar, "-", temp, f"Negación lógica no {lugar}")
            return temp
        if tipo == "llamada_funcion":
            lugares_args = [self.generar_expresion(arg) for arg in nodo["argumentos"]]
            for lugar_arg in lugares_args:
                self.gen("param", lugar_arg, "-", "-", f"Pasa parámetro {lugar_arg}")
            temp = self.nuevoTemp()
            self.gen(
                "llamar", nodo["nombre"], str(len(lugares_args)), temp,
                f"Invoca función {nodo['nombre']} con {len(lugares_args)} argumento(s)"
            )
            return temp
        if tipo == "operacion":
            izq = self.generar_expresion(nodo["izquierda"])
            der = self.generar_expresion(nodo["derecha"])
            temp = self.nuevoTemp()
            op = nodo["operador"]
            desc = f"Evalúa {izq} {op} {der}"
            self.gen(op, izq, der, temp, desc)
            return temp
        raise ErrorNumlang(f"Nodo de expresión desconocido: {tipo}")

    # -----------------------------------------------------------------
    # PARSER ESTRUCTURADO DE BLOQUES PARA NUMLANG
    # -----------------------------------------------------------------

    def compilar_programa(self, codigo: str) -> dict:
        """Procesa un programa completo en Numlang y genera todas las representaciones."""
        # --- INTEGRACIÓN: LLAMADA AL ANALIZADOR SEMÁNTICO ---
        resultado_semantico = analizar_codigo(codigo)
        if not resultado_semantico["valido"]:
            raise ErrorNumlang("Errores semánticos detectados:\n" + "\n".join(resultado_semantico["errores"]))

        lineas_limpias = []
        for num_linea, texto in enumerate(codigo.splitlines(), start=1):
            limpia = texto.strip().removesuffix(";").strip()
            if not limpia or limpia.startswith("nota:"):
                continue
            lineas_limpias.append((num_linea, limpia))

        self._procesar_bloque(lineas_limpias, 0, len(lineas_limpias))

        return {
            "valido": True,
            "notaciones": self.notaciones_registradas,
            "cuadruplos": self.cuadruplos,
            "tripletas": self.generar_tripletas(),
            "codigo_p": self.generar_codigo_p(),
            "codigo_tres_direcciones": [c["instruccion_equivalente"] for c in self.cuadruplos],
            "tabla_simbolos_semantica": resultado_semantico["tabla_simbolos"]
        }

    def _buscar_cierre_bloque(self, lineas: list, indice_inicio: int) -> tuple[int, int]:
        """Encuentra el índice de 'si_no' (si existe al mismo nivel) y el 'fin' correspondiente."""
        nivel = 1
        indice_sino = -1
        APERTURAS = ("si ", "mientras ", "para ", "funcion ", "estructura ")

        for i in range(indice_inicio + 1, len(lineas)):
            _, texto = lineas[i]
            if any(texto.startswith(pref) for pref in APERTURAS):
                nivel += 1
            elif texto == "si_no" and nivel == 1:
                indice_sino = i
            elif texto == "fin":
                nivel -= 1
                if nivel == 0:
                    return indice_sino, i
        raise ErrorNumlang(f"Bloque abierto en línea {lineas[indice_inicio][0]} sin instrucción 'fin'")

    def _procesar_bloque(self, lineas: list, inicio: int, fin: int):
        i = inicio
        while i < fin:
            num_linea, texto = lineas[i]

            # 1. ESTRUCTURA CONDICIONAL
            m_si = re.fullmatch(r"si\s+(.+?)(?:\s+entonces)?", texto)
            if m_si:
                cond_str = m_si.group(1)
                self._registrar_notacion(cond_str)
                arbol_cond = crear_arbol_extendido(cond_str)
                lugar_cond = self.generar_expresion(arbol_cond)

                idx_sino, idx_fin = self._buscar_cierre_bloque(lineas, i)
                etq_falso = self.nuevaEtiqueta("Lfalso")

                self.gen("if_false", lugar_cond, "-", etq_falso, f"Si {lugar_cond} es falso, salta a {etq_falso}")

                if idx_sino != -1:
                    etq_fin = self.nuevaEtiqueta("Lfin")
                    self._procesar_bloque(lineas, i + 1, idx_sino)
                    self.gen("goto", "-", "-", etq_fin, "Salta al final del bloque condicional")
                    self.gen("etiqueta", "-", "-", etq_falso, "Inicio del bloque si_no")
                    self._procesar_bloque(lineas, idx_sino + 1, idx_fin)
                    self.gen("etiqueta", "-", "-", etq_fin, "Marca el fin del condicional")
                else:
                    self._procesar_bloque(lineas, i + 1, idx_fin)
                    self.gen("etiqueta", "-", "-", etq_falso, "Marca el fin del condicional")

                i = idx_fin + 1
                continue

            # 2. CICLO MIENTRAS
            m_mientras = re.fullmatch(r"mientras\s+(.+?)(?:\s+hacer)?", texto)
            if m_mientras:
                cond_str = m_mientras.group(1)
                self._registrar_notacion(cond_str)
                _, idx_fin = self._buscar_cierre_bloque(lineas, i)

                etq_inicio = self.nuevaEtiqueta("Linicio")
                etq_fin = self.nuevaEtiqueta("Lfin")

                self.gen("etiqueta", "-", "-", etq_inicio, "Inicio del ciclo mientras")
                arbol_cond = crear_arbol_extendido(cond_str)
                lugar_cond = self.generar_expresion(arbol_cond)
                self.gen("if_false", lugar_cond, "-", etq_fin, f"Si {lugar_cond} es falso, sale a {etq_fin}")

                self._procesar_bloque(lineas, i + 1, idx_fin)
                self.gen("goto", "-", "-", etq_inicio, f"Regresa a evaluar el ciclo en {etq_inicio}")
                self.gen("etiqueta", "-", "-", etq_fin, "Fin del ciclo mientras")

                i = idx_fin + 1
                continue

            # 3. CICLO PARA
            m_para = re.fullmatch(
                r"para\s+(?:num\s+)?([a-zA-Z_]\w*)\s*=\s*(.+?)\s+hasta\s+(.+?)(?:\s+paso\s+(.+?))?(?:\s+hacer)?",
                texto,
            )
            if m_para:
                var_ctrl, ini_str, lim_str, paso_str = m_para.groups()
                paso_str = paso_str or "1"
                _, idx_fin = self._buscar_cierre_bloque(lineas, i)

                arbol_paso = crear_arbol_extendido(paso_str)
                paso_negativo = (
                    arbol_paso["tipo"] == "negativo"
                    or (arbol_paso["tipo"] == "numero" and arbol_paso["valor"] < 0)
                )
                operador_condicion = ">=" if paso_negativo else "<="
                simbolo_condicion = ">=" if paso_negativo else "<="

                lugar_ini = self.generar_expresion(crear_arbol_extendido(ini_str))
                self.gen("=", lugar_ini, "-", var_ctrl, f"Inicialización ciclo para {var_ctrl} = {lugar_ini}")

                etq_inicio = self.nuevaEtiqueta("Linicio")
                etq_fin = self.nuevaEtiqueta("Lfin")
                self.gen("etiqueta", "-", "-", etq_inicio, "Inicio de evaluación del ciclo para")

                lugar_lim = self.generar_expresion(crear_arbol_extendido(lim_str))
                temp_cond = self.nuevoTemp()
                self.gen(operador_condicion, var_ctrl, lugar_lim, temp_cond, f"Compara condición de parada {var_ctrl} {simbolo_condicion} {lugar_lim}")
                self.gen("if_false", temp_cond, "-", etq_fin, f"Si {temp_cond} es falso, termina el ciclo en {etq_fin}")

                self._procesar_bloque(lineas, i + 1, idx_fin)

                lugar_paso = self.generar_expresion(arbol_paso)
                temp_inc = self.nuevoTemp()
                self.gen("+", var_ctrl, lugar_paso, temp_inc, f"Incrementa variable de control {var_ctrl}")
                self.gen("=", temp_inc, "-", var_ctrl, f"Actualiza {var_ctrl} = {temp_inc}")
                self.gen("goto", "-", "-", etq_inicio, f"Siguiente iteración en {etq_inicio}")
                self.gen("etiqueta", "-", "-", etq_fin, "Fin del ciclo para")

                i = idx_fin + 1
                continue

            # 4. DECLARACIÓN DE FUNCIÓN
            m_func = re.fullmatch(r"funcion\s+([a-zA-Z_]\w*)\s*\((.*?)\)", texto)
            if m_func:
                nombre_fn, params_raw = m_func.groups()
                _, idx_fin = self._buscar_cierre_bloque(lineas, i)

                self.gen("etiqueta", "-", "-", f"func_{nombre_fn}", f"Inicio de función {nombre_fn}")
                if params_raw.strip():
                    for param in params_raw.split(","):
                        tokens_p = param.strip().split()
                        nombre_p = tokens_p[-1]
                        self.gen("param_recibir", "-", "-", nombre_p, f"Recibe parámetro {nombre_p}")

                self._procesar_bloque(lineas, i + 1, idx_fin)
                self.gen("etiqueta", "-", "-", f"fin_func_{nombre_fn}", f"Fin de función {nombre_fn}")

                i = idx_fin + 1
                continue

            # 5. DECLARACIÓN DE ESTRUCTURA
            m_est = re.fullmatch(r"estructura\s+([a-zA-Z_]\w*)", texto)
            if m_est:
                nombre_est = m_est.group(1)
                _, idx_fin = self._buscar_cierre_bloque(lineas, i)
                self.estructuras[nombre_est] = []
                for k in range(i + 1, idx_fin):
                    _, linea_campo = lineas[k]
                    m_campo = re.fullmatch(r"(num|msj|bool)\s+([a-zA-Z_]\w*)", linea_campo)
                    if m_campo:
                        tipo_c, nom_c = m_campo.groups()
                        self.estructuras[nombre_est].append((nom_c, tipo_c))
                        self.gen("campo_estructura", nom_c, tipo_c, nombre_est, f"Define campo {nom_c} ({tipo_c})")
                i = idx_fin + 1
                continue

            # 6. INSTRUCCIONES SIMPLES
            self._procesar_instruccion_simple(texto)
            i += 1

    def _procesar_instruccion_simple(self, texto: str):
        m_decl = re.fullmatch(r"(?:const\s+)?(num|msj|bool)\s+([a-zA-Z_]\w*)\s*=\s*(.+)", texto)
        m_asig = re.fullmatch(r"([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?)\s*=\s*(.+)", texto)
        m_mostrar = re.fullmatch(r"mostrar\s+(.+)", texto)
        m_retornar = re.fullmatch(r"retornar\s+(.+)", texto)
        m_llamar = re.fullmatch(r"llamar\s+([a-zA-Z_]\w*)\s*\((.*?)\)", texto)

        if m_decl:
            tipo_var, nombre, expr_str = m_decl.groups()
            self._registrar_notacion(expr_str)
            lugar = self.generar_expresion(crear_arbol_extendido(expr_str))
            self.gen("=", lugar, "-", nombre, f"Declaración {tipo_var} {nombre} = {lugar}")
            return

        if m_mostrar:
            expr_str = m_mostrar.group(1)
            self._registrar_notacion(expr_str)
            lugar = self.generar_expresion(crear_arbol_extendido(expr_str))
            self.gen("mostrar", lugar, "-", "-", f"Imprime {lugar} en pantalla")
            return

        if m_retornar:
            expr_str = m_retornar.group(1)
            self._registrar_notacion(expr_str)
            lugar = self.generar_expresion(crear_arbol_extendido(expr_str))
            self.gen("retornar", lugar, "-", "-", f"Retorna valor {lugar}")
            return

        if m_llamar:
            nombre_fn, args_raw = m_llamar.groups()
            args = [a.strip() for a in args_raw.split(",") if a.strip()]
            for arg in args:
                lugar_arg = self.generar_expresion(crear_arbol_extendido(arg))
                self.gen("param", lugar_arg, "-", "-", f"Pasa parámetro {lugar_arg}")
            self.gen("llamar", nombre_fn, str(len(args)), "-", f"Invoca procedimiento {nombre_fn}")
            return

        if m_asig:
            nombre, expr_str = m_asig.groups()
            self._registrar_notacion(expr_str)
            lugar = self.generar_expresion(crear_arbol_extendido(expr_str))
            self.gen("=", lugar, "-", nombre, f"Asignación {nombre} = {lugar}")
            return

        raise ErrorNumlang(f"Instrucción no reconocida: '{texto}'")

    # -----------------------------------------------------------------
    # CONVERSIÓN A TRIPLETAS Y CÓDIGO P
    # -----------------------------------------------------------------

    def generar_tripletas(self) -> list[dict]:
        mapa_temporales = {}
        tripletas = []

        def resolver_ref(operando: str) -> str:
            return mapa_temporales.get(operando, operando)

        for cuad in self.cuadruplos:
            idx = f"({cuad['num']})"
            op = cuad["op"]
            arg1 = resolver_ref(cuad["arg1"])
            arg2 = resolver_ref(cuad["arg2"])
            res = cuad["res"]

            if res.startswith("t") and res[1:].isdigit():
                mapa_temporales[res] = idx

            if op == "=":
                t_arg1, t_arg2 = res, arg1
                explicacion = f"Guarda {arg1} en {res}" if arg1.startswith("(") else f"Asigna {arg1} a la variable {res}"
            elif op == "if_false":
                t_arg1, t_arg2 = arg1, res
                explicacion = f"Si {arg1} es falso salta a {res}"
            elif op in ("goto", "etiqueta", "param_recibir"):
                t_arg1, t_arg2 = res, "-"
                explicacion = cuad["descripcion"]
            else:
                t_arg1, t_arg2 = arg1, arg2
                explicacion = cuad["descripcion"]

            tripletas.append({
                "indice": idx,
                "op": op,
                "arg1": t_arg1,
                "arg2": t_arg2,
                "explicacion": explicacion,
            })

        return tripletas

    def generar_codigo_p(self) -> list[str]:
        ops_p = {
            "+": "ADI", "-": "SBI", "*": "MPI", "/": "DVI",
            "elevado_a": "EXP", "residuo_de": "MOD",
            ">": "GRT", "<": "LES", ">=": "GEQ", "<=": "LEQ",
            "==": "EQU", "!=": "NEQ", "y": "AND", "o": "IOR",
        }
        instrucciones_p = []

        def cargar_operando(opnd: str):
            if re.fullmatch(r"-?\d+(?:\.\d+)?", opnd) or opnd.startswith('"') or opnd in ("verdadero", "falso"):
                instrucciones_p.append(f"LDC {opnd}")
            else:
                instrucciones_p.append(f"LOD {opnd}")

        for c in self.cuadruplos:
            op, a1, a2, res = c["op"], c["arg1"], c["arg2"], c["res"]
            if op == "=":
                cargar_operando(a1)
                instrucciones_p.append(f"STO {res}")
            elif op in ops_p:
                cargar_operando(a1)
                cargar_operando(a2)
                instrucciones_p.append(ops_p[op])
                instrucciones_p.append(f"STO {res}")
            elif op == "neg":
                cargar_operando(a1)
                instrucciones_p.append("NGI")
                instrucciones_p.append(f"STO {res}")
            elif op == "no":
                cargar_operando(a1)
                instrucciones_p.append("NOT")
                instrucciones_p.append(f"STO {res}")
            elif op == "if_false":
                cargar_operando(a1)
                instrucciones_p.append(f"FJP {res}")
            elif op == "goto":
                instrucciones_p.append(f"UJP {res}")
            elif op == "etiqueta":
                instrucciones_p.append(f"LAB {res}")
            elif op == "mostrar":
                cargar_operando(a1)
                instrucciones_p.append("WRT")
            elif op == "param":
                cargar_operando(a1)
                instrucciones_p.append("PAR")
            elif op == "llamar":
                instrucciones_p.append(f"CUP {a1} {a2}")
                if res != "-":
                    instrucciones_p.append(f"STO {res}")
            elif op == "retornar":
                cargar_operando(a1)
                instrucciones_p.append("RET")

        return instrucciones_p


# =====================================================================
# 4. IMPRESIÓN DE TABLAS Y DEMOSTRACIÓN INTEGRADA
# =====================================================================

def imprimir_reporte(titulo: str, resultado: dict):
    print("=" * 88)
    print(f" {titulo}")
    print("=" * 88)

    print("\n[0] TABLA DE SÍMBOLOS (Integrante 1):")
    for n, info in resultado["tabla_simbolos_semantica"].items():
        print(f"  • {n}: {info['tipo']} = {info['valor']}, scope={info['scope']}")

    if resultado["notaciones"]:
        print("\n[1] CONVERSIÓN DE NOTACIONES (INFIJA / PREFIJA / POSTFIJA):")
        for n in resultado["notaciones"]:
            print(f"  • Infija  : {n['infija']}")
            print(f"    Prefija : {n['prefija']}")
            print(f"    Postfija: {n['postfija']}")

    print("\n[2] TABLA DE CUÁDRUPLETAS:")
    encabezado = f"{'#':<4} | {'Operador (op)':<14} | {'Operando 1':<12} | {'Operando 2':<12} | {'Resultado (res)':<15} | {'Instrucción equivalente'}"
    print(encabezado)
    print("-" * len(encabezado))
    for c in resultado["cuadruplos"]:
        print(
            f"{c['num']:<4} | {c['op']:<14} | {c['arg1']:<12} | "
            f"{c['arg2']:<12} | {c['res']:<15} | {c['instruccion_equivalente']}"
        )

    print("\n[3] TABLA DE TRIPLETAS:")
    enc_trip = f"{'Índice':<8} | {'Operador (op)':<14} | {'Operando 1':<14} | {'Operando 2':<14} | {'Explicación'}"
    print(enc_trip)
    print("-" * len(enc_trip))
    for t in resultado["tripletas"]:
        print(
            f"{t['indice']:<8} | {t['op']:<14} | {t['arg1']:<14} | "
            f"{t['arg2']:<14} | {t['explicacion']}"
        )


def ejecutar_demos_documentacion():
    ejemplo_1 = """
    num a = 4
    num b = 3
    num resultado = a + b * 2
    """
    gen1 = GeneradorCodigoIntermedio()
    res1 = gen1.compilar_programa(ejemplo_1)
    imprimir_reporte("EJEMPLO 1 DOCUMENTADO: Expresión aritmética básica", res1)

    ejemplo_2 = """
    nota: ejemplo de condicional
    num x = 5
    num resultado = x * 2 + 1
    si resultado > 10 entonces
        mostrar "mayor"
    si_no
        mostrar "menor"
    fin
    """
    gen2 = GeneradorCodigoIntermedio()
    res2 = gen2.compilar_programa(ejemplo_2)
    imprimir_reporte("EJEMPLO 2 DOCUMENTADO: Estructura de control condicional", res2)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        ejecutar_demos_documentacion()
        sys.exit(0)

    archivo = Path(sys.argv[1])
    modo_json = len(sys.argv) == 3 and sys.argv[2] == "--json"

    try:
        codigo_fuente = archivo.read_text(encoding="utf-8")
        generador = GeneradorCodigoIntermedio()
        salida = generador.compilar_programa(codigo_fuente)
        if modo_json:
            print(json.dumps(salida, indent=2, ensure_ascii=False))
        else:
            imprimir_reporte(f"ARCHIVO: {archivo.name}", salida)
    except (OSError, ErrorNumlang) as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)