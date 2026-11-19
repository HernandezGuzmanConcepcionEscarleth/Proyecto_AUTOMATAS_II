; Numlang -> codigo objeto NASM x86-32 win32
; CRT de MinGW: _main, _printf; sin syscalls de Linux
; Frame de _main: 12 bytes
; [ebp+8] parametros; [ebp] viejo ebp; [ebp+4] retorno
; [ebp-4] EBX; [ebp-8] ESI; [ebp-12] EDI
; [ebp-16..] spills (0 bytes)
; Antes de cada call se realinea ESP a 16 bytes y se restaura desde EBP

section .data
fmt_int: db "%d", 10, 0
fmt_str: db "%s", 10, 0
v_a: dd 20
    times 4 db 0
v_b: dd 5
    times 4 db 0
v_suma: dd 25
    times 4 db 0
v_resta: dd 15
    times 4 db 0
v_multiplicacion: dd 100
    times 4 db 0
v_division: dd 4
    times 4 db 0

section .bss

section .text
global _main
extern _printf

_main:
    ; --- prologo de _main ---
    push ebp
    mov ebp, esp
    push ebx
    push esi
    push edi
    
    ; (=, 20, -, a)
    mov eax, 20
    mov [v_a], eax
    ; (=, 5, -, b)
    mov eax, 5
    mov [v_b], eax
    ; (+, a, b, t1)
    mov eax, [v_a]
    add eax, [v_b]
    mov ebx, eax
    ; (=, t1, -, suma)
    mov eax, ebx
    mov [v_suma], eax
    ; (-, a, b, t2)
    mov eax, [v_a]
    sub eax, [v_b]
    mov esi, eax
    ; (=, t2, -, resta)
    mov eax, esi
    mov [v_resta], eax
    ; (*, a, b, t3)
    mov eax, [v_a]
    imul eax, [v_b]
    mov edi, eax
    ; (=, t3, -, multiplicacion)
    mov eax, edi
    mov [v_multiplicacion], eax
    ; (/, a, b, t4)
    mov eax, [v_a]
    imul eax, [v_b]
    mov ebx, eax
    ; (=, t4, -, division)
    mov eax, ebx
    mov [v_division], eax
    ; (mostrar, suma, -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword [v_suma]
    push dword fmt_int
    call _printf
    ; llamador limpia argumentos cdecl
    mov esp, ebp
    sub esp, 12
    ; (mostrar, resta, -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword [v_resta]
    push dword fmt_int
    call _printf
    ; llamador limpia argumentos cdecl
    mov esp, ebp
    sub esp, 12
    ; (mostrar, multiplicacion, -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword [v_multiplicacion]
    push dword fmt_int
    call _printf
    ; llamador limpia argumentos cdecl
    mov esp, ebp
    sub esp, 12
    ; (mostrar, division, -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword [v_division]
    push dword fmt_int
    call _printf
    ; llamador limpia argumentos cdecl
    mov esp, ebp
    sub esp, 12
    mov eax, 0
    
    ; --- epilogo de _main ---
    mov esp, ebp
    sub esp, 12
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
