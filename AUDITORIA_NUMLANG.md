# Auditoría de implementación de NumLang contra la especificación formal

**Fecha:** 2026-11-22  
**Especificación de referencia:** `C:\Users\jarqu\Desktop\Trabajos\AutomatasII\Documentación Proyecto Final Numlang.pdf` (25 páginas; GLC en pp. 4–6, reglas semánticas en pp. 7–9, tripletas/cuádruplos en pp. 14–17, optimización y PVM en pp. 18–23, limitaciones en p. 24).  
**Código auditado:** proyecto en `C:\Users\jarqu\Desktop\Trabajos\AutomatasII\Numlang\Proyecto_AUTOMATAS_II`.  
**Método:** revisión estática de los 10 archivos `.py`, ejecución de los 15 programas solicitados, 26 sondas adicionales y ejecución end-to-end NASM; `python -m pytest -q` → **67 passed** (tras P0.4.a).  
**Aviso:** no se modificó ningún archivo `.py`. El único archivo creado es este reporte.

---

## 1. Resumen ejecutivo

| Métrica | Valor |
|---|---|
| Ítems evaluados del checklist | **71** |
| ✅ OK (cumplimiento total) | **33** (46.5 %) |
| ⚠️ Parcial | **11** (15.5 %) |
| ❌ Falta | **19** (26.8 %) |
| 🐛 Bug / comportamiento incorrecto | **8** (11.3 %) |
| **Cobertura estricta** (solo ✅) | **46.5 %** |
| **Cobertura ponderada** (✅ + 0.5·⚠️) | **54.2 %** |

**Conclusión ejecutiva:** la implementación cubre correctamente el subconjunto aritmético-básico (declaraciones, asignaciones, `mostrar`, `si`/`si_no`, `mientras`, cuádruplos y tripletas), pero **no implementa el núcleo diferencial del lenguaje**: ecuaciones (`ecu`/`resolver`), funciones (`func`), constantes (`PI`, `Eu`, `verdadero`, `falso`) ni los operadores verbales (`elevado_a`, `residuo_de`, `menor_o_igual`, `mayor_o_igual`, `igual_a`, `distinto_de`, `y`, `o`, `no`) en la ruta real de compilación. Existen fragmentos de código para algunos de ellos, pero quedan inalcanzables porque el analizador semántico los rechaza antes de la generación intermedia.

Los 67 tests propios pasan; cubren precedencia unario/potencia, precisión `float`, el backend NASM, el parser/semántica de `ecu`, la validación y resolución de `resolver`, y el parser de `func`/llamadas, pero **siguen sin ejercitar la semántica/evaluador de `func`, constantes `PI`/`Eu` ni operadores verbales en la ruta real**. Por ello, "tests en verde" no implica conformidad con la especificación.

**Discrepancias de mayor impacto (detalle en §5):**

1. ❌ `ecu`, `resolver`, `func`, `PI`, `Eu`, `verdadero`, `falso` y los operadores verbales son incompatibles con el pipeline completo.
2. 🐛 Precedencia `menos unario → elevado_a` incorrecta: se usa el AST de Python, donde `-2 ** 2 = -4`; la spec exige `(-2)^2 = 4`.
3. 🐛 `num` no es doble precisión en el código objeto: `1.5` se emite como entero `1` (`idiv`/`%d`).
4. 🐛 Lista de palabras reservadas errónea: permite `num ecu = 5`, `num resolver = 5`, etc.
5. 🐛 División entre cero en ejecución sin guardia: el intérprete referencia lanza `ZeroDivisionError` y NASM ejecutaría `idiv` con divisor 0.
6. 🐛 Las ramas de `si`/`si_no` se analizan ambas, generando redeclaraciones falsas y fugas de variables.
7. ❌ `para` y `funcion` están implementados aunque la spec los declara explícitamente fuera de alcance.
8. ⚠️ No hay parser GLC/LALR: el "parser" es regex por línea + AST de Python.

---

## 2. FASE 1 — Inventario del código

### 2.1 Archivos `.py`

| Archivo | Rol principal | Componentes clave |
|---|---|---|
| `analizador_semantico.py` (374 líneas) | Analizador semántico, tabla de símbolos, pila semántica, evaluador estático y CLI. Contiene un subconjunto de "lexer" por regex de línea. | `ErrorNumlang` :10; `crear_arbol` :14–51; palabras reservadas :66–71; `evaluar` :78–148; regex de sentencias :155–157; bloques :223–343; CLI :350–374. |
| `generador_intermedio.py` (797 líneas) | Conversiones infija/prefija/postfija, árbol extendido, generador de cuádruplos, tripletas y código P; parser de bloques por regex; CLI con demos. | `PRECEDENCIA` :19–25; tokenizador :29–39; Shunting-Yard :42–133; reemplazos de operadores :165–177; `crear_arbol_extendido` :197–266; `nuevoTemp`/`nuevaEtiqueta`/`gen` :283–307; `generar_expresion` :342–381; parser :387–610; tripletas :616–654; código P :656–710; CLI :779–797. |
| `motor_optimizacion.py` (252 líneas) | Optimizador local, de mirilla, global y de ciclos; métricas; CLI. | plegado/simplificación :27–63; mirilla :66–95; código muerto :98–138; ciclos (solo registro) :141–145; tripletas optimizadas :148–177. |
| `generador_objeto.py` (563 líneas) | Backend NASM x86-32 Win32, CLI de compilación/ensamblado/ejecución y lanzamiento de GUI. | conjuntos de opcodes :21–39; `NasmWin32Backend` :75–365; traducción :246–304; potencia :339–353; pitfall de `entero_nasm` :201–202; `compilar_cuadruplos` :454–467; CLI :522–563. |
| `asignador_registros.py` (172 líneas) | Asignación linear-scan de temporales a EBX/ESI/EDI con spill a `[ebp-N]`. | `AsignadorRegistros` :32–129. |
| `gestor_memoria.py` (265 líneas) | Segmentos `.data`/`.bss`, pool de cadenas, marco de pila y reportes. | `entero_nasm` :32–39; formatos `fmt_int`/`fmt_str` :63–69; variables :76–123; `generar_secciones` :184–212. |
| `interfaz_grafica.py` (326 líneas) | GUI Tkinter: editor, ejemplos, cuádruplos, ASM y ejecución en hilo. | `procesar_codigo` :36–77; `AplicacionNumlang` :80–322. |
| `tests/conftest.py` (8 líneas) | Ajusta `sys.path` para pytest. | :6–8. |
| `tests/interprete_referencia.py` (141 líneas) | Intérprete de cuádruplos **usado solo en pruebas**; no es un intérprete de usuario. | `InterpretadorReferencia` :17–136; `interpretar` :139–141. |
| `tests/test_codigo_objeto.py` (197 líneas) | Pruebas end-to-end del backend NASM y del intérprete referencia. | casos :20–36; pruebas :70–197. |

Archivos no-Python: `ejecutar_interfaz.bat` (lanzador), `LEEME.md`, `docs/codigo_objeto.md`, 8 programas en `src/`, artefactos en `build/`.

### 2.2 Localización de componentes clave

