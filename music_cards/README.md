## Diario de trabajo de la aplicación `music_cards`

### 8 de octubre de 2025

Consigo que se vayan actualizando las cajas y la cantidad de repasos que he hecho de cada music_item.

También he conseguido que se pueda calificar un music_item con un número de caja y que se actualice en la base de datos.

### 12 de octubre de 2025.

- [X] Hacer gráfico de la relación de la base de datos de `music_cards`.
- [X] Mostrar pordefecto la versión pdf de un music_item. Mostrar un desplegable si ese music item tuviera más archivos asociados para poder navegar por ellos.

### Trabajo para mañana
- [X] Preguntar, usando los gráficos de las bases de datos, si es un sistema bien optimizado.
- [X] Probar a estudiar usando la app.

## Algoritmo de Estudio

El sistema de repetición espaciada de Music Cards utiliza un algoritmo híbrido que combina el sistema Leitner con priorización pedagógica musical.

### 🎯 Proceso de Selección de Elementos

#### 1. **Incorporación de Elementos Nuevos**
- Busca automáticamente elementos musicales que nunca has estudiado
- Añade hasta **5 elementos nuevos** por sesión
- Los coloca en **Box 1** (nivel más básico del sistema Leitner)
- Garantiza exposición continua a contenido fresco

#### 2. **Filtrado por Etiquetas (Opcional)**
- Si seleccionas etiquetas específicas (estilo, instrumento): **filtra solo esos elementos**
- Si no seleccionas nada: **incluye todos tus elementos**
- Permite sesiones temáticas focalizadas

#### 3. **Ordenación Inteligente Multi-Criterio**

El algoritmo ordena los elementos según **3 criterios jerárquicos**:

##### **Criterio 1: Prioridad Pedagógica Musical**
```
1. "toque de oído" (máxima prioridad)
2. "lectura a primera vista"
3. "técnica"
4. "literatura"
5. "improvisación"
6. Elementos sin etiquetas específicas (mínima prioridad)
```

##### **Criterio 2: Sistema Leitner por Cajas** ⭐ **NUEVO**
```
Box 1 ("No lo sé") → Box 2 ("Difícil") → Box 3 ("Bien") → Box 4 ("Fácil")
```
**Prioriza elementos que peor te sabes para maximizar el aprendizaje**

##### **Criterio 3: Fecha de Última Revisión**
- Los elementos menos revisados recientemente aparecen primero
- Actúa como criterio de desempate

### 📊 Ejemplo de Ordenación

**Orden final de una sesión:**
```
1. "Riptide" (toque de oído, Box 1, hace 5 días)
2. "Escalas mayores" (técnica, Box 1, hace 3 días)
3. "Con tanta terneza" (toque de oído, Box 2, hace 2 días)
4. "Lectura rítmica" (lectura a primera vista, Box 2, hace 1 día)
5. "Improvisación blues" (improvisación, Box 4, hoy)
```

### 🎯 Características del Sistema

#### **✅ Elementos que SIEMPRE aparecen:**
- **Elementos nuevos**: Hasta 5 que nunca has estudiado
- **Todos tus UserReviews existentes**: Sin importar la caja (1-4)
- **Respeta filtros de etiquetas**: Solo si seleccionas etiquetas específicas

#### **🔄 Comportamiento del Sistema:**
- **Inclusivo**: Muestra todo lo que tienes pendiente (no hay límite máximo)
- **Pedagógicamente ordenado**: Refleja progresión educativa musical típica
- **Prioriza dificultades**: Los elementos de cajas bajas aparecen primero
- **Flexible**: Permite filtrado por estilo/instrumento específico

#### **📈 Beneficios:**
- **Más efectivo pedagógicamente**: Practicas primero lo que más necesitas
- **Mejor uso del tiempo**: Los elementos difíciles aparecen cuando estás más fresco
- **Progreso más rápido**: El sistema Leitner funciona mejor priorizando cajas bajas
- **Mantiene coherencia educativa**: Respeta la secuencia pedagógica musical

### 🔧 Implementación Técnica

**Método principal:** `UserStudySession.start_study_session(tags=None)`

**Algoritmo de ordenación:**
```python
# Para cada grupo de etiquetas pedagógicas:
tagged_reviews = reviews.filter(music_item__tags__key=tag)
                       .distinct()
                       .order_by('box', 'last_reviewed')

# Para elementos sin etiquetas específicas:
non_matching_reviews = reviews.exclude(id__in=matching_ids)
                             .distinct()
                             .order_by('box', 'last_reviewed')
```

**Resultado:** Un sistema de repetición espaciada que combina la efectividad del método Leitner con la estructura pedagógica de la educación musical profesional.

---

Ahora vamos a revisar también los modelos de bibliotecas compartidas en music_cards:

Basándome en la arquitectura implementada, te explico cómo se gestiona la **compartición de música y tips** entre estudiantes y la **asignación de elementos** para grupos clase:

## 🎓 **Sistema de Gestión Educativa Musical**

La aplicación tiene una **arquitectura completa de 4 apps interconectadas** que maneja estos casos de uso:

### 📚 **1. Compartición de Contenido Musical**

#### **🔄 Entre Profesores (ContentLibrary)**
```python
# music_cards/models.py - Líneas 439-468
class ContentLibrary(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, related_name='owned_libraries')
    collaborators = models.ManyToManyField(User, through='LibraryCollaboration')
    items = models.ManyToManyField(MusicItem, through='LibraryItem')
    is_public = models.BooleanField(default=False)
```

