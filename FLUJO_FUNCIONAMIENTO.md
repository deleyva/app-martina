# 📊 Flujo de Funcionamiento - Martina Bescós App

## 🏗️ Arquitectura General del Sistema

```mermaid
graph TB
    subgraph "Frontend"
        UI[🖥️ Interfaz Web]
        HTMX[⚡ HTMX]
        TW[🎨 Tailwind CSS]
    end
    
    subgraph "Backend Django"
        URLS[🔗 URLs Router]
        VIEWS[👁️ Views]
        MODELS[📊 Models]
        TASKS[⚙️ Huey Tasks]
    end
    
    subgraph "Bases de Datos"
        PG[(🐘 PostgreSQL)]
        REDIS[(🔴 Redis)]
    end
    
    subgraph "Servicios Externos"
        SPOT[🎵 Spotify API]
        GOOGLE[🔐 Google Auth]
        WAGTAIL[📝 Wagtail CMS]
    end
    
    UI --> URLS
    HTMX --> VIEWS
    VIEWS --> MODELS
    MODELS --> PG
    TASKS --> REDIS
    VIEWS --> SPOT
    UI --> GOOGLE
    VIEWS --> WAGTAIL
```

## 🎯 Módulos Principales

### 1. 📚 Sistema de Evaluaciones (`evaluations`)

```mermaid
flowchart TD
    START([👨‍🎓 Estudiante accede]) --> LOGIN{🔐 ¿Autenticado?}
    LOGIN -->|No| GOOGLE[🔐 Login con Google]
    LOGIN -->|Sí| DASHBOARD[📊 Dashboard Principal]
    
    GOOGLE --> DASHBOARD
    
    DASHBOARD --> EVAL_LIST[📋 Lista de Evaluaciones]
    EVAL_LIST --> EVAL_TYPE{📝 Tipo de Evaluación}
    
    EVAL_TYPE -->|Entrega Web| WEB_SUBMIT[💻 Formulario Web]
    EVAL_TYPE -->|Entrega Classroom| CLASS_SUBMIT[📤 Subida de Archivos]
    
    WEB_SUBMIT --> RUBRIC[📏 Sistema de Rúbricas]
    CLASS_SUBMIT --> UPLOAD[📁 Subida Video/Imagen]
    
    UPLOAD --> COMPRESS{🔄 ¿Es Video?}
    COMPRESS -->|Sí| HUEY_TASK[⚙️ Tarea de Compresión]
    COMPRESS -->|No| STORE[💾 Almacenar Archivo]
    
    HUEY_TASK --> FFMPEG[🎬 Procesamiento FFmpeg]
    FFMPEG --> STORE
    
    RUBRIC --> SCORE[📊 Cálculo de Puntuación]
    STORE --> PENDING[⏳ Estado Pendiente]
    
    SCORE --> FEEDBACK[💬 Retroalimentación]
    PENDING --> TEACHER_EVAL[👩‍🏫 Evaluación Profesor]
    
    TEACHER_EVAL --> RUBRIC
    FEEDBACK --> EMAIL[📧 Envío por Email]
```

#### 🔄 Estados de Evaluación

```mermaid
stateDiagram-v2
    [*] --> Creada
    Creada --> Pendiente : Estudiante asignado
    Pendiente --> EnProceso : Profesor inicia evaluación
    EnProceso --> Completada : Puntuación asignada
    Completada --> Enviada : Email enviado
    
    Pendiente --> ClassroomSubmission : Entrega por Classroom
    ClassroomSubmission --> Procesando : Video subido
    Procesando --> Completada : Compresión finalizada
    Procesando --> Error : Fallo en compresión
```

### 2. 🎵 Sistema de Ranking de Canciones (`songs_ranking`)

```mermaid
flowchart TD
    ADMIN[👩‍💼 Administrador] --> CREATE_SURVEY[📝 Crear Encuesta]
    CREATE_SURVEY --> CONFIG_PHASES[⏰ Configurar Fases]
    
    CONFIG_PHASES --> PROPOSAL_PHASE[💡 Fase de Propuestas]
    PROPOSAL_PHASE --> SPOTIFY_SEARCH[🔍 Búsqueda en Spotify]
    
    SPOTIFY_SEARCH --> ADD_SONG[➕ Proponer Canción]
    ADD_SONG --> PROPOSAL_DB[(💾 Guardar Propuesta)]
    
    PROPOSAL_PHASE --> VOTING_PHASE[🗳️ Fase de Votación]
    VOTING_PHASE --> SONG_LIST[📋 Lista de Canciones]
    
    SONG_LIST --> SPOTIFY_PLAYER[🎵 Reproductor Spotify]
    SPOTIFY_PLAYER --> VOTE[✅ Votar]
    
    VOTE --> VOTE_DB[(💾 Guardar Voto)]
    VOTING_PHASE --> RESULTS[📊 Resultados]
    
    RESULTS --> RANKING[🏆 Ranking Final]
```

