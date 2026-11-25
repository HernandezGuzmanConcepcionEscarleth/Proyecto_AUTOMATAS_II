# PROGRESO — NumLang

Actualizado: 2026-11-24. Último checkpoint: **P0.4.d aplicado** (117 tests en verde).

| Fase | Estado | Nota |
|---|---|---|
| P0.1 Precedencia unario antes que `elevado_a` | ✅ | `tests/test_precedencia.py` |
| P0.1.b Paréntesis explícitos con menos unario ante `elevado_a` | ✅ | `tests/test_precedencia.py` (10 tests); `-(2 elevado_a 2) = -4`, `-2 elevado_a 2 = 4` |
| P0.2 `num` doble precisión — intérprete/evaluador | ✅ | `tests/test_precision_num.py` |
| P0.2 `num` doble precisión — backend NASM | ⚠️ | Ver DT-1 |
| P0.3.a Front-end `ecu`/`resolver` | ✅ | `tests/test_ecu_parser.py` |
| P0.3.b Semántica de `DefEcu` | ✅ | D1–D7; `tests/test_ecu_semantica.py` (11 tests) |
| P0.3.c Resolver semántico (ID1 es ECU, ID2 == incógnita) | ✅ | `tests/test_resolver_semantica.py` (5 tests); nodo `valida=True` |
| P0.3.d Evaluador numérico grado 1 y 2 | ✅ | `tests/test_resolver_evaluador.py` (10 tests); `TOL=1e-9`, formato `x = 5` |
| P0.4.a Parser de `func`/llamadas | ✅ | `tests/test_func_parser.py` (9 tests); `func` reservada + `ast.Call` |
| P0.4.b Semántica de `DefFunc` | ✅ | D-F1..D-F3, D-F5, D-F8..D-F10; `tests/test_func_semantica.py` (18 tests) |
| P0.4.c Semántica de llamada | ✅ | D-F6, D-F12, D-F13; `tests/test_func_llamadas.py` (8 tests); deuda cerrada en P0.4.d |
| P0.4.d Evaluador con scope local | ✅ | D-F14, D-F15; `tests/test_func_scope.py` (9 tests); 117 passed |
| P0.5 `PI`/`Eu`/`verdadero`/`falso` como constantes evaluables | ✅ | D-C1 a D-C3; `tests/test_constantes.py` (6 tests); `PI`/`Eu` en ambas rutas |
| P1 — 8 errores semánticos | ⏳ | Incluye validación recursiva de tipos en ecuaciones |
| P2 — 11 ⚠️ + resto ❌ | ⏳ | Incluye revisión de reservadas |
| P3 — Eliminar `para`, verificar exclusiones de la spec | ⏳ | — |
| DT-1 — Backend NASM entero | ⏳ | Diferido; decisión al final de P3 |

Deuda P0.4.d registrada (cerrada en P0.4.d):
- test obligatorio: mostrar f(w + 1) con w sin declarar -> 'no está declarada' (resuelto por evaluación de argumentos)

Deuda P2 registrada:
- (a) bool se muestra como `1` en el oráculo (`compilar_programa` + `interpretar`), no como `verdadero`/`falso`.
- (b) `PI = 4` da "no declarada" en vez de "reservada"; solo `num PI = 3` usa la validación de reservada.
- (c) `GeneradorCodigoIntermedio().compilar_programa("func f(x) = x + 1\nmostrar f(3)\n")` → `ErrorNumlang: Instrucción no reconocida: 'func f(x) = x + 1'`.

Deuda P0.4.b registrada:
- `x / 0` literal en el cuerpo de `func` no valida división por cero → P1.
- `func g(f) = f(2)` (llamada a parámetro) → decidir en P0.4.c.
- `y` sigue reservada como operador; revisión en P2.