| Componente | Archivo:línea | Observación |
|---|---|---|
| Definición de tokens / palabras reservadas | `analizador_semantico.py:66-71`; `generador_intermedio.py:19-39`, `:165-177` | **No existe clase `Token` ni lexer dedicado.** Lista de reservadas incompleta (ver §5 C4). |
| Gramática / parser | `analizador_semantico.py:150-202` (regex de sentencia), `:204-343` (bloques); `generador_intermedio.py:197-266` (AST de Python), `:387-610` (parser de bloques por regex) | No hay PLY/ANTLR ni GLC ejecutable. La recursividad izquierda la resuelve Python/Shunting-Yard, no una gramática declarada. |
| Tabla de símbolos | `analizador_semantico.py:56-57`, `:176-177`, `:213-217` | Campos: `tipo`, `valor`, `scope="global"`. Direcciones en `self.direcciones` :176. Sin `incógnita`, `grado` ni `nParams`. |
| Analizador semántico | `analizador_semantico.py:54-343` | Evaluación estática con pila :78–148; errores acumulados en `self.errores`. |
| Generador de cuádruplos / tripletas | `generador_intermedio.py:283-307` (`nuevoTemp`, `nuevaEtiqueta`, `gen`), `:342-381`, `:616-654`, `:656-710` | También genera código P (`LDC/LOD/STO/...`). |
| Evaluador / intérprete | `analizador_semantico.py:78-148` (evaluación estática) y `tests/interprete_referencia.py:17-136` (intérprete de pruebas). Backend real: `generador_objeto.py:75-365` (NASM) | No existe un intérprete de NumLang para el usuario final. |
| Manejo de errores | `ErrorNumlang` en `analizador_semantico.py:10-12`; capturas en `:241-242`, `:263-264`, `:314-315`, `:321-326`; CLI `:365-374`; `generador_intermedio.py:390-392`, `:795-797`; `generador_objeto.py:479-483` | Los errores del generador (`:610`) no incluyen número de línea. |

---

## 3. FASE 2 — Checklist de la especificación (ítem por ítem)

Leyenda: ✅ OK · ⚠️ Parcial · ❌ Falta · 🐛 Bug.

### 2.1 Tipos de datos

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.1.1 | `num` = punto flotante doble, sin int/float/double | ⚠️ | `analizador_semantico.py:38,192,209`; `generador_intermedio.py:353`; `tests/interprete_referencia.py:48,53`; `gestor_memoria.py:32-39,110`; `generador_objeto.py:22,201-202,317-324` | **Intérprete ✅ (P0.2):** literales, símbolos y resultados son `float`; `5 + 0.1 → 5.1`. **Backend NASM ⚠️:** sigue `int(float(valor))`, `dd`/`%d`/`idiv`, por lo que `1.5 → 1` y `5/2 → 2`. Diferido a P3.5 (DT-1). |
| 2.1.2 | `bool` | ✅ | `analizador_semantico.py:91-95`, `:133-146`, `:155` | `bool b = 5 > 3` funciona; literales `verdadero/falso` evaluados como bool en el evaluador. |
| 2.1.3 | `msj` (cadena) | ✅ | `analizador_semantico.py:86-90`, `:155`, `:173-174` | `msj x = "hola"` y `mostrar x` → `hola`. |
| 2.1.4 | `ecu` estructural (incógnita y grado) | ❌ | `analizador_semantico.py:155-202`; `generador_intermedio.py:566-610` | No hay regex ni rama para `DefEcu`; no existe campo `incógnita`/`grado`. Casos 7/14/15 → "Instrucción no reconocida". |
| 2.1.5 | `func` (parámetros y expresión) | ❌ | `analizador_semantico.py:150-202`; `generador_intermedio.py:528-544` | `func f(x) = ...` no se parsea. Solo existe `funcion ... fin` multi-sentencia en el generador, bloqueado por el analizador (ver 2.11.5). |
| 2.1.6 | Constantes `PI`, `Eu`, `verdadero`, `falso` | ❌ | `analizador_semantico.py:96-103`; `generador_intermedio.py:175-176` | `PI`/`Eu` → "variable no declarada"; `verdadero`/`falso` → "variable no declarada". El mapeo a `True/False` del generador es código inalcanzable porque la semántica falla primero. |

### 2.2 Operadores y expresiones

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.2.1 | Aritméticos `+ - * /` | ⚠️ | `analizador_semantico.py:118-131`; `generador_objeto.py:317-324`; `tests/test_codigo_objeto.py:146-156` | Operadores presentes, pero `/` es división entera truncada en NASM (`-7/2 = -3`), incompatible con `num` doble. |
| 2.2.2 | Potencia `elevado_a` (der.) | ❌ | `analizador_semantico.py:21-24`; `generador_intermedio.py:26`, `:166`, `:227-232` | El evaluador no incluye `ast.Pow`; caso 2 → "Expresión mal escrita". El soporte aislado del generador es correcto (postfija `2 3 2 elevado_a elevado_a`, AST anidado a la derecha) pero inalcanzable. |
| 2.2.3 | Residuo `residuo_de` | ❌ | `analizador_semantico.py:21-24`; `generador_intermedio.py:167` | Caso 3 → "Expresión mal escrita". `%` tampoco funciona en la semántica (sonda P3). |
| 2.2.4 | Comparación `< > menor_o_igual mayor_o_igual igual_a distinto_de` | ⚠️ | `analizador_semantico.py:23`, `:133-146`; `generador_intermedio.py:168-171` | `<`/`>` ✅; `>=`, `<=`, `==`, `!=` aceptados como alias de símbolo (no en `T` de la spec); `menor_o_igual`, `mayor_o_igual`, `distinto_de` rechazados; `igual_a` solo se normaliza en el generador, nunca llega por la semántica (sondas E2–E5, P5). |
| 2.2.5 | Lógicos `y o no` | ❌ | `analizador_semantico.py:21-24`; `generador_intermedio.py:172-174`, `:243-257`, `:358-362` | `mostrar verdadero y falso` → "Expresión mal escrita"; `mostrar no falso` → ídem. El generador tiene cuádruplos `y/o/no`, pero son inalcanzables. |
| 2.2.6 | Menos unario | 🐛 | `analizador_semantico.py:47-48`, `:104-111`; `generador_intermedio.py:253-257` | Implementado, pero con precedencia de Python. `crear_arbol_extendido("-2 elevado_a 2")` produce `negativo(pow(2,2))` = **−4**, mientras la spec exige **4** (sonda E1). |
| 2.2.7 | Paréntesis | ✅ | `generador_intermedio.py:54-61`, `:111-115`; AST de Python en `:17`, `:201` | `mostrar (2 + 3) * 4` y paréntesis anidados funcionan; paréntesis desbalanceados → `ErrorNumlang` :60/:80. |
| 2.2.8 | Multiplicación siempre explícita (`2x` no, `2*x` sí) | ✅ | `analizador_semantico.py:17-19`, `:36-49`; `generador_intermedio.py:29-39` | `2x` → "Expresión mal escrita"; `2(3)` → "Operación no soportada"; `2*x` ✅ (sondas E13/E14, caso 1). |

### 2.3 Estructuras de control

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.3.1 | `si ... entonces ... fin` | ✅ | `analizador_semantico.py:230-249`; `generador_intermedio.py:437-461` | Caso 5: salida real `mayor`; cuádruplos `(>,5,3,t1)`, `(if_false,t1,-,Lfalso)`, `(etiqueta,-,-,Lfalso)`. |
| 2.3.2 | `si ... entonces ... si_no ... fin` | ✅ | `analizador_semantico.py:233-246`; `generador_intermedio.py:449-458` | `src/programa.src` y test `programa.src` → `mayor`; emite `goto Lfin` y `etiqueta Lfalso/Lfin`. |
| 2.3.3 | `mientras ... hacer ... fin` | ✅ | `analizador_semantico.py:252-268`; `generador_intermedio.py:464-483` | Caso 6 (`x < 10`) → `0..9`; `Linicio`/`Lfin`/`goto` correctos. |
| 2.3.4 | Condiciones deben ser BOOL (error semántico si no) | ✅ | `analizador_semantico.py:239-240`, `:261-262` | Caso 13 → "La condición del 'si' debe ser booleana, se recibió num". (Caveat de análisis estático en §5 C6.) |

