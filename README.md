# 🛒 Sugerido Automático – CPFR Simplificado

Herramienta para calcular sugeridos de reposición por **código/tienda** en entornos **retail/wholesale**, basada en principios de **CPFR (Collaborative Planning, Forecasting and Replenishment)**.

---

## 🚀 ¿Qué hace esta app?

- Calcula el **pedido sugerido** por tienda y SKU usando:
  - Ventas históricas (últimas 4 semanas)
  - Stock actual en tienda
  - Stock disponible en bodega
- Aplica lógica CPFR simplificada:
  - Forecast = Ventas promedio diaria × Horizonte
  - Stock de seguridad configurable
  - Política para SKUs sin histórico (mínimos iniciales)
- Asigna pedidos respetando **stock disponible** y **prioridades**.

---

## 📂 Estructura del archivo Excel

La app **solo acepta un archivo Excel** con las siguientes hojas:

HojaColumnas requeridasstock_tiendastienda_id, sku, stock_tienda| **ventas_4sem**      | `tienda_id`, `sku`, `ventas_4_sem`                  |
| **stock_disponible** | `sku`, `stock_disponible`                            |
| **minimos_iniciales**| `sku`, `min_inicial` *(para SKUs sin histórico)*     |
| **parametros**       | `cobertura_dias`, `lead_time_dias`, `ss_pct`, `pack_default`, `cobertura_incluye_leadtime`, `priorizar_sin_historico` |

📥 **Descarga la plantilla aquí:**  
[SugeridoAutomatico_template.xlsx](./SugeridoAutomatico_templateos

ParámetroDescripcióncobertura_diasDías de cobertura objetivo (ej. 14)| **lead_time_dias**          | Tiempo de entrega en días (ej. 7)                                          |
| **ss_pct**                  | Stock de seguridad como % del forecast (ej. 0.15 = 15%)                    |
| **pack_default**            | Múltiplo mínimo de pedido (ej. 1 = sin restricción)                        |
| **cobertura_incluye_leadtime** | TRUE si la cobertura ya incluye el lead time                              |
| **priorizar_sin_historico** | TRUE para asignar primero SKUs sin ventas (mínimos)                        |

---

## 🖥️ Cómo usar la app

1. **Clona el repositorio**:
   ```bash
   git clone https://github.com/sebasalinas27/SugeridoAutomatico.git
   cd SugeridoAutomatico
