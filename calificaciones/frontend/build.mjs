// Construye la pantalla de calificaciones en un solo fichero que Django sirve
// como estático.
//
//     cd calificaciones/frontend && bun install && bun run build
//
// **El resultado se confirma en git.** La imagen de producción solo se queda
// con el CSS de su fase de Node; el JavaScript que sirve es el del repo. Por
// eso el paquete lleva en la primera línea la huella del código fuente, y un
// test (`test_el_bundle_esta_y_esta_al_dia`) la recalcula: si alguien cambia
// el JSX y olvida reconstruir, el test falla antes de desplegar.
//
// **Nunca `sourcemap`.** El almacenamiento con manifiesto de Django reescribe
// las líneas `//# sourceMappingURL`; sin el `.map` al lado, `collectstatic`
// falla y el contenedor de producción no arranca.

import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';

const AQUI = dirname(fileURLToPath(import.meta.url));
const SALIDA = join(AQUI, '..', 'static', 'calificaciones', 'registro.js');

function ficheros(dir) {
  return readdirSync(dir)
    .flatMap((nombre) => {
      const ruta = join(dir, nombre);
      return statSync(ruta).isDirectory() ? ficheros(ruta) : [ruta];
    })
    .filter((ruta) => !ruta.endsWith('.test.js'));
}

// La misma cuenta que hace el test en Python: rutas relativas ordenadas, y de
// cada fichero su ruta y su contenido separados por un byte nulo.
export function huella() {
  const hash = createHash('sha256');
  const rutas = [...ficheros(join(AQUI, 'src')), join(AQUI, 'package.json'), join(AQUI, 'build.mjs')]
    .map((ruta) => relative(AQUI, ruta).split(sep).join('/'))
    .sort();
  for (const ruta of rutas) {
    hash.update(ruta);
    hash.update('\0');
    hash.update(readFileSync(join(AQUI, ruta)));
    hash.update('\0');
  }
  return hash.digest('hex');
}

const opciones = {
  entryPoints: [join(AQUI, 'src', 'main.jsx')],
  outfile: SALIDA,
  bundle: true,
  format: 'iife',
  jsx: 'automatic',
  minify: true,
  target: 'es2020',
  legalComments: 'none',
  sourcemap: false,
  // Con `minify` esbuild ya lo define; se dice a la vista para que una
  // construcción sin minificar no meta el React de desarrollo.
  define: { 'process.env.NODE_ENV': '"production"' },
  banner: { js: `/* fuente: ${huella()} */` },
  logLevel: 'info',
};

if (process.argv.includes('--watch')) {
  // En modo vigilancia la huella de la cabecera se queda vieja: antes de
  // confirmar, `bun run build`.
  const contexto = await esbuild.context(opciones);
  await contexto.watch();
} else {
  await esbuild.build(opciones);
}