### 2.4 Declaraciones e instrucciones

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.4.1 | `Tipo ID = Expr` | ✅ | `analizador_semantico.py:155`, `:159-179`; `generador_intermedio.py:567`, `:573-578` | Casos 1/9/11/12; emite `(=, Expr.lugar, -, ID)`. |
| 2.4.2 | `ID = Expr` (sin tipo) | ✅ | `analizador_semantico.py:156`, `:180-191`; `generador_intermedio.py:568`, `:603-608` | `num x = 5 / x = 6 / mostrar x` → 6 (sonda E15). |
| 2.4.3 | `mostrar Expr` | ✅ | `analizador_semantico.py:157`, `:193-200`; `generador_intermedio.py:569`, `:580-585` | Caso 5; opcode `mostrar` en cuádruplos y `WRT` en código P :696-698. |
| 2.4.4 | Comentarios con `nota:` | ✅ | `analizador_semantico.py:152-153`, `:207-209`; `generador_intermedio.py:396-398` | Solo a inicio de línea; `nota:` embebido en una sentencia no se ignora (ambigüedad §7). |
| 2.4.5 | `SALTO` como terminador | ✅ | `analizador_semantico.py:206-209`; `generador_intermedio.py:394-399` | Procesamiento línea a línea; además se tolera `;` opcional (`:151`, `:396`), extensión no especificada. |

### 2.5 Ecuaciones — ✅ completo (parser+semántico+evaluador)

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.5.1 | `ecu ID : Expr = Expr` | ✅ | `analizador_semantico.py:175,375`; `generador_intermedio.py:579,612` | **P0.3.a/b/d:** el parser reconoce `ecu ID : E1 = E2`, la semántica valida tipos, incógnita, grado y coeficientes, y `_evaluar_resolucion` (`:110`) imprime la solución. `2x` sigue fallando en fase sintáctica. Deuda P2: cuádruples de `resolver`. |
| 2.5.2 | Detección de exactamente UNA incógnita no declarada | ✅ | `analizador_semantico.py:241` | `_incognitas_en_arbol` (dedup por nombre, declarados excluidos) verificado de extremo a extremo por `tests/test_ecu_semantica.py` y `tests/test_resolver_evaluador.py`. |
| 2.5.3 | Validación de grado ≤ 2 | ✅ | `analizador_semantico.py:283`; tabla de símbolos `:375` | P0.3.b calcula grado/coeficientes con poda `1e-12`; P0.3.d usa `TOL_DISCRIMINANTE = 1e-9` (`:11`) para discriminante doble/reales y rechaza `grado > 2`. |
| 2.5.4 | `resolver ID para ID` verifica que el 2.º ID sea la incógnita | ✅ | `analizador_semantico.py:298,439,463` | P0.3.a/c validan forma, existencia, tipo ECU e incógnita; P0.3.d evalúa el nodo `valida=True`, imprime `x = 5` (formato del intérprete) y ordena las dos soluciones de mayor a menor. |

### 2.6 Funciones — ⚠️ parser OK, semántico/evaluador pendientes

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.6.1 | `func ID (Params) = Expr` | ⚠️ | `analizador_semantico.py:357,384`; `generador_intermedio.py:528-544` | **P0.4.a:** `func` reservada, regex DefFunc con 0/1/N params y cuerpo de una Expr; `ast.Call` en `crear_arbol` (`:40`). Falta insertar en símbolos y validar semántica/evaluador. |
| 2.6.2 | Parámetros son NUM dentro de la función | ❌ | `generador_intermedio.py:534-538`; `analizador_semantico.py:177` | `param_recibir` no valida tipos; no hay ámbito de función ni entrada `nParams`. |
| 2.6.3 | Llamada `ID(Args)` con verificación de n.º de argumentos | ❌ | `analizador_semantico.py:40`; `generador_intermedio.py:258-263`, `:363-372`, `:594-601` | **P0.4.a:** `crear_arbol` ya produce nodo `llamada`; falta validar existencia/aridad/tipos y evaluarlo. El generador emite `llamar` con `nArgs` pero **nunca compara** con una definición. |
| 2.6.4 | Retorno NUM | ❌ | `generador_intermedio.py:587-592`; `analizador_semantico.py:150-202` | Existe opcode `retornar` pero sin verificación de tipo; ambas sentencias son rechazadas por la semántica (sonda P10). |

### 2.7 Gramática y precedencia

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.7.1 | Precedencia exacta `paréntesis → menos unario → elevado_a (der) → * / residuo_de → + - → comparaciones → no → y → o` | 🐛 | `generador_intermedio.py:19-26`; `analizador_semantico.py:17`, `:201` | La ruta real usa Python: `-` unario tiene **menor** precedencia que `**` (`-2**2 = -4`). El Shunting-Yard sí declara `NEG:8 > elevado_a:7` (`:24-26`), pero no es la ruta que genera cuádruplos. |
| 2.7.2 | Gramática no ambigua | ⚠️ | `analizador_semantico.py:150-202`; `generador_intermedio.py:387-610` | No hay GLC ejecutable; el comportamiento es determinista para el subconjunto implementado, pero no se puede verificar la propiedad sobre las 29 producciones. Alias de símbolos (`>=`, `<=`, `==`, `%`) crean más de una forma de escribir lo mismo. |
| 2.7.3 | Recursividad izquierda manejada/transformada | ⚠️ | `generador_intermedio.py:42-83` (Shunting-Yard); `analizador_semantico.py:17` (AST de Python) | Se resuelve de facto con pila de operadores y con el parser de CPython; no hay transformación documentada de las producciones `Expr → Expr o ExprY`, `Suma → Suma + Term`, etc. |
| 2.7.4 | `elevado_a` asocia a la DERECHA (`2 elevado_a 3 elevado_a 2 = 512`) | ⚠️ | `generador_intermedio.py:26`, `:63-75`, `:227-232` | Asociatividad correcta en helpers aislados (postfija `2 3 2 elevado_a elevado_a`; AST anidado a la derecha), pero el caso 2 falla en el pipeline por el analizador semántico. |

### 2.8 Reglas semánticas

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.8.1 | Sin conversión automática entre tipos | ✅ | `analizador_semantico.py:119-120`, `:173-174`, `:188-189` | Caso 12 → error. El `float()` interno de la optimización (:31-44 de `motor_optimizacion.py`) es solo plegado de literales, no conversión de tipos de lenguaje. |
| 2.8.2 | Tipos exactos en declaración/asignación | ✅ | `analizador_semantico.py:173-174`, `:188-189` | Mensajes: "se esperaba num, se recibió msj" / "Tipos incompatibles en asignación". |
| 2.8.3 | Variable no declarada | ✅ | `analizador_semantico.py:97-99`, `:182-183` | Caso 10 → "La variable 'y' no está declarada". |
| 2.8.4 | Redeclaración | ⚠️ | `analizador_semantico.py:166-167`, `:329-343` | Caso 11 ✅; pero ramas mutuamente excluyentes de `si/si_no` producen falso positivo (sonda P6: `num z` en ambas ramas → error). |
| 2.8.5 | División entre cero detectada | ⚠️ | `analizador_semantico.py:127`; `generador_objeto.py:317-324`; P7 | Caso 9 ✅ (detección estática), pero `5/d` con `d=0` tras un ciclo pasa la semántica y el intérprete referencia lanza `ZeroDivisionError` (sonda P7). |
| 2.8.6 | Uso de variable antes de declarar → error | ✅ | `analizador_semantico.py:97-99`, `:206-211` | Procesamiento secuencial; caso 10 y E6 (`b` usado después de fallar su declaración) confirman. |
| 2.8.7 | `igual_a` / `distinto_de` requieren mismo tipo | ❌ | `analizador_semantico.py:133-135`; `generador_intermedio.py:168-169` | Las palabras `igual_a`/`distinto_de` no se aceptan (E4/E5). Los alias `==`/`!=` sí exigen igualdad de tipos (`:134`), pero no son la sintaxis spec. |
| 2.8.8 | `< > menor_o_igual mayor_o_igual` requieren NUM en ambos lados | 🐛 | `analizador_semantico.py:133-146` | Solo exige `tipo_izq == tipo_der`: `mostrar "a" < "b"` es **aceptado** y devuelve 1 (sonda P1). Las formas verbales `menor_o_igual`/`mayor_o_igual` no existen. |

