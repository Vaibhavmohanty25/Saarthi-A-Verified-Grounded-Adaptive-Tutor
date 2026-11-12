export async function generatePdfThumbnail(file: File): Promise<string | undefined> {
  try {
    const { getDocument, GlobalWorkerOptions } = await import("pdfjs-dist");
    GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.js",
      import.meta.url,
    ).toString();
    const task = getDocument({ data: new Uint8Array(await file.arrayBuffer()), isEvalSupported: false });
    try {
      const pdf = await task.promise;
      const page = await pdf.getPage(1);
      const original = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale: Math.min(480 / original.width, 1) });
      const canvas = document.createElement("canvas");
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      const canvasContext = canvas.getContext("2d");
      if (!canvasContext) return;
      await page.render({ canvasContext, viewport }).promise;
      return canvas.toDataURL("image/png");
    } finally {
      await task.destroy();
    }
  } catch {
    // Attachments still work when a PDF preview cannot be generated.
    return undefined;
  }
}
