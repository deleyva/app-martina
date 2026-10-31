# Primeros pasos

## Acceso

La aplicación usa **autenticación con Google** (django-allauth). Los profesores necesitan una cuenta con permisos de staff; el alumnado accede con su cuenta de Google del centro.

## Conceptos clave

- **Asignatura (Subject)**: materia que impartes (p. ej. Música 1º ESO).
- **Grupo (Group)**: un grupo-clase concreto (p. ej. "1º ESO A — Música — 2025-2026"). Cada grupo tiene uno o varios profesores.
- **Matrícula (Enrollment)**: relación alumno ↔ grupo. Un alumno puede estar en varios grupos a la vez.
- **Invitaciones**: cada grupo puede generar un enlace de invitación; el alumno que lo abre queda matriculado automáticamente.

## Flujo del profesor, resumido

1. **Publica contenido** en el CMS (artículos con adjuntos, partituras, libros con capítulos). Ver [Contenidos](contenidos.md).
2. **Asigna los libros al grupo** desde la página de libros del grupo, en el orden de la clase. Ver [Bibliotecas](bibliotecas.md#los-libros-del-grupo).
3. **Programa el trimestre** en `/programacion/`: crea un plan por grupo y añade los recursos en orden. Ver [Programaciones](programaciones.md).
4. **Crea sesiones de clase** (a mano en `/clases/sessions/` o con un clic desde el plan) y preséntalas en el aula. Ver [Clases](clases.md).
5. **Finaliza cada clase con una reflexión** de texto o voz: te servirá para retomar el hilo y ajustar el plan.

## Invitar a un grupo

En la gestión de grupos puedes generar un enlace de invitación y compartirlo. El enlace exige inicio de sesión y matricula al alumno en el grupo al abrirlo.