### 2.9 Tabla de símbolos

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.9.1 | Almacena nombre, tipo, valor | ✅ | `analizador_semantico.py:176-177`, `:216-217` | `self.simbolos[nombre] = {"tipo": ..., "valor": ..., "scope": "global"}`; `src/correcto.src` produce `a, b, resultado` con valores 4, 3, 10. |
| 2.9.2 | Para `ecu`: incógnita y grado | ❌ | `analizador_semantico.py:177` | Estructura de entrada fija; sin campos `incógnita`/`grado`. |
| 2.9.3 | Para `func`: `nParams` | ❌ | `generador_intermedio.py:368-370`, `:538` | `nArgs` se cuenta al emitir `llamar`, pero nunca se almacena en la tabla de símbolos. |
| 2.9.4 | Ámbitos (scopes), si aplica | ⚠️ | `analizador_semantico.py:177`, `:301`, `:244-246`, `:266` | `scope` es siempre la cadena `"global"`; no hay pila de ámbitos. Variables declaradas en ramas de `si` quedan visibles después. |

### 2.10 Código intermedio

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.10.1 | Cuádruplos `(op, arg1, arg2, res)` | ✅ | `generador_intermedio.py:294-307`, `:733-741` | Caso 1: `(=,4,-,a)`, `(*,b,2,t1)`, `(+,a,t1,t2)`, `(=,t2,-,resultado)`. |
| 2.10.2 | Función `gen(op, arg1, arg2, res)` | ✅ | `generador_intermedio.py:294-307` | Firma con valores por defecto `"-"`; devuelve índice 1-based. |
| 2.10.3 | Función `nuevoTemp()` | ✅ | `generador_intermedio.py:283-286` | `t1, t2, ...`. |
| 2.10.4 | Función `nuevaEtiqueta()` | ✅ | `generador_intermedio.py:288-292` | `Lfalso`, `Lfalso2`, `Lfin`, `Linicio`. |
| 2.10.5 | `-` para arg2 vacío en unarias/asignaciones | ✅ | `generador_intermedio.py:294`, `:311-334`, `:356`, `:577` | `(=,4,-,a)`, `(if_false,t1,-,Lfalso)`, `(mostrar,"mayor",-,-)`. |
| 2.10.6 | Temporales `t1, t2, ...` | ✅ | `generador_intermedio.py:283-286`, `:376-380` | Asignador de registros los mapea a EBX/ESI/EDI (`asignador_registros.py:32-129`). |
| 2.10.7 | Etiquetas `Lfalso`, `Lfin`, `Linicio` | ✅ | `generador_intermedio.py:445`, `:450`, `:470-471`, `:479-480` | Casos 5 y 6 muestran las tres etiquetas. |
| 2.10.8 | Opcodes `+ - * / elevado_a residuo_de < > igual_a distinto_de y o no = if_false goto etiqueta llamar mostrar` | ⚠️ | `generador_intermedio.py:205-213`, `:356-372`, `:447-480`, `:577-584`; `generador_objeto.py:24-39` | Emitidos: `+ - * / < > <= >= == != y o no neg = if_false goto etiqueta llamar mostrar param retornar campo_estructura`. **Nunca se emiten** `elevado_a`, `residuo_de`, `igual_a`, `distinto_de` en la ruta real (se normalizan a `**`, `%`, `==`, `!=`, o se rechazan). El backend usa además `diferente_de`, `menor_que`, `mayor_que` (`generador_objeto.py:34-36`), nombres distintos a la spec. |
| 2.10.9 | (Opcional) tripletas con referencia por índice | ✅ | `generador_intermedio.py:616-654`, `:743-751`; `motor_optimizacion.py:148-177` | `(4) + a (3)` para `a + b*2`; `mapa_temporales` resuelve `t1 → (3)`. |

### 2.11 Limitaciones (verificar que NO estén implementadas)

| # | Limitación de la spec | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.11.1 | Sin arreglos, matrices ni listas | ✅ | búsqueda global: sin `[` en gramática de sentencias | Ningún operador/indexador; `2x` y `x[0]` son error de sintaxis. |
| 2.11.2 | Sin derivadas, integrales ni límites | ✅ | — | No hay tokens ni palabras reservadas relacionadas. |
| 2.11.3 | Sin álgebra simbólica (factorizar/simplificar con variables) | ⚠️ | `motor_optimizacion.py:49-63` | El optimizador aplica `x+0 → x`, `x*1 → x`, `x*0 → 0` sobre cuádruplos con variables. No es factorización, pero sí "simplificación con variables", que la spec p.4/p.24 excluye; en cambio la spec p.19 exige esas identidades. Ambigüedad §7. |
| 2.11.4 | Sin sistemas de ecuaciones ni grado > 2 | ✅ | `analizador_semantico.py:150-202` | No hay ecuaciones en absoluto; la limitación se respeta por ausencia total. |
| 2.11.5 | Sin ciclo `para`, recursividad ni funciones multi-sentencia | ❌ | `analizador_semantico.py:270-319`; `generador_intermedio.py:485-525`, `:527-544`; `tests/test_codigo_objeto.py:160-170`; `src/prueba_for.src` | **`para` está implementado y probado** (`para i = 1 hasta 5 paso -1` → `5..1`). `funcion ... fin` está implementado en el generador; la recursividad no está implementada. |
| 2.11.6 | Sin entrada de usuario, archivos ni gráficas | ✅ | — | No hay `leer`, `archivo` ni primitivas gráficas; la GUI es herramienta de desarrollo, no entrada del lenguaje. |
| 2.11.7 | Sin números complejos | ✅ | `analizador_semantico.py:27-29` | Solo `float`, `str`, `bool`. |
| 2.11.8 | Sin conversión automática de tipos | ✅ | `analizador_semantico.py:173-174`, `:188-189` | Caso 12 confirma rechazo. La truncación a entero del backend es pérdida de precisión, no conversión entre tipos NumLang. |

### 2.12 Restricciones de diseño

| # | Requisito | Estado | Archivo:línea | Evidencia |
|---|---|---|---|---|
| 2.12.1 | `=` en `ecu` = igualdad; en decl/asig = asignación | ❌ | `analizador_semantico.py:155-156`; `generador_intermedio.py:566-568` | En decl/asig ✅ (`gen("=",...)`); la igualdad de ecuación no existe: `ecu ... = ...` se rechaza como sentencia desconocida. |
| 2.12.2 | Incógnita de ecuación NO se declara | ⚠️ | `analizador_semantico.py:96-103`, `:166-167` | No aplicable sin ecuaciones; además hoy cualquier ID (incluido `x`) puede declararse, por lo que no se impide el conflicto. |
| 2.12.3 | `num` internamente float doble | ⚠️ | `analizador_semantico.py:38,192,209`; `generador_intermedio.py:353`; `tests/interprete_referencia.py:48,53`; `gestor_memoria.py:110`; `generador_objeto.py:22,201-202,243-245` | **Intérprete ✅ (P0.2):** `float` de Python en toda la evaluación; salida entera se formatea sin `.0` para conservar compatibilidad. **Backend NASM ⚠️:** imprime `1` para `1.5`; diferido a P3.5 (DT-1). |
| 2.12.4 | IDs no pueden coincidir con reservadas ni funciones nativas | 🐛 | `analizador_semantico.py:66-71`, `:163-164`; `generador_intermedio.py:190-194` | La lista omite `ecu`, `func`, `resolver`, `elevado_a`, `residuo_de`, `igual_a`, `distinto_de`, `menor_o_igual`, `mayor_o_igual`, `PI`, `Eu`, `nota` e incluye `hasta`, `paso`, `funcion`, `retornar`, `estructura`, `const`, que no están en la spec. Sondas E11/E12: `num ecu = 5` y `num resolver = 5` funcionan. No hay "funciones nativas" registradas. |
| 2.12.5 | Regex ID `[a-zA-Z_][a-zA-Z0-9_]*` | ✅ | `analizador_semantico.py:155-156`; `generador_intermedio.py:35`, `:567-568` | Coincide en la semántica. El generador usa `\w*`, que admite unicode (ej. `á`), desviación menor. |
| 2.12.6 | Regex NUM `[0-9]+(\.[0-9]+)?` | 🐛 | `generador_intermedio.py:36`; `analizador_semantico.py:17`, `:27-29` | El tokenizador sí usa ese patrón, pero el evaluador usa `ast.parse` de Python: `1e3`, `0x10`, `1_000` son aceptados. Sonda E9: `num x = 1e3` → `1000`. |
| 2.12.7 | Regex CADENA `"[^"]*"` | 🐛 | `generador_intermedio.py:32`, `:190`; `analizador_semantico.py:30-31`; `generador_objeto.py:44-46` | Comillas simples son aceptadas: `msj x = 'hola'` → `hola` (sonda E10). También se aceptan escapes de Python (`"a\nb"`). |

