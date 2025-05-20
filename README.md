# 🏪 Reposición de Productos a Tiendas (v1.0)

Este módulo en Python con Streamlit permite **calcular y asignar stock de reposición** a tiendas en base a las ventas recientes, el stock actual y el stock disponible en bodega. Es especialmente útil para empresas de retail que necesitan definir **reposición semanal o quincenal** de forma automatizada.

---

## 📂 Estructura del archivo Excel de entrada

El archivo debe contener **cuatro hojas** con la siguiente información:

### 1. `Stock Tienda`
| Codigo | Tienda | Stock Actual |
|--------|--------|---------------|
| A001   | Paris Arauco | 5       |

### 2. `Ventas`
| Codigo | Semana | Tienda | Unidades Vendidas |
|--------|--------|--------|-------------------|
| A001   | 2025-18 | Paris Arauco | 3         |

### 3. `Stock Bodega`
| Codigo | Stock Disponible |
|--------|------------------|
| A001   | 120              |

### 4. `Prioridad Tiendas`
| Tienda | Prioridad |
|--------|-----------|
| Paris Arauco | 1     |

> 📌 Donde prioridad 1 es la más alta. Si una tienda no está en la tabla, se le asigna prioridad 5 por defecto.

---

## ⚙️ Lógica del sistema

1. Calcula la **demanda sugerida** con el promedio de ventas de las últimas 4 semanas por tienda y código.
2. Compara la demanda con el stock actual en tienda para estimar la **reposició‍n necesaria**.
3. Distribuye el stock disponible de bodega según uno de los dos métodos seleccionados por el usuario:
   - 🔁 **Por prioridad directa:** asigna secuencialmente desde la tienda más prioritaria.
   - ⚖️ **Proporcional ponderada:** distribuye proporcionalmente según demanda y prioridad inversa.

---

## 📤 Archivos de salida

El sistema genera un Excel con 3 hojas:

- `Asignación`: stock asignado por código y tienda.
- `Reposición Sugerida`: cálculo base de demanda, stock y necesidad.
- `Resumen Reposición`: resumen ejecutivo con métricas clave.

---

## 🚀 Cómo ejecutarlo localmente

```bash
pip install streamlit pandas openpyxl xlsxwriter matplotlib seaborn
streamlit run app.py

### 📥 Archivo de ejemplo

Puedes descargar y usar el siguiente archivo de ejemplo para probar la aplicación:

👉 [archivo_ejemplo.xlsx](archivo_ejemplo.xlsx)

