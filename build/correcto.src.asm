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
v_a: dd 4
    times 4 db 0
v_b: dd 3
    times 4 db 0
v_resultado: dd 10
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
    
    ; (=, 4, -, a)
    mov eax, 4
    mov [v_a], eax
    ; (=, 3, -, b)
    mov eax, 3
    mov [v_b], eax
    ; (*, b, 2, t1)
    mov eax, [v_b]
    imul eax, 2
    mov ebx, eax
    ; (+, a, t1, t2)
    mov eax, [v_a]
    add eax, ebx
    mov esi, eax
    ; (=, t2, -, resultado)
    mov eax, esi
    mov [v_resultado], eax
    ; (mostrar, resultado, -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword [v_resultado]
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
