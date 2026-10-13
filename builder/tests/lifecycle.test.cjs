const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('background and periodic saves flush pending Flash state without restarting the player', () => {
  let running = true, pending = 'new settings', saved = null, interval;
  const window = new EventTarget();
  window.flashGetPlayer = () => ({ruffle: () => ({pause() {running = false;}, play() {running = true;}})});
  window.addEventListener('pagehide', () => {saved = pending;});
  const context = vm.createContext({window, PageTransitionEvent: Event, setInterval(fn) {interval = fn;}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../template/player/lifecycle.js'), 'utf8'), context);
  window.flashPause();
  assert.equal(saved, 'new settings');
  assert.equal(running, false);
  window.flashResume();
  assert.equal(running, true);
  pending = 'later settings';
  interval();
  assert.equal(saved, 'later settings');
  window.flashGetPlayer = () => null;
  assert.doesNotThrow(() => {window.flashPause(); window.flashResume();});
});