---

## 4. FASE 3 — Pruebas de comportamiento

Ejecución real: CLI `python generador_intermedio.py <archivo> --json`, intérprete de cuádruplos de `tests/interprete_referencia.py` y, cuando compila, `python generador_objeto.py <archivo> -o ... --ejecutar` (NASM + gcc -m32 disponibles).

| # | Programa mínimo | Esperado (spec) | Salida real | Veredicto |
|---|---|---|---|---|
| 1 | `num a = 4` / `num b = 3` / `num resultado = a + b * 2` / `mostrar resultado` | `10` | `10` (CLI rc=0; .exe imprime `10`; cuádruplos `t1=b*2`, `t2=a+t1`) | ✅ |
| 2 | `mostrar 2 elevado_a 3 elevado_a 2` | `512` | `Error: Errores semánticos detectados: Línea 1: Expresión mal escrita: '2 elevado_a 3 elevado_a 2'` | ❌ |
| 3 | `mostrar 7 residuo_de 3` | `1` | `Error: ... Línea 1: Expresión mal escrita: '7 residuo_de 3'` | ❌ |
| 4 | `mostrar PI` / `mostrar Eu` | `3.141592653589793` / `2.718281828459045` | `Línea 1: La variable 'PI' no está declarada`; `Línea 2: La variable 'Eu' no está declarada` | ❌ |
| 5 | `si 5 > 3 entonces` / `mostrar "mayor"` / `fin` | `mayor` | `mayor` (.exe incluido) | ✅ |
| 6 | `num x = 0` / `mientras x < 10 hacer` / `mostrar x` / `x = x + 1` / `fin` | `0 1 2 3 4 5 6 7 8 9` | `0\n1\n2\n3\n4\n5\n6\n7\n8\n9\n` (.exe incluido) | ✅ |
| 7 | `ecu e1: 2*x + 5 = 15` / `resolver e1 para x` | `x = 5` | `Línea 1: Instrucción no reconocida: 'ecu e1: 2*x + 5 = 15'`; `Línea 2: Instrucción no reconocida: 'resolver e1 para x'` | ❌ |
| 8 | `func f(x) = x elevado_a 2 + 1` / `mostrar f(3)` | `10` | `Línea 1: Instrucción no reconocida: 'func f(x) = x elevado_a 2 + 1'`; `Línea 2: Operación no soportada en la expresión` | ❌ |
| 9 | `num x = 10 / 0` | error de división entre cero | `Línea 1: División entre cero` (detección estática, no en ejecución) | ⚠️ |
| 10 | `mostrar y` (sin declarar) | error de variable no declarada | `Línea 1: La variable 'y' no está declarada` | ✅ |
| 11 | `num x = 5` / `num x = 6` | error de redeclaración | `Línea 2: La variable 'x' ya fue declarada` | ✅ |
| 12 | `num x = "hola"` | error de tipo | `Línea 1: Tipos incompatibles: se esperaba num, se recibió msj` | ✅ |
| 13 | `si 5 entonces` / `mostrar "x"` / `fin` | error, condición no BOOL | `Línea 1: La condición del 'si' debe ser booleana, se recibió num` | ✅ |
| 14 | `ecu e2: x^3 = 8` | error por grado > 2 | Error, pero por `Instrucción no reconocida: 'ecu e2: x^3 = 8'`; nunca se evalúa el grado (y `^` sería XOR en Python) | ⚠️ |
| 15 | `ecu e3: x + y = 10` | error por más de una incógnita | Error, pero por `Instrucción no reconocida: 'ecu e3: x + y = 10'`; nunca se cuentan incógnitas | ⚠️ |

### 4.1 Sondas adicionales (evidencia de las discrepancias)

| Sonda | Programa / expresión | Resultado real | Qué demuestra |
|---|---|---|---|
| E1 | `crear_arbol_extendido("-2 elevado_a 2")` | `{"tipo":"negativo","expresion":{... "elevado_a" 2 2}}` → −4 | Precedencia unario/potencia invertida (spec → 4). |
| E2/E3 | `mostrar 5 menor_o_igual 10` / `5 mayor_o_igual 10` | "Expresión mal escrita" | Operadores verbales de la spec ausentes. |
| E4/E5 | `mostrar 5 distinto_de 10` / `5 igual_a 5` | "Expresión mal escrita" | `distinto_de` e `igual_a` inutilizables. |
| E6–E8 | `bool b = verdadero`, `verdadero y falso`, `no falso` | errores ("variable no declarada" / "Expresión mal escrita") | Constantes y lógicos no implementados en la ruta real. |
| E9 | `num x = 1e3` | rc=0, salida `1000` | NUM acepta notación científica, fuera del regex spec. |
| E10 | `msj x = 'hola'` | rc=0, salida `hola` | CADENA acepta comilla simple, fuera del regex spec. |
| E11/E12 | `num ecu = 5`, `num resolver = 5` | rc=0, salida `5` | Palabras reservadas de la spec no protegidas. |
| E13/E14 | `num x = 2x`, `num x = 2(3)` | errores | Multiplicación implícita correctamente rechazada. |
| P1 | `mostrar "a" < "b"` | rc=0, salida `1` | `<` no exige NUM; comparación de cadenas permitida. |
| P2 | `bool b = True` | rc=0, salida `1` | Se filtra el literal Python `True`, no spec. |
| P6 | `num z` en ambas ramas de `si/si_no` | "Línea 4: La variable 'z' ya fue declarada" | Falso positivo por análisis de ramas excluyentes. |
| P7 | ciclo que deja `d=0` y luego `5 / d` | semántica OK; intérprete → `ZeroDivisionError` | División por cero en ejecución sin guardia. |
| F1 | `num a = 1.5` / `mostrar a` | `.asm`: `v_a: dd 1`, `fmt_int`, salida `1` | `num` truncado a entero de 32 bits. |

---

## 5. Discrepancias críticas

**C1 — El lenguaje diferencial no existe en la ruta ejecutable.** `ecu`, `resolver`, `func`, `PI`, `Eu`, `verdadero`, `falso`, `elevado_a`, `residuo_de`, `y`, `o`, `no`, `igual_a`, `distinto_de`, `menor_o_igual`, `mayor_o_igual` son rechazados por `crear_arbol` (`analizador_semantico.py:21-24`) o por el tiny-parser de sentencias (`:155-157`). Los reemplazos de `generador_intermedio.py:165-177` y los opcodes de `generador_objeto.py:24-39` son código muerto en la práctica: `compilar_programa` llama primero a `analizar_codigo` y aborta (`generador_intermedio.py:390-392`). Impacto: casos 2, 3, 4, 7, 8 fallan; casos 14/15 fallan por la razón equivocada.

