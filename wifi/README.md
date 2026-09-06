# wifi — altas de dispositivos en la red del centro

El profesorado se identifica con Google, envía la MAC **real** de su dispositivo, y
los administrativos copian de una tacada las que faltan por dar de alta en el software
de la red. Al marcarlas, cada solicitante recibe el correo con la clave.

Estado, criterios y evidencia: sección **Fase 26** de `ISA.md`, en la raíz del repo.

## Puesta en marcha

1. **Variables de entorno** en `.envs/.production/.django`:

   ```
   DJANGO_WIFI_SSID=MARTINABESCOS
   DJANGO_WIFI_PASSWORD=<la clave de la red>
   ```

   La clave **no** tiene valor por defecto en el código: este repositorio es público.
   Sin ella la app funciona, pero no manda ningún correo, y lo avisa en pantalla.

2. **Grupo de administrativos.** En `/admin`, crear el grupo **`Gestión WiFi`** y meter
   en él a quien deba usar `/wifi/gestion/`. Los superusuarios entran siempre.

3. **Excepciones de acceso.** Solo el personal puede solicitar. La regla es que la parte
   local del correo empiece por letra (`eromero`), frente al prefijo numérico de
   promoción del alumnado (`0125eromero`). Se ajusta con `DJANGO_WIFI_PATRON_PERSONAL`,
   y el grupo **`WiFi personal autorizado`** permite autorizar cuentas sueltas a mano.

## Cómo se usa

- `/wifi/` — formulario de alta, tutoriales por sistema operativo y mis dispositivos.
- `/wifi/gestion/` — pendientes de alta, pendientes de baja y activos en la red.

El flujo de gestión es siempre el mismo: **copiar → pegar en el otro programa → marcar**.
Son dos clics a propósito. Marcar actúa sobre los identificadores que se copiaron, nunca
sobre «lo pendiente ahora mismo»: entre copiar y marcar puede entrar una solicitud nueva
que nadie ha pegado en ningún sitio.

## Detalles que conviene saber

- **MACs aleatorias rechazadas.** El bit localmente administrado (bit 1 del primer octeto)
  delata las MACs privadas que generan iOS y Android por red. El formulario las rechaza
  con los pasos para desactivarlas, en vez de que el problema aparezca semanas después.
- **Esto es censo, no seguridad.** Una MAC se falsifica en segundos. Sirve para saber qué
  dispositivos hay y poder cortar uno concreto; no es una barrera de acceso.
- **El correo no se envía dos veces.** Lo garantiza la máquina de estados
  (`pendiente → anadida`), no el sello `notificado_at`, que es solo el registro.

## Tests

```
just test          # toda la suite
docker compose run --rm django pytest wifi/    # solo esta app
```
