# CHANGELOG — NumLang

## 2026-11-24 — P0.4.d: evaluador de llamadas con pila de scopes

Estado: **aplicado**. `python -B -m pytest -q -p no:cacheprovider` → **117 passed**.

- Se corrige D-F6: las variables en argumentos no declaradas dan "no está declarada" (antes "no declarada").
- **D-F14.** `self._scopes` es una pila de dicts `{param: valor}`. Los argumentos se evalúan en el scope actual antes de apilar el de la función; los parámetros NO se registran en `self.simbolos`. Con scope activo, una variable se busca SOLO en el scope superior; si no está: `variable fuera de alcance`, sin caer a globales. `_validar_llamada` se aplica solo a llamadas de nivel superior; dentro del cuerpo no se revalida.
- **D-F15.** El scope se desapila en `finally`, incluso si el cuerpo lanza error; el resultado es `("num", float)` y no modifica símbolos globales. La pila queda igual que con la expresión equivalente sin función.
- Deuda P0.4.c cerrada: `mostrar f(w + 1)` con `w` sin declarar ahora da "no está declarada".
- Deuda P2 registrada: `GeneradorCodigoIntermedio().compilar_programa("func f(x) = x + 1\nmostrar f(3)\n")` lanza `ErrorNumlang: Instrucción no reconocida: 'func f(x) = x + 1'` (generador sin soporte `func`; no se toca en P0).

## 2026-11-24 — P0.4.c: semántica de llamadas ID(Args)

Estado: **aplicado**. `python -B -m pytest -q -p no:cacheprovider` → **108 passed**.

- **D-F6.** `_tipo_arbol` soporta "llamada": el callee debe existir en simbolos con tipo "func" (si no: "Función 'f' no definida"; NUNCA caer al fallback "num"), aridad == n_params, cada argumento debe ser NUM; resultado "num". Las variables en los argumentos deben estar declaradas (error "no está declarada"); llamadas anidadas se validan recursivamente.
- **D-F12.** las llamadas resuelven SOLO a funciones. En el cuerpo de una func, si el callee es un parámetro: error "'f' es un parámetro, no una función" (ajuste al validador de P0.4.b).
- **D-F13.** llamadas dentro de ecu prohibidas con error claro ("llamadas a funciones no permitidas dentro de una ecuación"), comprobado ANTES de _tipo_arbol y de calcular incógnitas.

Deuda P0.4.d registrada (cerrada en P0.4.d):
- test obligatorio: mostrar f(w + 1) con w sin declarar -> 'no está declarada' (resuelto por evaluación de argumentos)

## 2026-11-23 — P0.4.b: semántica de `DefFunc` sin evaluación de llamadas

Estado: **aplicado**. `python -B -m pytest -q -p no:cacheprovider` → **99 passed**.

- **D-F1.** Definición antes de uso: el validador solo acepta llamadas a funciones ya presentes en `tabla_simbolos`.
- **D-F2.** Parámetros shadow de globales: el cuerpo resuelve primero el nombre contra `params`; la global no dispara error cuando el parámetro existe.
- **D-F3.** Cuerpo self-contained: se validan parámetros, literales (`PI`/`Eu` ya son nodos `numero`) y llamadas a funciones previas con aridad correcta; los argumentos se validan recursivamente con el mismo validador propio. No se reutiliza `_tipo_arbol`.
- **D-F5.** Recursión bloqueada: el símbolo se inserta después de validar el cuerpo; una llamada al propio nombre da `recursión no permitida en la definición de función`.
- **D-F8.** `func`, `ecu` y variables comparten namespace; colisión = `ya fue declarada`.
- **D-F9.** Parámetros duplicados o reservados y nombre de función reservado = error. La excepción de `y` quedó eliminada en P0.4.b.1: la excepción cubría también tests propios que usaban `y` como parámetro; `y` sigue reservada como operador lógico.
- **D-F10.** El cuerpo debe tipar `num`; comparaciones, cadenas y booleanos dan `cuerpo de función debe ser NUM`.

