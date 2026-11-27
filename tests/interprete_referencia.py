"""Interprete de referencia de cuadruplos de Numlang para las pruebas."""


def div_entera(a: int, b: int) -> int:
    """Division entera con truncamiento hacia cero (como IDIV de x86)."""
    if b == 0:
        raise ZeroDivisionError("division entre cero")
    cociente = abs(a) // abs(b)
    return -cociente if (a < 0) ^ (b < 0) else cociente


def residuo_entero(a: int, b: int) -> int:
    """Residuo con el signo del dividendo (como IDIV de x86)."""
    return a - div_entera(a, b) * b


class InterpretadorReferencia:
    """Ejecuta cuadruplos y devuelve la salida de `mostrar`."""

    def __init__(self, cuadruplos, simbolos=None):
        self.cuadruplos = list(cuadruplos)
        self.simbolos = dict(simbolos or {})
        self.valores = {}
        self.salida = []
        self.etiquetas = {}
        self.parametros = []

    def _valor(self, texto):
        texto = str(texto)
        if texto == "-":
            return None
        if texto in self.valores:
            return self.valores[texto]
        if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in ("'", '"'):
            return texto[1:-1]
        if texto in ("verdadero", "True"):
            return 1
        if texto in ("falso", "False"):
            return 0
        try:
            numero = float(texto)
        except ValueError:
            if texto in self.simbolos:
                valor = self.simbolos[texto].get("valor")
                if isinstance(valor, str):
                    return valor
                try:
                    return float(valor)
                except (TypeError, ValueError):
                    return 0
            raise AssertionError(f"Simbolo desconocido en el interprete: {texto}")
        return numero

    def _guardar(self, nombre, valor):
        if nombre != "-":
            self.valores[nombre] = valor

    @staticmethod
    def _binario(valor):
        return 1 if valor else 0

    @staticmethod
    def _formatear(valor):
        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))
        return str(valor)

    def ejecutar(self):
        for indice, cuad in enumerate(self.cuadruplos):
            if cuad["op"] == "etiqueta":
                self.etiquetas[cuad["res"]] = indice

        contador = 0
        pc = 0
        while pc < len(self.cuadruplos):
            contador += 1
            if contador > 100000:
                raise AssertionError("Posible bucle infinito en el interprete de referencia")
            cuad = self.cuadruplos[pc]
            op = cuad["op"]
            arg1, arg2, res = cuad["arg1"], cuad["arg2"], cuad["res"]
            siguiente = pc + 1

            if op == "=":
                self._guardar(res, self._valor(arg1))
            elif op == "+":
                self._guardar(res, self._valor(arg1) + self._valor(arg2))
            elif op == "-":
                self._guardar(res, self._valor(arg1) - self._valor(arg2))
            elif op == "*":
                self._guardar(res, self._valor(arg1) * self._valor(arg2))
            elif op == "/":
                self._guardar(res, div_entera(self._valor(arg1), self._valor(arg2)))
            elif op in ("%", "residuo_de"):
                self._guardar(res, residuo_entero(self._valor(arg1), self._valor(arg2)))
            elif op in ("elevado_a", "**"):
                self._guardar(res, self._valor(arg1) ** self._valor(arg2))
            elif op == ">":
                self._guardar(res, int(self._valor(arg1) > self._valor(arg2)))
            elif op == "<":
                self._guardar(res, int(self._valor(arg1) < self._valor(arg2)))
            elif op == ">=":
                self._guardar(res, int(self._valor(arg1) >= self._valor(arg2)))
            elif op == "<=":
                self._guardar(res, int(self._valor(arg1) <= self._valor(arg2)))
            elif op == "==":
                self._guardar(res, int(self._valor(arg1) == self._valor(arg2)))
            elif op == "!=":
                self._guardar(res, int(self._valor(arg1) != self._valor(arg2)))
            elif op == "y":
                self._guardar(res, self._binario(self._valor(arg1)) & self._binario(self._valor(arg2)))
            elif op == "o":
                self._guardar(res, self._binario(self._valor(arg1)) | self._binario(self._valor(arg2)))
            elif op == "no":
                self._guardar(res, int(not self._valor(arg1)))
            elif op == "neg":
                self._guardar(res, -self._valor(arg1))
            elif op == "etiqueta":
                pass
            elif op == "goto":
                siguiente = self.etiquetas[res]
            elif op == "if_false":
                if not self._valor(arg1):
                    siguiente = self.etiquetas[res]
            elif op == "mostrar":
                valor = self._valor(arg1)
                self.salida.append(self._formatear(valor))
            elif op == "param":
                self.parametros.append(self._valor(arg1))
            elif op == "llamar":
                self.parametros.clear()
                if res != "-":
                    self._guardar(res, 0)
            elif op == "retornar":
                break
            elif op in ("campo_estructura", "param_recibir"):
                pass
            else:
                raise AssertionError(f"Operador no soportado por el interprete: {op}")
            pc = siguiente

        return "\n".join(self.salida) + ("\n" if self.salida else "")


def interpretar(cuadruplos, simbolos=None):
    """Atajo para obtener la salida de un programa de cuadruplos."""
    return InterpretadorReferencia(cuadruplos, simbolos).ejecutar()
