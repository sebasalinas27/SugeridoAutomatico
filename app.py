# app.py
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from pathlib import Path

# -----------------------------
# Utilidades
# -----------------------------
def normaliza_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def validar_columnas(df: pd.DataFrame, requeridas: set, nombre: str) -> None:
    cols = set(df.columns)
    faltantes = requeridas - cols
    if faltantes:
        st.error(f"Faltan columnas en hoja '{nombre}': {faltantes}")
        st.stop()

def leer_parametro(df_params: pd.DataFrame, col: str, default):
    try:
        val = df_params.iloc[0][col]
        if pd.isna(val):
            return default
        return val
    except Exception:
        return default

def leer_parametro_bool(df_params: pd.DataFrame, col: str, default=False):
    v = str(leer_parametro(df_params, col, default)).strip().lower()
    if v in ["true", "1", "si", "sí", "y", "yes"]:
        return True
    if v in ["false", "0", "no", "n"]:
        return False
    return bool(default)

# -----------------------------
# Cálculo Sugerido Automático
# -----------------------------
def calcular_sugerido(
    stock_tiendas: pd.DataFrame,
    ventas_4sem: pd.DataFrame,
    stock_disponible: pd.DataFrame,
    minimos_sku: pd.DataFrame,
    cobertura_dias: int,
    lead_time_dias: int,
    ss_pct: float,
    pack_default: int,
    cobertura_incluye_leadtime: bool,
    priorizar_sin_historico: bool,
):
    # Normalizar
    stock_tiendas = normaliza_cols(stock_tiendas)
    ventas_4sem = normaliza_cols(ventas_4sem)
    stock_disponible = normaliza_cols(stock_disponible)
    minimos_sku = normaliza_cols(minimos_sku)

    # Validar
    validar_columnas(stock_tiendas, {"tienda_id","sku","stock_tienda"}, "stock_tiendas")
    validar_columnas(ventas_4sem, {"tienda_id","sku","ventas_4_sem"}, "ventas_4sem")
    validar_columnas(stock_disponible, {"sku","stock_disponible"}, "stock_disponible")
    if not minimos_sku.empty:
        validar_columnas(minimos_sku, {"sku","min_inicial"}, "minimos_iniciales")

    # Horizonte
    H = int(cobertura_dias) if cobertura_incluye_leadtime else int(cobertura_dias) + int(lead_time_dias)

    # Unificar base
    df = (stock_tiendas.merge(ventas_4sem, on=["tienda_id","sku"], how="outer")
                      .merge(stock_disponible, on="sku", how="left"))

    df["stock_tienda"] = pd.to_numeric(df["stock_tienda"], errors="coerce").fillna(0.0)
    df["ventas_4_sem"] = pd.to_numeric(df["ventas_4_sem"], errors="coerce").fillna(0.0)
    df["stock_disponible"] = pd.to_numeric(df["stock_disponible"], errors="coerce").fillna(0.0)

    # Traer mínimos por SKU (opcional)
    if not minimos_sku.empty:
        df = df.merge(minimos_sku.rename(columns={"min_inicial":"min_inicial_sku"}), on="sku", how="left")
    else:
        df["min_inicial_sku"] = np.nan

    # Métricas base
    df["vpd"] = df["ventas_4_sem"] / 28.0
    df["horizon_dias"] = H
    df["forecast"] = df["vpd"] * df["horizon_dias"]
    df["ss"] = df["forecast"] * float(ss_pct)

    # Pedido bruto
    cond_hist = df["vpd"] > 0
    df["pedido_bruto"] = 0.0
    df.loc[cond_hist, "pedido_bruto"] = np.maximum(
        0.0, df.loc[cond_hist,"forecast"] + df.loc[cond_hist,"ss"] - df.loc[cond_hist,"stock_tienda"]
    )
    df.loc[~cond_hist, "pedido_bruto"] = np.maximum(
        0.0, df.loc[~cond_hist,"min_inicial_sku"].fillna(0.0) - df.loc[~cond_hist,"stock_tienda"]
    )

    # Comentarios iniciales
    df["comentario"] = ""
    df.loc[~cond_hist & df["min_inicial_sku"].notna(), "comentario"] = "sin histórico - mínimo inicial"
    df.loc[~cond_hist & df["min_inicial_sku"].isna(), "comentario"] = "sin histórico - sin mínimo definido"

    # Prioridad de asignación
    EPS = 1e-9
    df["cover_dias"] = df["stock_tienda"] / (df["vpd"] + EPS)
    df["pedido_final"] = 0.0

    for sku, grp in df.groupby("sku", sort=False):
        rem = float(grp["stock_disponible"].iloc[0]) if len(grp) else 0.0
        if rem <= 0:
            continue

        idx_hist = grp[grp["vpd"] > 0].sort_values(by=["cover_dias","vpd"], ascending=[True, False]).index
        idx_sin_hist = grp[grp["vpd"] <= 0].index

        orden = list(idx_hist) + list(idx_sin_hist)
        if priorizar_sin_historico:
            orden = list(idx_sin_hist) + list(idx_hist)

        for idx in orden:
            pedido = float(df.at[idx, "pedido_bruto"])
            if pedido <= 0 or rem <= 0:
                continue
            pack = max(1, int(pack_default))
            asignado = min(pedido, rem)
            asignado = pack * np.floor(asignado / pack)
            if asignado <= 0 and rem > 0 and pedido > 0:
                asignado = min(pack, rem)

            df.at[idx, "pedido_final"] = asignado
            if asignado < pedido:
                df.at[idx, "comentario"] = (df.at[idx, "comentario"] + "; " if df.at[idx, "comentario"] else "") + "capado por stock disponible"
            rem -= asignado

    # Resumen por SKU
    resumen = (df.groupby("sku", as_index=False)
                 .agg(stock_disponible=("stock_disponible","first"),
                      asignado_total=("pedido_final","sum")))
    resumen["remanente_bodega"] = resumen["stock_disponible"] - resumen["asignado_total"]

    # Orden columnas output
    cols = ["tienda_id","sku","stock_tienda","ventas_4_sem","vpd","horizon_dias","forecast","ss","pedido_bruto","pedido_final","comentario"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    df_out = df[cols].copy()

    return df_out, resumen

# -----------------------------
# UI Streamlit
# -----------------------------
st.set_page_config(page_title="Sugerido Automático (CPFR simplificado)", layout="wide")
st.title("Sugerido por CPFR simplificado")
st.caption("Sube la plantilla Excel con todas las hojas. El cálculo se hace por código/tienda.")

# --- Bloque informativo y descarga de plantilla (no cambia layout ni anchura) ---
def render_about_and_download():
    st.markdown(
        """
        <div style="padding:12px 16px;border:1px solid #E6E6E6;border-radius:10px;background:#FAFAFA;">
          <h3 style="margin-top:0;">Acerca de esta app</h3>
          <ul style="margin-bottom:8px;">
            <li><b>Objetivo:</b> sugerir reposición por <i>código/tienda</i> con enfoque CPFR simplificado.</li>
            <li><b>Cómo funciona:</b> 1) Sube el Excel, 2) Ajusta parámetros, 3) Calcula el sugerido.</li>
            <li><b>Datos que usa:</b> ventas 4 semanas, stock en tienda, stock disponible y mínimos por SKU (para lanzamientos/sin histórico).</li>
            <li><b>Salidas:</b> CSV por tienda/SKU, resumen por SKU y un Excel con ambos reportes.</li>
          </ul>
          <p style="margin:0;color:#333;"><i>Fórmula base:</i> pedido = max(0, forecast + SS − stock_tienda)</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    template_path = Path(__file__).with_name("SugeridoAutomatico_template.xlsx")
    if template_path.exists():
        with open(template_path, "rb") as f:
            st.download_button(
                label="⬇️ Descargar plantilla Excel (SugeridoAutomatico_template.xlsx)",
                data=f.read(),
                file_name="SugeridoAutomatico_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Plantilla con todas las hojas y columnas requeridas"
            )
    else:
        st.warning(
            "No se encontró **SugeridoAutomatico_template.xlsx** en la carpeta del proyecto. "
            "Agrega el archivo a la raíz del repo para habilitar la descarga."
        )

# MOSTRAR CARD + BOTÓN DE DESCARGA
render_about_and_download()

uploaded = st.file_uploader("Sube el archivo Excel: SugeridoAutomatico_template.xlsx", type=["xlsx"])

if uploaded is not None:
    try:
        xls = pd.ExcelFile(uploaded)
        hojas = {name: normaliza_cols(pd.read_excel(xls, sheet_name=name)) for name in xls.sheet_names}

        requeridas = ["stock_tiendas","ventas_4sem","stock_disponible","parametros"]
        faltan = [h for h in requeridas if h not in hojas]
        if faltan:
            st.error(f"Faltan hojas obligatorias en el Excel: {faltan}")
            st.stop()

        stock_tiendas = hojas["stock_tiendas"]
        ventas_4sem = hojas["ventas_4sem"]
        stock_disponible = hojas["stock_disponible"]
        minimos_sku = hojas.get("minimos_iniciales", pd.DataFrame())
        df_params = hojas["parametros"]

        # Leer parámetros desde hoja
        cobertura_dias = int(leer_parametro(df_params, "cobertura_dias", 14))
        lead_time_dias = int(leer_parametro(df_params, "lead_time_dias", 7))
        ss_pct = float(leer_parametro(df_params, "ss_pct", 0.15))
        pack_default = int(leer_parametro(df_params, "pack_default", 1))
        cobertura_incluye_lt = leer_parametro_bool(df_params, "cobertura_incluye_leadtime", False)
        priorizar_sin_hist = leer_parametro_bool(df_params, "priorizar_sin_historico", False)

        with st.sidebar:
            st.subheader("Parámetros (desde el Excel)")
            cobertura_dias = st.number_input("Cobertura (días)", min_value=1, value=int(cobertura_dias))
            lead_time_dias = st.number_input("Lead Time (días)", min_value=0, value=int(lead_time_dias))
            cobertura_incluye_lt = st.checkbox("Cobertura incluye Lead Time (H = cobertura)", value=bool(cobertura_incluye_lt))
            ss_pct = st.number_input("Stock de seguridad (% forecast)", min_value=0.0, max_value=1.0, value=float(ss_pct), step=0.05, format="%.2f")
            pack_default = st.number_input("Múltiplo de pedido (pack)", min_value=1, value=int(pack_default), step=1)
            priorizar_sin_hist = st.checkbox("Priorizar mínimos (sin histórico) primero", value=bool(priorizar_sin_hist))

        st.markdown("### Vista previa de datos")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**stock_tiendas**")
            st.dataframe(stock_tiendas.head(10), use_container_width=True, height=220)
            st.write("**ventas_4sem**")
            st.dataframe(ventas_4sem.head(10), use_container_width=True, height=220)
        with c2:
            st.write("**stock_disponible**")
            st.dataframe(stock_disponible.head(10), use_container_width=True, height=220)
            if not minimos_sku.empty:
                st.write("**minimos_iniciales**")
                st.dataframe(minimos_sku.head(10), use_container_width=True, height=220)

        st.divider()
        if st.button("Calcular sugerido", type="primary"):
            df_out, resumen = calcular_sugerido(
                stock_tiendas, ventas_4sem, stock_disponible, minimos_sku,
                cobertura_dias=cobertura_dias,
                lead_time_dias=lead_time_dias,
                ss_pct=ss_pct,
                pack_default=pack_default,
                cobertura_incluye_leadtime=cobertura_incluye_lt,
                priorizar_sin_historico=priorizar_sin_hist
            )

            st.success("¡Cálculo finalizado!")
            st.subheader("Sugerido por tienda / SKU")
            st.dataframe(df_out, use_container_width=True, height=320)

            st.subheader("Resumen por SKU")
            st.dataframe(resumen, use_container_width=True, height=240)

            # Descargas
            st.download_button(
                "Descargar sugerido_por_tienda.csv",
                data=df_out.to_csv(index=False).encode("utf-8"),
                file_name="sugerido_por_tienda.csv",
                mime="text/csv"
            )
            st.download_button(
                "Descargar resumen_por_sku.csv",
                data=resumen.to_csv(index=False).encode("utf-8"),
                file_name="resumen_por_sku.csv",
                mime="text/csv"
            )

            bio = BytesIO()
            with pd.ExcelWriter(bio, engine="openpyxl") as writer:
                df_out.to_excel(writer, index=False, sheet_name="sugerido")
                resumen.to_excel(writer, index=False, sheet_name="resumen")
            bio.seek(0)
            st.download_button(
                "Descargar resultados.xlsx",
                data=bio.getvalue(),
                file_name="resultados_sugerido.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Ocurrió un error leyendo el Excel: {e}")
else:
    st.info("Sube el archivo **SugeridoAutomatico_template.xlsx** para continuar.")    
