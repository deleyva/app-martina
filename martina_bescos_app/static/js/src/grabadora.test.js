import { describe, expect, test } from "bun:test";
import { TIPOS, elegirTipo, extensionDe } from "./grabadora.js";

describe("formato de la grabación", () => {
  test("Chrome: webm con opus; Safari: mp4", () => {
    expect(elegirTipo(TIPOS, (t) => t.startsWith("audio/webm"))).toBe("audio/webm;codecs=opus");
    expect(elegirTipo(TIPOS, (t) => t === "audio/mp4")).toBe("audio/mp4");
    expect(elegirTipo(TIPOS, () => false)).toBe("");
  });

  test("la extensión sale del tipo que dio el navegador", () => {
    expect(extensionDe("audio/mp4")).toBe("m4a");
    expect(extensionDe("audio/webm;codecs=opus")).toBe("webm");
    expect(extensionDe("audio/ogg")).toBe("ogg");
    expect(extensionDe("")).toBe("webm");
  });
});
