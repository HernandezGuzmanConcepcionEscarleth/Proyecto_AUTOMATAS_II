# Numlang — Compilador Fase 2 (Análisis Semántico, Código Intermedio y Optimización)

## Descripción general
Este proyecto implementa un compilador funcional para el lenguaje **Numlang**, dividido en tres fases principales:
1. **Análisis Semántico (Integrante 1):** Valida tipos, declaraciones, palabras reservadas y construye la tabla de símbolos.
2. **Generación de Código Intermedio (Integrante 2):** Convierte el código fuente en cuádruplos, tripletas y Código P.
3. **Motor de Optimización (Integrante 3):** Aplica técnicas de optimización local, de mirilla, global y de ciclos sobre los cuádruplos generados, y evalúa el ahorro en tiempo y memoria.


## Requisitos
- Python 3.9 o superior.
- No requiere librerías externas.

## Cómo ejecutar el compilador (flujo completo)
Para compilar un archivo y ver el código intermedio (sin optimizar), ejecuta:
```bash
python generador_intermedio.py src/programa.src
```

Para ver la salida en formato JSON (ideal para conectar con otros módulos):
```bash
python generador_intermedio.py src/programa.src --json
```

## Cómo ejecutar el motor de optimización
Para optimizar un archivo y ver las métricas de mejora, ejecuta:
```bash
python motor_optimizacion.py src/prueba_motor.src
```

El motor imprimirá un reporte con:
- Métricas de reducción de instrucciones.
- Análisis de flujo de datos y ahorro en tiempo/memoria.
- Lista detallada de optimizaciones aplicadas.
- Tabla de cuádruplos y tripletas optimizadas.

## Palabras reservadas del lenguaje
Las siguientes palabras no pueden usarse como nombres de variables:
`num`, `msj`, `bool`, `mostrar`, `si`, `si_no`, `entonces`, `mientras`, `para`, `hasta`, `paso`, `hacer`, `fin`, `y`, `o`, `no`, `verdadero`, `falso`, `funcion`, `retornar`, `estructura`, `const`.

## Créditos
- **Integrante 1:** Análisis Semántico.
- **Integrante 2:** Generación de Código Intermedio.
- **Integrante 3:** Motor de Optimización.