Deudas registradas: `x / 0` literal en el cuerpo no se valida divisiones por cero → **P1**; `func g(f) = f(2)` (llamada a parámetro) → decidir en **P0.4.c**.

## 2026-11-23 — P0.5 mínimo: constantes `PI`, `Eu`, `verdadero`, `falso`

Estado: **aplicado**. `python -B -m pytest -q -p no:cacheprovider` → **81 passed** (75 + 6).

- **D-C1.** `PI` y `Eu` se convierten en `{"tipo": "numero", "valor": math.pi / math.e}` en `crear_arbol` y en `crear_arbol_extendido`. No se insertan en la tabla de símbolos: dejan de contarse como incógnitas en `ecu` y el cuerpo de `func` los ve como literales. `generador_intermedio.py` añade `import math` como soporte.
- **D-C2.** `PI` y `Eu` se añaden a `palabras_reservadas` con sensibilidad a mayúsculas; `pi` y `e` siguen siendo identificadores normales. `num PI = 3` falla como palabra reservada.
- **D-C3.** `verdadero`/`falso` verificados en ambas rutas: `analizar_codigo` (`analisis["salidas"]`) y `compilar_programa` + `interpretar`. `tests/test_constantes.py::test_verdadero_en_ambas_rutas` pasa en las dos; el oráculo imprime `1`/`0` en vez de `verdadero`/`falso`. Sin arreglo: se registra como deuda P2.

Deuda P2 registrada: (a) bool se muestra como `1` en el oráculo; (b) `PI = 4` da "no declarada" en vez de "reservada".

## 2026-11-23 — P0.1.b: paréntesis explícitos con menos unario ante `elevado_a`

Estado: **aplicado**. `python -B -m pytest -q -p no:cacheprovider` → **75 passed** (67 - 2 + 10).

`menos_unario_esta_parentizado` lee los bytes UTF-8 del texto realmente parseado (`fuente` en `crear_arbol`, `expr_limpia` en `crear_arbol_extendido`) entre `nodo.col_offset + 1` y `nodo.operand.col_offset`. Si hay `(`, el menos unario no se reescribe: `-(2 elevado_a 2) = -4`, `-2 elevado_a 2 = 4`.

## 2026-11-23 — P0.3.b: semántica de `DefEcu`

Estado: **aplicado**. `pytest -q` → **43 passed** (32 previos + 11 nuevos).

### Decisiones D1–D7 aplicadas

- **D1 — Incógnita.** `_incognitas_en_arbol` recorre los AST de E1 y E2, acumula en un `set` los IDs no declarados y los deduplica por nombre (`2*x = x + 5` → una sola incógnita `x`). IDs presentes en la tabla de símbolos se tratan como constantes. 0 incógnitas → `no hay incógnita en la ecuación`; ≥2 → `la ecuación tiene más de una incógnita: ...`; 1 → válido.
- **D2 — Grado simbólico.** Se construye el AST de `(E1 - E2)` y `_coeficientes` devuelve diccionarios `{grado: coef}`. Suma/resta por grado, multiplicación por convolución y potencia entera ≥0 por convolución repetida. División solo con divisor constante no nulo. **Poda `|c| < 1e-12`** en cada operación y al final; `grado = max(claves)`. No se cuenta `elevado_a` en el AST ni se evalúa la ecuación en puntos: esas estrategias darían grado 2 en `x² - x² + x` y en `0*x² + 3*x`, y grado 3 en `(x-x)*x² + x`. La cancelación estructural de los dicts hace que los tres casos terminen en `{1:1, 0:-6}` → grado 1, coefs `(0,1,-6)`.
- **D3 — Coeficientes.** Tupla `(a, b, c)` de `a*x² + b*x + c = 0`, tomada de `polinomio.get(2/1/0, 0.0)`.
- **D4 — Tipos.** `_tipo_arbol` calcula el tipo sin evaluar; E1 y E2 deben ser `num`, si no → `tipos no NUM en la ecuación`. D4 se ejecuta **antes** que D1.
- **D5 — Tabla de símbolos.** Se inserta `e1` con `tipo="ecu"`, `incognita`, `grado`, `coefs`, `lado_izq`, `lado_der`, `scope` y `valor=None`. La incógnita **no** se registra como variable `num`.
- **D6 — Multiplicación explícita.** Sin cambios: `2x` ya falla en el parser desde P0.3.a. `^` **no es sintaxis válida**; la potencia se escribe `elevado_a` (en Python `^` es XOR y no es terminal de la gramática; aceptarlo exigiría tocar el lexer, fuera de alcance).
- **D7 — Sin scope creep.** No se modificaron el evaluador (`evaluar`), `resolver`, el generador intermedio, el backend NASM ni DT-1. `_coeficientes` no llama a `self.evaluar`, por lo que no muta la pila ni el historial.

