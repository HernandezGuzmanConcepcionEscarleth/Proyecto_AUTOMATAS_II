"""Numlang - Integrante 1: Analizador Semántico (Actualizado Fase 2)."""

import ast
import json
import re
import sys
from pathlib import Path


class ErrorNumlang(Exception):
    """Error de sintaxis o semántica de una instrucción de Numlang."""


def crear_arbol(expresion):
    """Convierte una expresión en un árbol simple (diccionarios)."""
    try:
        raiz = ast.parse(expresion, mode="eval").body
    except SyntaxError as exc:
        raise ErrorNumlang(f"Expresión mal escrita: '{expresion}'") from exc

    operaciones = {
        ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
        ast.Gt: ">", ast.Lt: "<", ast.GtE: ">=", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!="
    }

    def convertir(nodo):
        if isinstance(nodo, ast.Constant):
            if type(nodo.value) in (int, float):
                return {"tipo": "numero", "valor": float(nodo.value)}
            if type(nodo.value) is str:
                return {"tipo": "cadena", "valor": nodo.value}
            if type(nodo.value) is bool:
                return {"tipo": "booleano", "valor": nodo.value}
        if isinstance(nodo, ast.Name):
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
            return {"tipo": "negativo", "expresion": convertir(nodo.operand)}
        raise ErrorNumlang("Operación no soportada en la expresión")

    return convertir(raiz)


class AnalizadorSemantico:
    def __init__(self):
        self.simbolos = {}
        self.direcciones = {}
        self.pila = []
        self.historial_pila = []
        self.arboles = []
        self.errores = []
        self.salidas = []
        self.linea = 0
        self._lineas = []
        # Lista de palabras reservadas del lenguaje
        self.palabras_reservadas = {
            "num", "msj", "bool", "mostrar", "si", "si_no", "entonces", 
            "mientras", "para", "hasta", "paso", "hacer", "fin", 
            "y", "o", "no", "verdadero", "falso", "funcion", "retornar", 
            "estructura", "const"
        }

    def registrar_pila(self, accion):
        self.historial_pila.append({
            "linea": self.linea, "accion": accion, "pila": self.pila.copy()
        })

    def evaluar(self, nodo):
        """Evalúa un nodo del árbol verificando tipos y usando la pila."""
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

        tipo_izq, _ = self.evaluar(nodo["izquierda"])
        tipo_der, _ = self.evaluar(nodo["derecha"])
        
        op = nodo["operador"]
        
        if op in ("+", "-", "*", "/"):
            if tipo_izq != "num" or tipo_der != "num":
                raise ErrorNumlang(f"Tipos incompatibles: la operación '{op}' requiere 'num'")
            b = self.pila.pop()
            a = self.pila.pop()
            if op == "+": valor = a + b
            elif op == "-": valor = a - b
            elif op == "*": valor = a * b
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

    def ejecutar_instruccion(self, texto):
        texto = texto.strip().removesuffix(";").strip()
        if not texto or texto.startswith("nota:"):
            return

        declaracion = re.fullmatch(r"(num|msj|bool)\s+([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(.+)", texto)
        asignacion = re.fullmatch(r"([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(.+)", texto)
        salida = re.fullmatch(r"mostrar\s+(.+)", texto)

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
            
            self.direcciones[nombre] = hex(0x1000 + len(self.direcciones) * 8)
            self.simbolos[nombre] = {"tipo": tipo_var, "valor": valor, "scope": "global"}
            self.arboles.append({"linea": self.linea, "instruccion": "declaracion", "destino": nombre, "expresion": arbol})
            
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


def analizar_codigo(codigo):
    return AnalizadorSemantico().analizar(codigo)


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