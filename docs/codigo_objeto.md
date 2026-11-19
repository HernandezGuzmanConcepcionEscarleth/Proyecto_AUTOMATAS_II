# Generación de código objeto y memoria (Numlang)

Esta fase toma los **cuádruplos ya optimizados** y produce un `.asm` NASM que se ensambla y enlaza en Windows como ejecutable PE/COFF de 32 bits.

## Arquitectura elegida

- **x86 de 32 bits**, sintaxis **NASM**, formato **win32** (`nasm -f win32`).
- Enlazado con **gcc de MinGW** usando `gcc -m32`; la E/S se hace con `printf` de la CRT (`extern _printf`), sin `int 0x80`.
- En win32 los símbolos C llevan guion bajo: `global _main`, `extern _printf`. El CRT llama a `_main`; el programa termina con `mov eax, 0` + `ret`.
- Se eligió esta combinación porque es la que permite generar un `.exe` de 32 bits directamente desde CMD/PowerShell sin toolchains de Linux.

La generación queda detrás de `TargetBackend` (`generador_objeto.py`). Solo se implementa `NasmWin32Backend`; agregar otro destino requiere crear otra subclase con `generar(cuadruplos, contexto)`.

## Interfaz gráfica

`interfaz_grafica.py` abre una ventana con un cuadro de texto para escribir instrucciones Numlang:

```powershell
python interfaz_grafica.py
python interfaz_grafica.py src\programa.src
python generador_objeto.py --gui
```

También existe `ejecutar_interfaz.bat` para abrirla con doble clic en Windows. La ventana tiene:

- Selector de ejemplos de `src/`.
- Editor de código y botones `Compilar y ejecutar`, `Solo generar .asm` y `Limpiar` (Ctrl+Enter también compila y ejecuta).
- Casillas `Optimizar` y `Ejecutar .exe`.
- Pestañas `Salida del programa`, `Cuadruplos`, `ASM generado` y `Registros y memoria`.

La compilación corre en un hilo secundario para no congelar la ventana; el `.asm` se deja en `build\interfaz.asm` para poder ensamblarlo manualmente.

## Registros

| Registro | Rol | Se preserva |
|---|---|---|
| `EAX` | Scratch: resultados aritméticos, retorno de `printf` y de rutinas | No (caller-saved) |
| `ECX` | Scratch: divisor de `idiv`, comparaciones lógicas | No (caller-saved) |
| `EDX` | Scratch: extensión de signo para `cdq` y residuo de `idiv` | No (caller-saved) |
| `EBX` | Temporal asignable por linear scan | Sí (push/pop en `_main`) |
| `ESI` | Temporal asignable por linear scan | Sí (push/pop en `_main`) |
| `EDI` | Temporal asignable por linear scan | Sí (push/pop en `_main`) |
| `ESP` | Pila | Reservado |
| `EBP` | Marco de pila | Reservado |

Los temporales `t1`, `t2`, ... se asignan con `AsignadorRegistros` (`linear scan`). Si hay más de tres vivos a la vez, los excedentes se derraman a `[ebp-N]` y el slot se reutiliza cuando el temporal muere. Ningún temporal vive en `EAX/ECX/EDX` a través de una llamada a `printf`.

Las variables de usuario siempre viven en memoria (`.data`/`.bss`); se cargan a un registro solo para operar. `GestorMemoria` conserva la dirección declarada por el analizador (`0x1000`, `0x1008`, ...) en el reporte y usa etiquetas `v_<nombre>` con 8 bytes por variable para respetar el paso de 8 de esas direcciones.

## Memoria y marco de pila

```
section .data
    fmt_int        db "%d", 10, 0
    fmt_str        db "%s", 10, 0
    v_x            dd 5
                   times 4 db 0       ; 8 bytes por variable
    cad_1          db "mayor", 0

section .bss
    v_y            resb 8             ; variables sin valor inicial

section .text
    global _main
    extern _printf
_main:
    push ebp                         ; [ebp]   = viejo EBP
    mov ebp, esp                     ; [ebp+4] = retorno, [ebp+8..] = parámetros
    push ebx                         ; [ebp-4]
    push esi                         ; [ebp-8]
    push edi                         ; [ebp-12]
    sub esp, <bytes_de_spill>        ; [ebp-16..] = spills
    ...
    mov esp, ebp
    sub esp, 12                      ; apunta a [ebp-12] antes de los pop
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
```

Antes de cada `call _printf` se reconstruye `ESP` desde `EBP`, se aplica `and esp, -16` y se resta el padding necesario según el número de argumentos (8 bytes para dos argumentos, 12 para uno). Después de la llamada se restaura `ESP` desde `EBP`; el propio llamador limpia los argumentos cdecl.

## Traducción de cuádruplos

| Cuádruplo | ASM generado |
|---|---|
| `(=, a, b, t1)` | `mov eax, [a]` / `mov t1, eax` |
| `(+, a, b, t1)` | `mov eax, [a]` / `add eax, [b]` / `mov t1, eax` |
| `(-, a, b, t1)` | `sub eax, [b]` |
| `(*, a, b, t1)` | `imul eax, [b]` |
| `(/, a, b, t1)` | `cdq` / `mov ecx, [b]` / `idiv ecx` |
| `(%, residuo_de)` | igual, luego `mov eax, edx` |
| `elevado_a`, `**` | bucle con `imul edx, eax` y `dec ecx` |
| `< > <= >= == !=` | `cmp` + `setcc` + `movzx` |
| `y`, `o`, `no` | `test` + `setne/setz` + `and/or` normalizados a 0/1 |
| `neg` | `neg eax` |
| `etiqueta` | `L_<nombre>:` |
| `goto` | `jmp L_<nombre>` |
| `if_false` | `test eax,eax` / `jz L_<nombre>` |
| `mostrar` | alineación / `push valor` / `push fmt` / `call _printf` / restaurar `ESP` |
| `param`, `llamar` | argumentos apilados en orden inverso; `call`; `EAX` se guarda en `res` |
| `retornar` | valor en `EAX`, epílogo y `ret` |
| `campo_estructura`, `param_recibir` | resueltos en compilación; no emiten código |

