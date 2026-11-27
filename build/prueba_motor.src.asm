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
v_a: dd 9
    times 4 db 0
v_b: dd 8
    times 4 db 0
v_x: dd 1
    times 4 db 0
v_w: dd 10
    times 4 db 0
v_z: dd 10
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
    ; (=, 10, -, z)
    mov eax, 10
    mov [v_z], eax
    ; (etiqueta, -, -, Linicio)
L_Linicio:
    ; (<, x, 5, t4)
    mov eax, [v_x]
    cmp eax, 5
    setl al
    movzx eax, al
    mov ebx, eax
    ; (if_false, t4, -, Lfin)
    mov eax, ebx
    test eax, eax
    jz L_Lfin
    ; (+, a, 1, t5)
    mov eax, [v_a]
    add eax, 1
    mov esi, eax
    ; (=, t5, -, a)
    mov eax, esi
    mov [v_a], eax
    ; (+, x, 1, t7)
    mov eax, [v_x]
    add eax, 1
    mov edi, eax
    ; (=, t7, -, x)
    mov eax, edi
    mov [v_x], eax
    ; (goto, -, -, Linicio)
    jmp L_Linicio
    ; (etiqueta, -, -, Lfin)
L_Lfin:
    ; (mostrar, z, -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword [v_z]
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
