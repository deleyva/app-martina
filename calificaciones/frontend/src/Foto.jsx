// La foto de carné junto al nombre. Sin foto, la inicial: la fila no cambia de alto.
export default function Foto({ alumno, className = 'w-8 h-8 rounded-full' }) {
  if (alumno.foto) {
    return (
      <img
        src={alumno.foto}
        alt=""
        loading="lazy"
        className={`${className} object-cover object-top shrink-0 bg-slate-100`}
      />
    );
  }
  return (
    <div className={`${className} shrink-0 bg-slate-100 text-slate-400 flex items-center justify-center font-black`}>
      {alumno.nombre.charAt(0)}
    </div>
  );
}
