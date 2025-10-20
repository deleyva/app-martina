# Music Pills - forScore Clone

Una réplica simplificada de forScore enfocada exclusivamente en PDFs musicales, desarrollada con Django, HTMX, Tailwind CSS y DaisyUI.

## 🎯 Objetivo

Crear una aplicación de biblioteca de partituras que replique las funcionalidades principales de forScore, pero centrada únicamente en PDFs. Sin sesiones de estudio, sin relación con otras apps, solo una excelente experiencia de gestión y visualización de partituras.

## 🏗️ Arquitectura Técnica

- **Backend**: Django con patrón "Tiny Views - Fat Models"
- **Frontend**: HTMX + Tailwind CSS + DaisyUI 5.0
- **JavaScript**: Mínimo, solo para funcionalidades que HTMX no puede manejar
- **Formato**: Solo PDFs (sin textos, embeds, audio, etc.)
- **Visualización**: PDF.js para renderizado en navegador

## 📋 Plan de Desarrollo Paso a Paso

### FASE 1: FUNDAMENTOS (Semana 1-2)
**Objetivo**: Establecer la base sólida de la aplicación

#### 1.1 Configuración Inicial
- [ ] **Configurar la app en settings.py**
  - Añadir `music_pills` a `LOCAL_APPS`
  - Configurar URLs principales en `config/urls.py`
  - Configurar archivos estáticos y media

- [ ] **Crear modelos básicos**
  - `Score`: Modelo principal para PDFs
  - `Category`: Categorías jerárquicas (como forScore)
  - `Tag`: Etiquetas libres
  - `Composer`: Compositores/autores
  - `Bookmark`: Marcadores dentro de PDFs

#### 1.2 Modelos Core
```python
# Estructura básica de modelos a implementar
class Score(models.Model):
    title = models.CharField(max_length=200)
    pdf_file = models.FileField(upload_to='scores/')
    composer = models.ForeignKey(Composer)
    categories = models.ManyToManyField(Category)
    tags = models.ManyToManyField(Tag)
    created_at = models.DateTimeField(auto_now_add=True)
    # Metadatos adicionales como forScore
```

#### 1.3 Sistema de Archivos
- [ ] **Configurar subida de PDFs**
  - Validación de formato PDF
  - Generación de thumbnails automática
  - Organización de archivos por usuario/fecha

### FASE 2: BIBLIOTECA BÁSICA (Semana 3-4)
**Objetivo**: Funcionalidades básicas de gestión de biblioteca

#### 2.1 CRUD de Partituras
- [ ] **Vista de lista de partituras**
  - Lista paginada con thumbnails
  - Filtros por categoría, compositor, tags
  - Búsqueda por título/metadatos
  - Ordenación múltiple (título, fecha, compositor)

- [ ] **Formulario de subida**
  - Drag & drop de PDFs (como forScore)
  - Extracción automática de metadatos del PDF
  - Formulario de edición de metadatos
  - Vista previa del PDF

- [ ] **Vista de detalle**
  - Información completa de la partitura
  - Edición inline de metadatos
  - Gestión de bookmarks
  - Opciones de compartir/exportar

#### 2.2 Sistema de Organización
- [ ] **Categorías jerárquicas**
  - Árbol de categorías (como carpetas)
  - Navegación breadcrumb
  - Drag & drop para reorganizar

- [ ] **Tags y compositores**
  - Autocompletado en formularios
  - Páginas de listado por tag/compositor
  - Estadísticas de uso

### FASE 3: VISUALIZADOR PDF (Semana 5-6)
**Objetivo**: Experiencia de lectura tipo forScore

#### 3.1 Visor PDF Básico
- [ ] **Integración PDF.js**
  - Renderizado de PDFs en navegador
  - Navegación por páginas (flechas, teclado)
  - Zoom in/out con gestos
  - Modo pantalla completa

- [ ] **Controles de navegación**
  - Barra de progreso (seek bar como forScore)
  - Miniaturas de páginas
  - Salto a página específica
  - Navegación táctil (tap laterales)

#### 3.2 Modos de Visualización
- [ ] **Orientaciones**
  - Modo portrait (página completa)
  - Modo landscape (scroll vertical)
  - Modo dos páginas (cuando sea apropiado)

