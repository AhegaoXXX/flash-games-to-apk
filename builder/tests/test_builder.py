import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).resolve().parents[1] / 'build_game.py'
spec = importlib.util.spec_from_file_location('build_game', MODULE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.games = self.root / 'games'
        self.game = self.games / '\u0418\u0433\u0440\u0430 \u0441 \u043f\u0440\u043e\u0431\u0435\u043b\u043e\u043c'
        self.game.mkdir(parents=True)

    def swf(self, name):
        file = self.game / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b'FWS\x06test')
        return file

    def config(self, **values):
        (self.game / 'game.json').write_text(json.dumps(values, ensure_ascii=False), encoding='utf-8')

    def load(self):
        return builder.read_game(self.games, self.game.name)

    def test_single_nested_swf_is_selected_and_name_defaults_to_folder(self):
        self.swf('\u0434\u0430\u043d\u043d\u044b\u0435/\u0441\u0442\u0430\u0440\u0442 \u0438\u0433\u0440\u044b.swf')
        game = self.load()
        self.assertEqual(game['main'], '\u0434\u0430\u043d\u043d\u044b\u0435/\u0441\u0442\u0430\u0440\u0442 \u0438\u0433\u0440\u044b.swf')
        self.assertEqual(game['name'], self.game.name)

    def test_multiple_swfs_require_main_and_error_lists_candidates(self):
        self.swf('main.swf')
        self.swf('scene.swf')
        with self.assertRaisesRegex(builder.BuildError, 'main.swf.*scene.swf'):
            self.load()

    def test_config_selects_main_and_preserves_special_characters_in_label(self):
        self.swf('one.swf')
        self.swf('two.swf')
        self.config(main='two.swf', name='\u0418\u0433\u0440\u0430 "A&B" <test>')
        self.assertEqual(self.load()['main'], 'two.swf')
        self.assertEqual(self.load()['name'], '\u0418\u0433\u0440\u0430 "A&B" <test>')

    def test_missing_main_and_parent_escape_are_rejected(self):
        self.swf('one.swf')
        for main in ('missing.swf', '../outside.swf', 'C:/outside.swf'):
            self.config(main=main)
            with self.subTest(main=main), self.assertRaises(builder.BuildError):
                self.load()
        with self.assertRaises(builder.BuildError):
            builder.read_game(self.games, '../escape')

    def test_package_is_stable_case_insensitive_and_distinct(self):
        self.assertEqual(builder.package_id('ExampleGame'), builder.package_id('examplegame'))
        self.assertNotEqual(builder.package_id('ExampleGame'), builder.package_id('OtherGame'))
        self.assertNotEqual(builder.package_id('ExampleGame'), 'local.examplegame')
        self.assertRegex(builder.package_id(self.game.name), r'^local\.flashgame\.g[a-f0-9]{16}$')

    def test_game_files_preserve_structure_and_exclude_only_root_config(self):
        self.swf('main.swf')
        self.config(main='main.swf')
        (self.game / 'images').mkdir()
        (self.game / 'images/a b.png').write_bytes(b'picture')
        (self.game / 'images/game.json').write_bytes(b'nested resource')
        self.assertEqual(set(builder.game_files(self.game)), {'main.swf', 'images/a b.png', 'images/game.json'})

    def test_missing_swf_and_invalid_configuration_have_clear_errors(self):
        with self.assertRaisesRegex(builder.BuildError, 'SWF'):
            self.load()
        self.swf('main.swf')
        for value in ('{broken', '[]', '{"main": 17}', '{"name": ""}'):
            (self.game / 'game.json').write_text(value, encoding='utf-8')
            with self.subTest(value=value), self.assertRaises(builder.BuildError):
                self.load()

    def test_next_version_respects_existing_apk_even_if_state_is_missing(self):
        output = self.root / 'dist/games/ExampleGame'
        output.mkdir(parents=True)
        (output / 'ExampleGame-v1.apk').write_bytes(b'old APK')
        (output / 'ExampleGame-v3.apk').write_bytes(b'newer APK')
        self.assertEqual(builder.next_version(output, 'ExampleGame', {}), 4)
        self.assertEqual(builder.next_version(output, 'ExampleGame', {'version': 8}), 9)

    def test_preservation_guard_rejects_changed_original(self):
        (self.root / 'builder').mkdir()
        (self.root / 'dist/preserved').mkdir(parents=True)
        original = self.root / 'dist/ExampleGame.apk'
        backup = self.root / 'dist/preserved/ExampleGame.apk'
        original.write_bytes(b'original')
        backup.write_bytes(b'original')
        record = {'apk': 'dist/ExampleGame.apk', 'backup': 'dist/preserved/ExampleGame.apk', 'sha256': builder.digest(original)}
        (self.root / 'dist/preserved/builder-preservation.json').write_text(json.dumps(record))
        builder.verify_original(self.root)
        original.write_bytes(b'changed')
        with self.assertRaisesRegex(builder.BuildError, 'Preserved APK'):
            builder.verify_original(self.root)

    def test_packaging_and_verification_detect_missing_or_foreign_resources(self):
        self.swf('main.swf')
        game = self.load()
        assets = self.root / 'assets'
        (assets / 'game').mkdir(parents=True)
        (assets / 'player/ruffle').mkdir(parents=True)
        (assets / 'game/main.swf').write_bytes((self.game / 'main.swf').read_bytes())
        (assets / 'player/index.html').write_text('<html>local</html>')
        (assets / 'player/game-config.js').write_text('window.gameConfig={};')
        (assets / 'player/lifecycle.js').write_text('local lifecycle')
        (assets / 'player/ruffle/ruffle.js').write_text('core.ruffle.abc.js')
        (assets / 'player/ruffle/core.ruffle.abc.js').write_text('core')
        for name in ('a.wasm', 'b.wasm'):
            (assets / 'player/ruffle' / name).write_bytes(b'\x00asmtest')
        resources = self.root / 'resources.apk'
        with zipfile.ZipFile(resources, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'compiled manifest')
        dex = self.root / 'classes.dex'
        dex.write_bytes(b'dex\n035\x00test')
        apk = self.root / 'new.apk'
        builder.package_apk(resources, dex, assets, apk)
        builder.verify_assets(apk, game)
        (self.game / 'main.swf').write_bytes(b'changed source')
        with self.assertRaisesRegex(builder.BuildError, 'differs from source'):
            builder.verify_assets(apk, game)
        (self.game / 'main.swf').write_bytes(b'FWS\x06test')
        with zipfile.ZipFile(apk, 'a') as archive:
            archive.writestr('assets/game/another-game.swf', b'foreign')
        with self.assertRaisesRegex(builder.BuildError, 'resources'):
            builder.verify_assets(apk, game)


if __name__ == '__main__':
    unittest.main()
