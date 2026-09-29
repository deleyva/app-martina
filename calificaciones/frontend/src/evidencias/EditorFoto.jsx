// El editor de la foto: recortar, girar, filtro de escáner y exportar a JPEG.
// Copiado de `notas` sin tocar una línea del componente.

import { useCallback, useEffect, useRef, useState } from 'react';
import { Crop, Maximize, RotateCcw, RotateCw } from 'lucide-react';

export default function EditorFoto({ imageDataUrl, onAccept, onRetake }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const containerRef = useRef(null);
  const [rotation, setRotation] = useState(0);
  const [scanFilter, setScanFilter] = useState(false);
  const [crop, setCrop] = useState(null); // { x, y, w, h } in image-pixel space
  const [dragging, setDragging] = useState(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Load image once
  useEffect(() => {
    const img = new window.Image();
    img.onload = () => {
      imgRef.current = img;
      setCrop({ x: 0, y: 0, w: img.width, h: img.height });
      setImageLoaded(true);
    };
    img.src = imageDataUrl;
  }, [imageDataUrl]);

  // Get display dimensions accounting for rotation
  const getDisplayInfo = useCallback(() => {
    if (!imgRef.current || !containerRef.current) return null;
    const img = imgRef.current;
    const container = containerRef.current;
    const cw = container.clientWidth;
    const ch = container.clientHeight;
    const isRotated = rotation === 90 || rotation === 270;
    const imgW = isRotated ? img.height : img.width;
    const imgH = isRotated ? img.width : img.height;
    const scale = Math.min(cw / imgW, ch / imgH);
    const dispW = imgW * scale;
    const dispH = imgH * scale;
    const offX = (cw - dispW) / 2;
    const offY = (ch - dispH) / 2;
    return { scale, offX, offY, dispW, dispH, imgW, imgH, isRotated };
  }, [rotation]);

  // Convert image-space crop to screen-space
  const cropToScreen = useCallback((c) => {
    const info = getDisplayInfo();
    if (!info || !c) return null;
    const { scale, offX, offY, isRotated } = info;
    const img = imgRef.current;
    let sx, sy, sw, sh;
    if (!isRotated) {
      sx = c.x; sy = c.y; sw = c.w; sh = c.h;
    } else if (rotation === 90) {
      sx = c.y; sy = img.width - c.x - c.w; sw = c.h; sh = c.w;
    } else if (rotation === 180) {
      sx = img.width - c.x - c.w; sy = img.height - c.y - c.h; sw = c.w; sh = c.h;
    } else {
      sx = img.height - c.y - c.h; sy = c.x; sw = c.h; sh = c.w;
    }
    return {
      left: offX + sx * scale,
      top: offY + sy * scale,
      width: sw * scale,
      height: sh * scale,
    };
  }, [getDisplayInfo, rotation]);

  // Convert screen coords to image-space
  const screenToImage = useCallback((sx, sy) => {
    const info = getDisplayInfo();
    if (!info) return { ix: 0, iy: 0 };
    const { scale, offX, offY, isRotated } = info;
    const img = imgRef.current;
    const rx = (sx - offX) / scale;
    const ry = (sy - offY) / scale;
    if (!isRotated) return { ix: rx, iy: ry };
    if (rotation === 90) return { ix: img.width - ry, iy: rx };
    if (rotation === 180) return { ix: img.width - rx, iy: img.height - ry };
    return { ix: ry, iy: img.height - rx };
  }, [getDisplayInfo, rotation]);

  // Draw preview
  useEffect(() => {
    if (!imageLoaded || !canvasRef.current || !containerRef.current) return;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    const ctx = canvas.getContext('2d');
    const img = imgRef.current;
    const cw = container.clientWidth;
    const ch = container.clientHeight;
    canvas.width = cw;
    canvas.height = ch;

    const info = getDisplayInfo();
    if (!info) return;
    const { scale, offX, offY, dispW, dispH } = info;

    ctx.clearRect(0, 0, cw, ch);
    ctx.save();
    ctx.translate(offX + dispW / 2, offY + dispH / 2);
    ctx.rotate((rotation * Math.PI) / 180);
    const drawW = (rotation === 90 || rotation === 270) ? dispH : dispW;
    const drawH = (rotation === 90 || rotation === 270) ? dispW : dispH;
    if (scanFilter) {
      ctx.filter = 'grayscale(1) contrast(2.5) brightness(1.2)';
    }
    ctx.drawImage(img, -drawW / 2, -drawH / 2, drawW, drawH);
    ctx.restore();

    // Dark overlay outside crop
    if (crop) {
      const sc = cropToScreen(crop);
      if (sc) {
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        // Top
        ctx.fillRect(0, 0, cw, sc.top);
        // Bottom
        ctx.fillRect(0, sc.top + sc.height, cw, ch - sc.top - sc.height);
        // Left
        ctx.fillRect(0, sc.top, sc.left, sc.height);
        // Right
        ctx.fillRect(sc.left + sc.width, sc.top, cw - sc.left - sc.width, sc.height);

        // Crop border
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.strokeRect(sc.left, sc.top, sc.width, sc.height);

        // Rule of thirds
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.lineWidth = 1;
        for (let i = 1; i <= 2; i++) {
          ctx.beginPath();
          ctx.moveTo(sc.left + (sc.width * i) / 3, sc.top);
          ctx.lineTo(sc.left + (sc.width * i) / 3, sc.top + sc.height);
          ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(sc.left, sc.top + (sc.height * i) / 3);
          ctx.lineTo(sc.left + sc.width, sc.top + (sc.height * i) / 3);
          ctx.stroke();
        }

        // Draw handles
        const handles = getHandles(sc);
        ctx.fillStyle = 'white';
        handles.forEach(h => {
          ctx.beginPath();
          ctx.arc(h.x, h.y, 6, 0, Math.PI * 2);
          ctx.fill();
        });
      }
    }
  }, [imageLoaded, rotation, scanFilter, crop, getDisplayInfo, cropToScreen]);

  const getHandles = (sc) => {
    if (!sc) return [];
    const { left: l, top: t, width: w, height: h } = sc;
    return [
      { id: 'tl', x: l, y: t },
      { id: 'tr', x: l + w, y: t },
      { id: 'bl', x: l, y: t + h },
      { id: 'br', x: l + w, y: t + h },
      { id: 'tm', x: l + w / 2, y: t },
      { id: 'bm', x: l + w / 2, y: t + h },
      { id: 'ml', x: l, y: t + h / 2 },
      { id: 'mr', x: l + w, y: t + h / 2 },
    ];
  };

  const handlePointerDown = (e) => {
    if (!crop) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const sc = cropToScreen(crop);
    if (!sc) return;

    const handles = getHandles(sc);
    const HIT = 22;
    for (const h of handles) {
      if (Math.abs(px - h.x) < HIT && Math.abs(py - h.y) < HIT) {
        e.target.setPointerCapture(e.pointerId);
        setDragging({ handle: h.id, startX: px, startY: py, startCrop: { ...crop } });
        return;
      }
    }
    // Check if inside crop for move
    if (px >= sc.left && px <= sc.left + sc.width && py >= sc.top && py <= sc.top + sc.height) {
      e.target.setPointerCapture(e.pointerId);
      setDragging({ handle: 'move', startX: px, startY: py, startCrop: { ...crop } });
    }
  };

  const handlePointerMove = (e) => {
    if (!dragging || !imgRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const dx = px - dragging.startX;
    const dy = py - dragging.startY;
    const info = getDisplayInfo();
    if (!info) return;
    const { scale } = info;
    const img = imgRef.current;
    const sc = dragging.startCrop;
    const MIN = 30;

    // Convert screen delta to image delta
    const isRotated = rotation === 90 || rotation === 270;
    let idx, idy;
    if (rotation === 0) { idx = dx / scale; idy = dy / scale; }
    else if (rotation === 90) { idx = -dy / scale; idy = dx / scale; }
    else if (rotation === 180) { idx = -dx / scale; idy = -dy / scale; }
    else { idx = dy / scale; idy = -dx / scale; }

    let nx = sc.x, ny = sc.y, nw = sc.w, nh = sc.h;
    const h = dragging.handle;

    if (h === 'move') {
      nx = Math.max(0, Math.min(img.width - sc.w, sc.x + idx));
      ny = Math.max(0, Math.min(img.height - sc.h, sc.y + idy));
    } else {
      if (h.includes('l')) { nx = Math.min(sc.x + sc.w - MIN, sc.x + idx); nw = sc.w - (nx - sc.x); }
      if (h.includes('r')) { nw = Math.max(MIN, sc.w + idx); }
      if (h.includes('t') && h !== 'tr' && h !== 'tl' || h === 'tl' || h === 'tm' || h === 'tr') {
        if (h === 'tm' || h === 'tl' || h === 'tr') { ny = Math.min(sc.y + sc.h - MIN, sc.y + idy); nh = sc.h - (ny - sc.y); }
      }
      if (h === 'bm' || h === 'bl' || h === 'br') { nh = Math.max(MIN, sc.h + idy); }
      // Clamp
      nx = Math.max(0, nx);
      ny = Math.max(0, ny);
      nw = Math.min(nw, img.width - nx);
      nh = Math.min(nh, img.height - ny);
    }
    setCrop({ x: nx, y: ny, w: nw, h: nh });
  };

  const handlePointerUp = () => setDragging(null);

  const rotateRight = () => setRotation((r) => (r + 90) % 360);
  const rotateLeft = () => setRotation((r) => (r + 270) % 360);
  const resetCrop = () => {
    if (imgRef.current) setCrop({ x: 0, y: 0, w: imgRef.current.width, h: imgRef.current.height });
  };

  const processAndExport = async () => {
    if (!imgRef.current || !crop) return;
    setProcessing(true);
    try {
      const img = imgRef.current;
      const offscreen = document.createElement('canvas');
      const ctx = offscreen.getContext('2d');

      // Determine output size after crop + rotation
      const isRotated = rotation === 90 || rotation === 270;
      let outW = crop.w;
      let outH = crop.h;
      if (isRotated) { outW = crop.h; outH = crop.w; }

      // Scale to max 1920px
      const maxDim = 1920;
      let finalScale = 1;
      if (Math.max(outW, outH) > maxDim) {
        finalScale = maxDim / Math.max(outW, outH);
      }
      const fw = Math.round(outW * finalScale);
      const fh = Math.round(outH * finalScale);
      offscreen.width = fw;
      offscreen.height = fh;

      ctx.save();
      ctx.translate(fw / 2, fh / 2);
      ctx.rotate((rotation * Math.PI) / 180);
      const drawW = (isRotated ? fh : fw);
      const drawH = (isRotated ? fw : fh);
      ctx.drawImage(img, crop.x, crop.y, crop.w, crop.h, -drawW / 2, -drawH / 2, drawW, drawH);
      ctx.restore();

      // Apply scan filter (sigmoid threshold for high-contrast B&W)
      if (scanFilter) {
        const imageData = ctx.getImageData(0, 0, fw, fh);
        const d = imageData.data;
        for (let i = 0; i < d.length; i += 4) {
          const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
          const norm = gray / 255;
          const sig = 1 / (1 + Math.exp(-12 * (norm - 0.45)));
          const val = Math.round(sig * 255);
          d[i] = d[i + 1] = d[i + 2] = val;
        }
        ctx.putImageData(imageData, 0, 0);
      }

      const blob = await new Promise(res => offscreen.toBlob(res, 'image/jpeg', 0.80));
      const file = new window.File([blob], `foto-${Date.now()}.jpg`, { type: 'image/jpeg' });
      onAccept(file);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-black flex flex-col" style={{ touchAction: 'none' }}>
      {/* Preview area */}
      <div ref={containerRef} className="flex-1 relative overflow-hidden">
        {imageLoaded ? (
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            style={{ touchAction: 'none' }}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-white/60 text-sm font-medium animate-pulse">Cargando imagen...</span>
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="bg-black/90 backdrop-blur-sm px-4 py-2 flex items-center justify-center gap-3">
        <button onClick={rotateLeft} className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center text-white hover:bg-white/20 transition-colors" title="Rotar izquierda">
          <RotateCcw size={18} />
        </button>
        <button onClick={rotateRight} className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center text-white hover:bg-white/20 transition-colors" title="Rotar derecha">
          <RotateCw size={18} />
        </button>
        <button
          onClick={() => setScanFilter(f => !f)}
          className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${scanFilter ? 'bg-amber-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'}`}
          title="Filtro escaner"
        >
          <Maximize size={18} />
        </button>
        <button onClick={resetCrop} className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center text-white hover:bg-white/20 transition-colors" title="Restablecer recorte">
          <Crop size={18} />
        </button>
      </div>

      {/* Action bar */}
      <div className="bg-black/80 backdrop-blur-sm px-6 py-4 flex items-center justify-center gap-4 safe-area-bottom">
        <button
          onClick={onRetake}
          className="px-5 py-2.5 bg-white/10 text-white rounded-xl text-sm font-bold hover:bg-white/20 transition-colors"
        >
          Repetir
        </button>
        <button
          onClick={processAndExport}
          disabled={processing || !imageLoaded}
          className={`px-6 py-2.5 rounded-xl text-sm font-bold transition-colors flex items-center gap-2 ${
            processing ? 'bg-amber-400 text-black' : 'bg-white text-black hover:bg-white/90'
          }`}
        >
          {processing ? 'Procesando...' : 'Usar foto'}
        </button>
      </div>
    </div>
  );
}

