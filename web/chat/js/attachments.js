// Image attachments: picker, paste, drag-and-drop, downscaling, thumbnails.

import { els } from "./dom.js";
import { state } from "./state.js";
import { toast } from "./toast.js";

const MAX_IMAGE_SIDE = 1600;  // downscale big photos before sending
const MAX_UNSCALED_BYTES = 1.5e6;

/** Read a file as a data URL, shrinking large photos to JPEG. */
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error(`Could not read image ${file.name}`));
      img.onload = () => {
        const scale = Math.min(1, MAX_IMAGE_SIDE / Math.max(img.width, img.height));
        if (scale === 1 && file.size < MAX_UNSCALED_BYTES) return resolve(reader.result);
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#fff";  // transparent PNGs become white, not black
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

export async function addFiles(files) {
  for (const file of files) {
    if (!file.type.startsWith("image/")) continue;
    try { state.pending.push(await fileToDataUrl(file)); } catch (e) { toast(e.message); }
  }
  renderThumbs();
  els.input.focus();
}

export function renderThumbs() {
  els.thumbs.innerHTML = "";
  state.pending.forEach((src, i) => {
    const thumb = document.createElement("div");
    thumb.className = "thumb";
    const img = new Image();
    img.src = src;
    img.alt = "attachment";
    const remove = document.createElement("button");
    remove.textContent = "×";
    remove.title = "Remove";
    remove.onclick = () => { state.pending.splice(i, 1); renderThumbs(); };
    thumb.append(img, remove);
    els.thumbs.appendChild(thumb);
  });
}

export function openFilePicker() {
  els.file.click();
}

export function initAttachments() {
  els.attach.addEventListener("click", openFilePicker);
  els.file.addEventListener("change", () => { addFiles([...els.file.files]); els.file.value = ""; });
  els.input.addEventListener("paste", (e) => {
    const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith("image/"));
    if (files.length) { e.preventDefault(); addFiles(files); }
  });
  for (const ev of ["dragenter", "dragover"]) {
    document.addEventListener(ev, (e) => { e.preventDefault(); els.composer.classList.add("drag"); });
  }
  for (const ev of ["dragleave", "drop"]) {
    document.addEventListener(ev, (e) => { e.preventDefault(); els.composer.classList.remove("drag"); });
  }
  document.addEventListener("drop", (e) => addFiles([...(e.dataTransfer?.files || [])]));
}