Cada cuádruplo se precede de un comentario con el cuádruplo original, por ejemplo `; (+, a, b, t1)`. El `.asm` se escribe en UTF-8 sin BOM, con saltos de línea LF y solo ASCII en comentarios y cadenas.

## Cómo compilar y ejecutar en Windows

Desde CMD o PowerShell, en la raíz del proyecto:

```powershell
python generador_objeto.py src\programa.src -o build\programa.asm --ejecutar
```

Opciones:

```powershell
python generador_objeto.py src\ejemplo.src -o build\ejemplo.asm [--sin-optimizar] [--reporte-registros] [--reporte-memoria] [--ejecutar]
```

Comandos manuales equivalentes:

```cmd
nasm -f win32 build\programa.asm -o build\programa.obj
gcc -m32 build\programa.obj -o build\programa.exe
build\programa.exe
```

En esta máquina `gcc` está en PATH (`C:\MinGW\bin\gcc.EXE`, MinGW 6.3.0) y NASM está instalado pero **no en PATH**: `C:\Program Files (x86)\SASM\NASM\nasm.exe`. La CLI usa `shutil.which` y luego busca rutas típicas de Windows, incluida SASM. Si no encuentra las herramientas, imprime los comandos manuales y avisa qué instalar (NASM y MinGW-w64 i686 con soporte `-m32`).

## Ejemplo completo

Fuente (`src/programa.src`):

```numlang
num x = 5
num w = x * 2 + 1
si w > 10 entonces
    mostrar "mayor"
si_no
    mostrar "menor"
fin
```

Cuádruplos optimizados:

```
(=, 5, -, x)
(*, x, 2, t1)
(+, t1, 1, t2)
(=, t2, -, w)
(>, w, 10, t3)
(if_false, t3, -, Lfalso)
(mostrar, "mayor", -, -)
(goto, -, -, Lfin)
(etiqueta, -, -, Lfalso)
(mostrar, "menor", -, -)
(etiqueta, -, -, Lfin)
```

Fragmento del `.asm` generado:

```asm
section .text
global _main
extern _printf

_main:
    push ebp
    mov ebp, esp
    push ebx
    push esi
    push edi

    ; (=, 5, -, x)
    mov eax, 5
    mov [v_x], eax
    ; (*, x, 2, t1)
    mov eax, [v_x]
    imul eax, 2
    mov ebx, eax
    ; (>, w, 10, t3)
    mov eax, [v_w]
    cmp eax, 10
    setg al
    movzx eax, al
    mov edi, eax
    ; (if_false, t3, -, Lfalso)
    mov eax, edi
    test eax, eax
    jz L_Lfalso
    ...
L_Lfalso:
    ...
L_Lfin:
    mov eax, 0
    mov esp, ebp
    sub esp, 12
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
```

Salida del ejecutable: `mayor`.

## Pruebas

```powershell
python -m pytest -q
```

El intérprete de referencia (`tests/interprete_referencia.py`) ejecuta los mismos cuádruplos en Python y se compara con la salida real del `.exe`. Las pruebas que necesitan NASM/gcc se omiten con un motivo claro si faltan herramientas.

## Limitaciones conocidas

- Solo enteros de 32 bits con signo; los valores decimales se truncan con `entero_nasm`.
- La división por cero no tiene manejo en tiempo de ejecución: produce una excepción de Windows.
- `elevado_a` con exponente negativo devuelve 0; con exponente variable usa un bucle simple.
- `funcion`, `estructura`, `const`, `llamar` y `retornar` están traducidos en el backend, pero el analizador semántico actual los rechaza en el flujo completo. `campo_estructura` y `param_recibir` no generan código.
- Los operadores verbales (`residuo_de`, `elevado_a`, `y`, `o`, `no`) son reconocidos por el generador intermedio, pero el analizador semántico no los acepta todavía en todas las expresiones.
- `optimizar_ciclos()` del motor sigue siendo solo un análisis informativo; la optimización real aplicada es local, de mirilla y de código muerto.
- No hay soporte para arreglos, cadenas dinámicas ni biblioteca estándar más allá de `printf`.
- El frame asume un único `_main`; no se generan rutinas adicionales con su propio frame.

## Depuración en vivo (opcional)

Si el profesor pide ver registros en tiempo de ejecución:

1. Genera el `.exe` sin borrar los símbolos: `python generador_objeto.py src\programa.src -o build\programa.asm --ejecutar`.
2. Abre `build\programa.exe` en **x32dbg** (32 bits, no x64dbg).
3. Busca el símbolo `_main` y coloca breakpoints en las líneas `cmp`, `jz` o `call _printf`.
4. Observa `EBX/ESI/EDI` para los temporales y `[ebp-N]` para los spills; `EAX/ECX/EDX` cambian libremente porque son scratch.