**C2 — Precedencia menos unario vs. potencia invertida.** La spec (p.6 y p.7) exige que el unario se aplique antes que `elevado_a`; `crear_arbol_extendido` delega en CPython (`generador_intermedio.py:199-201`), donde `-2 ** 2 = -(2**2)`. El Shunting-Yard interno sí tiene `NEG:8` y `elevado_a:7` (`generador_intermedio.py:24-26`), pero solo se usa para las vistas prefija/postfija, no para los cuádruplos. Impacto: incluso habilitando `elevado_a`, `-2 elevado_a 2` daría −4 en lugar de 4.

**C3 — `num` no es double en el destino.** `entero_nasm` (`gestor_memoria.py:32-39`) y `PATRON_NUMERO` (`generador_objeto.py:22`, `:201-202`) convierten todo literal a `int`; `fmt_int`/`idiv` (`gestor_memoria.py:66`, `generador_objeto.py:317-324`) fijan aritmética entera. La spec p.5/p.20 exige float de doble precisión y traducción a Python. Impacto: `1.5 → 1`, `5/2 → 2`; la exactitud de todo cálculo con decimales se pierde.

**C4 — Lista de palabras reservadas errónea.** `analizador_semantico.py:66-71` incluye términos que no están en el terminal de la spec (`para`, `hasta`, `paso`, `funcion`, `retornar`, `estructura`, `const`) y omite los que sí lo están (`ecu`, `func`, `resolver`, `elevado_a`, `residuo_de`, `igual_a`, `distinto_de`, `menor_o_igual`, `mayor_o_igual`, `PI`, `Eu`, `nota`). El único punto de control es `:163-164` para declaraciones y `:276-277` para `para`. Impacto: identificadores que deberían estar prohibidos son legales (E11/E12), y etiquetas/operadores verbales pueden colisionar con nombres de usuario. Tampoco existe registro de "funciones nativas".

**C5 — División entre cero solo se detecta en análisis estático.** `analizador_semantico.py:127` lanza el error solo cuando evalúa la expresión en ese instante; los cuádruplos `(`/`)` no llevan guardia (`generador_objeto.py:317-324`). La sonda P7 muestra un divisor que vale 0 en ejecución pero no en análisis: el intérprete referencia lanza `ZeroDivisionError` sin mensaje en español y el backend NASM ejecutaría `idiv ecx` con `ecx=0`. La spec p.22 pide mensaje "Error: división entre cero" en ejecución; la p.13 la trata como regla semántica. Ambas lecturas están incumplidas en el caso dinámico.

**C6 — Análisis de control con efectos colaterales y sin ámbitos.** `_procesar_bloque` (`analizador_semantico.py:223-343`) recorre **ambas** ramas de `si/si_no` (`:244-246`) y el cuerpo de `mientras` una sola vez (`:266`), ejecutando `evaluar` y mutando `self.simbolos`. Consecuencias: falso error de redeclaración en ramas excluyentes (P6), variables que "se declaran" dentro de un bloque y quedan visibles fuera, y condiciones cuyo tipo se infiere con el valor de la primera pasada. `scope` es una cadena constante (`analizador_semantico.py:177`).

**C7 — Léxico real más permisivo que la spec.** `crear_arbol` usa `ast.parse` (`analizador_semantico.py:17`) y por tanto acepta `1e3`, `0x10`, `1_000`, `'hola'`, `True`, `False`, además de operadores Python `^`, `|`, `//`, `**` (algunos son rechazados por el conversor, otros no). El tokenizador propio (`generador_intermedio.py:29-39`) implementa los regex correctos, pero no gobierna la validación. Impacto: programas inválidos según la spec compilan (E9, E10, P2).

**C8 — Características explícitamente excluidas están presentes.** El ciclo `para` está en `analizador_semantico.py:270-319` y `generador_intermedio.py:486-525`, con tests dedicados (`tests/test_codigo_objeto.py:160-170`) y `src/prueba_for.src`. `funcion ... fin` (funciones multi-sentencia) está en `generador_intermedio.py:528-544` y `estructura` en `:547-560`. La spec p.4/p.24/p.25 las enumera como fuera de alcance. No es un bug funcional, pero sí una desviación de alcance que además consume nombres reservados.

**C9 — Nombres de opcode y de operadores divergentes.** La spec usa `distinto_de`, `menor_o_igual`, `mayor_o_igual`, `igual_a`; el código usa `diferente_de`, `menor_que`, `mayor_que` (`generador_intermedio.py:33`, `:169-171`; `generador_objeto.py:34-36`) y símbolos `<=`, `>=`, `==`, `!=`. Ningún cuádruplo real contiene `elevado_a`, `residuo_de`, `igual_a` ni `distinto_de`: se normalizan a `**`, `%`, `==`, `!=` antes de `gen` (`generador_intermedio.py:165-177`, `:205-213`). Impacto: la tabla de cuádruplos no es la descrita en la spec p.14–17.

**C10 — No hay gramática libre de contexto ejecutable.** La spec define 29 producciones y afirma aptitud LALR(1) (pp. 6, 24–25). El proyecto implementa un analizador ad-hoc basado en `re.fullmatch` por línea (`analizador_semantico.py:155-157`, `generador_intermedio.py:566-572`) más el parser de CPython para expresiones (`analizador_semantico.py:17`, `generador_intermedio.py:201`). No se puede verificar "no ambigua" ni "recursividad izquierda transformada"; la afirmación de la spec sobre LALR no tiene contraparte en código.

---

## 6. Discrepancias menores

1. **Terminador `;` tolerado.** `analizador_semantico.py:151`, `generador_intermedio.py:396` eliminan un `;` final opcional; la spec define `SALTO` como terminador. Extensión inofensiva pero no especificada.
2. **Renumeración de cuádruplos tras optimizar.** `motor_optimizacion.py:66-95`, `:98-138` eliminan entradas sin recalcular el campo `num` asignado en `generador_intermedio.py:296`. Las tripletas optimizadas sí renumeran (`:153-154`), por lo que ambas representaciones pueden discrepar.
3. **Optimización de ciclos ficticia.** `motor_optimizacion.py:141-145` solo registra un mensaje; no hay reducción de fuerza real pese al reporte de "ahorro".
4. **Errores sin línea en el generador.** `generador_intermedio.py:610`, `:795-797` informan "Instrucción no reconocida" sin número de línea, mientras el analizador sí lo incluye (`analizador_semantico.py:325`).
5. **`nota:` solo al inicio de línea.** Un comentario embebido como `num x = 5 nota: ...` no se ignora (`:152`, `:207-209`); la spec no lo aclara.
6. **Identificadores con punto.** `generador_intermedio.py:35` y `:225-226` aceptan `a.b` como nombre, fuera del regex ID; `campo_estructura` (`:332`, `:552-558`) da soporte a una característica excluida.
7. **Manejo de cadenas frágil.** `normalizar_expresion_numlang` divide por `"`/`'` con `re.split` (`generador_intermedio.py:190-194`); comillas escapadas y cadenas multilínea no se tratan.
8. **Representación de salida booleana.** NASM usa `fmt_int` para todo lo que no sea cadena (`generador_objeto.py:243-245`), por lo que `mostrar verdadero` —si se habilitara— imprimiría `1`, no `verdadero`. La spec no define esta representación.
9. **GUI muestra traceback crudo.** `interfaz_grafica.py:287-311` muestra `traceback.format_exc()` ante errores de compilación en lugar del mensaje semántico acumulado.
10. **Alias de Python filtrados.** Los reemplazos `y→and`, `o→or`, `no→not` (`generador_intermedio.py:172-174`) también permiten escribir directamente `and`, `or`, `not`, `True`, `False` cuando la semántica está desactivada; no son terminales de la spec.
11. **`^` no es potencia.** En el caso 14, `x^3` sería XOR en Python si se habilitara ecuaciones; la spec usa `elevado_a` y solo emplea `^` en prosa (pp. 2, 19). Riesgo de implementación futura.
12. **Pruebas sesgadas.** `tests/test_codigo_objeto.py:20-36` solo ejercita 6 programas del subconjunto implementado; no hay tests unitarios de `gen`, `nuevoTemp`, precedencia, ecuaciones ni funciones.

