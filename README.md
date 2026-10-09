# Procesamiento de CDRs - Facturación

Aplicación de escritorio interactiva desarrollada en Python con Tkinter para el procesamiento, enriquecimiento y cruce iterativo de registros de llamadas (CDRs) entre archivos del sistema Delta / Neon y archivo de Banco.

---

## Características Principales

### Compatibilidad y Formatos

* Soporta archivos de entrada CSV (`.csv`) y Excel (`.xlsx`).
* Detección automática de delimitadores (coma, punto y coma, tabulador) y codificaciones (`utf-8`, `cp1252`, `latin1`).
* Mapeo inteligente para la asignación de columnas de Fecha, Hora y Teléfono.

### Normalización de Datos

* **Teléfonos:** Limpieza de prefijos de país y estandarización a 10 dígitos.
* **Fechas y Horas:** Reconocimiento de formatos ISO de 24 horas y formatos en español (`a. m. / p. m.` o `AM / PM`).

### Algoritmo de Cruce Iterativo (Matching)

* Cruce por días comunes y número telefónico.
* Algoritmo codicioso 1 a 1 (Greedy 1-to-1) ordenado por menor desfase de tiempo (`delta_seconds`).
* Tolerancia desde minuto exacto hasta ventanas de ±1440 minutos (24 horas).

### Archivos de Salida

* **Coincidencias (`_coincidencias.csv`):** Registros de Delta combinados con información de Banco (prefijada con `CW_`). Incluye la columna calculada `CW_minutes` (`CW_dialog / 60`) y remueve columnas técnicas intermedias (`TIER_CRUCE`, `DELTA_SEGUNDOS`, `date`, `telephone`).
* **Remanentes Delta (`_remanentes_left.csv`):** Registros de Delta sin coincidencia.
* **Remanentes Banco (`_remanentes_right.csv`):** Registros de Banco sin coincidencia.

### Interfaz de Usuario

* Barra de progreso y registros en tiempo real.
* Resumen gráfico de resultados (total de matches, remanentes y días procesados).
* Cancelación segura de procesos en cualquier momento.

---

## Requisitos Previos

* Python 3.10 o superior
* Dependencias incluidas en `requirements.txt`:
* `pandas`
* `openpyxl`
* `pyinstaller`



---

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/tu-usuario/FacturaMatcher.git
cd FacturaMatcher

```


2. (Opcional) Crear y activar entorno virtual:
```bash
python -m venv venv

# En Windows:
venv\Scripts\activate

# En Linux/macOS:
source venv/bin/activate

```


3. Instalar dependencias:
```bash
pip install -r requirements.txt

```



---

## Uso de la Aplicación

### Ejecución desde Código Fuente

```bash
python facturar_app.py

```

### Flujo de Trabajo

1. **Carga y Mapeo**
* Selecciona el archivo Delta/Neon y confirma las columnas de Fecha, Hora y Teléfono.
* Selecciona el archivo Banco y confirma las columnas de Fecha y Teléfono.


2. **Configuración de Salida**
* Define el nombre base del archivo (por defecto `Facturacion`) y la ruta de destino.


3. **Procesamiento**
* Haz clic en **Iniciar Cruce** para ejecutar el proceso y monitorear el progreso en tiempo real.



---

## Pruebas Unitarias

Ejecuta la suite de pruebas con `unittest`:

```bash
python -m unittest test_facturar.py

```

---

## Compilación a Executable (.exe)

Para generar el ejecutable independiente en Windows sin requerir Python instalado:

1. Ejecuta el script de compilación:
```cmd
build_exe.bat

```


2. Encuentra el ejecutable generado en:
`dist/Facturar.exe`

---

## Estructura del Proyecto

```text
├── facturar_app.py        # Código fuente principal (GUI y motor)
├── test_facturar.py       # Pruebas unitarias
├── build_exe.bat          # Script para compilar con PyInstaller
├── requirements.txt       # Dependencias
├── procesar.ico           # Icono del ejecutable
├── procesar.png           # Imagen de la interfaz
└── README.md              # Documentación

```
