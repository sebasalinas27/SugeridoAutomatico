# ✅ REPOSICIÓN TIENDAS v1.0 - Base con Prioridad y Selección de Método
import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(page_title="Reposición de Tiendas", layout="centered")
st.title("🏪 Reposición de Productos a Tiendas (v1.0)")

st.markdown("""
### 📦 ¿Qué hace este módulo?

- Calcula la necesidad de reposición a tiendas en base a ventas recientes y stock actual.
- Asigna el stock de bodega considerando prioridad de tiendas.
- Permite elegir el método de asignación:
  - 🔁 Asignación Directa por Prioridad
  - ⚖️ Distribución Proporcional Ponderada
- Exporta un archivo Excel con la asignación final, stock y resumen.
""")

# 2. CARGA DEL ARCHIVO
uploaded_file = st.file_uploader("Sube tu archivo Excel con ventas, stock y prioridades", type=["xlsx"])

if uploaded_file:
    # 3. VISTA PREVIA
    df_stock_tienda = pd.read_excel(uploaded_file, sheet_name="Stock Tienda")
    df_ventas = pd.read_excel(uploaded_file, sheet_name="Ventas")
    df_stock_bodega = pd.read_excel(uploaded_file, sheet_name="Stock Bodega")
    df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Tiendas")

    st.subheader("👁️ Vista previa de los datos cargados")
    st.write("- Stock en tiendas:", df_stock_tienda.shape)
    st.write("- Ventas registradas:", df_ventas.shape)
    st.write("- Stock en bodega:", df_stock_bodega.shape)
    st.write("- Prioridad de tiendas:", df_prioridad.shape)

    # 4. PARÁMETROS Y SELECCIÓN DE MÉTODO
    metodo_asignacion = st.radio(
        "Selecciona el método de asignación de stock a tiendas:",
        ["🔁 Por prioridad directa", "⚖️ Por proporcionalidad ponderada"]
    )

    if st.button("🚀 Ejecutar reposición"):
        try:
            # 5. CÁLCULO DE REPOSICIÓN SUGERIDA (simple: promedio 4 semanas)
            df_ventas_recientes = df_ventas.sort_values("Semana", ascending=False).groupby(["Codigo", "Tienda"]).head(4)
            df_ventas_sugerido = df_ventas_recientes.groupby(["Codigo", "Tienda"]).agg({"Unidades Vendidas": "mean"}).reset_index()
            df_ventas_sugerido.rename(columns={"Unidades Vendidas": "Reposición Sugerida"}, inplace=True)

            # Agregar stock actual y prioridad
            df = df_ventas_sugerido.merge(df_stock_tienda, on=["Codigo", "Tienda"], how="left")
            df = df.merge(df_prioridad, on="Tienda", how="left")
            df["Prioridad"] = pd.to_numeric(df["Prioridad"], errors='coerce').fillna(5)
            df["Reposición Necesaria"] = (df["Reposición Sugerida"] - df["Stock Actual"]).clip(lower=0)

            # Bodega a dict
            stock_bodega = df_stock_bodega.set_index("Codigo")["Stock Disponible"].to_dict()

            # 6. ASIGNACIÓN SEGÚN MÉTODO
            asignaciones = []
            if metodo_asignacion == "🔁 Por prioridad directa":
                for codigo in df["Codigo"].unique():
                    df_codigo = df[df["Codigo"] == codigo].sort_values("Prioridad")
                    disponible = stock_bodega.get(codigo, 0)
                    for _, row in df_codigo.iterrows():
                        pedir = row["Reposición Necesaria"]
                        asignado = min(disponible, pedir)
                        disponible -= asignado
                        asignaciones.append({"Codigo": codigo, "Tienda": row["Tienda"], "Asignado": asignado})

            else:  # proporcional ponderada
                for codigo in df["Codigo"].unique():
                    df_codigo = df[df["Codigo"] == codigo].copy()
                    disponible = stock_bodega.get(codigo, 0)
                    df_codigo = df_codigo[df_codigo["Reposición Necesaria"] > 0]
                    if df_codigo.empty or disponible == 0:
                        continue
                    # Ponderador inverso a prioridad
                    df_codigo["Peso"] = 1 / df_codigo["Prioridad"]
                    df_codigo["Demanda Ponderada"] = df_codigo["Reposición Necesaria"] * df_codigo["Peso"]
                    total_ponderado = df_codigo["Demanda Ponderada"].sum()
                    for _, row in df_codigo.iterrows():
                        asignado = min(
                            disponible,
                            disponible * row["Demanda Ponderada"] / total_ponderado
                        )
                        asignaciones.append({"Codigo": codigo, "Tienda": row["Tienda"], "Asignado": round(asignado)})

            df_asignacion = pd.DataFrame(asignaciones)

            # 7. RESUMEN FINAL
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

            # 8. MOSTRAR RESUMEN EN APP
            st.subheader("📋 Resumen de Reposición")
            st.dataframe(df_resumen)

            # 9. EXPORTACIÓN
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_asignacion.to_excel(writer, sheet_name="Asignación", index=False)
                df.to_excel(writer, sheet_name="Reposición Sugerida", index=False)
                df_resumen.to_excel(writer, sheet_name="Resumen Reposición", index=False)
            output.seek(0)

            st.download_button(
                label="📥 Descargar Excel de resultados",
                data=output.getvalue(),
                file_name="reposicion_resultados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"❌ Error al ejecutar la reposición: {e}")
