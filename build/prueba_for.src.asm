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
v_x: dd 1
    times 4 db 0
v_i: dd 1
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
    
    ; (=, 0, -, x)
    mov eax, 0
    mov [v_x], eax
    ; (=, 1, -, i)
    mov eax, 1
    mov [v_i], eax
    ; (etiqueta, -, -, Linicio)
L_Linicio:
    ; (<=, i, 5, t1)
    mov eax, [v_i]
    cmp eax, 5
    setle al
    movzx eax, al
    mov ebx, eax
    ; (if_false, t1, -, Lfin)
    mov eax, ebx
    test eax, eax
    jz L_Lfin
    ; (+, x, 1, t2)
    mov eax, [v_x]
    add eax, 1
    mov esi, eax
    ; (=, t2, -, x)
    mov eax, esi
    mov [v_x], eax
    ; (mostrar, x, -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword [v_x]
    push dword fmt_int
    call _printf
    ; llamador limpia argumentos cdecl
    mov esp, ebp
    sub esp, 12
    ; (+, i, 1, t3)
    mov eax, [v_i]
    add eax, 1
    mov edi, eax
    ; (=, t3, -, i)
    mov eax, edi
    mov [v_i], eax
    ; (goto, -, -, Linicio)
    jmp L_Linicio
    ; (etiqueta, -, -, Lfin)
L_Lfin:
    mov eax, 0
    
    ; --- epilogo de _main ---
    mov esp, ebp
    sub esp, 12
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
