# Guía de Despliegue: Refactor Multi-Grupo/Multi-Asignatura

## 📋 Resumen del cambio

Este refactor actualiza el sistema para permitir que un usuario esté matriculado en **múltiples grupos** (multi-asignatura), en lugar de estar limitado a un solo grupo.

### Cambios principales

- **Nuevo modelo**: `Enrollment` (relación many-to-many User ↔ Group)
- **Modelo deprecado**: `Student` sigue existiendo para compatibilidad, pero ya no se usa en el código
- **Vista actualizada**: Todas las vistas ahora usan `Enrollment` en lugar de `student_profile.group`
- **Invitaciones**: Ahora permiten unirse a múltiples grupos sin conflicto

### Base de datos

- **Nueva tabla**: `clases_enrollment`
- **Tablas preservadas**: `evaluations_student` (no se modifica ni elimina, por compatibilidad)
- **Migración de datos**: Copia automática de `Student` → `Enrollment`

---

## 🚀 Despliegue en Local (desarrollo)

### 1. Verificar cambios en Git

```bash
git status
git diff
```

### 2. Ejecutar migraciones

```bash
just migrate
```

Las migraciones harán lo siguiente:

- **0006**: Crea modelo `Enrollment` y marca `Student` como deprecado
- **0007**: Copia todos los `Student` existentes → `Enrollment` (migración de datos)

### 3. Verificar en el admin

Ir a `/admin/clases/enrollment/` y verificar que:

- Todos los estudiantes aparecen con sus grupos correspondientes
- El campo `is_active` está en `True` para todos

### 4. Probar funcionalidades

- Login como estudiante y verificar que ve las sesiones de su(s) grupo(s)
- Probar enlace de invitación nuevo (debe permitir unirse a múltiples grupos)
- Verificar que los menús "Mi librería" y "Sesiones" aparecen correctamente

---

## 📦 Despliegue en Stage

### Pre-requisitos

- Tener acceso SSH configurado: `$SSH_MARTINA_USER_AND_IP`
- Variables de entorno `.envs/.production/.django` y `.envs/.production/.postgres` actualizadas

### 1. Hacer backup de la base de datos ANTES de desplegar

**⚠️ CRÍTICO: Hacer backup antes de cualquier cambio en producción**

```bash
just stage-backup-db
```

Verificar que el backup se ha creado:

```bash
just stage-list-backups
```

Opcional: descargar el backup localmente para mayor seguridad:

```bash
just stage-download-backup postgres <nombre_del_archivo_backup.sql.gz>
```

### 2. Commit y push de cambios

```bash
git add .
git commit -m "feat: multi-grupo/multi-asignatura refactor con Enrollment"
git push origin main
```

### 3. Desplegar a stage

```bash
just deploy-stage
```

Este comando:

- Copia archivos `.envs/.production/` al servidor
- Hace git pull en el servidor
- Reconstruye las imágenes Docker
- Reinicia los contenedores
- Aplica migraciones automáticamente (incluidas 0006 y 0007)

### 4. Verificar migraciones en stage

```bash
just stage-manage showmigrations clases
```

Debe mostrar:

```
[X] 0006_alter_student_options_alter_student_group_enrollment
[X] 0007_migrate_students_to_enrollments
```

### 5. Verificar datos migrados

```bash
just stage-manage shell
```

Dentro del shell de Django:

```python
from clases.models import Student, Enrollment

# Ver cuántos Students hay
print(f"Students: {Student.objects.count()}")

# Ver cuántos Enrollments se han creado
print(f"Enrollments: {Enrollment.objects.count()}")

# Verificar que todos los Students tienen su Enrollment
for student in Student.objects.all():
    enrollment = Enrollment.objects.filter(user=student.user, group=student.group).first()
    if not enrollment:
        print(f"⚠️ FALTA ENROLLMENT para {student}")
    else:
        print(f"✓ {student} → {enrollment}")
```

### 6. Probar en stage

- Acceder a la URL de stage
- Login como estudiante
- Verificar sesiones y bibliotecas
- Probar enlace de invitación a un segundo grupo

### 7. Si algo sale mal: rollback

Si detectas un problema **ANTES** de que los usuarios generen nuevos datos:

```bash
# Restaurar backup de BD
just stage-restore-db <nombre_del_archivo_backup.sql.gz>

# Hacer rollback de código (volver al commit anterior)
just stage-manage "cd ~/app-martina-stage && git reset --hard HEAD~1"
just deploy-stage
```

---

## 🏭 Despliegue en Production

**⚠️ IMPORTANTE: Desplegar primero en stage y verificar durante al menos 24-48 horas antes de ir a production**

### 1. Backup de production

```bash
just production-backup-full
```

Espera confirmación y verifica:

```bash
just production-list-backups
```

**Descargar backup localmente (muy recomendado):**

```bash
just production-download-backup postgres <nombre_backup.sql.gz>
just production-download-backup media <nombre_backup_media.tar.gz>
```

### 2. Notificar a usuarios

⏰ **Recomendado**: Hacer el despliegue en horario de bajo uso (noche/fin de semana)

Notificar a profesores/administradores:

> "El sistema estará en mantenimiento durante 15-30 minutos para una actualización. Se añade soporte multi-asignatura para estudiantes."

### 3. Activar modo mantenimiento (opcional)

Si tienes un template de mantenimiento, activarlo temporalmente.

### 4. Desplegar a production

```bash
just deploy-production
```

### 5. Verificar migraciones en production

