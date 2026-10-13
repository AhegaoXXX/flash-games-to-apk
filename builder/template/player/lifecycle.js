// Ruffle flushes SharedObjects on pagehide; Android backgrounding needs an explicit event.
window.flashSave = () => window.dispatchEvent(new PageTransitionEvent("pagehide", {persisted: true}));
window.flashPause = () => {
  window.flashSave();
  const player = window.flashGetPlayer();
  if (player) player.ruffle().pause();
};
window.flashResume = () => {
  const player = window.flashGetPlayer();
  if (player) player.ruffle().play();
};
setInterval(window.flashSave, 5000);
