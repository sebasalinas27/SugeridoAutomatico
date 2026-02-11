import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Sugerido Automático v2.2",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados
st.markdown("""
<style>
    .main-header {
        font-size: 32px;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 10px;
    }
    .step-header {
        font-size: 20px;
        font-weight: bold;
        color: #2ca02c;
        margin-top: 20px;
        margin-bottom: 10px;
        border-left: 4px solid #2ca02c;
        padding-left: 10px;
    }
    .metric-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        padding: 12px;
        border-radius: 5px;
        margin: 10px 0;
        border-left: 4px solid #ffc107;
    }
    .success-box {
        background-color: #d4edda;
        padding: 12px;
        border-radius: 5px;
        margin: 10px 0;
        border-left: 4px solid #28a745;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 12px;
        border-radius: 5px;
        margin: 10px 0;
        border-left: 4px solid #dc3545;
    }
    .order-badge {
        display: inline-block;
        background-color: #0066cc;
        color: white;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        margin-right: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ==================== FUNCIONES AUXILIARES ====================

def crear_template_descargable():
    """Crea un template Excel descargable con estructura actualizada"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Stock Tiendas (CON PRIORIDAD)
        df_tiendas = pd.DataFrame({
            'tienda_id': ['T001', 'T001', 'T001', 'T002', 'T002', 'T003', 'T003'],
            'sku': ['SKU-001', 'SKU-002', 'SKU-003', 'SKU-001', 'SKU-002', 'SKU-001', 'SKU-003'],
            'producto': ['Producto A', 'Producto B', 'Producto C', 'Producto A', 'Producto B', 'Producto A', 'Producto C'],
            'stock_actual': [8, 0, 5, 3, 12, 1, 0],
            'venta_ultima_semana': [5, 0, 2, 4, 6, 3, 0],
            'venta_4_semanas': [22, 0, 8, 18, 24, 12, 0],
            'tipo_carga': ['reposicion', 'inicial', 'reposicion', 'reposicion', 'reposicion', 'reposicion', 'inicial'],
            'prioridad_tienda': [1, 1, 1, 2, 2, 3, 3]
        })
        df_tiendas.to_excel(writer, sheet_name='Stock Tiendas', index=False)
        
        # Hoja 2: Stock Disponible Bodega
        df_bodega = pd.DataFrame({
            'sku': ['SKU-001', 'SKU-002', 'SKU-003'],
            'producto': ['Producto A', 'Producto B', 'Producto C'],
            'stock_bodega': [150, 80, 45]
        })
        df_bodega.to_excel(writer, sheet_name='Stock Bodega', index=False)
        
        # Hoja 3: Parámetros
        df_params = pd.DataFrame({
            'parametro': ['Carga Mínima (reposición)', 'Carga Inicial (productos nuevos)', 'Máximo por SKU/Tienda'],
            'valor': [2, 8, 20],
            'descripcion': ['Mínimo de unidades por tienda', 'Unidades iniciales para nuevos productos', 'Máximo de unidades por SKU en una tienda']
        })
        df_params.to_excel(writer, sheet_name='Parámetros', index=False)
        
        # Hoja 4: Instrucciones
        df_instrucciones = pd.DataFrame({
            'Campo': ['tienda_id', 'sku', 'producto', 'stock_actual', 'venta_ultima_semana', 'venta_4_semanas', 'tipo_carga', 'prioridad_tienda'],
            'Descripción': [
                'ID único de la tienda (ej: T001)',
                'Código único del SKU (ej: SKU-001)',
                'Nombre del producto (opcional)',
                'Unidades actuales en tienda',
                'Venta en últimos 7 días',
                'Venta en últimas 4 semanas',
                'Marca como "reposicion" o "inicial"',
                'Orden de carga: 1=primero, 5=último'
            ],
            'Ejemplo': ['T001', 'SKU-001', 'Producto A', '8', '5', '22', 'reposicion', '1']
        })
        df_instrucciones.to_excel(writer, sheet_name='Instrucciones', index=False)
        
        writer.close()
    
    output.seek(0)
    return output

def calcular_sugerido_con_prioridad(df_tiendas, df_bodega, carga_minima, carga_inicial, carga_maxima):
    """
    Calcula el sugerido de carga respetando:
    1. PRIORIDAD de tiendas
    2. MÁXIMO de carga por SKU/tienda
    """
    
    # Crear copia mutable del stock bodega
    stock_bodega_disponible = df_bodega.set_index('sku')['stock_bodega'].to_dict()
    
    # Ordenar por prioridad_tienda
    df_tiendas_ordenadas = df_tiendas.sort_values(['prioridad_tienda', 'tienda_id', 'sku']).reset_index(drop=True)
    
    resultados = []
    orden_carga = 0
    
    for idx, row in df_tiendas_ordenadas.iterrows():
        orden_carga += 1
        
        sku = row['sku']
        tienda = row['tienda_id']
        stock_actual = row['stock_actual']
        tipo_carga = row['tipo_carga']
        prioridad = row['prioridad_tienda']
        
        # Obtener stock disponible en bodega
        stock_bodega = stock_bodega_disponible.get(sku, 0)
        
        # Determinar cantidad sugerida
        if tipo_carga.lower() == 'inicial':
            cantidad_sugerida = carga_inicial
            razon = f"Carga inicial (nuevo producto)"
        else:  # reposición
            cantidad_sugerida = max(0, carga_minima - stock_actual)
            if cantidad_sugerida == 0:
                razon = "Tienda en nivel mínimo"
            else:
                razon = f"Reposición a mínimo ({carga_minima} unidades)"
        
        # APLICAR MÁXIMO DE CARGA por SKU/tienda
        cantidad_sugerida = min(cantidad_sugerida, carga_maxima)
        
        # Ajustar por disponibilidad en bodega
        cantidad_real = min(cantidad_sugerida, stock_bodega)
        
        if cantidad_real < cantidad_sugerida and cantidad_sugerida > 0:
            estado = "Parcialmente cargada"
            razon += f" (solo {cantidad_real} de {cantidad_sugerida} disponibles)"
        elif cantidad_real == 0 and cantidad_sugerida > 0:
            estado = "No cargada"
            razon += " (bodega insuficiente)"
        else:
            estado = "Completa" if cantidad_sugerida > 0 else "Sin necesidad"
        
        # Actualizar stock bodega
        stock_bodega_disponible[sku] = stock_bodega - cantidad_real
        disponible_despues = stock_bodega_disponible[sku]
        stock_despues = stock_actual + cantidad_real
        
        resultados.append({
            'tienda_id': tienda,
            'sku': sku,
            'producto': row.get('producto', sku),
            'prioridad': prioridad,
            'stock_antes': stock_actual,
            'stock_despues': stock_despues,
            'cantidad_a_despachar': cantidad_real,
            'razon': razon,
            'venta_ultima_semana': row.get('venta_ultima_semana', 0),
            'venta_4_semanas': row.get('venta_4_semanas', 0),
            'stock_bodega_disponible': stock_bodega,
            'stock_bodega_despues': disponible_despues,
            'tipo_carga': tipo_carga,
            'orden_carga': orden_carga,
            'estado': estado,
            'carga_maxima_aplicada': carga_maxima
        })
    
    df_resultados = pd.DataFrame(resultados)
    
    # Calcular resumen de completitud por tienda
    resumen_tiendas = df_resultados.groupby('tienda_id').agg({
        'estado': lambda x: (x == 'Completa').sum() / len(x),
        'prioridad': 'first'
    }).reset_index()
    resumen_tiendas.columns = ['tienda_id', 'porcentaje_carga', 'prioridad']
    
    return df_resultados, resumen_tiendas, stock_bodega_disponible

def generar_reporte_descargable(df_resultados, df_bodega, stock_bodega_final):
    """Genera un archivo Excel con los reportes de carga y bodega"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Resumen ejecutivo
        total_unidades = df_resultados['cantidad_a_despachar'].sum()
        tiendas_completas = (df_resultados.groupby('tienda_id')['estado'].apply(lambda x: (x == 'Completa').all())).sum()
        tiendas_parciales = (df_resultados.groupby('tienda_id')['estado'].apply(lambda x: ((x == 'Parcialmente cargada').any() and (x != 'Completa').any()))).sum()
        tiendas_no_cargadas = (df_resultados.groupby('tienda_id')['estado'].apply(lambda x: (x == 'No cargada').all())).sum()
        
        carga_maxima = df_resultados['carga_maxima_aplicada'].iloc[0] if len(df_resultados) > 0 else 0
        
        resumen = pd.DataFrame({
            'Métrica': [
                'Total unidades a despachar',
                'Total SKUs a reponer',
                'Tiendas completamente cargadas',
                'Tiendas parcialmente cargadas',
                'Tiendas no cargadas',
                'Stock bodega inicial',
                'Stock bodega final',
                'Stock bodega usado',
                'Máximo por SKU/Tienda (aplicado)'
            ],
            'Valor': [
                total_unidades,
                df_resultados['sku'].nunique(),
                tiendas_completas,
                tiendas_parciales,
                tiendas_no_cargadas,
                df_bodega['stock_bodega'].sum(),
                sum(stock_bodega_final.values()),
                df_bodega['stock_bodega'].sum() - sum(stock_bodega_final.values()),
                carga_maxima
            ]
        })
        resumen.to_excel(writer, sheet_name='Resumen', index=False)
        
        # Hoja 2: Detalle por tienda (en orden de prioridad)
        df_por_tienda = df_resultados[['orden_carga', 'tienda_id', 'prioridad', 'sku', 'producto', 'stock_antes', 
                                        'stock_despues', 'cantidad_a_despachar', 'tipo_carga', 'estado']].copy()
        df_por_tienda = df_por_tienda.sort_values(['orden_carga', 'tienda_id', 'sku'])
        df_por_tienda.to_excel(writer, sheet_name='Detalle Tiendas', index=False)
        
        # Hoja 3: Carga por Prioridad
        df_prioridad = df_resultados.groupby(['prioridad', 'tienda_id']).agg({
            'cantidad_a_despachar': 'sum',
            'estado': lambda x: 'Completa' if (x == 'Completa').all() else ('Parcial' if (x == 'Parcialmente cargada').any() else 'No cargada')
        }).reset_index()
        df_prioridad = df_prioridad.rename(columns={
            'prioridad': 'Prioridad',
            'tienda_id': 'Tienda',
            'cantidad_a_despachar': 'Total Despachar',
            'estado': 'Estado'
        })
        df_prioridad.to_excel(writer, sheet_name='Carga por Prioridad', index=False)
        
        # Hoja 4: Impacto bodega
        df_bodega_impacto = df_resultados.groupby('sku').agg({
            'cantidad_a_despachar': 'sum',
            'stock_bodega_disponible': 'first',
            'stock_bodega_despues': 'first'
        }).reset_index()
        df_bodega_impacto['stock_bodega_final'] = df_bodega_impacto['sku'].map(stock_bodega_final)
        df_bodega_impacto = df_bodega_impacto.rename(columns={
            'sku': 'SKU',
            'cantidad_a_despachar': 'Total Despachar',
            'stock_bodega_disponible': 'Stock Antes',
            'stock_bodega_despues': 'Stock Después (calculado)',
            'stock_bodega_final': 'Stock Final (real)'
        })
        df_bodega_impacto.to_excel(writer, sheet_name='Impacto Bodega', index=False)
        
        # Hoja 5: Antes vs Después (agrupado por tienda)
        pivot_antes_despues = df_resultados.groupby('tienda_id').agg({
            'stock_antes': 'sum',
            'stock_despues': 'sum',
            'cantidad_a_despachar': 'sum',
            'estado': lambda x: 'Completa' if (x == 'Completa').all() else ('Parcial' if (x == 'Parcialmente cargada').any() else 'No cargada'),
            'prioridad': 'first'
        }).reset_index()
        pivot_antes_despues['diferencia'] = pivot_antes_despues['stock_despues'] - pivot_antes_despues['stock_antes']
        pivot_antes_despues = pivot_antes_despues.rename(columns={
            'tienda_id': 'Tienda',
            'stock_antes': 'Stock Antes',
            'stock_despues': 'Stock Después',
            'cantidad_a_despachar': 'Despachar',
            'diferencia': 'Cambio',
            'estado': 'Estado',
            'prioridad': 'Prioridad'
        })
        pivot_antes_despues = pivot_antes_despues[['Prioridad', 'Tienda', 'Stock Antes', 'Stock Después', 'Cambio', 'Despachar', 'Estado']]
        pivot_antes_despues.to_excel(writer, sheet_name='Antes vs Después', index=False)
        
        writer.close()
    
    output.seek(0)
    return output

# ==================== INTERFAZ PRINCIPAL ====================

st.markdown('<div class="main-header">📦 Sugerido Automático v2.2</div>', unsafe_allow_html=True)
st.markdown("**Repone automáticamente tu inventario respetando PRIORIDAD de tiendas y MÁXIMO de carga**")
st.divider()

# Sidebar con pasos
with st.sidebar:
    st.markdown("### 📋 Pasos")
    step = st.radio("Selecciona un paso:", 
                    ["1️⃣ Descargar Template", 
                     "2️⃣ Cargar Datos",
                     "3️⃣ Configurar Parámetros",
                     "4️⃣ Generar Sugerido",
                     "5️⃣ Descargar Reporte"],
                    label_visibility="collapsed")

# PASO 1: Descargar Template
if "1️⃣" in step:
    st.markdown('<div class="step-header">Paso 1: Descargar Template</div>', unsafe_allow_html=True)
    
    st.info("📌 Descarga el template y completa con tus datos.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **¿Qué necesitas?**
        - Stock actual por SKU y tienda
        - Ventas última semana y 4 semanas
        - Stock disponible en bodega
        - **Tipo de carga:** inicial o reposición
        - **Prioridad tienda:** 1=urgente, 5=menos urgente
        """)
    
    with col2:
        template = crear_template_descargable()
        st.download_button(
            label="⬇️ Descargar Template Excel",
            data=template,
            file_name=f"SugeridoAutomatico_Template_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    st.markdown('<div class="warning-box"><strong>💡 Tip:</strong> El template tiene 4 hojas. La columna <strong>prioridad_tienda</strong> determina el orden de carga (1→2→3).</div>', unsafe_allow_html=True)

# PASO 2: Cargar Datos
elif "2️⃣" in step:
    st.markdown('<div class="step-header">Paso 2: Cargar Datos</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("📥 Carga tu archivo Excel", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        try:
            # Leer las hojas
            df_tiendas = pd.read_excel(uploaded_file, sheet_name='Stock Tiendas')
            df_bodega = pd.read_excel(uploaded_file, sheet_name='Stock Bodega')
            df_params = pd.read_excel(uploaded_file, sheet_name='Parámetros')
            
            # Guardar en session state
            st.session_state['df_tiendas'] = df_tiendas
            st.session_state['df_bodega'] = df_bodega
            st.session_state['df_params'] = df_params
            
            st.markdown('<div class="success-box"><strong>✅ Datos cargados correctamente!</strong></div>', unsafe_allow_html=True)
            
            # Mostrar preview
            st.markdown("**Preview de datos:**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Stock Tiendas:**")
                st.dataframe(df_tiendas.head(10), use_container_width=True)
            
            with col2:
                st.markdown("**Stock Bodega:**")
                st.dataframe(df_bodega, use_container_width=True)
            
        except Exception as e:
            st.error(f"❌ Error al cargar archivo: {e}")
            st.info("Asegúrate que el archivo tiene las hojas: 'Stock Tiendas', 'Stock Bodega' y 'Parámetros'")

# PASO 3: Configurar Parámetros
elif "3️⃣" in step:
    st.markdown('<div class="step-header">Paso 3: Configurar Parámetros</div>', unsafe_allow_html=True)
    
    if 'df_tiendas' not in st.session_state:
        st.warning("⚠️ Primero carga los datos en el Paso 2")
    else:
        st.markdown("""
        Ajusta los parámetros de reposición. Estos determinan cuánto stock debe tener cada tienda.
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            carga_minima = st.number_input(
                "🏪 Carga Mínima (reposición)",
                min_value=1,
                max_value=20,
                value=2,
                help="Número mínimo de unidades que debe tener una tienda de un producto"
            )
            st.markdown('<div class="metric-box"><strong>Ejemplo:</strong> Si tienda tiene 0 unidades, se repone a 2</div>', unsafe_allow_html=True)
        
        with col2:
            carga_inicial = st.number_input(
                "🆕 Carga Inicial (productos nuevos)",
                min_value=1,
                max_value=30,
                value=8,
                help="Cantidad de unidades iniciales para productos nuevos"
            )
            st.markdown('<div class="metric-box"><strong>Ejemplo:</strong> Nuevo producto se carga con 8 unidades</div>', unsafe_allow_html=True)
        
        with col3:
            carga_maxima = st.number_input(
                "📊 Máximo por SKU/Tienda",
                min_value=5,
                max_value=100,
                value=20,
                help="Máximo de unidades que puede recibir una tienda de un SKU"
            )
            st.markdown('<div class="metric-box"><strong>Ejemplo:</strong> Máximo 20 unidades por SKU en una tienda</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Tabla de restricciones
        st.markdown("**Restricciones Aplicadas:**")
        restricciones = pd.DataFrame({
            'Parámetro': ['Carga Mínima', 'Carga Inicial', 'Máximo por SKU/Tienda', 'Límite Bodega'],
            'Valor': [f'{carga_minima} unidades', f'{carga_inicial} unidades', f'{carga_maxima} unidades', 'Stock disponible'],
            'Descripción': [
                'Mínimo para reposición',
                'Fijo para productos nuevos',
                'No puede exceder este máximo',
                'No puede superar bodega'
            ]
        })
        st.dataframe(restricciones, use_container_width=True)
        
        # Validación de parámetros
        if carga_inicial > carga_maxima:
            st.warning(f"⚠️ Carga inicial ({carga_inicial}) > Máximo ({carga_maxima}). Se limitará a {carga_maxima}.")
        
        if carga_minima > carga_maxima:
            st.warning(f"⚠️ Carga mínima ({carga_minima}) > Máximo ({carga_maxima}). Se limitará a {carga_maxima}.")
        
        # Guardar parámetros
        st.session_state['carga_minima'] = carga_minima
        st.session_state['carga_inicial'] = carga_inicial
        st.session_state['carga_maxima'] = carga_maxima
        
        st.success("✅ Parámetros configurados")

# PASO 4: Generar Sugerido
elif "4️⃣" in step:
    st.markdown('<div class="step-header">Paso 4: Generar Sugerido</div>', unsafe_allow_html=True)
    
    if 'df_tiendas' not in st.session_state or 'carga_minima' not in st.session_state:
        st.warning("⚠️ Completa los pasos anteriores primero (cargar datos y parámetros)")
    else:
        # Calcular sugerido con prioridad y máximo
        df_resultados, resumen_tiendas, stock_bodega_final = calcular_sugerido_con_prioridad(
            st.session_state['df_tiendas'],
            st.session_state['df_bodega'],
            st.session_state['carga_minima'],
            st.session_state['carga_inicial'],
            st.session_state['carga_maxima']
        )
        
        st.session_state['df_resultados'] = df_resultados
        st.session_state['stock_bodega_final'] = stock_bodega_final
        
        # Resumen ejecutivo
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📦 Total a Despachar", f"{df_resultados['cantidad_a_despachar'].sum()} unidades")
        
        with col2:
            tiendas_completas = (df_resultados.groupby('tienda_id')['estado'].apply(lambda x: (x == 'Completa').all())).sum()
            st.metric("✅ Tiendas Completas", tiendas_completas)
        
        with col3:
            st.metric("📊 SKUs", df_resultados['sku'].nunique())
        
        with col4:
            bodega_usado = st.session_state['df_bodega']['stock_bodega'].sum() - sum(stock_bodega_final.values())
            bodega_total = st.session_state['df_bodega']['stock_bodega'].sum()
            st.metric("🏭 Bodega Usado", f"{bodega_usado}/{bodega_total}")
        
        st.divider()
        
        # Alertas de completitud
        tiendas_parciales = (df_resultados.groupby('tienda_id')['estado'].apply(lambda x: ((x == 'Parcialmente cargada').any() or (x == 'No cargada').any()))).sum()
        tiendas_no_cargadas = (df_resultados.groupby('tienda_id')['estado'].apply(lambda x: (x == 'No cargada').all())).sum()
        
        if tiendas_no_cargadas > 0:
            st.markdown(f'<div class="error-box"><strong>🔴 Bodega insuficiente:</strong> {tiendas_no_cargadas} tienda(s) no se cargó/cargaron (bodega agotada)</div>', unsafe_allow_html=True)
        elif tiendas_parciales > 0:
            st.markdown(f'<div class="warning-box"><strong>🟡 Carga parcial:</strong> {tiendas_parciales} tienda(s) cargada(s) parcialmente</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="success-box"><strong>🟢 Éxito:</strong> ✅ Todas las tiendas cargadas correctamente</div>', unsafe_allow_html=True)
        
        # Mostrar parámetros aplicados
        st.markdown("**Parámetros Aplicados:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"🏪 **Carga Mínima:** {st.session_state['carga_minima']} unidades")
        with col2:
            st.info(f"🆕 **Carga Inicial:** {st.session_state['carga_inicial']} unidades")
        with col3:
            st.info(f"📊 **Máximo:** {st.session_state['carga_maxima']} unidades")
        
        st.divider()
        
        # Tabs para diferentes vistas
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Detalle Completo", "🏪 Por Tienda", "🏭 Impacto Bodega", "📍 Orden de Carga"])
        
        with tab1:
            st.markdown("**Detalle completo de la carga recomendada:**")
            df_display = df_resultados[['orden_carga', 'tienda_id', 'sku', 'producto', 'stock_antes', 
                                        'stock_despues', 'cantidad_a_despachar', 'razon', 'tipo_carga', 'estado']].copy()
            df_display = df_display.rename(columns={
                'orden_carga': 'Orden',
                'tienda_id': 'Tienda',
                'sku': 'SKU',
                'producto': 'Producto',
                'stock_antes': 'Stock Antes',
                'stock_despues': 'Stock Después',
                'cantidad_a_despachar': 'Despachar',
                'razon': 'Razón',
                'tipo_carga': 'Tipo',
                'estado': 'Estado'
            })
            st.dataframe(df_display, use_container_width=True)
        
        with tab2:
            st.markdown("**Resumen antes vs después por tienda:**")
            df_por_tienda = df_resultados.groupby('tienda_id').agg({
                'prioridad': 'first',
                'stock_antes': 'sum',
                'stock_despues': 'sum',
                'cantidad_a_despachar': 'sum'
            }).reset_index()
            df_por_tienda['cambio'] = df_por_tienda['stock_despues'] - df_por_tienda['stock_antes']
            df_por_tienda = df_por_tienda.rename(columns={
                'tienda_id': 'Tienda',
                'prioridad': 'Prioridad',
                'stock_antes': 'Stock Antes',
                'stock_despues': 'Stock Después',
                'cantidad_a_despachar': 'Total Despachar',
                'cambio': 'Cambio'
            })
            st.dataframe(df_por_tienda, use_container_width=True)
            
            # Gráfico
            col1, col2 = st.columns(2)
            with col1:
                st.bar_chart(df_por_tienda.set_index('Tienda')[['Stock Antes', 'Stock Después']])
            with col2:
                st.bar_chart(df_por_tienda.set_index('Tienda')['Total Despachar'])
        
        with tab3:
            st.markdown("**Impacto en el stock de bodega:**")
            df_bodega_impacto = df_resultados.groupby('sku').agg({
                'cantidad_a_despachar': 'sum',
                'stock_bodega_disponible': 'first',
                'stock_bodega_despues': 'first'
            }).reset_index()
            df_bodega_impacto = df_bodega_impacto.rename(columns={
                'sku': 'SKU',
                'cantidad_a_despachar': 'Total Despachar',
                'stock_bodega_disponible': 'Stock Antes',
                'stock_bodega_despues': 'Stock Después'
            })
            st.dataframe(df_bodega_impacto, use_container_width=True)
        
        with tab4:
            st.markdown("**Orden de carga por prioridad de tienda:**")
            df_orden = df_resultados[['orden_carga', 'prioridad', 'tienda_id', 'sku', 'producto', 'cantidad_a_despachar', 'estado']].copy()
            df_orden = df_orden[df_orden['cantidad_a_despachar'] > 0].drop_duplicates(subset=['orden_carga', 'tienda_id', 'sku'])
            df_orden = df_orden.sort_values('orden_carga')
            df_orden = df_orden.rename(columns={
                'orden_carga': 'Orden de Carga',
                'prioridad': 'Prioridad',
                'tienda_id': 'Tienda',
                'sku': 'SKU',
                'producto': 'Producto',
                'cantidad_a_despachar': 'Cantidad',
                'estado': 'Estado'
            })
            st.dataframe(df_orden, use_container_width=True)
            
            st.markdown("**Secuencia:**")
            for idx, row in df_orden.iterrows():
                if row['Estado'] == 'Completa':
                    color = "🟢"
                elif row['Estado'] == 'Parcialmente cargada':
                    color = "🟡"
                else:
                    color = "❌"
                st.markdown(f"{color} **Orden {row['Orden de Carga']}:** {row['Tienda']} (Prio {row['Prioridad']}) - {row['SKU']} - {row['Cantidad']} unidades")

# PASO 5: Descargar Reporte
elif "5️⃣" in step:
    st.markdown('<div class="step-header">Paso 5: Descargar Reporte</div>', unsafe_allow_html=True)
    
    if 'df_resultados' not in st.session_state:
        st.warning("⚠️ Primero genera el sugerido en el Paso 4")
    else:
        st.info("📌 Descarga el reporte con todos los detalles de la carga")
        
        reporte = generar_reporte_descargable(
            st.session_state['df_resultados'],
            st.session_state['df_bodega'],
            st.session_state['stock_bodega_final']
        )
        
        st.download_button(
            label="⬇️ Descargar Reporte Excel",
            data=reporte,
            file_name=f"SugeridoAutomatico_Reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        st.markdown('<div class="success-box"><strong>✅ El reporte incluye:</strong><br>• Resumen ejecutivo<br>• Detalle por tienda<br>• Carga por prioridad<br>• Impacto en bodega<br>• Antes vs Después</div>', unsafe_allow_html=True)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; margin-top: 20px;'>
    <small>v2.2 | Sugerido Automático | Sistema de Reposición por Prioridad con Máximo de Carga</small>
</div>
""", unsafe_allow_html=True)