```bash
just production-manage showmigrations clases
```

### 6. Verificar datos en production

```bash
just production-manage shell
```

```python
from clases.models import Student, Enrollment

# Verificación rápida
students_count = Student.objects.count()
enrollments_count = Enrollment.objects.count()

print(f"Students: {students_count}")
print(f"Enrollments: {enrollments_count}")
print(f"Ratio: {enrollments_count / students_count if students_count > 0 else 0:.2f} (debe ser ~1.0)")

# Si el ratio no es 1.0, investigar diferencias
if enrollments_count != students_count:
    print("⚠️ Diferencias detectadas, investigar...")
    for student in Student.objects.filter(user__isnull=False):
        if not Enrollment.objects.filter(user=student.user, group=student.group).exists():
            print(f"⚠️ FALTA: {student}")
```

### 7. Smoke tests en production

- Login como profesor → verificar sesiones
- Login como estudiante → verificar sesiones de grupo
- Crear nuevo enlace de invitación → compartir y probar
- Verificar que estudiante puede unirse a segundo grupo sin error

### 8. Monitorear logs

```bash
just logs django
```

Buscar errores relacionados con `Enrollment`, `student_profile`, o `group`.

### 9. Si hay problemas CRÍTICOS: rollback

**Solo si hay errores graves que impidan el uso del sistema:**

```bash
# 1. Restaurar BD
just production-restore-db <nombre_backup.sql.gz>

# 2. Rollback de código
ssh $SSH_MARTINA_USER_AND_IP "cd ~/app-martina-production && git reset --hard HEAD~1 && docker compose -f docker-compose.production.yml down && docker compose -f docker-compose.production.yml up -d"

# 3. Verificar
just logs django
```

---

## ✅ Checklist de Verificación Post-Despliegue

### Funcionalidades que deben seguir funcionando

- [ ] Login de estudiantes y profesores
- [ ] Ver lista de sesiones de clase
- [ ] Ver detalle de sesión
- [ ] Biblioteca personal del estudiante
- [ ] Biblioteca de grupo (profesor)
- [ ] Crear nueva sesión (profesor)
- [ ] Añadir items a sesión (profesor)

### Nuevas funcionalidades

- [ ] Estudiante puede unirse a múltiples grupos mediante invitaciones
- [ ] Estudiante ve sesiones de **todos** sus grupos en `/clases/sessions/`
- [ ] Admin muestra `Enrollment` en `/admin/clases/enrollment/`
- [ ] Crear invitación y compartir enlace funciona correctamente
- [ ] Al clicar invitación, usuario se une sin error de "otro grupo"

### Compatibilidad hacia atrás

- [ ] Modelo `Student` sigue existiendo (no se ha eliminado)
- [ ] Tabla `evaluations_student` no se ha modificado
- [ ] Sistema de evaluaciones no se ha roto

---

## 🔍 Troubleshooting

### Problema: "No tienes permiso para ver esta sesión"

**Causa**: Falta `Enrollment` activo para el usuario en ese grupo.

**Solución**:

```python
from clases.models import Enrollment
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email="alumno@example.com")

# Ver enrollments del usuario
print(user.enrollments.all())

# Verificar si están activos
print(user.enrollments.filter(is_active=True))

# Si falta, crear manualmente
from clases.models import Group
group = Group.objects.get(pk=X)
Enrollment.objects.create(user=user, group=group, is_active=True)
```

### Problema: Menús "Mi librería" / "Sesiones" no aparecen

**Causa**: Template verifica `user.enrollments.exists` pero no hay enrollments activos.

**Solución**: Verificar que el usuario tiene al menos un `Enrollment` con `is_active=True`.

### Problema: Estudiante antiguo no migrado

**Causa**: El `Student` no tenía `user` asociado.

**Solución**:

```python
from clases.models import Student, Enrollment

# Buscar Students sin Enrollment
for student in Student.objects.filter(user__isnull=False):
    if not Enrollment.objects.filter(user=student.user, group=student.group).exists():
        print(f"Creando Enrollment para {student}")
        Enrollment.objects.create(user=student.user, group=student.group, is_active=True)
```

---

## 📊 Monitoreo Post-Despliegue

### Primeras 24 horas

- Revisar logs cada 2-4 horas
- Preguntar a profesores si notan algún problema
- Verificar que estudiantes pueden acceder a sus sesiones

### Primera semana

- Monitorear número de `Enrollments` creados (debe crecer si hay invitaciones activas)
- Verificar que no hay errores 500 relacionados con `group` o `enrollment`

### Siguientes pasos (futuro)

Una vez verificado que todo funciona correctamente (1-2 meses):

- [ ] **Opcional**: Eliminar modelo `Student` y migrar nombre de tabla `evaluations_student` a `clases_student`
- [ ] **Opcional**: Renombrar resto de tablas `evaluations_*` → `clases_*`

---

## 🆘 Contacto de Emergencia

Si hay un problema crítico en production:

1. **Rollback inmediato** (ver sección anterior)
2. Crear issue en GitHub con logs y descripción
3. Notificar a usuarios que se ha revertido temporalmente

---

## ✨ Beneficios del Cambio

- ✅ Estudiantes pueden estar en múltiples asignaturas simultáneamente
- ✅ Invitaciones funcionan sin conflicto de "ya en otro grupo"
- ✅ Preparado para sistema multi-asignatura completo
- ✅ Sin pérdida de datos (Student se preserva)
- ✅ Migración reversible con backups

---

**Última actualización**: 11 de diciembre de 2025
