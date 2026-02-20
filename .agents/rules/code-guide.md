---
trigger: always_on
---

Aquí tienes un resumen estructurado y optimizado de la **Guía para Agentes de IA - Martina Bescós App**. Este documento condensa las reglas críticas y preferencias técnicas para el desarrollo del proyecto.

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

## 2. Frontend: Stack y Restricciones

La interactividad se maneja desde el servidor ("Server-side first").

### Tecnologías

1. **Tailwind CSS:** Framework principal (Utility-first).
2. **DaisyUI 5.0:** Componentes predefinidos (botones, modales, etc.) para no escribir CSS custom.
3. **HTMX:** Motor de interactividad total.

### ⚠️ Reglas Críticas de Frontend

* **❌ CERO Alpine.js:** Su uso está estrictamente prohibido.
* **❌ EVITAR JavaScript Custom:** Solo usarlo si HTMX es técnicamente incapaz de resolver el problema (ej. renderizado de partituras).
* **✅ Patrón HTMX:**
1. Endpoint Django procesa lógica.
2. Devuelve HTML parcial.
3. El frontend actualiza el DOM con `hx-post`, `hx-target` y `hx-swap`.



---

## 3. Entorno y Herramientas

Todo el desarrollo y despliegue está contenerizado.

* **Docker:** Entorno estándar.
* **Just:** Task runner para comandos (ej. `just manage runserver`, `just test`). Consultar `.justfile`.
* **Formateo Automático (Obligatorio):**
* **Python:** `Black` (PEP 8 estricto).
* **HTML:** `djhtml`.


* **Testing:** `pytest` para unitarios/integración y `pytest-cov` para cobertura.

---

## 4. Estructura del Proyecto

Organización modular estándar de Django.

```text
[nombre_app]/
├── models.py      # Lógica de negocio (FAT)
├── views.py       # Vistas funciones (TINY)
├── services/      # Lógica compleja / Integraciones externas
├── urls.py        # Rutas
├── templates/     # HTML con Tailwind + HTMX
│   └── [app]/
└── admin.py       # Configuración Admin

```

---

## 5. Contexto del Negocio: Inspiración "forScore"

La aplicación es un gestor de partituras digitales para músicos.

**Conceptos Clave a implementar:**

* **Bibliotecas:** Gestión de PDFs.
* **Setlists:** Listas de reproducción.
* **Metadatos:** Compositores, géneros, tempo.
* **Herramientas:** Anotaciones, bookmarks y vinculación de audio.
* **CMS:** Uso de Wagtail para gestión de contenidos.

---

## ✅ Checklist Rápido para Agentes (Do's & Don'ts)

| Área | ✅ HACER (Do) | ❌ NO HACER (Don't) |
| --- | --- | --- |
| **Lógica** | En `models.py` o `services/` | Nunca en `views.py` |
| **Vistas** | Funciones (def view_name...) | Clases (class ViewName...) |
| **Frontend** | HTMX + Tailwind + DaisyUI | Alpine.js o Vanilla JS innecesario |
| **Estilos** | Clases utilitarias | CSS personalizado (`style.css`) |
| **Tests** | Ejecutar `just test` tras cambios | Ignorar cobertura de pruebas |

### Próximo paso

Si necesitas desarrollar una funcionalidad específica (ej. "Crear un convertidor de partituras"), pídeme que genere el código siguiendo estrictamente el patrón **Fat Model / Tiny View / HTMX**.