#### 📅 Fases de la Encuesta

```mermaid
gantt
    title Cronología de Encuesta Musical
    dateFormat YYYY-MM-DD
    section Fases
    Fase de Propuestas    :active, proposal, 2024-01-01, 7d
    Fase de Votación      :voting, after proposal, 7d
    Resultados           :results, after voting, 1d
```

### 3. 🔑 Sistema de API Keys (`api_keys`)

```mermaid
flowchart LR
    USER[👤 Usuario] --> REQUEST[📝 Solicitar API Key]
    REQUEST --> GENERATE[🔐 Generar UUID]
    GENERATE --> STORE_KEY[(💾 Almacenar Clave)]
    
    API_CALL[📡 Llamada API] --> VALIDATE[✅ Validar Clave]
    VALIDATE --> AUTHORIZED{🔒 ¿Autorizado?}
    
    AUTHORIZED -->|Sí| PROCESS[⚙️ Procesar Solicitud]
    AUTHORIZED -->|No| REJECT[❌ Rechazar]
    
    PROCESS --> UPDATE_USAGE[📊 Actualizar Uso]
    UPDATE_USAGE --> RESPONSE[📤 Respuesta]
```

### 4. 📰 Sistema CMS (`cms` - Wagtail)

```mermaid
flowchart TD
    EDITOR[✍️ Editor] --> CMS_LOGIN[🔐 Admin CMS]
    CMS_LOGIN --> PAGE_TYPES[📄 Tipos de Página]
    
    PAGE_TYPES --> HOME[🏠 Página Inicio]
    PAGE_TYPES --> STANDARD[📝 Página Estándar]
    PAGE_TYPES --> BLOG_INDEX[📚 Índice Blog]
    PAGE_TYPES --> BLOG_POST[📰 Artículo Blog]
    
    HOME --> HERO[🎯 Sección Hero]
    HERO --> CONTENT[📄 Contenido]
    
    BLOG_INDEX --> LIST_POSTS[📋 Listar Artículos]
    BLOG_POST --> RICH_CONTENT[📝 Contenido Rico]
    
    CONTENT --> PUBLISH[🚀 Publicar]
    RICH_CONTENT --> PUBLISH
    
    PUBLISH --> PUBLIC_SITE[🌐 Sitio Público]
```

## 🔐 Sistema de Autenticación

```mermaid
flowchart TD
    VISITOR[👤 Visitante] --> AUTH_TYPE{🔐 Tipo de Auth}
    
    AUTH_TYPE -->|Google| GOOGLE_OAUTH[🔐 Google OAuth]
    AUTH_TYPE -->|Password| PASS_LOGIN[🔑 Login Tradicional]
    
    GOOGLE_OAUTH --> GOOGLE_CALLBACK[↩️ Callback Google]
    GOOGLE_CALLBACK --> CREATE_USER{👤 ¿Usuario Existe?}
    
    CREATE_USER -->|No| NEW_USER[➕ Crear Usuario]
    CREATE_USER -->|Sí| EXISTING_USER[✅ Usuario Existente]
    
    PASS_LOGIN --> VALIDATE_PASS[✅ Validar Contraseña]
    VALIDATE_PASS --> ADMIN_CHECK{👑 ¿Es Admin?}
    
    ADMIN_CHECK -->|Sí| ALLOW_PASS[✅ Permitir Login]
    ADMIN_CHECK -->|No| REDIRECT_GOOGLE[↗️ Redirigir a Google]
    
    NEW_USER --> SESSION[🎫 Crear Sesión]
    EXISTING_USER --> SESSION
    ALLOW_PASS --> SESSION
    
    SESSION --> DASHBOARD[📊 Dashboard]
    
    DASHBOARD --> IMPERSONATE{👥 ¿Superuser?}
    IMPERSONATE -->|Sí| IMPERSONATE_MENU[👥 Menú Impersonar]
    IMPERSONATE_MENU --> SELECT_USER[👤 Seleccionar Usuario]
    SELECT_USER --> TEMP_SESSION[🎭 Sesión Temporal]
```

