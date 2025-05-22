# ✅ SUGERIDO AUTOMÁTICO v1.0 - Asignación de Stock a Tiendas por Prioridad y Demanda
import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(page_title="Sugerido Automático", layout="centered")

st.markdown("""
<style>
h1, h2, h3 {
    text-align: center;
}
hr {
    margin-top: 1rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
# 🤖 Sugerido Automático de Productos a Tiendas (v1.0)

Este sistema permite automatizar la asignación de stock disponible a tiendas físicas, utilizando datos históricos de ventas, inventario actual y stock en bodega. Su propósito es **generar sugerencias de reposición** de productos para cada tienda y cada código.

🔍 El modelo se basa en:
- El **promedio de ventas** de las últimas 4 semanas por producto y tienda.
- El **stock actual en tienda**, comparado contra la demanda estimada.
- El **stock disponible en bodega**, el cual se asigna según el método elegido.
- La **prioridad de cada tienda**, para definir a quién abastecer primero si hay escasez.

📈 El resultado final es un archivo Excel que muestra:
- Cuántas unidades asignar por tienda y código.
- Qué tiendas no fueron abastecidas.
- Un resumen de cobertura de demanda.

Puedes elegir entre dos métodos de asignación:
- 🔁 **Prioridad directa:** abastece primero a las tiendas más importantes.
- ⚖️ **Proporcional ponderada:** reparte stock considerando tanto la demanda como la prioridad.

Ideal para equipos comerciales, planificadores o sistemas de reposición que requieren eficiencia y control centralizado.
""")

# 2. ENLACE AL ARCHIVO DE EJEMPLO
st.markdown("""
### 📥 Archivo de ejemplo para probar la app
👉 [Descargar archivo de ejemplo](https://github.com/sebasalinas27/SugeridoAutomatico/raw/main/archivo_ejemplo.xlsx)
""")

st.markdown("---")

# 3. CARGA DEL ARCHIVO
uploaded_file = st.file_uploader("Sube tu archivo Excel con ventas, stock y prioridades", type=["xlsx"])

