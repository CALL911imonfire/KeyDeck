# KeyDeck

A customizable on-screen keyboard for Windows that types into any program.

The standard Windows on-screen keyboard only lets you hold Shift, Ctrl and Alt.
KeyDeck lets you hold **any** key, which is handy for games where you hold a key
(like `A`) and click to do something many times.

## Features

- **Types into any program.** It never steals focus, so keystrokes go to whatever you were using.
- **Hold any key.** Right-click a key to hold it, right-click again to release. The **Hold** toolbar button makes every left-click toggle a hold. **Release all** lets go of everything.
- **Full key set.** F1-F24, navigation cluster, arrows, numpad and media keys.
- **Edit layout.** Drag keys to move them, drag a corner to resize, change what a key sends, its label and colors, and add, duplicate or delete keys.
- **Loadouts.** Save and switch between as many layouts as you like (stored as JSON in `%APPDATA%\KeyDeck\loadouts`).
- **Predictive text.** A suggestion bar offers word completions and next-word guesses, and learns your words and phrases as you type. Everything stays on your computer.
- **Resizable interface.** Tiny to extra large, or a custom size. Buttons and the suggestion bar scale with the keys.
- **Scan-code input** (on by default) for games that ignore ordinary key events.

## Run it

Requires Windows and Python 3 (no extra packages).

```
python keydeck.py
```

## Build an .exe

```
python -m pip install pyinstaller
python -m PyInstaller --noconsole --onefile --name KeyDeck keydeck.py
```

The executable is created at `dist\KeyDeck.exe`.

## Notes

- Windows blocks injected input into programs running as administrator unless KeyDeck is also run as administrator.
- Key codes assume a US keyboard layout.
- Settings, loadouts and learned words are saved in `%APPDATA%\KeyDeck`.
- Predictive text only learns from what you type on KeyDeck, not your physical keyboard. Held letter keys (as in games) are never learned.
