import Foundation
import Vision
import AppKit

// OCR de una imagen con el motor Vision de macOS. Uso: ocr <fichero.png>
guard CommandLine.arguments.count > 1 else { FileHandle.standardError.write("uso: ocr <img>\n".data(using:.utf8)!); exit(2) }
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("no se pudo abrir \(path)\n".data(using:.utf8)!); exit(1)
}
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.recognitionLanguages = ["es-ES"]
req.usesLanguageCorrection = false
req.minimumTextHeight = 0.005
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([req])
var out: [String] = []
for obs in (req.results ?? []) {
    guard let top = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox   // origen abajo-izquierda, normalizado
    // y0 medido desde arriba, para poder ordenar y localizar
    let y0 = 1.0 - b.maxY
    out.append(String(format: "%.4f\t%.4f\t%.4f\t%.3f\t%@", y0, b.minX, b.maxX, top.confidence, top.string))
}
print(out.joined(separator: "\n"))