---

## 7. Ambigüedades del documento y criterio adoptado

1. **Arquitectura destino.** La spec pp. 20–22 elige la PVM de Python (`float`, `math.pi`, `print`), pero el proyecto genera NASM x86-32 (`docs/codigo_objeto.md:1-12`, `generador_objeto.py:1`). El checklist del usuario no exige la arquitectura, así que se auditó el comportamiento observable; aun así, la restricción "num = doble" se incumple en NASM (C3). *Interpretación propuesta:* tratar NASM como extensión legítima solo si se implementa aritmética de doble precisión; de lo contrario, alinear con la spec.
2. **División entre cero: ¿semántica o ejecución?** La p. 13 exige "no se permitirá dividir entre cero"; la p. 22 afirma que "solo puede detectarse durante la ejecución"; la p. 9 la lista entre errores semánticos detectados. *Interpretación:* exigir ambas —detección estática cuando el divisor es literal conocido **y** guardia en ejecución con mensaje en español—. El código solo hace la primera (C5).
3. **Ámbitos.** El objetivo específico de la p. 3 pide "manejo de variables y ámbitos", pero la gramática (p. 6) no define bloques con ámbito propio y la tabla de símbolos de ejemplo (p. 12) es global. El checklist dice explícitamente "si aplica". *Interpretación:* ámbitos son opcionales; se calificó como ⚠️ por el campo `scope` inerte y el análisis de ramas, no como ❌.
4. **`^` en los ejemplos.** Aparece en `x^2+2x+1` (p. 2) y `x^3=8` (caso 14 del usuario), pero `^` no está en el conjunto de terminales (p. 5); la potencia es `elevado_a`. *Interpretación:* `^` es taquigrafía proseada, no sintaxis válida; el error del caso 14 se atribuye a la ausencia de `ecu`, no a que `^` debiera aceptarse.
5. **Tipos de las constantes.** `PI`/`Eu` se describen como "Especiales" (p. 2) fuera de `Tipo ∈ {num, bool, msj}` (p. 6), y no hay producción `Const -> PI | Eu`. *Interpretación:* son identificadores predefinidos de tipo NUM; por eso se calificó su ausencia como ❌ y no como ambigüedad insoluble.
6. **Funciones nativas.** La p. 5 prohíbe IDs que coincidan con "nombres de funciones nativas", pero nunca se enumeran. *Interpretación:* conjunto vacío hasta nueva definición; aun así, las palabras reservadas explícitas de la p. 5 sí deben protegerse (C4).
7. **Comentarios `nota:`.** Los ejemplos los muestran al inicio de línea (p. 16, `src/*.src`); no se especifica comentario embebido. *Interpretación:* comentario de línea completa; el comportamiento actual es aceptable.
8. **Formato de salida de `mostrar`.** La spec dice `mostrar → print()` (p. 20) pero no define si un bool se imprime como `verdadero` o `1`. *Interpretación:* se evaluó solo el valor, no la representación; se anotó como menor (§6.8).
9. **Álgebra simbólica vs. optimización.** La p. 4 excluye "simplificar expresiones con variables", pero la p. 19 exige `x*1 → x`, `x+0 → x`, `x^1 → x`. *Interpretación:* la exclusión se refiere a factorización/simplificación algebraica general, no a identidades locales; por eso el ítem 2.11.3 es ⚠️ y no ❌, y se recomienda homologar el documento.
10. **`SALTO` vs. `;`.** La p. 10 muestra sentencias terminadas con `;` en prosa, pero la GLC (p. 6) las termina con `SALTO`. *Interpretación:* `SALTO` manda; tolerar `;` es una extensión benigna registrada en §6.1.

---

## 8. Recomendaciones priorizadas

### P0 — Crítico (impacto directo en la spec)

1. **Unificar el front-end.** Reemplazar `crear_arbol` (`analizador_semantico.py:14-51`) por el mismo canonicalizador que `normalizar_expresion_numlang`/`crear_arbol_extendido` (`generador_intermedio.py:165-266`), corrigiendo los nombres a los de la spec (`distinto_de`, `menor_o_igual`, `mayor_o_igual`) y eliminando alias Python. Esto desbloquea de un solo cambio los casos 2, 3, 4 y E2–E8.
2. **Implementar `DefEcu` y `Resolver`.** Nuevas ramas en `ejecutar_instruccion` (`analizador_semantico.py:150-202`), búsqueda de exactamente una incógnita no declarada, cálculo de grado ≤ 2, entrada en tabla de símbolos con `incógnita`/`grado` y resolución por fórmula general (p. 22). Casos 7, 14, 15.
3. **Implementar `DefFunc` de una expresión.** `func ID(Params) = Expr`, validación de parámetros NUM, `nParams` en símbolos y chequeo de `nArgs` en `llamada_funcion` (`generador_intermedio.py:258-263`). Caso 8.
4. **Registrar constantes.** `PI`, `Eu` como NUM predefinidos; `verdadero`/`falso` como BOOL en el evaluador, con valores `math.pi`/`math.e` en el destino. Caso 4.
5. **Corregir precedencia.** Ajustar el AST extendido para que `-` unario se evalúe antes que `elevado_a` (spec p. 6), o bien cambiar la spec si se decide adoptar precedencia Python; documentar la decisión. Sonda E1.
6. **Corregir léxico.** Usar un único tokenizador con los regex de la p. 5 en toda la pipeline; eliminar `1e3`, `'hola'`, `True`, `False`, `^`, `%`, `**` como azúcar accidental. Sondas E9/E10/P2.
7. **Corregir palabras reservadas.** Sustituir el conjunto de `analizador_semantico.py:66-71` por el de la p. 5 más `nota`, e implantar la restricción también en asignaciones y parámetros, no solo en declaraciones. Sondas E11/E12.
8. **Decidir el destino numérico.** Si se conserva NASM, emitir float de doble precisión (`dd` con `printf("%g")`, x87/SSE) o, si se adopta la PVM de la spec, generar Python. P0.2 ya corrigió el intérprete; el backend sigue con `1.5 → 1` (F1) y queda diferido a P3.5 (DT-1).
9. **División por cero en ejecución.** Emitir guardia en el cuádruplo `/` (o verificar en el intérprete/backend) con mensaje "Error: división entre cero", además de la detección estática actual. Sonda P7.
10. **Aislar análisis de ramas.** No mutar la tabla de símbolos al analizar `si/si_no`/`mientras`; hacer tipos separados de evaluación y manejar ámbitos con pila si se decide que "si aplica". Sonda P6.

### P1 — Alto

11. Formalizar la GLC de 29 producciones en un parser (PLY/ANTLR o descendente recursivo) y eliminar el parseo por `re.fullmatch` por línea; esto permite reclamar "no ambigua / LALR(1)" con evidencia.
12. Emitir los opcodes exactos de la spec (`elevado_a`, `residuo_de`, `igual_a`, `distinto_de`) en `gen`, en lugar de normalizarlos a `**`/`%/==`/`!=`, y retirar `diferente_de`/`menor_que`/`mayor_que`.
13. Incluir número de línea en todos los errores del generador; mostrar mensajes semánticos en la GUI en vez de tracebacks.
14. Renumerar el campo `num` de los cuádruplos después de optimizar o eliminar ese campo de la representación canónica; recomputar tripletas desde la tabla final.
15. Completar la comprobación de tipos relacionales (`< > <= >=` solo NUM) y lógicos (`y/o/no` solo BOOL) en el analizador semántico.

### P2 — Nice-to-have / documentación

