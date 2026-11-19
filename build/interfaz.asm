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
v_x: dd 5
    times 4 db 0
v_w: dd 11
    times 4 db 0
cad_1: db "mayor", 0
cad_2: db "menor", 0

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
    
    ; (=, 5, -, x)
    mov eax, 5
    mov [v_x], eax
    ; (*, x, 2, t1)
    mov eax, [v_x]
    imul eax, 2
    mov ebx, eax
    ; (+, t1, 1, t2)
    mov eax, ebx
    add eax, 1
    mov esi, eax
    ; (=, t2, -, w)
    mov eax, esi
    mov [v_w], eax
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
    ; (mostrar, "mayor", -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword cad_1
    push dword fmt_str
    call _printf
    ; llamador limpia argumentos cdecl
    mov esp, ebp
    sub esp, 12
    ; (goto, -, -, Lfin)
    jmp L_Lfin
    ; (etiqueta, -, -, Lfalso)
L_Lfalso:
    ; (mostrar, "menor", -, -)
    ; alineacion de pila: se reconstruye desde EBP
    mov esp, ebp
    sub esp, 12
    and esp, -16
    sub esp, 8
    push dword cad_2
    push dword fmt_str
    call _printf
    ; llamador limpia argumentos cdecl
    mov esp, ebp
    sub esp, 12
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