## 📊 Flujo de Datos Completo

```mermaid
flowchart TB
    subgraph "Capa de Presentación"
        TEMPLATES[📄 Templates Django]
        STATIC[🎨 Archivos Estáticos]
        HTMX_JS[⚡ HTMX JavaScript]
    end
    
    subgraph "Capa de Aplicación"
        VIEWS[👁️ Views]
        FORMS[📝 Forms]
        SERIALIZERS[🔄 Serializers]
        API_NINJA[🥷 Django Ninja API]
    end
    
    subgraph "Capa de Negocio"
        MODELS[📊 Models]
        MANAGERS[👔 Managers]
        SIGNALS[📡 Signals]
        TASKS[⚙️ Huey Tasks]
    end
    
    subgraph "Capa de Datos"
        POSTGRES[(🐘 PostgreSQL)]
        REDIS[(🔴 Redis Cache)]
        MEDIA[📁 Media Files]
    end
    
    subgraph "Servicios Externos"
        SPOTIFY_API[🎵 Spotify Web API]
        GOOGLE_AUTH[🔐 Google OAuth]
        EMAIL_SERVICE[📧 Email Service]
    end
    
    TEMPLATES --> VIEWS
    HTMX_JS --> API_NINJA
    VIEWS --> FORMS
    FORMS --> MODELS
    API_NINJA --> SERIALIZERS
    SERIALIZERS --> MODELS
    
    MODELS --> POSTGRES
    TASKS --> REDIS
    MODELS --> MEDIA
    
    VIEWS --> SPOTIFY_API
    VIEWS --> GOOGLE_AUTH
    TASKS --> EMAIL_SERVICE
    
    SIGNALS --> TASKS
```

## 🔄 Procesos Asíncronos (Huey)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant V as Vista Django
    participant H as Huey Queue
    participant W as Worker
    participant F as FFmpeg
    participant DB as Base de Datos
    
    U->>V: Sube video
    V->>DB: Guarda SubmissionVideo (PENDING)
    V->>H: Encola tarea compresión
    V->>U: Respuesta inmediata
    
    H->>W: Asigna tarea a worker
    W->>DB: Actualiza estado (PROCESSING)
    W->>F: Ejecuta compresión FFmpeg
    F->>W: Video comprimido
    W->>DB: Guarda video comprimido (COMPLETED)
    
    Note over W,DB: Si hay error: estado FAILED
```

## 🎯 Casos de Uso Principales

### 📝 Evaluación de Estudiante

1. **Estudiante accede** → Login con Google
2. **Ve evaluaciones pendientes** → Selecciona evaluación
3. **Tipo de entrega**:
   - **Web**: Completa formulario con rúbricas
   - **Classroom**: Sube archivos (video/imagen)
4. **Procesamiento**: Videos se comprimen automáticamente
5. **Profesor evalúa** → Asigna puntuaciones por rúbricas
6. **Retroalimentación** → Se envía por email

### 🎵 Encuesta Musical

1. **Admin crea encuesta** → Define fases temporales
2. **Fase propuestas**: Usuarios buscan y proponen canciones
3. **Fase votación**: Usuarios escuchan y votan canciones
4. **Resultados**: Se muestra ranking final

### 📰 Gestión de Contenido

1. **Editor accede a CMS** → Wagtail Admin
2. **Crea/edita páginas** → Diferentes tipos disponibles
3. **Publica contenido** → Visible en sitio público

## 🛠️ Tecnologías Utilizadas

- **Backend**: Django 4.x + PostgreSQL
- **Frontend**: HTMX + Tailwind CSS
- **CMS**: Wagtail
- **API**: Django Ninja
- **Autenticación**: Django Allauth + Google OAuth
- **Tareas Asíncronas**: Huey + Redis
- **Procesamiento Video**: FFmpeg
- **Servicios Externos**: Spotify Web API

## 📈 Métricas y Monitoreo

```mermaid
flowchart LR
    LOGS[📋 Logs Django] --> MONITORING[📊 Monitoreo]
    API_USAGE[📡 Uso de APIs] --> MONITORING
    USER_ACTIVITY[👤 Actividad Usuarios] --> MONITORING
    TASK_STATUS[⚙️ Estado Tareas] --> MONITORING
    
    MONITORING --> ALERTS[🚨 Alertas]
    MONITORING --> REPORTS[📊 Reportes]
```

---

*Este diagrama representa el flujo completo de funcionamiento de la aplicación Martina Bescós, mostrando la interacción entre todos los módulos y sistemas integrados.*