16. Retirar `para`, `funcion` y `estructura`, o documentarlos explícitamente como extensiones fuera de spec; actualizar `LEEME.md:37-39`, que hoy lista palabras reservadas que no son de la spec.
17. Añadir tests para `gen`, `nuevoTemp`, `nuevaEtiqueta`, precedencia, tripletas y los 15 casos de esta auditoría.
18. Homologar el PDF en los puntos §7.1, §7.2 y §7.9 para que "doble precisión", "detección en ejecución" y "simplificación con variables" no se contradigan.
19. Eliminar código muerto (`campo_estructura`, `param_recibir`, `optimizar_ciclos`, `funcion`) o marcarlo claramente como experimental.
20. Soportar `nota:` embebido y definir la representación de salida de `bool` en `mostrar`.

---

## 9. Anexo — Fragmentos citados textualmente

**`analizador_semantico.py:21-24` — operadores soportados por el evaluador real (sin potencia, residuo ni lógicos):**

```python
    operaciones = {
        ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
        ast.Gt: ">", ast.Lt: "<", ast.GtE: ">=", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!="
    }
```

**`analizador_semantico.py:66-71` — palabras reservadas (desalineadas con la spec):**

```python
        self.palabras_reservadas = {
            "num", "msj", "bool", "mostrar", "si", "si_no", "entonces", 
            "mientras", "para", "hasta", "paso", "hacer", "fin", 
            "y", "o", "no", "verdadero", "falso", "funcion", "retornar", 
            "estructura", "const"
        }
```

**`analizador_semantico.py:155-157` — "parser" de sentencias (no reconoce `ecu`, `func`, `resolver`):**

```python
        declaracion = re.fullmatch(r"(num|msj|bool)\s+([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(.+)", texto)
        asignacion = re.fullmatch(r"([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(.+)", texto)
        salida = re.fullmatch(r"mostrar\s+(.+)", texto)
```

**`analizador_semantico.py:239-240` y `:244-246` — condición y recorrido de ambas ramas:**

```python
                    if tipo != "bool":
                        raise ErrorNumlang(f"La condición del 'si' debe ser booleana, se recibió {tipo}")
...
                self._procesar_bloque(i + 1, idx_sino if idx_sino != -1 else idx_fin)
                if idx_sino != -1:
                    self._procesar_bloque(idx_sino + 1, idx_fin)
```

**`analizador_semantico.py:127` — división entre cero solo en evaluación estática:**

```python
                if b == 0: raise ErrorNumlang("División entre cero")
```

**`generador_intermedio.py:24-26` — precedencia correcta solo en el convertidor de notaciones:**

```python
    "elevado_a": 7, "**": 7, "NEG": 8,
}
ASOCIATIVIDAD_DERECHA = {"elevado_a", "**", "no", "NEG"}
```

**`generador_intermedio.py:165-177` — nombres de operadores que no coinciden con la spec (`diferente_de`, `menor_que`, `mayor_que`):**

```python
REEMPLAZOS_OPERADORES = [
    (r"\belevado_a\b", "**"),
    (r"\bresiduo_de\b", "%"),
    (r"\bigual_a\b", "=="),
    (r"\bdiferente_de\b", "!="),
    (r"\bmenor_que\b", "<"),
    (r"\bmayor_que\b", ">"),
```

**`generador_intermedio.py:283-307` — funciones auxiliares exigidas por la spec (sí presentes):**

```python
    def nuevoTemp(self) -> str:
        self.contador_temp += 1
        return f"t{self.contador_temp}"

    def nuevaEtiqueta(self, base: str = "L") -> str:
        conteo = self.contadores_etiquetas.get(base, 0) + 1
        self.contadores_etiquetas[base] = conteo
        return base if conteo == 1 else f"{base}{conteo}"

    def gen(self, op: str, arg1: str = "-", arg2: str = "-", res: str = "-", descripcion: str = "") -> int:
        indice = len(self.cuadruplos) + 1
```

**`generador_intermedio.py:390-392` — punto donde la semántica bloquea todo lo demás:**

```python
        resultado_semantico = analizar_codigo(codigo)
        if not resultado_semantico["valido"]:
            raise ErrorNumlang("Errores semánticos detectados:\n" + "\n".join(resultado_semantico["errores"]))
```

**`gestor_memoria.py:32-39` — truncación de `num` a entero en el backend:**

```python
def entero_nasm(valor: object) -> int:
    """Normaliza booleanos y numeros del analizador a enteros de 32 bits."""
    if isinstance(valor, bool):
        return 1 if valor else 0
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0
```

**`generador_objeto.py:317-324` — división/residuo sin guardia de cero:**

```python
    def _traducir_division(self, op: str, arg1: str, arg2: str, res: str) -> None:
        self._cargar("eax", arg1)
        self._emitir("cdq")
        self._cargar("ecx", arg2)
        self._emitir("idiv ecx")
        if op in ("%", "residuo_de"):
            self._emitir("mov eax, edx")
        self._guardar(res)
```

**`analizador_semantico.py:270-319` — ciclo `para`, explícitamente excluido por la spec (extracto):**

```python
            m_para = re.fullmatch(r"para\s+(?:num\s+)?([a-zA-Z_]\w*)\s*=\s*(.+?)\s+hasta\s+(.+?)(?:\s+paso\s+(.+?))?(?:\s+hacer)?", texto)
            if m_para:
                var_ctrl, ini_str, lim_str, paso_str = m_para.groups()
```

---

¿Quieres que proceda a corregir estas discrepancias? Si sí, ¿en qué orden: **P0 completo** (front-end unificado → ecu/func/constantes → precedencia/léxico → precisión numérica → errores en ejecución), **solo los 5 críticos que rompen los casos de prueba**, o algún subconjunto concreto que indiques?

---

## 9. Estado de correcciones (fases en curso)

| Ítem | Estado | Evidencia |
|---|---|---|
| P0.1 Precedencia unario antes que `elevado_a` | ✅ | `-2 elevado_a 2 → 4`; `2 elevado_a 3 elevado_a 2 → 512`. `tests/test_precedencia.py`. |
| P0.2 `num` doble precisión — intérprete/evaluador | ✅ | Literales y símbolos `float`; `5 + 0.1 → 5.1`; salida entera estable (`5`). `tests/test_precision_num.py`. |
| P0.2 `num` doble precisión — backend NASM | ⚠️ | Diferido a P3.5; se documenta como DT-1. `test_negativos_y_division_entera` sigue pasando. |
| P0.3.a Front-end `ecu`/`resolver` | ✅ | Parser OK: `2x` falla en fase sintáctica y `resolver` parsea. `tests/test_ecu_parser.py`. |
| P0.3.b Semántica de `DefEcu` | ✅ | D1–D7: detección de incógnita, grado simbólico, coeficientes `(a,b,c)`, poda `1e-12`, BOOL `verdadero/falso`. `tests/test_ecu_semantica.py` (11 tests). |
| P0.3.c Resolver semántico | ✅ | Valida ID1 declarada y de tipo `ecu`, e ID2 exactamente igual a la incógnita; marca el nodo con `valida=True`. `tests/test_resolver_semantica.py` (5 tests). |
| P0.3.d Evaluador numérico | ✅ | `TOL_DISCRIMINANTE=1e-9`, `_formatear_num` (copia del intérprete), grado 1/2, discriminante, orden mayor primero, `valida` defensivo. `tests/test_resolver_evaluador.py` (10 tests). |
| P0.4.a Parser de `func`/llamadas | ✅ | `func` reservada, `DefFunc` regex con params 0/1/N, `ast.Call` → nodo `llamada`. `tests/test_func_parser.py` (9 tests). |

---

## Deuda técnica registrada

### DT-1: Backend NASM usa enteros, no doble precisión
- Estado: diferido desde P0.2.
- Impacto: si se compila a NASM, `5/2` da 2 en vez de 2.5; no hay soporte float.
- Opciones a decidir más adelante con el usuario:
  a) Migrar backend a SSE2 (`movsd`/`addsd`/`divsd`/`cvtsi2sd`/`roundsd`) — costoso.
  b) Declarar "backend NASM solo enteros" como limitación documentada — barato.
  c) Eliminar el backend NASM si no es requisito de la materia — radical.
- Decisión pendiente: se tomará al final de P3.
