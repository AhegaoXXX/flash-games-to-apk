let player;
window.flashGetPlayer = () => player;
window.flashReady = (async () => {
  const status = document.getElementById("status");
  status.textContent = "Loading “" + window.gameConfig.name + "”…";
  try {
    player = window.RufflePlayer.newest().createPlayer();
    document.body.prepend(player);
    const encoded = window.gameConfig.main.split("/").map(encodeURIComponent).join("/");
    const swf = new URL("../game/" + encoded, location.href);
    await player.ruffle().load({url: swf.href, base: new URL("./", swf).href, upgradeToHttps: false});
    status.hidden = true;
    console.info("FLASH_GAME_LOADED");
  } catch (error) {
    status.textContent = "Could not start the game: " + String(error);
    console.error(error);
  }
})();
