# Flash game to APK

A Windows command-line builder that packages a Flash game as an offline Android
app using bundled Ruffle 0.7.1. Each game folder becomes a separate app.
Ruffle is included in every APK; no separate download or installation is needed
on the phone.

## Requirements

- Windows with Python 3.12+, Java 17+, and Node.js supporting `node --test`.
- Android SDK platform 34 and build-tools 36.0.0.
- An Android 9+ phone with Android System WebView.

Java and Node.js must be on PATH. Set `ANDROID_HOME` or `ANDROID_SDK_ROOT`,
or install the SDK in `%LOCALAPPDATA%/Android/Sdk`. Keep the builder and SDK
paths free of Cyrillic characters; game and resource names may contain them.

## Build a game

1. Create `games/ExampleGame` and copy in the SWF and all its resources,
   keeping their folder structure and filenames.
2. Open PowerShell in the repository folder and run:

   ```powershell
   .\build-game.ps1 -Game ExampleGame
   ```

3. Transfer the APK from `dist/games/ExampleGame/ExampleGame-v1.apk` to your
   phone and install it. Later builds create `-v2.apk`, `-v3.apk`, and so on.

`ExampleGame` is a placeholder folder name. Quote names containing spaces.
To use another SDK location, add `-Sdk "C:\Android\Sdk"`.

If there is one SWF, it is selected automatically. If there are several,
add `game.json` in the game folder:

```json
{
  "name": "App display name",
  "main": "data/start.swf"
}
```

`main` is relative to the game folder. `name` is optional. All game files except
this root configuration are included in the APK. Links and junctions are unsupported.

## Compatible games

Best suited to offline SWF games controlled by clicks and dragging, such as
puzzles, card games, point-and-click adventures, and dress-up games.

- The SWF must work with the bundled Ruffle version. ActionScript 1/2 and 3
  compatibility depends on the features used; see [Ruffle compatibility](https://ruffle.rs/compatibility).
  That page describes current Ruffle, which may differ from bundled 0.7.1.
- All required resources must load locally. Internet access is blocked, so
  multiplayer, server login, and remote downloads cannot work.
- There are no on-screen keyboard controls or key remapping. Games requiring
  WASD, arrow keys, hover, or right-click need separate control checks.
- JavaScript integration is disabled; the original host page and FlashVars
  are not supplied. Games depending on them need adaptation.
- EXE, Adobe AIR, HTML5, and Unity games are unsupported.

Apps use landscape orientation and keep the game's aspect ratio. Test gameplay,
resources, sound, controls, and saves on your phone, especially for demanding
or 3D games. A successful build does not guarantee playable gameplay.

## Updates and saves

Keep the game folder name and `builder/signing/flash-local.p12` unchanged to
install updates over the existing app. Back up `builder/signing` and
`builder/state`; losing the signing key prevents compatible updates.
The key is intended for personal builds.

Each app stores its own Flash data. Data is flushed periodically and when
leaving the app; restoring progress depends on the game's save logic.
The current scene is not restored automatically.

Game files, APKs, signing keys, and version state are ignored by Git.
Copy them separately when moving the project. Optional local preservation
checks use `dist/preserved/builder-preservation.json`, also ignored by Git.

## Developer checks

```powershell
python -m unittest discover -s builder/tests -p "test_*.py" -v
node --test builder/tests/lifecycle.test.cjs builder/tests/player.test.cjs
```

Set `RUN_APK_INTEGRATION=1` to include real SDK builds in the Python tests.
Ruffle licenses are in `builder/template/player/ruffle/LICENSE_*`.