if uploaded_file:

    # 4. VISTA PREVIA DE LOS DATOS
    st.subheader("👁️ Vista previa de los datos cargados")
    col1, col2 = st.columns(2)
    df_stock_tienda = pd.read_excel(uploaded_file, sheet_name="Stock Tienda")
    df_ventas = pd.read_excel(uploaded_file, sheet_name="Ventas")
    df_stock_bodega = pd.read_excel(uploaded_file, sheet_name="Stock Bodega")
    df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Tiendas")

    col1.metric("📦 Stock en Tiendas", df_stock_tienda.shape[0])
    col2.metric("🛒 Ventas Registradas", df_ventas.shape[0])
    col1.metric("🏬 Tiendas", df_stock_tienda['Tienda'].nunique())
    col2.metric("🔢 Códigos", df_stock_tienda['Codigo'].nunique())

    st.markdown("---")

    # 5. SELECCIÓN DE MÉTODO DE ASIGNACIÓN
    # 🔎 RECOMENDACIÓN AUTOMÁTICA SEGÚN STOCK
    total_stock = df_stock_bodega['Stock Disponible'].sum()
    total_sugerido = df_ventas.groupby(['Codigo', 'Tienda']).tail(4).groupby(['Codigo', 'Tienda'])['Unidades Vendidas'].mean().clip(lower=0).sum()

    if total_sugerido > 0:
        cobertura = total_stock / total_sugerido
        if cobertura < 0.75:
            st.warning("🔎 Recomendación: Usa **'Por prioridad directa'** porque el stock disponible es limitado.")
        elif cobertura >= 0.75 and cobertura < 1.25:
            st.info("🔎 Recomendación: Ambas estrategias son válidas, considera tu objetivo comercial.")
        else:
            st.success("🔎 Recomendación: Usa **'Proporcionalidad ponderada'** porque el stock disponible es alto.")
    st.subheader("⚙️ Parámetros de asignación")
    metodo_asignacion = st.radio(
        "Selecciona el método de asignación de stock a tiendas:",
        ["🔁 Por prioridad directa", "⚖️ Por proporcionalidad ponderada"]
    )

    if metodo_asignacion == "🔁 Por prioridad directa":
        st.info("""
        🔁 **Por prioridad directa**:
        - Se asigna stock comenzando por las tiendas de mayor prioridad.
        - Si el stock disponible no alcanza, las tiendas con menor prioridad pueden no recibir unidades.
        - Es ideal cuando se quiere garantizar abastecimiento a tiendas clave.
        """)
    elif metodo_asignacion == "⚖️ Por proporcionalidad ponderada":
        st.info("""
        ⚖️ **Por proporcionalidad ponderada**:
        - El stock se reparte proporcionalmente según la demanda estimada.
        - Se pondera a favor de tiendas con mayor prioridad, pero se distribuye entre todas.
        - Es ideal para mantener presencia equilibrada en puntos de venta.
        """)

    # 6. EJECUCIÓN DEL MODELO
    st.subheader("🚀 Ejecutar sugerido automático")
    if st.button("Ejecutar reposición"):
        try:
            # 6.1 CÁLCULO DE REPOSICIÓN SUGERIDA
            df_ventas_recientes = df_ventas.sort_values("Semana", ascending=False).groupby(["Codigo", "Tienda"]).head(4)
            df_ventas_sugerido = df_ventas_recientes.groupby(["Codigo", "Tienda"]).agg({"Unidades Vendidas": "mean"}).reset_index()
            df_ventas_sugerido.rename(columns={"Unidades Vendidas": "Reposición Sugerida"}, inplace=True)

            df = df_ventas_sugerido.merge(df_stock_tienda, on=["Codigo", "Tienda"], how="left")
            df = df.merge(df_prioridad, on="Tienda", how="left")
            df["Prioridad"] = pd.to_numeric(df["Prioridad"], errors='coerce').fillna(5)
            df["Reposición Necesaria"] = (df["Reposición Sugerida"] - df["Stock Actual"]).clip(lower=0)

            stock_bodega = df_stock_bodega.set_index("Codigo")["Stock Disponible"].to_dict()
            asignaciones = []

            # 6.2 ASIGNACIÓN SEGÚN MÉTODO
            if metodo_asignacion == "🔁 Por prioridad directa":
                for codigo in df["Codigo"].unique():
                    df_codigo = df[df["Codigo"] == codigo].sort_values("Prioridad")
                    disponible = stock_bodega.get(codigo, 0)
                    for _, row in df_codigo.iterrows():
                        pedir = row["Reposición Necesaria"]
                        asignado = int(min(disponible, pedir))
                        disponible -= asignado
                        asignaciones.append({"Codigo": codigo, "Tienda": row["Tienda"], "Asignado": asignado})
            else:
                for codigo in df["Codigo"].unique():
                    df_codigo = df[df["Codigo"] == codigo].copy()
                    disponible = stock_bodega.get(codigo, 0)
                    df_codigo = df_codigo[df_codigo["Reposición Necesaria"] > 0]
                    if df_codigo.empty or disponible == 0:
                        continue
                    df_codigo["Peso"] = 1 / df_codigo["Prioridad"]
                    df_codigo["Demanda Ponderada"] = df_codigo["Reposición Necesaria"] * df_codigo["Peso"]
                    total_ponderado = df_codigo["Demanda Ponderada"].sum()
                    for _, row in df_codigo.iterrows():
                        asignado = int(min(disponible, disponible * row["Demanda Ponderada"] / total_ponderado))
                        asignaciones.append({"Codigo": codigo, "Tienda": row["Tienda"], "Asignado": round(asignado)})

            df_asignacion = pd.DataFrame(asignaciones)

            # 6.3 RESUMEN FINAL
            stock_total = df_stock_bodega["Stock Disponible"].sum()
            sugerido_total = df["Reposición Necesaria"].sum()
            asignado_total = df_asignacion["Asignado"].sum()
            tiendas_sin_asignacion = set(df["Tienda"]) - set(df_asignacion[df_asignacion["Asignado"] > 0]["Tienda"])

            df_resumen = pd.DataFrame({
                "Elemento": [
                    "Fecha ejecución",
                    "Método de asignación usado",
                    "Total stock en bodega",
                    "Total unidades sugeridas",
                    "Total unidades asignadas",
                    "Porcentaje de demanda cubierta",
                    "Número de tiendas abastecidas",
                    "Tiendas sin asignación"
                ],
                "Valor": [
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    metodo_asignacion,
                    stock_total,
                    sugerido_total,
                    asignado_total,
                    f"{(asignado_total / sugerido_total * 100):.1f}%" if sugerido_total > 0 else "0%",
                    df_asignacion[df_asignacion["Asignado"] > 0]["Tienda"].nunique(),
                    len(tiendas_sin_asignacion)
                ]
            })

            # 7. VISUALIZACIÓN Y EXPORTACIÓN
            st.markdown("---")
            st.header("📋 Resumen de Reposición")
            st.dataframe(df_resumen)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación", index=False)
                df.to_excel(writer, sheet_name="Reposición Sugerida", index=False)
                df_resumen.to_excel(writer, sheet_name="Resumen Reposición", index=False)
            output.seek(0)

            st.download_button(
                label="📥 Descargar Excel de resultados",
                data=output.getvalue(),
                file_name="sugerido_resultados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"❌ Error al ejecutar la reposición: {e}")
        except Exception as e:
            st.error(f"❌ Error al ejecutar la reposición: {e}")
