const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = () => fs.readFileSync(path.join(__dirname, '../template/player/player.js'), 'utf8');

function setup(main, fail = false) {
  let loaded;
  const status = {hidden: false, textContent: ''};
  const player = {ruffle: () => ({async load(options) {loaded = options; if (fail) throw new Error('missing scene');}})};
  const window = {gameConfig: {name: '<Game & name>', main}, RufflePlayer: {newest: () => ({createPlayer: () => player})}};
  const context = vm.createContext({window, document: {getElementById: () => status, body: {prepend() {}}},
    location: {href: 'https://appassets.androidplatform.net/assets/player/index.html'}, URL,
    console: {info() {}, error() {}}});
  vm.runInContext(source(), context);
  return {window, status, loaded: () => loaded, player};
}

test('nested Unicode and space paths load relative resources from the main SWF directory', async () => {
  const app = setup('\u0434\u0430\u043d\u043d\u044b\u0435/\u0441\u0442\u0430\u0440\u0442 \u0438\u0433\u0440\u044b.swf');
  await app.window.flashReady;
  const expected = 'https://appassets.androidplatform.net/assets/game/' + encodeURIComponent('\u0434\u0430\u043d\u043d\u044b\u0435') + '/';
  assert.equal(app.loaded().url, expected + encodeURIComponent('\u0441\u0442\u0430\u0440\u0442 \u0438\u0433\u0440\u044b.swf'));
  assert.equal(app.loaded().base, expected);
  assert.equal(app.status.hidden, true);
  assert.equal(app.window.flashGetPlayer(), app.player);
});

test('URL punctuation in filenames stays part of the filename', async () => {
  const app = setup('a+b%test#.swf');
  await app.window.flashReady;
  assert.equal(app.loaded().url, 'https://appassets.androidplatform.net/assets/game/a%2Bb%25test%23.swf');
});

test('load failure displays a readable message', async () => {
  const app = setup('main.swf', true);
  await app.window.flashReady;
  assert.equal(app.status.hidden, false);
  assert.match(app.status.textContent, /missing scene/);
});
