"use strict";

// Core content and links work without JavaScript. Clipboard is a progressive enhancement.
document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copy);
    const status = document.getElementById("copy-status");
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target.textContent.trim());
      const label = button.textContent;
      button.textContent = "Copied!";
      status.textContent = "Commands copied to clipboard.";
      button.disabled = true;
      window.setTimeout(() => { button.textContent = label; button.disabled = false; }, 1800);
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(target);
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = "Copy was unavailable. The command is selected; use your device's copy shortcut.";
    }
  });
});

if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.querySelectorAll("video").forEach((video) => {
    video.autoplay = false;
    video.pause();
  });
}