### Extensión booleana mínima

`crear_arbol` ya reconocía `True`/`False` vía `ast.Constant`; ahora también tipa los IDs `verdadero` y `falso` como nodos `booleano` en la rama `ast.Name` (`analizador_semantico.py:44`). Esto permite que `ecu e7: verdadero = falso` falle por `tipos no NUM` en vez de por «2 incógnitas». **No** implementa PI/Eu, constantes read-only ni P0.5 completo.

### Tests

`tests/test_ecu_semantica.py` creado con los 11 tests mínimos (grado 1/2, 2 incógnitas, grado 3, sin incógnita, degenerada, tipos, dedup y las tres cancelaciones simbólicas). usa `elevado_a`, nunca `^`.

## 2026-11-23 — P0.3.c: validación semántica de `resolver`

Estado: **aplicado**. `pytest -q` → **48 passed** (43 + 5).

Se extendió la rama `resolucion` (`analizador_semantico.py:439`) sin tocar el evaluador, el generador intermedio ni NASM:

1. ID1 no existe → `la ecuación '<id>' no está declarada`.
2. ID1 existe pero no es `ecu` → `'<id>' no es una ecuación`.
3. ID2 no coincide con la incógnita registrada → `'<id>' no es la incógnita de '<ecu>' (la incógnita es '<incógnita>')`.
4. Caso válido → se conserva el `append` original y se añade `"valida": True` para que P0.3.d solo evalúe resoluciones ya validadas.

Nota: `y` es palabra reservada del lenguaje (`y`/`o`/`no`), por lo que la comparación con la incógnita se evalúa antes del chequeo de reservadas de ID2; así `resolver e1 para y` informa correctamente el error de incógnita. El chequeo de reservadas se conserva para ID1 y para resoluciones válidas. No se calcula discriminante ni valor de `x`.

`tests/test_resolver_semantica.py` creado con los 5 tests (válido grado 1, incógnita distinta, no ecuación, ecuación inexistente, válido grado 2).

## 2026-11-23 — P0.3.d: evaluador numérico de `resolver`

Estado: **aplicado**. `pytest -q` → **58 passed** (48 + 10). Salida literal verificada: `x = 5\n` (una sola línea).

- `TOL_DISCRIMINANTE = 1e-9` (`analizador_semantico.py:11`): los coeficientes ya llegan podados a `1e-12` desde P0.3.b, así que `1e-9` separa `d==0` de `d=1e-10` sin ser laxo.
- `_evaluar_resolucion` (`:110`): grado 1 → `x = -c/b`; grado 2 → `d = b² - 4ac`, doble si `|d| <= TOL`, error `la ecuación no tiene soluciones reales` si `d < -TOL`, y dos soluciones `(-b ± √d)/(2a)` ordenadas mayor primero (maneja `a < 0`). Grado 1 con `b == 0` → `ecuación degenerada en evaluación` (defensivo).
- `_formatear_num` (`:105`) es copia exacta de `tests/interprete_referencia.py:63-66`; se usa en los 3 prints de `resolver` para imprimir `x = 5` (sin `.0`), alineado con el intérprete de referencia. `_sin_cero_negativo` evita `-0`.
- Decisión A puro: **no** se tocó `mostrar` ni el CLI `__main__:606`. `salidas` sigue siendo `list[float]` (contrato de tests programáticos: `[5.0]`, `[5.1]`, `[4.0]`, `[512.0]`).

