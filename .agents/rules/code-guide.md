---
trigger: always_on
---

# 📋 Resumen Ejecutivo: Reglas de Desarrollo

## 1. Filosofía y Arquitectura Backend

**Principio Rector:** Actúa como un experto en Django que prioriza la legibilidad y la simplicidad.

### Regla de Oro: "Tiny Views - Fat Models"

* **Fat Models (Modelos Robustos):**
* Toda la lógica de negocio, validaciones y transformación de datos vive en `models.py`.
* Implementar métodos personalizados en el modelo para manipular datos.


* **Tiny Views (Vistas Delgadas):**
* Responsabilidad única: Recibir petición HTTP  Llamar método del modelo  Renderizar template.
* **Prohibido:** Lógica de negocio en las vistas.



### Estilo de Vistas

* **✅ OBLIGATORIO:** Usar **Function-Based Views (FBVs)**.
* **❌ PROHIBIDO:** Class-Based Views (CBVs).
* *Motivo:* Mayor explicitud y facilidad de mantenimiento.

### Capa de Servicios (Service Layer)

Para lógica muy compleja que involucre múltiples modelos o APIs externas (ej. IA, Pagos), no sobrecargar el modelo.

* **Ubicación:** `[app]/services/`
* **Uso:** Clases con métodos públicos claros, type hints y manejo de errores robusto.

---

## 2. Contexto del Negocio: Inspiración "forScore"

La aplicación es un gestor de partituras digitales para músicos.

**Conceptos Clave a implementar:**

* **Bibliotecas:** Gestión de PDFs.
* **Setlists:** Listas de reproducción.
* **Metadatos:** Compositores, géneros, tempo.
* **Herramientas:** Anotaciones, bookmarks y vinculación de audio.
* **CMS:** Uso de Wagtail para gestión de contenidos.
