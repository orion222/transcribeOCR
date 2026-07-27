const OK_TYPES = new Set(["image/png", "image/jpeg", "application/pdf"]);
const OK_EXT = /\.(png|jpe?g|pdf)$/i;

export function acceptFile(file) {
  return OK_TYPES.has(file.type) || OK_EXT.test(file.name || "");
}

export function reorder(items, from, to) {
  const next = items.slice();
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}