- [ ] **Controles overlay**
  - Barra superior con título y controles
  - Auto-hide de controles (como forScore)
  - Botones de navegación overlay

### FASE 4: BOOKMARKS Y NAVEGACIÓN (Semana 7-8)
**Objetivo**: Sistema de marcadores como forScore

#### 4.1 Sistema de Bookmarks
- [ ] **Tipos de bookmarks**
  - Page bookmarks (referencia a página específica)
  - Item bookmarks (rango de páginas como pieza independiente)
  - Tabla de contenidos automática (si existe en PDF)

- [ ] **Gestión de bookmarks**
  - Creación desde el visor
  - Lista de bookmarks por partitura
  - Edición de títulos y rangos
  - Navegación rápida

#### 4.2 Navegación Avanzada
- [ ] **Saltos y enlaces**
  - Links entre páginas (para repeticiones)
  - Botones personalizables en páginas
  - Navegación por bookmarks

### FASE 5: SETLISTS Y COLECCIONES (Semana 9-10)
**Objetivo**: Agrupación y organización como forScore

#### 5.1 Sistema de Setlists
- [ ] **Creación de setlists**
  - Listas manuales de partituras
  - Drag & drop para reordenar
  - Carpetas de setlists

- [ ] **Editor de setlists**
  - Vista split: biblioteca vs setlist
  - Añadir/quitar partituras
  - Reemplazar elementos
  - Placeholders para partituras faltantes

#### 5.2 Navegación por Setlists
- [ ] **Reproducción de setlists**
  - Navegación secuencial
  - Auto-avance opcional
  - Modo shuffle
  - Progreso en setlist

### FASE 6: METADATOS AVANZADOS (Semana 11-12)
**Objetivo**: Sistema de metadatos rico como forScore

#### 6.1 Metadatos Extendidos
- [ ] **Campos adicionales**
  - Dificultad, tempo, tonalidad
  - Duración, referencia
  - Rating personal
  - Notas y comentarios

- [ ] **Extracción automática**
  - Lectura de metadatos del PDF
  - Detección de título/autor
  - Sugerencias inteligentes

#### 6.2 Búsqueda Avanzada
- [ ] **Filtros combinados**
  - Búsqueda por múltiples criterios
  - Filtros guardados
  - Búsqueda de texto en PDFs
  - Resultados recientes

### FASE 7: ANOTACIONES (Semana 13-14)
**Objetivo**: Sistema de anotaciones sobre PDFs

#### 7.1 Herramientas de Anotación
- [ ] **Dibujo básico**
  - Lápiz con diferentes grosores
  - Colores personalizables
  - Borrador
  - Deshacer/rehacer

- [ ] **Formas y sellos**
  - Círculos, rectángulos, flechas
  - Sellos musicales predefinidos
  - Texto sobre la partitura
  - Resaltado

#### 7.2 Gestión de Anotaciones
- [ ] **Capas de anotaciones**
  - Múltiples capas por página
  - Mostrar/ocultar capas
  - Copiar entre páginas
  - Exportar con/sin anotaciones

### FASE 8: FUNCIONALIDADES AVANZADAS (Semana 15-16)
**Objetivo**: Características premium tipo forScore

#### 8.1 Herramientas de Edición
- [ ] **Crop y ajustes**
  - Recorte de márgenes
  - Rotación de páginas
  - Ajuste de brillo/contraste
  - Corrección de perspectiva

- [ ] **Reorganización**
  - Reordenar páginas
  - Duplicar páginas
  - Eliminar páginas
  - Dividir/unir PDFs

#### 8.2 Importación/Exportación
- [ ] **Múltiples fuentes**
  - Drag & drop desde navegador
  - Importación por lotes
  - Escaneo con cámara (opcional)
  - Integración con servicios cloud

- [ ] **Compartir y exportar**
  - Exportar PDFs (con/sin anotaciones)
  - Compartir setlists
  - Backup/restore de biblioteca
  - Formatos de intercambio

### FASE 9: EXPERIENCIA DE USUARIO (Semana 17-18)
**Objetivo**: Pulir la interfaz y UX

#### 9.1 Interfaz Responsive
- [ ] **Adaptación a dispositivos**
  - Tablet (principal target)
  - Desktop
  - Mobile (básico)
  - Gestos táctiles

