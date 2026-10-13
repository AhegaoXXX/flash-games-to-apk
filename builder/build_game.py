"""Offline Android APK builder. Standard library only; SDK/Java supplied locally."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / 'template'
ANDROID_NS = 'http://schemas.android.com/apk/res/android'
KEY_PASSWORD = 'flash-local-build'


class BuildError(Exception):
    pass


def digest(file):
    with Path(file).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def is_link(path):
    return path.is_symlink() or path.is_junction()


def game_files(folder):
    """Return relative asset paths; never traverse links or include builder config."""
    result = {}
    for current, dirs, files in os.walk(folder, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(current) / name
            if is_link(path):
                raise BuildError(f'Links/junctions are not supported in game data: {path}')
            if any(ord(char) < 32 for char in name):
                raise BuildError(f'Unsupported control character in resource name: {path!s}')
        for name in sorted(files):
            path = Path(current) / name
            relative = path.relative_to(folder).as_posix()
            if relative != 'game.json':
                result[relative] = path
    return dict(sorted(result.items()))


def package_id(folder_name):
    identity = hashlib.sha256(folder_name.casefold().encode('utf-8')).hexdigest()[:16]
    return 'local.flashgame.g' + identity


def read_game(games, folder_name):
    if not folder_name or folder_name in ('.', '..') or '/' in folder_name or '\\' in folder_name or PureWindowsPath(folder_name).drive:
        raise BuildError('-Game must be the name of one direct subfolder of games.')
    games = Path(games).resolve()
    folder = games / folder_name
    if not folder.is_dir() or is_link(folder) or folder.resolve().parent != games:
        raise BuildError(f'Game folder not found or outside games: {folder}')
    folder = folder.resolve()
    files = game_files(folder)
    config_file = folder / 'game.json'
    config = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding='utf-8-sig'))
        except (ValueError, OSError) as error:
            raise BuildError(f'Cannot read game.json: {error}') from error
        if not isinstance(config, dict):
            raise BuildError('game.json must contain a JSON object.')
    candidates = sorted(name for name in files if name.lower().endswith('.swf'))
    if not candidates:
        raise BuildError(f'No SWF files found in {folder}.')
    if 'main' in config:
        main = config['main']
        if not isinstance(main, str) or not main:
            raise BuildError('game.json: main must be a nonempty relative SWF path.')
        main = main.replace('\\', '/')
        if PureWindowsPath(main).drive or any(part in ('', '.', '..') for part in main.split('/')):
            raise BuildError('game.json: main must stay inside the game folder.')
        if main not in candidates:
            raise BuildError(f'Configured main SWF not found: {main}')
    elif len(candidates) == 1:
        main = candidates[0]
    else:
        raise BuildError('Several SWF files found. Set "main" in game.json. Candidates: ' + ', '.join(candidates))
    name = config.get('name', folder.name)
    if not isinstance(name, str) or not name.strip() or any(ord(char) < 32 for char in name):
        raise BuildError('game.json: name must be a nonempty string without control characters.')
    with files[main].open('rb') as stream:
        if stream.read(3) not in (b'FWS', b'CWS', b'ZWS'):
            raise BuildError(f'Invalid SWF header: {main}')
    return {'folder': folder, 'slug': folder.name, 'name': name, 'main': main,
            'package': package_id(folder.name), 'files': files}


def next_version(output, slug, state):
    previous = state.get('version', 0)
    if not isinstance(previous, int) or isinstance(previous, bool) or previous < 0:
        raise BuildError('Invalid version in builder/state. Restore the state file from backup.')
    for file in Path(output).glob('*.apk'):
        match = re.fullmatch(re.escape(slug) + r'-v(\d+)\.apk', file.name)
        if match:
            previous = max(previous, int(match[1]))
    if previous >= 2_100_000_000:
        raise BuildError('Android versionCode limit reached.')
    return previous + 1


def verify_original(root):
    record = root / 'dist/preserved/builder-preservation.json'
    if record.exists():
        data = json.loads(record.read_text(encoding='utf-8'))
        for key in ('apk', 'backup'):
            file = root / data[key]
            if not file.is_file() or digest(file) != data['sha256']:
                raise BuildError(f'Preserved APK is missing or changed: {file}')


def run(arguments, capture=False):
    arguments = [str(value) for value in arguments]
    # No shell, including for SDK tools: D8 and apksigner run as Java programs.
    completed = subprocess.run(arguments, capture_output=capture, text=capture,
                               encoding='utf-8' if capture else None, errors='replace' if capture else None)
    if completed.returncode:
        detail = (completed.stdout or '') + (completed.stderr or '') if capture else ''
        raise BuildError(f'{Path(arguments[0]).name} failed (exit {completed.returncode}). {detail}')
    return completed.stdout if capture else None


def preflight(sdk_arg):
    programs = {}
    for command in ('java', 'javac', 'jar', 'keytool', 'node'):
        programs[command] = shutil.which(command)
        if not programs[command]:
            raise BuildError(f'Required tool missing from PATH: {command}. Install Java 17+ / Node.js.')
    sdk = sdk_arg or os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk:
        sdk = str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Android/Sdk')
    sdk = Path(sdk).resolve()
    tools = sdk / 'build-tools/36.0.0'
    programs.update({name: tools / name for name in ('aapt2.exe', 'aapt.exe', 'zipalign.exe')})
    programs['d8.jar'] = tools / 'lib/d8.jar'
    programs['apksigner.jar'] = tools / 'lib/apksigner.jar'
    programs['android.jar'] = sdk / 'platforms/android-34/android.jar'
    for name, file in programs.items():
        if not Path(file).is_file():
            raise BuildError(f'Required SDK component missing: {file}. Install platform 34 and build-tools 36.0.0, or pass -Sdk.')
    if not (TEMPLATE / 'player/ruffle/ruffle.js').is_file():
        raise BuildError('Bundled Ruffle runtime is missing from builder/template/player/ruffle.')
    return programs


def prepare(game, work, version):
    shutil.copytree(TEMPLATE / 'res', work / 'res')
    shutil.copytree(TEMPLATE / 'player', work / 'assets/player')
    for relative, original in game['files'].items():
        target = work / 'assets/game' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    (work / 'assets/player/game-config.js').write_text(
        'window.gameConfig=' + json.dumps({'name': game['name'], 'main': game['main']}, ensure_ascii=True) + ';\n', encoding='utf-8')
    values = work / 'res/values'
    values.mkdir()
    resources = ET.Element('resources')
    ET.SubElement(resources, 'string', {'name': 'app_name', 'formatted': 'false'}).text = '"' + game['name'].replace('\\', '\\\\').replace('"', '\\"') + '"'
    ET.ElementTree(resources).write(values / 'strings.xml', encoding='utf-8', xml_declaration=True)
    ET.register_namespace('android', ANDROID_NS)
    manifest = ET.parse(TEMPLATE / 'AndroidManifest.xml')
    manifest.getroot().set('package', game['package'])
    manifest.getroot().set('{' + ANDROID_NS + '}versionCode', str(version))
    manifest.getroot().set('{' + ANDROID_NS + '}versionName', f'1.{version}')
    manifest.write(work / 'AndroidManifest.xml', encoding='utf-8', xml_declaration=True)


def package_apk(resources, dex, assets, output):
    with zipfile.ZipFile(resources) as source, zipfile.ZipFile(output, 'w') as apk:
        for entry in source.infolist():
            apk.writestr(entry, source.read(entry.filename))
        apk.write(dex, 'classes.dex', compress_type=zipfile.ZIP_DEFLATED)
        for file in sorted(Path(assets).rglob('*')):
            if file.is_file():
                apk.write(file, 'assets/' + file.relative_to(assets).as_posix(), compress_type=zipfile.ZIP_DEFLATED)


def verify_assets(apk_path, game):
    with zipfile.ZipFile(apk_path) as apk:
        names = set(apk.namelist())
        if len(names) != len(apk.namelist()) or apk.testzip() is not None:
            raise BuildError('Corrupt APK or duplicate entries.')
        actual = {name[len('assets/game/'):] for name in names if name.startswith('assets/game/')}
        if actual != set(game['files']):
            raise BuildError('APK game resources do not match selected game; missing or foreign resources.')
        for relative, original in game['files'].items():
            if hashlib.sha256(apk.read('assets/game/' + relative)).hexdigest() != digest(original):
                raise BuildError(f'APK resource differs from source: {relative}')
        for required in ('classes.dex', 'assets/player/index.html', 'assets/player/game-config.js', 'assets/player/lifecycle.js', 'assets/player/ruffle/ruffle.js'):
            if required not in names:
                raise BuildError(f'APK runtime file missing: {required}')
        runtime = apk.read('assets/player/ruffle/ruffle.js').decode('utf-8')
        for name in re.findall(r'core\.ruffle\.[a-f0-9]+\.js', runtime):
            if 'assets/player/ruffle/' + name not in names:
                raise BuildError(f'Ruffle JS core missing: {name}')
        wasm = [name for name in names if name.startswith('assets/player/ruffle/') and name.endswith('.wasm')]
        if len(wasm) != 2 or any(not apk.read(name).startswith(b'\x00asm') for name in wasm):
            raise BuildError('Ruffle WASM cores missing or invalid.')


@contextmanager
def build_lock(state_dir):
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = state_dir / 'build.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise BuildError(f'Another build is running. If a previous build was interrupted, remove {lock} and retry.') from error
    try:
        with os.fdopen(descriptor, 'w') as file:
            file.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def build_game(root, folder_name, sdk_arg=None):
    # Windows pipe encoding may default to cp1252 even when paths contain Cyrillic.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    root = Path(root).resolve()
    game = read_game(root / 'games', folder_name)
    programs = preflight(sdk_arg)
    verify_original(root)
    state_dir = root / 'builder/state'
    with build_lock(state_dir):
        output = root / 'dist/games' / game['slug']
        state_file = state_dir / (game['package'] + '.json')
        try:
            state = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
        except (ValueError, OSError) as error:
            raise BuildError(f'Cannot read version state: {state_file}') from error
        if not isinstance(state, dict):
            raise BuildError(f'Invalid version state: {state_file}')
        version = next_version(output, game['slug'], state)
        key = root / 'builder/signing/flash-local.p12'
        if not key.is_file():
            if list(state_dir.glob('*.json')) or list((root / 'dist/games').glob('**/*.apk')):
                raise BuildError('Signing key missing. Restore builder/signing/flash-local.p12 to preserve update compatibility.')
            key.parent.mkdir(parents=True, exist_ok=True)
            run([programs['keytool'], '-genkeypair', '-keystore', key, '-storetype', 'PKCS12', '-storepass', KEY_PASSWORD,
                 '-keypass', KEY_PASSWORD, '-alias', 'flash', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Flash Local Builder'])
        if state.get('key_sha256') and state['key_sha256'] != digest(key):
            raise BuildError('Signing key changed. Restore the key used for previous versions.')
        build_root = root / 'builder/build'
        build_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='apk-', dir=build_root) as temporary:
            work = Path(temporary).resolve()
            if work.parent != build_root.resolve():
                raise BuildError('Build directory escaped the workspace.')
            print(f"Building {game['name']} / {game['package']} / version {version}", flush=True)
            prepare(game, work, version)
            for directory in ('classes', 'tests', 'dex'):
                (work / directory).mkdir()
            route = TEMPLATE / 'java/local/flashshell/AssetRoute.java'
            run([programs['javac'], '-encoding', 'UTF-8', '-d', work / 'tests', route, HERE / 'tests/AssetRouteTest.java'])
            run([programs['java'], '-cp', work / 'tests', 'local.flashshell.AssetRouteTest'])
            run([programs['node'], '--test', HERE / 'tests/lifecycle.test.cjs', HERE / 'tests/player.test.cjs'])
            run([programs['aapt2.exe'], 'compile', '--dir', work / 'res', '-o', work / 'resources.zip'])
            run([programs['aapt2.exe'], 'link', '-o', work / 'resources.apk', '-I', programs['android.jar'],
                 '--manifest', work / 'AndroidManifest.xml', work / 'resources.zip'])
            sources = sorted((TEMPLATE / 'java').rglob('*.java'))
            run([programs['javac'], '-encoding', 'UTF-8', '--release', '8', '-classpath', programs['android.jar'], '-d', work / 'classes', *sources])
            run([programs['jar'], '--create', '--file', work / 'classes.jar', '-C', work / 'classes', '.'])
            run([programs['java'], '-cp', programs['d8.jar'], 'com.android.tools.r8.D8', '--lib', programs['android.jar'], '--min-api', '28', '--output', work / 'dex', work / 'classes.jar'])
            package_apk(work / 'resources.apk', work / 'dex/classes.dex', work / 'assets', work / 'unsigned.apk')
            run([programs['zipalign.exe'], '-f', '-p', '4', work / 'unsigned.apk', work / 'aligned.apk'])
            run([programs['java'], '-jar', programs['apksigner.jar'], 'sign', '--ks', key, '--ks-key-alias', 'flash', '--ks-pass', 'pass:' + KEY_PASSWORD,
                 '--out', work / 'signed.apk', work / 'aligned.apk'])
            run([programs['java'], '-jar', programs['apksigner.jar'], 'verify', '--verbose', work / 'signed.apk'])
            verify_assets(work / 'signed.apk', game)
            permissions = run([programs['aapt.exe'], 'dump', 'permissions', work / 'signed.apk'], capture=True)
            if 'android.permission.INTERNET' in permissions:
                raise BuildError('Unexpected INTERNET permission in APK.')
            badging = run([programs['aapt.exe'], 'dump', 'badging', work / 'signed.apk'], capture=True)
            if f"name='{game['package']}'" not in badging or f"versionCode='{version}'" not in badging:
                raise BuildError('APK package/version differs from selected game.')
            verify_original(root)
            output.mkdir(parents=True, exist_ok=True)
            apk = output / f"{game['slug']}-v{version}.apk"
            with apk.open('xb') as target, (work / 'signed.apk').open('rb') as source:
                shutil.copyfileobj(source, target)
            sha = digest(apk)
            apk.with_suffix('.apk.sha256').write_text(f'{sha}  {apk.name}\n', encoding='utf-8')
            state_tmp = state_file.with_suffix('.tmp')
            state_tmp.write_text(json.dumps({'version': version, 'package': game['package'], 'key_sha256': digest(key)}, indent=2) + '\n', encoding='utf-8')
            state_tmp.replace(state_file)
            print(f"Verified {len(game['files'])} game files, bundled Ruffle, signature and offline permissions.", flush=True)
            print(f'APK: {apk}\nSHA256: {sha}', flush=True)
            return apk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, help='Direct subfolder name under games')
    parser.add_argument('--sdk', help='Android SDK directory')
    args = parser.parse_args()
    try:
        build_game(HERE.parent, args.game, args.sdk)
    except (BuildError, OSError, ValueError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
