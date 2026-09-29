// El clip de cada celda. Es el de `notas`, con un quinto elemento: grabar vídeo.

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Camera, FileText, MessageSquare, Mic, Paperclip, Square, Upload, Video, X,
} from 'lucide-react';
import EditorFoto from './EditorFoto.jsx';
import Galeria from './Galeria.jsx';

// El servidor no acepta más de 50 MB. A este ritmo son unos dos minutos y
// medio de vídeo; la grabación se para sola un poco antes, en vez de perderse
// entera al subir.
const BITS_DE_VIDEO = 2_500_000;
const TOPE_DE_VIDEO = 45 * 1024 * 1024;

const elegirTipo = (candidatos) => candidatos.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
const extensionDe = (tipo) => (tipo.includes('mp4') ? 'mp4' : tipo.includes('ogg') ? 'ogg' : 'webm');

export default function BotonEvidencia({ alumno, prueba, items, onUpload, onDelete, onAddComment }) {
  const count = items.length;
  // closed | menu | recording | camera | editing | commenting | video
  const [mode, setMode] = useState('closed');
  const [recordingTime, setRecordingTime] = useState(0);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [grabandoVideo, setGrabandoVideo] = useState(false);
  const [capturedImage, setCapturedImage] = useState(null);
  const [commentText, setCommentText] = useState('');
  const [popoverStyle, setPopoverStyle] = useState({});
  const btnRef = useRef(null);
  const popoverRef = useRef(null);
  const menuRef = useRef(null);
  const fileRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const pesoRef = useRef(0);
  const canceladoRef = useRef(false);
  const timerRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  // Close popover on outside click (only for menu/commenting mode)
  useEffect(() => {
    if (mode !== 'menu' && mode !== 'commenting') return undefined;
    const handler = (e) => {
      if (menuRef.current?.contains(e.target)) return;
      if (popoverRef.current?.contains(e.target)) return;
      setMode('closed');
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [mode]);

  // Cleanup all resources on unmount
  useEffect(() => () => {
    clearInterval(timerRef.current);
    canceladoRef.current = true;
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  const closeAll = () => {
    clearInterval(timerRef.current);
    canceladoRef.current = true;
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraReady(false);
    setGrabandoVideo(false);
    setCapturedImage(null);
    setCommentText('');
    setRecordingTime(0);
    setMode('closed');
  };

  const computePopoverPos = (menuHeight = 240) => {
    const rect = btnRef.current?.getBoundingClientRect();
    if (!rect) return {};
    const openUp = rect.bottom + menuHeight > window.innerHeight;
    return {
      position: 'fixed',
      right: window.innerWidth - rect.right,
      ...(openUp ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 }),
      zIndex: 9999,
    };
  };

  const openMode = (newMode) => {
    setPopoverStyle(computePopoverPos(newMode === 'commenting' ? 160 : 240));
    setMode(newMode);
  };

  const submitComment = async () => {
    const text = commentText.trim();
    if (!text) return;
    await onAddComment(alumno, prueba, text);
    setCommentText('');
    setMode('closed');
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMode('closed');
    await onUpload(alumno, prueba, file, 'archivo');
    e.target.value = '';
  };

  // ── Camera ──
  const abrirCamara = async (modo, restricciones) => {
    setMode(modo);
    setCameraReady(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia(restricciones);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => setCameraReady(true);
      }
    } catch (err) {
      console.error('Camera access denied:', err);
      closeAll();
    }
  };

  const openCamera = () => abrirCamara('camera', {
    video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 960 } },
  });

  const takePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCapturedImage(dataUrl);
    setMode('editing');
  };

  // ── Grabar: lo común al audio y al vídeo ──
  const grabar = (stream, mimeType, tipo, opciones = {}) => {
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType, ...opciones })
      : new MediaRecorder(stream, opciones);
    chunksRef.current = [];
    pesoRef.current = 0;
    canceladoRef.current = false;
    recorder.ondataavailable = (e) => {
      if (e.data.size === 0) return;
      chunksRef.current.push(e.data);
      pesoRef.current += e.data.size;
      if (tipo === 'video' && pesoRef.current > TOPE_DE_VIDEO && recorder.state === 'recording') recorder.stop();
    };
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      clearInterval(timerRef.current);
      setRecordingTime(0);
      setGrabandoVideo(false);
      setMode('closed');
      if (canceladoRef.current) return;
      const real = recorder.mimeType || mimeType || (tipo === 'video' ? 'video/webm' : 'audio/webm');
      const blob = new Blob(chunksRef.current, { type: real });
      const file = new window.File([blob], `grabacion-${Date.now()}.${extensionDe(real)}`, { type: real });
      await onUpload(alumno, prueba, file, tipo);
    };
    mediaRecorderRef.current = recorder;
    recorder.start(1000);
    setRecordingTime(0);
    timerRef.current = setInterval(() => setRecordingTime((t) => t + 1), 1000);
  };

  // ── Audio recording ──
  const startRecording = async () => {
    setMode('recording');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      grabar(stream, elegirTipo(['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']), 'audio');
    } catch (err) {
      console.error('Mic access denied:', err);
      closeAll();
    }
  };

  // ── Vídeo: primero se encuadra, luego se graba ──
  const openVideo = () => abrirCamara('video', {
    video: { facingMode: 'environment', width: { ideal: 1280 } },
    audio: true,
  });

  const startVideo = () => {
    if (!streamRef.current) return;
    setGrabandoVideo(true);
    grabar(
      streamRef.current,
      elegirTipo(['video/webm;codecs=vp9,opus', 'video/webm', 'video/mp4']),
      'video',
      { videoBitsPerSecond: BITS_DE_VIDEO },
    );
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
  };

  const formatTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  const hasEvidence = count > 0;
  const alternar = () => (mode === 'closed' ? openMode('menu') : setMode('closed'));

  return (
    <>
      <div className="relative" ref={menuRef}>
        <button
          ref={btnRef}
          onClick={alternar}
          onContextMenu={(e) => { e.preventDefault(); alternar(); }}
          tabIndex={-1}
          className={`relative flex-shrink-0 w-5 h-5 flex items-center justify-center rounded transition-all ${
            hasEvidence
              ? 'bg-indigo-100 text-indigo-600 hover:bg-indigo-200'
              : 'text-slate-300 hover:text-slate-400 hover:bg-slate-100'
          }`}
          title={hasEvidence ? `${count} evidencia(s)` : 'Anadir evidencia'}
        >
          <Paperclip size={10} strokeWidth={2.5} />
          {hasEvidence && (
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-indigo-600 text-white text-[7px] font-black rounded-full flex items-center justify-center leading-none">
              {count}
            </span>
          )}
        </button>

        <input ref={fileRef} type="file" className="hidden" onChange={handleFileUpload} />
      </div>

      {/* Popover menu — rendered as portal to avoid overflow clipping */}
      {mode === 'menu' && createPortal(
        <div ref={popoverRef} style={popoverStyle} className="bg-white rounded-xl shadow-xl border border-slate-200 p-1 min-w-[140px] animate-in">
          <button
            onClick={() => fileRef.current?.click()}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Upload size={13} className="text-slate-400" />
            Subir archivo
          </button>
          <button
            onClick={openCamera}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Camera size={13} className="text-amber-500" />
            Hacer foto
          </button>
          <button
            onClick={startRecording}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Mic size={13} className="text-red-500" />
            Grabar audio
          </button>
          <button
            onClick={openVideo}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Video size={13} className="text-purple-500" />
            Grabar video
          </button>
          <button
            onClick={() => openMode('commenting')}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <MessageSquare size={13} className="text-indigo-500" />
            Comentario
          </button>
          {hasEvidence && (
            <>
              <div className="border-t border-slate-100 my-0.5" />
              <button
                onClick={() => { setGalleryOpen(true); setMode('closed'); }}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium text-indigo-600 hover:bg-indigo-50 transition-colors"
              >
                <FileText size={13} />
                Ver evidencias ({count})
              </button>
            </>
          )}
        </div>,
        document.body,
      )}

      {/* Comment popover — rendered as portal */}
      {mode === 'commenting' && createPortal(
        <div ref={popoverRef} style={popoverStyle} className="bg-white rounded-xl shadow-xl border border-slate-200 p-2 min-w-[200px] animate-in">
          <textarea
            autoFocus
            className="w-full bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-700 p-2 outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
            rows={3}
            placeholder="Escribe un comentario..."
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitComment(); } }}
          />
          <div className="flex justify-end gap-1 mt-1">
            <button
              onClick={closeAll}
              className="px-2 py-1 text-[10px] font-medium text-slate-500 hover:bg-slate-100 rounded"
            >
              Cancelar
            </button>
            <button
              onClick={submitComment}
              className="px-2 py-1 text-[10px] font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded"
            >
              Guardar
            </button>
          </div>
        </div>,
        document.body,
      )}

      {/* Camera fullscreen modal */}
      {mode === 'camera' && createPortal(
        <div className="fixed inset-0 z-[100] bg-black flex flex-col">
          <canvas ref={canvasRef} className="hidden" />
          <div className="flex-1 relative overflow-hidden">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 w-full h-full object-cover"
            />
            {!cameraReady && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-white/60 text-sm font-medium animate-pulse">Activando camara...</span>
              </div>
            )}
          </div>
          <div className="bg-black/80 backdrop-blur-sm px-6 py-5 flex items-center justify-center gap-6 safe-area-bottom">
            <button
              onClick={closeAll}
              className="w-12 h-12 rounded-full bg-white/10 border-2 border-white/30 flex items-center justify-center text-white hover:bg-white/20 transition-colors"
            >
              <X size={20} />
            </button>
            <button
              onClick={takePhoto}
              disabled={!cameraReady}
              className={`w-16 h-16 rounded-full border-4 border-white flex items-center justify-center transition-all ${
                cameraReady
                  ? 'bg-white hover:bg-white/90 active:scale-90'
                  : 'bg-white/30 border-white/30'
              }`}
            >
              <div className={`w-12 h-12 rounded-full ${cameraReady ? 'bg-white' : 'bg-white/30'}`} />
            </button>
            <div className="w-12 h-12" /> {/* spacer for symmetry */}
          </div>
        </div>,
        document.body,
      )}

      {/* Vídeo: el mismo marco que la cámara */}
      {mode === 'video' && createPortal(
        <div className="fixed inset-0 z-[100] bg-black flex flex-col">
          <div className="flex-1 relative overflow-hidden">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 w-full h-full object-cover"
            />
            {!cameraReady && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-white/60 text-sm font-medium animate-pulse">Activando camara...</span>
              </div>
            )}
            {grabandoVideo && (
              <div className="absolute top-4 left-4 flex items-center gap-3 bg-black/60 backdrop-blur-sm px-4 py-2 rounded-xl">
                <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                <span className="text-sm font-bold text-white">Grabando video</span>
                <span className="text-sm font-mono text-white/90 tabular-nums">{formatTime(recordingTime)}</span>
              </div>
            )}
          </div>
          <div className="bg-black/80 backdrop-blur-sm px-6 py-5 flex items-center justify-center gap-6 safe-area-bottom">
            <button
              onClick={closeAll}
              className="w-12 h-12 rounded-full bg-white/10 border-2 border-white/30 flex items-center justify-center text-white hover:bg-white/20 transition-colors"
            >
              <X size={20} />
            </button>
            {grabandoVideo ? (
              <button
                onClick={stopRecording}
                className="px-6 py-2.5 bg-red-600 text-white rounded-xl text-sm font-bold hover:bg-red-700 transition-colors flex items-center gap-2"
              >
                <Square size={14} fill="white" />
                Detener y guardar
              </button>
            ) : (
              <button
                onClick={startVideo}
                disabled={!cameraReady}
                className={`w-16 h-16 rounded-full border-4 border-white flex items-center justify-center transition-all ${
                  cameraReady ? 'hover:bg-white/10 active:scale-90' : 'border-white/30'
                }`}
                title="Empezar a grabar"
              >
                <div className={`w-12 h-12 rounded-full ${cameraReady ? 'bg-red-600' : 'bg-red-600/30'}`} />
              </button>
            )}
            <div className="w-12 h-12" /> {/* spacer for symmetry */}
          </div>
        </div>,
        document.body,
      )}

      {/* Photo editor modal */}
      {mode === 'editing' && capturedImage && createPortal(
        <EditorFoto
          imageDataUrl={capturedImage}
          onAccept={async (file) => {
            setCapturedImage(null);
            setMode('closed');
            await onUpload(alumno, prueba, file, 'foto');
          }}
          onRetake={() => {
            setCapturedImage(null);
            openCamera();
          }}
        />,
        document.body,
      )}

      {/* Recording fullscreen overlay */}
      {mode === 'recording' && createPortal(
        <div className="fixed inset-0 z-[100] bg-slate-900/95 backdrop-blur-sm flex items-center justify-center">
          <div className="flex flex-col items-center gap-6">
            <div className="flex items-center gap-3">
              <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
              <span className="text-lg font-bold text-white">Grabando audio</span>
            </div>
            <span className="text-4xl font-mono text-white/90 tabular-nums">{formatTime(recordingTime)}</span>
            {/* Waveform */}
            <div className="flex items-center gap-[3px] h-12">
              {Array.from({ length: 24 }).map((_, i) => (
                <div
                  key={i}
                  className="w-1 bg-red-400 rounded-full origin-center"
                  style={{
                    height: '32px',
                    animation: `wave-bar 0.6s ease-in-out ${i * 0.06}s infinite alternate`,
                  }}
                />
              ))}
            </div>
            <div className="flex items-center gap-4 mt-2">
              <button
                onClick={closeAll}
                className="px-5 py-2.5 bg-white/10 text-white rounded-xl text-sm font-bold hover:bg-white/20 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={stopRecording}
                className="px-6 py-2.5 bg-red-600 text-white rounded-xl text-sm font-bold hover:bg-red-700 transition-colors flex items-center gap-2"
              >
                <Square size={14} fill="white" />
                Detener y guardar
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* Gallery modal */}
      {galleryOpen && createPortal(
        <Galeria
          items={items}
          onClose={() => setGalleryOpen(false)}
          onDelete={onDelete}
          onAdd={() => { setGalleryOpen(false); openMode('menu'); }}
        />,
        document.body,
      )}
    </>
  );
}