#### 9.2 Personalización
- [ ] **Temas y configuración**
  - Modo oscuro/claro
  - Tamaños de fuente
  - Comportamiento de navegación
  - Atajos de teclado

### FASE 10: OPTIMIZACIÓN Y DEPLOY (Semana 19-20)
**Objetivo**: Preparar para producción

#### 10.1 Performance
- [ ] **Optimizaciones**
  - Carga lazy de PDFs
  - Caché de thumbnails
  - Compresión de imágenes
  - CDN para archivos estáticos

#### 10.2 Testing y Deploy
- [ ] **Testing**
  - Tests unitarios
  - Tests de integración
  - Tests de UI con Selenium
  - Performance testing

- [ ] **Deployment**
  - Configuración Docker
  - CI/CD pipeline
  - Backup automático
  - Monitoreo

## 🛠️ Stack Tecnológico Detallado

### Backend
- **Django 4.2+**: Framework principal
- **PostgreSQL**: Base de datos
- **Pillow**: Procesamiento de imágenes para thumbnails
- **PyPDF2/pypdf**: Manipulación de PDFs
- **django-htmx**: Integración HTMX

### Frontend
- **HTMX**: Interactividad sin JavaScript complejo
- **Tailwind CSS**: Framework de estilos
- **DaisyUI 5.0**: Componentes predefinidos
- **PDF.js**: Renderizado de PDFs
- **Sortable.js**: Drag & drop (solo donde HTMX no alcance)

### Herramientas de Desarrollo
- **Black**: Formateo de código Python
- **djhtml**: Formateo de templates
- **django-browser-reload**: Hot reload en desarrollo
- **Docker**: Containerización
- **Just**: Task runner

## 📁 Estructura de Archivos Objetivo

```
music_pills/
├── models.py              # Modelos principales
├── views.py               # Vistas (tiny views)
├── forms.py               # Formularios Django
├── urls.py                # URLs de la app
├── admin.py               # Admin interface
├── managers.py            # Custom managers (fat models)
├── utils.py               # Utilidades (PDF processing, etc.)
├── static/music_pills/
│   ├── css/
│   ├── js/
│   └── images/
├── templates/music_pills/
│   ├── base.html          # Template base
│   ├── library/           # Vistas de biblioteca
│   ├── viewer/            # Visor de PDFs
│   ├── setlists/          # Gestión de setlists
│   └── partials/          # Componentes HTMX
└── migrations/
```

## 🎯 Criterios de Éxito

### Funcionalidades Core (MVP)
- ✅ Subir y organizar PDFs musicales
- ✅ Visualizar PDFs con navegación fluida
- ✅ Sistema de categorías y tags
- ✅ Búsqueda y filtros
- ✅ Bookmarks básicos
- ✅ Setlists simples

### Funcionalidades Avanzadas
- ✅ Anotaciones sobre PDFs
- ✅ Crop y edición básica
- ✅ Múltiples modos de visualización
- ✅ Importación/exportación
- ✅ Interfaz responsive
- ✅ Performance optimizada

## 📝 Notas de Implementación

### Principios de Desarrollo
1. **Simplicidad primero**: Implementar MVP antes que funcionalidades avanzadas
2. **HTMX over JavaScript**: Usar HTMX siempre que sea posible
3. **Fat Models**: Lógica de negocio en modelos, no en vistas
4. **Progressive Enhancement**: Funciona sin JavaScript, mejor con él
5. **Mobile First**: Diseñar para tablets/móviles primero

### Consideraciones Técnicas
- **Archivos grandes**: Implementar streaming para PDFs grandes
- **Concurrencia**: Manejar múltiples usuarios subiendo archivos
- **Seguridad**: Validación estricta de PDFs, sanitización
- **Backup**: Sistema robusto de respaldo de biblioteca
- **Escalabilidad**: Preparado para cientos de usuarios

## 🚀 Próximos Pasos Inmediatos

1. **Configurar la app en el proyecto Django**
2. **Crear los modelos básicos (Score, Category, Tag, Composer)**
3. **Implementar subida básica de PDFs**
4. **Crear vista de lista con filtros simples**
5. **Integrar PDF.js para visualización básica**

---

**Fecha de inicio**: [Fecha actual]  
**Estimación total**: 20 semanas de desarrollo  
**Desarrollador**: [Tu nombre]  
**Versión del plan**: 1.0