**Funcionalidades:**
- **Bibliotecas compartidas**: Los profesores pueden crear bibliotecas de contenido
- **Colaboración con permisos**: 4 niveles (view, contribute, edit, admin)
- **Bibliotecas públicas**: Contenido accesible para toda la comunidad
- **Organización**: Tags y notas específicas por biblioteca

#### **🎯 Contenido Creado por Estudiantes (StudentContribution)**
```python
# classroom/models.py - Líneas 191-232
class StudentContribution(models.Model):
    student = models.ForeignKey(User, related_name='contributions')
    course = models.ForeignKey(Course, related_name='student_contributions')
    content_object = GenericForeignKey()  # Referencia polimórfica
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('submitted', 'Enviado para revisión'),
        ('approved', 'Aprobado'),
        ('needs_revision', 'Necesita revisión'),
        ('rejected', 'Rechazado'),
    ]
    approved_for_library = models.BooleanField(default=False)
```

**Workflow de Moderación:**
1. **Estudiante crea** contenido (draft)
2. **Envía para revisión** (submitted)
3. **Profesor revisa** y da feedback
4. **Si aprueba**: Puede añadirlo a biblioteca compartida
5. **Flujo bidireccional**: El contenido fluye entre todas las apps

### 🎯 **2. Asignación de Elementos para Grupos Clase**

#### **📅 Gestión de Cursos y Sesiones**
```python
# classroom/models.py - Líneas 9-34
class Course(models.Model):
    teacher = models.ForeignKey(User, related_name='courses_taught')
    students = models.ManyToManyField(User, through='Enrollment')
    academic_year = models.CharField(max_length=20)

# Líneas 57-87
class ClassSession(models.Model):
    course = models.ForeignKey(Course, related_name='class_sessions')
    content_items = models.ManyToManyField('music_cards.MusicItem', 
                                         through='SessionContent')
```

#### **📝 Sistema de Asignaciones**
```python
# classroom/models.py - Líneas 109-138
class Assignment(models.Model):
    class_session = models.ForeignKey(ClassSession, related_name='assignments')
    music_items = models.ManyToManyField('music_cards.MusicItem', 
                                       through='AssignmentItem')
    students = models.ManyToManyField(User, through='StudentAssignment')
    due_date = models.DateTimeField()
    is_mandatory = models.BooleanField(default=True)
```

**Proceso de Asignación:**
1. **Profesor crea sesión de clase** con contenido específico
2. **Define asignaciones** con elementos musicales específicos
3. **Asigna a estudiantes** (individual o grupal)
4. **Seguimiento de progreso** con estados y fechas
5. **Feedback bidireccional** profesor ↔ estudiante

### 🔄 **3. Flujo de Contenido Bidireccional**

#### **Desde Bibliotecas → Asignaciones**
- Los profesores pueden **seleccionar contenido** de sus bibliotecas compartidas
- **Asignar directamente** a sesiones de clase
- **Personalizar instrucciones** por elemento

#### **Desde Estudiantes → Bibliotecas**
- Estudiantes **crean contenido** (tips, transcripciones, ejercicios)
- **Sistema de moderación** con feedback del profesor
- **Contenido aprobado** se puede añadir a bibliotecas compartidas
- **Reutilización** en futuras asignaciones

### 📊 **4. Seguimiento y Evaluación**

#### **Estado de Asignaciones**
```python
# classroom/models.py - Líneas 157-188
class StudentAssignment(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Asignada'),
        ('in_progress', 'En progreso'), 
        ('submitted', 'Entregada'),
        ('reviewed', 'Revisada'),
        ('completed', 'Completada'),
    ]
    teacher_feedback = models.TextField()
    grade = models.DecimalField(max_digits=5, decimal_places=2)
```

#### **Integración con Sistema de Estudio**
- Las **asignaciones se integran** con el sistema de repetición espaciada individual
- Los estudiantes pueden **estudiar contenido asignado** usando el algoritmo Leitner
- **Progreso individual** se combina con **objetivos de clase**

## 🎯 **Casos de Uso Prácticos**

### **👨‍🏫 Para Profesores:**
1. **Crear biblioteca** de ejercicios de técnica
2. **Compartir con colegas** (permisos de colaboración)
3. **Planificar sesión** de clase con contenido específico
4. **Asignar tareas** a grupos de estudiantes
5. **Revisar contribuciones** estudiantiles
6. **Incorporar tips estudiantiles** aprobados a bibliotecas

### **👨‍🎓 Para Estudiantes:**
1. **Recibir asignaciones** específicas del profesor
2. **Estudiar usando repetición espaciada** personal
3. **Crear y compartir** transcripciones, tips, ejercicios
4. **Colaborar** con compañeros a través de contribuciones
5. **Recibir feedback** personalizado del profesor

## 🏗️ **Arquitectura Técnica**

- **Referencias polimórficas**: Contenido flexible entre apps
- **Permisos granulares**: 4 niveles de colaboración
- **Workflow de moderación**: Control de calidad del contenido
- **Bidireccionalidad**: Flujo de contenido en todas las direcciones
- **Integración completa**: Asignaciones + Estudio personal + Bibliotecas compartidas

**Resultado:** Un ecosistema educativo musical completo que permite tanto la gestión formal de clases como la colaboración orgánica entre estudiantes y profesores.