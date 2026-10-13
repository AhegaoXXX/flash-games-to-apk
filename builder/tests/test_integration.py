"""Opt-in real SDK builds, using isolated fixture games under builder/build."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('integration_builder', HERE / 'build_game.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def minimal_swf():
    # A valid one-frame SWF: 320x240 stage, 24 fps, solid blue background.
    bits = '01110' + ''.join(format(value, '014b') for value in (0, 6400, 0, 4800))
    bits += '0' * (-len(bits) % 8)
    rectangle = int(bits, 2).to_bytes(len(bits) // 8, 'big')
    body = rectangle + struct.pack('<HH', 24 * 256, 1)
    body += struct.pack('<H', (9 << 6) | 3) + b'\x22\x55\x88'
    body += struct.pack('<HH', 1 << 6, 0)
    return b'FWS\x06' + struct.pack('<I', len(body) + 8) + body


@unittest.skipUnless(os.environ.get('RUN_APK_INTEGRATION') == '1', 'Set RUN_APK_INTEGRATION=1 for real SDK builds')
class IntegrationTests(unittest.TestCase):
    def test_unicode_game_updates_other_game_and_preserved_original(self):
        work_root = HERE / 'build'
        work_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='integration-', dir=work_root) as temporary:
            root = Path(temporary).resolve()
            self.assertEqual(root.parent, work_root.resolve())
            original = root / 'dist/ExampleGame.apk'
            backup = root / 'dist/preserved/ExampleGame.apk'
            backup.parent.mkdir(parents=True)
            original.write_bytes(b'original APK must remain unchanged')
            backup.write_bytes(original.read_bytes())
            (root / 'builder').mkdir()
            (root / 'dist/preserved/builder-preservation.json').write_text(json.dumps({
                'apk': 'dist/ExampleGame.apk', 'backup': 'dist/preserved/ExampleGame.apk', 'sha256': builder.digest(original)
            }))
            game = root / 'games/\u0418\u0433\u0440\u0430 \u0441 \u043f\u0440\u043e\u0431\u0435\u043b\u043e\u043c'
            (game / '\u0434\u0430\u043d\u043d\u044b\u0435').mkdir(parents=True)
            (game / '\u0434\u0430\u043d\u043d\u044b\u0435/\u0441\u0442\u0430\u0440\u0442 \u0438\u0433\u0440\u044b.swf').write_bytes(minimal_swf())
            (game / '\u0434\u0430\u043d\u043d\u044b\u0435/\u0440\u0435\u0441\u0443\u0440\u0441 & \u0442\u0435\u0441\u0442.xml').write_text('<data>nested</data>', encoding='utf-8')
            (game / 'game.json').write_text(json.dumps({'name': '\u0418\u0433\u0440\u0430 "A&B" <\u0422\u0435\u0441\u0442> @new'}, ensure_ascii=False), encoding='utf-8')
            sdk = os.environ.get('ANDROID_HOME')
            first = builder.build_game(root, game.name, sdk)
            first_digest = builder.digest(first)
            second = builder.build_game(root, game.name, sdk)
            self.assertEqual(first.name, game.name + '-v1.apk')
            self.assertEqual(second.name, game.name + '-v2.apk')
            self.assertEqual(builder.digest(first), first_digest)
            programs = builder.preflight(sdk)
            certificates = []
            for number, apk in enumerate((first, second)):
                # This Windows JDK uses the system code page for CLI arguments.
                # The builder signs/verifies in its ASCII staging folder before publishing Unicode output names.
                verification_copy = root / f'verify-{number}.apk'
                shutil.copyfile(apk, verification_copy)
                self.assertEqual(builder.digest(verification_copy), builder.digest(apk))
                result = builder.run([programs['java'], '-jar', programs['apksigner.jar'], 'verify', '--print-certs', verification_copy], capture=True)
                certificates.append(next(line for line in result.splitlines() if 'certificate SHA-256 digest:' in line))
            self.assertEqual(certificates[0], certificates[1])
            other = root / 'games/OtherGame'
            other.mkdir()
            (other / 'only.swf').write_bytes(minimal_swf())
            third = builder.build_game(root, other.name, sdk)
            with zipfile.ZipFile(third) as apk:
                self.assertIn('assets/game/only.swf', apk.namelist())
                self.assertFalse(any('\u0441\u0442\u0430\u0440\u0442 \u0438\u0433\u0440\u044b.swf' in name for name in apk.namelist()))
            builder.verify_original(root)
            state = json.loads(next((root / 'builder/state').glob(builder.package_id(game.name) + '.json')).read_text())
            self.assertEqual(state['version'], 2)
            # A missing signing key must not silently create incompatible updates.
            key = root / 'builder/signing/flash-local.p12'
            key.rename(key.with_suffix('.saved'))
            with self.assertRaisesRegex(builder.BuildError, 'Signing key missing'):
                builder.build_game(root, game.name, sdk)
            self.assertEqual(state, json.loads((root / 'builder/state' / (builder.package_id(game.name) + '.json')).read_text()))
            self.assertFalse((root / 'builder/state/build.lock').exists())


if __name__ == '__main__':
    unittest.main()
