// La galería de evidencias de una celda. Es la de `notas`; los ficheros los
// sirve Django, solo al profesorado del grupo.

import { useEffect, useRef, useState } from 'react';
import {
  File, FileAudio, Image, Link as Enlace, MessageSquare, Paperclip, Pause, Play, Trash2, Upload, Video, X,
} from 'lucide-react';

// Las barras del reproductor son decoración; se fijan una vez para que no
// bailen cada vez que se repinta la galería.
const BARRAS = Array.from({ length: 32 }, (_, i) => 2 + Math.sin(i * 0.6) * 8 + ((i * 37) % 7));

export default function Galeria({ items, onClose, onDelete, onAdd }) {
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [playingAudio, setPlayingAudio] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => {
      document.removeEventListener('keydown', handler);
      audioRef.current?.pause();
    };
  }, [onClose]);

  const isComment = (item) => item.tipo === 'texto';
  const isLink = (item) => item.tipo === 'enlace';
  const isImage = (item) => item.tipo === 'foto';
  const isAudio = (item) => item.tipo === 'audio';
  const isVideo = (item) => item.tipo === 'video';
  const isFile = (item) => item.tipo === 'archivo';

  const getIcon = (item) => {
    if (isComment(item)) return MessageSquare;
    if (isLink(item)) return Enlace;
    if (isImage(item)) return Image;
    if (isAudio(item)) return FileAudio;
    if (isVideo(item)) return Video;
    return File;
  };

  const formatDate = (ts) => {
    const d = new Date(ts);
    return `${d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })} ${
      d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`;
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const toggleAudio = (item) => {
    if (playingAudio === item.id) {
      audioRef.current?.pause();
      setPlayingAudio(null);
    } else {
      if (audioRef.current) audioRef.current.pause();
      const audio = new Audio(item.url);
      audio.onended = () => setPlayingAudio(null);
      audioRef.current = audio;
      audio.play();
      setPlayingAudio(item.id);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div
        className="relative bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md max-h-[80vh] flex flex-col animate-in fade-in zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h3 className="text-sm font-black text-slate-800 flex items-center gap-2">
            <Paperclip size={14} className="text-indigo-600" />
            Evidencias ({items.length})
          </h3>
          <div className="flex items-center gap-1">
            <button
              onClick={onAdd}
              className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
              title="Anadir mas"
            >
              <Upload size={14} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {items.length === 0 ? (
            <div className="text-center text-slate-400 text-sm py-8">Sin evidencias</div>
          ) : (
            items.map((item) => {
              const Icon = getIcon(item);
              return (
                <div
                  key={item.id}
                  className="group bg-slate-50 rounded-xl border border-slate-100 overflow-hidden hover:border-slate-200 transition-colors"
                >
                  {/* Comment display */}
                  {isComment(item) && (
                    <div className="px-3 pt-3">
                      <div className="bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 text-[11px] text-slate-700 whitespace-pre-wrap">
                        {item.texto}
                      </div>
                    </div>
                  )}

                  {isLink(item) && (
                    <div className="px-3 pt-3">
                      <a
                        href={item.texto}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 text-[11px] text-indigo-700 underline break-all"
                      >
                        {item.texto}
                      </a>
                    </div>
                  )}

                  {/* Image preview */}
                  {isImage(item) && (
                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                      <img
                        src={item.url}
                        alt={item.nombre}
                        className="w-full h-32 object-cover cursor-pointer hover:opacity-90 transition-opacity"
                      />
                    </a>
                  )}

                  {/* Video preview */}
                  {isVideo(item) && (
                    <div className="px-3 pt-3">
                      <video
                        src={item.url}
                        controls
                        playsInline
                        preload="metadata"
                        className="w-full rounded-lg border border-slate-200 bg-black"
                        style={{ maxHeight: '200px' }}
                      />
                      {item.estado !== 'listo' && (
                        <div className="text-[9px] text-amber-600 font-bold mt-1">
                          {item.estado === 'fallido'
                            ? 'No se ha podido comprimir: se sirve el original'
                            : 'Comprimiendo… en algunos dispositivos no se vera hasta que termine'}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Audio player */}
                  {isAudio(item) && (
                    <div className="px-3 pt-3">
                      <button
                        onClick={() => toggleAudio(item)}
                        className="w-full flex items-center gap-3 bg-white px-3 py-2.5 rounded-lg border border-slate-200"
                      >
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                          playingAudio === item.id ? 'bg-red-100 text-red-600' : 'bg-indigo-100 text-indigo-600'
                        }`}>
                          {playingAudio === item.id ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
                        </div>
                        <div className="flex-1 h-4 flex items-end gap-[1px]">
                          {BARRAS.map((alto, i) => (
                            <div
                              key={i}
                              className={`flex-1 rounded-full transition-all ${
                                playingAudio === item.id ? 'bg-red-300' : 'bg-indigo-200'
                              }`}
                              style={{ height: `${alto}px` }}
                            />
                          ))}
                        </div>
                      </button>
                    </div>
                  )}

                  {/* File info */}
                  <div className="flex items-center gap-2.5 px-3 py-2.5">
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      isComment(item) || isLink(item) ? 'bg-indigo-100 text-indigo-600' :
                      isImage(item) ? 'bg-amber-100 text-amber-600' :
                      isAudio(item) ? 'bg-red-100 text-red-600' :
                      isVideo(item) ? 'bg-purple-100 text-purple-600' :
                      'bg-slate-200 text-slate-500'
                    }`}>
                      <Icon size={13} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] font-medium text-slate-700 truncate">
                        {isComment(item) ? 'Comentario' : isLink(item) ? 'Enlace' : isFile(item) ? (
                          <a href={item.url} className="underline hover:text-indigo-600">{item.nombre}</a>
                        ) : item.nombre}
                      </div>
                      <div className="text-[9px] text-slate-400">
                        {isComment(item) || isLink(item)
                          ? formatDate(item.fecha)
                          : <>{formatSize(item.tamano)} &middot; {formatDate(item.fecha)}</>}
                      </div>
                    </div>
                    {confirmDelete === item.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => { onDelete(item.id); setConfirmDelete(null); }}
                          className="px-2 py-1 bg-red-600 text-white rounded text-[9px] font-bold hover:bg-red-700"
                        >
                          Si
                        </button>
                        <button
                          onClick={() => setConfirmDelete(null)}
                          className="px-2 py-1 bg-slate-200 text-slate-600 rounded text-[9px] font-bold hover:bg-slate-300"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDelete(item.id)}
                        className="opacity-0 group-hover:opacity-100 focus:opacity-100 [@media(pointer:coarse)]:opacity-100 p-1.5 text-slate-300 hover:text-red-500 rounded-lg transition-all"
                        title="Borrar"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
