WRECKED CARMAGEDDON
by breakVanilla (https://breakvanilla.com, https://github.com/breakvanilla, youtube.com/@BreakVanilla)

Wrecked Carmageddon runs Carmageddon and the Carmageddon Splat Pack on modern Windows and macOS, with new graphics, weapons and destruction. It is built on dethrace, an open-source remake of the Carmageddon engine.

- Full-resolution widescreen graphics, with smoothly upscaled menus and HUD.
- Every texture AI-upscaled 4x (skies 8x).
- Light from fires, explosions, sparks and police cars, and headlights (N).
- Rounded car bodies and wheels, shiny paint and sun shadows.
- Soft smoke and new flames on burning cars.
- See-through water with waves, reflections and splashes. Cars float, then sink.
- A roof minigun (G) and a rocket launcher (F). Rockets leave craters and blow holes in walls.

WHAT YOU NEED

- Your own copy of Carmageddon or the Splat Pack, with its 3dfx files (DATA/PIXELMAP/SMOKE.PIX). Tested with the Max Pack sold on Steam and with its DOS release.
- Windows 10 or 11 (64-bit), or macOS 11 or later.
- A graphics card with OpenGL 4.1.

On a Mac, copy the game files from a PC, or unpack the GOG installer with innoextract (brew install innoextract).

Music plays from MUSIC/Track02.ogg, Track03.ogg and so on in the game folder. The Steam and GOG releases have them; from a CD, rip its audio tracks to these files.

INSTALL

Each game is a folder with a DATA folder in it; for the Splat Pack, repeat the steps in its folder. In the Steam version these are CARMA and CARSPLAT in steamapps\common\Carmageddon1 (in Steam: right-click the game, Manage, Browse local files).

Windows:
1. If the game isn't from Steam and is in Program Files, copy its folder elsewhere first, for example C:\Games, or it can't save there.
2. Copy "Wrecked Carmageddon.exe", SDL2.dll and the wrecked-carmageddon folder into the game folder, next to DATA.
3. Double-click "Wrecked Carmageddon.exe".
4. Windows can show "Windows protected your PC". If it does, click "More info", then "Run anyway".

Mac:
1. Copy "Wrecked Carmageddon.app" and the wrecked-carmageddon folder into the game folder, next to DATA.
2. Double-click "Wrecked Carmageddon.app".
3. The first time, macOS says it can't check the app, because the app isn't signed by an Apple developer. If it does, click "Done". Open System Settings, then Privacy & Security, and scroll down. Click "Open Anyway" next to Wrecked Carmageddon, then confirm.
4. If the game folder is in Downloads, Documents or Desktop, click "Allow" when macOS asks. If the game still can't find its files, move the game folder elsewhere, for example to your home folder.

If the game crashes or doesn't start, send wrecked-carmageddon/dethrace.log with your report at https://github.com/breakvanilla/carmageddon-wrecked/issues.

KEYS

The game's own keys work as before. The mod adds:

  G               roof minigun: up or away
  F               fire a rocket (hold for a salvo)
  N               headlights on or off

SETTINGS

Edit wrecked-carmageddon/dethrace.ini in a text editor and restart the game. For example, GameCompleted=1 opens every race, car and upgrade, and Windowed=1 plays in a window.

REMOVE THE MOD

Delete the files you copied. The mod doesn't change the game's own files; the game keeps saving its options and saved games in DATA, as before.

LICENCES AND SOURCE

Wrecked Carmageddon is a modified dethrace (https://github.com/dethrace-labs/dethrace) and, like it, free software under the GNU GPL version 3. It also uses BRender (MIT), SDL2 (zlib), miniaudio, inih, libsmacker (LGPL 2.1) and stb_image. Their licences are in wrecked-carmageddon/LICENSES, and the source of the changes is in wrecked-carmageddon/SOURCE.

The mod has no files from the original game; its HD textures are upscaled from the game's own. Carmageddon belongs to its owners.
