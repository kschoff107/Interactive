/**
 * Ref-counted body scroll lock for overlapping modals.
 * Multiple modals can call lockScroll/unlockScroll independently —
 * the body only scrolls again once ALL modals have released their lock.
 */
let openCount = 0;

export function lockScroll() {
  openCount++;
  document.body.style.overflow = 'hidden';
}

export function unlockScroll() {
  openCount = Math.max(0, openCount - 1);
  if (openCount === 0) {
    document.body.style.overflow = 'unset';
  }
}