Nota de precedencia: el test con `a < 0` usa `0 - x elevado_a 2 + 4 = 0`. La forma `-x elevado_a 2 + 4 = 0` da `a = +1` porque P0.1 fija que el menos unario precede a `elevado_a` (`tests/test_precedencia.py:8-14`), por lo que equivale a `(-x)² + 4`.

P0.1 (menos unario antes de `elevado_a`) implica `-x elevado_a 2 = (-x)^2; para -(x^2) usar -(x elevado_a 2) o 0 - x elevado_a 2`.

`tests/test_resolver_evaluador.py` creado con los 10 tests (grado 1, b negativo, c=0, dos soluciones, doble, sin reales, a<0, cancelación simbólica, `valida` ausente/False, doble `resolver`).

### Deudas registradas para P2

- **P2:** generar cuádruples de `resolver` en `generador_intermedio.py`; hoy `resolver` imprime directamente desde el semántico.
- **P2:** unificar canales: asimetría `mostrar` → `salidas` (floats) vs `resolver` → stdout; el CLI debug `:606` sigue mostrando `[5.0]`.
- **P2:** añadir test explícito para `resolver e1 para <reservada>` → error `reserved`; hoy da `no es la incógnita` por enmascaramiento (reordenación de P0.3.c).

## 2026-11-23 — P0.4.a: front-end de `func`/llamadas

Estado: **aplicado**. `pytest -q` → **67 passed** (58 + 9).

- `func` añadida a `palabras_reservadas` (`analizador_semantico.py:91`).
- `crear_arbol` reconoce `ast.Call` (`:40`) → nodo `{"tipo": "llamada", "nombre": ..., "args": [...]}`; exige callee `ast.Name` y sin `keywords`.
- `DefFunc` regex (`:357`) y rama parser (`:384`) capturan `func ID ( Params ) = Expr` con 0/1/N params. Params se validan solo sintácticamente; nombres reservados/duplicados y tipos se validan en P0.4.b.
- Todavía **no** se inserta en `simbolos`, no se valida aridad/tipos de llamadas y no se evalúan: `mostrar f(3)` sigue fallando hasta P0.4.c/d.

`tests/test_func_parser.py` creado con 9 tests (1/2/0 params, llamada en primario, cuerpo con llamada, `func` reservada, falta `)`, falta `=`, parámetro inválido).

### Restricciones/dudas documentadas

- **P3:** `funcion` sigue en `palabras_reservadas`; decidir si se elimina (la spec no la menciona) o se documenta como alias deprecado. No se toca ahora.
- **P2:** `f(*args)` / `f(**kw)` no están soportados: caen en el fallback `Operación no soportada en la expresión`. La spec no incluye expansiones.
- **P2:** el regex de cuerpo usa `(.+)` → una sola línea. Cuerpo multi-línea captura solo la primera; la spec define cuerpo = una Expr.

### Pendientes derivados de observaciones menores

- **P1:** D4 valida solo el tipo de la raíz de E1/E2; un `bool b` dentro de `b*x` no se detecta y `_coeficientes` lo convertiría con `float(True) == 1.0`.
- **P2:** revisar la cobertura de `verdadero`/`falso` como palabras reservadas en todos los contextos (observación reportada; ya figuran en `palabras_reservadas`, falta validar su enforcement completo).
- **CHANGELOG/robustez:** `float(simbolo.get("valor") or 0.0)` interpreta una declarada sin valor como `0`; hoy no es alcanzable porque toda declaración lleva asignación.
- **P0.4.c:** `_tipo_arbol` aún no maneja nodos `llamada`; se extenderá con D-F6.
