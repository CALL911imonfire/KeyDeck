# KeyDeck

**A fully customizable on-screen keyboard that types into any program.**

KeyDeck is built around one idea: your keyboard should be whatever you need it to be. Build the layout you want, save it as a loadout, program each button to send a key or a whole shortcut, and scale the whole thing to a size that suits you. Hold down any key, and let KeyDeck learn the words you use as you type. It never takes focus from the program you're typing into.

<p align="center">
  <img src="screenshots/keyboard.png" alt="The default KeyDeck keyboard" width="760"><br>
  <em>The default KeyDeck layout: main keys, navigation cluster and numpad, plus a predictive text bar.</em>
</p>

## What makes KeyDeck different

| | |
|---|---|
| [Build your own layout](#build-your-own-layout) | Move, resize, recolor, add and delete keys, or start from a blank board |
| [Loadouts](#loadouts) | Save any number of layouts and switch between them in a click |
| [Programmable keys](#programmable-keys) | Set any button to send any key, or a whole shortcut like Ctrl+Shift+Esc |
| [Scalable interface](#scalable-interface) | Everything resizes together, from tiny to extra large, with adjustable opacity |
| [Hold any key](#hold-any-key) | Letters, numbers, F-keys, everything, not just Shift, Ctrl and Alt |
| [Predictive text](#predictive-text) | Suggestions that learn your words and phrases |
| [Types anywhere](#types-anywhere) | Works with games and apps, without stealing focus |

---

## Build your own layout

The layout is not fixed. Switch on **Edit layout** and shape the keyboard however you like.

- **Move** keys by dragging them. They snap to a grid so everything stays tidy.
- **Resize** a key by dragging its bottom-right corner, or type exact width and height values.
- **Recolor** each key and its text individually, or reset it to the default.
- **Add** new keys, **duplicate** existing ones, and **delete** the ones you don't need.
- **Clear all** empties the board, and **Blank layout** in the Loadouts menu starts a new one from scratch.

Start from the full default keyboard (main keys, navigation cluster and numpad) and rearrange it, strip it down to a handful of big keys, or build something entirely your own.

<p align="center">
  <img src="screenshots/dvorak.png" alt="A Dvorak-style layout with a tinted home row" width="720"><br>
  <em>A Dvorak-style arrangement with the home row recolored. Every button sends the key it shows.</em>
</p>

<p align="center">
  <img src="screenshots/rainbow%20abc.png" alt="The letters A to Z as large keys shaded from red to violet" width="460"><br>
  <em>Just the letters A to Z, resized and recolored from red to violet.</em>
</p>

## Loadouts

A loadout is a saved layout, including every key's position, size, label, color and what it sends, shortcuts included. Make as many as you need.

- **Save** the current layout, or **Save as** a new loadout under any name.
- Switch between loadouts from the **Loadouts** menu in one click, for example one for a game, one for writing, and one for a compact corner of your screen.
- KeyDeck remembers which loadout you used last and opens with it.
- Loadouts are plain JSON files in `%APPDATA%\KeyDeck\loadouts`. The **Open loadouts folder** menu item takes you straight there, so you can back them up or share them by copying a file.
- **Reset to default layout** brings back the built-in keyboard whenever you want a fresh start.

## Programmable keys

Every button on KeyDeck is programmable. A button is a position, a size, a label and **what it sends**, and you can change each of those independently. What it sends can be a single key or a whole shortcut.

**Send any key.** Open **Edit layout**, select a button, and pick from the **Sends** list of 120+ keys: letters, numbers, punctuation, F1 to F24, arrows, the navigation cluster, the numpad and media keys. Give the button any **label** you like, and an optional **shift label** that appears while Shift is active.

**Program a shortcut.** Select a button and click **Program shortcut...** to make it send a combination of keys with one click. Type the shortcut with `+` between keys:

| You type | What the button does |
|---|---|
| `Ctrl+Shift+Esc` | Opens Task Manager |
| `Alt+F4` | Closes the active window |
| `Win+D` | Shows the desktop |
| `Ctrl+C` / `Ctrl+V` | Copy and paste |
| `Win+Shift+S` | Starts a screenshot snip |

You can combine Ctrl, Shift, Alt and Win with any other key, and common names like `Esc`, `Del`, `PageUp` and `Return` work too. KeyDeck checks what you type and tells you if it doesn't recognize a key. The button is labeled with your shortcut by default, and you can rename it. Windows blocks software from generating Ctrl+Alt+Delete, so KeyDeck won't accept that one.

With programmable keys you can put your game's controls exactly where you want them, turn a spare button into a dedicated F-key or media control, or build a keypad of the shortcuts you use every day.

<p align="center">
  <img src="screenshots/programable%20keys.png" alt="A board of large one-click shortcut buttons" width="520"><br>
  <em>A board made entirely of programmed shortcut buttons: Copy, Paste, Alt+Tab, Task Manager and more, each one click.</em>
</p>

## Scalable interface

KeyDeck can be as big, as small and as see-through as you want. The **whole interface scales together**, not just the keys.

- Choose **Tiny, Very small, Small, Medium, Large or Extra large**, or enter a **custom size** from 14 to 80 pixels.
- The toolbar buttons, menus, suggestion bar and editing panel all grow and shrink with the keys, so nothing looks out of proportion.
- Key labels shrink and trim themselves to fit, so text never spills over neighboring keys at small sizes.
- **Opacity** can be set to 100%, 90%, 80%, 70% or 55% under **Settings**, so you can see the window or game behind the keyboard.
- Pin KeyDeck **always on top** so it stays within reach.

<p align="center">
  <img src="screenshots/scalability%20and%20opacity.png" alt="KeyDeck at two sizes, the larger one partly transparent over the desktop" width="760"><br>
  <em>The same keyboard at a small size (top) and a large size with reduced opacity (bottom), showing the desktop through it.</em>
</p>

## Hold any key

Most on-screen keyboards let you latch Shift, Ctrl and Alt and nothing else. KeyDeck lets you hold **every** key.

- **Right-click** any key to hold it down. Right-click it again to release it.
- Switch on the **Hold** button in the toolbar and every ordinary left-click becomes a hold toggle instead of a tap.
- **Release all** lets go of everything at once, so nothing is ever left stuck down.
- Held keys are shown in orange so you can see at a glance what is down.

This is handy for any game or tool where you hold a key while doing something else, such as holding `A` while clicking to collect crops all at once, holding `W` to walk, or holding Shift while you work with the mouse.

Modifier keys (Shift, Ctrl, Alt, Win) behave the way you'd expect from an on-screen keyboard: a single click applies to the next key and then releases, and right-click locks them down. You can switch that one-shot behavior off in Settings. When Shift is active, the number and symbol keys switch to their shifted characters so you can see what you'll get.

<p align="center">
  <img src="screenshots/hold.png" alt="Five keys held down at once, shown in orange" width="760"><br>
  <em>Five keys held down at the same time (Q, O, D, J and N), shown in orange.</em>
</p>

## Predictive text

A suggestion bar above the keys offers three predictions as you type, and it gets better the more you use it.

- **Completes words** as you type them, and **suggests the next word** between words.
- Starts with a built-in vocabulary of 1,200+ common words and over 100 starter phrases, so it is useful from the first keystroke.
- **Learns from you.** It remembers the words you use, which words tend to follow each other, and the phrases you repeat. A new word is only learned after you've typed it twice, so typos and one-offs don't pollute your suggestions.
- Follows your **capitalization**, including names, sentence starts and ALL CAPS.
- Click a suggestion to type it. **Right-click** one to make KeyDeck forget that word. Use **Forget everything** in Settings to start over.
- Everything it learns stays on your computer, in a single file in `%APPDATA%\KeyDeck`. Nothing is sent anywhere.
- It knows when you're gaming, not writing. Held keys pause suggestions, so your game controls are never learned as words.

<p align="center">
  <img src="screenshots/predictive%20text.png" alt="KeyDeck suggesting quick, quickly and quite after typing the q into a text editor" width="700"><br>
  <em>After typing "the q" into a text editor, KeyDeck offers "quick", "quickly" and "quite". Click one to finish the word.</em>
</p>

## Types anywhere

- **Never steals focus.** Clicking a key does not pull focus away from the program you're typing into, so keystrokes go where you were working.
- **Hardware scan codes** are sent by default, which is what most games listen for. You can switch to standard key events in Settings.
- Optional **auto-repeat** when you press and hold a key, just like a physical keyboard.
- The **Caps Lock** key lights up while Caps Lock is on, even if you turned it on from your physical keyboard.

---

## Getting started

KeyDeck needs Windows and Python 3. It uses only the standard library, so there is nothing else to install.

```
python keydeck.py
```

### Build an executable

```
python -m pip install pyinstaller
python -m PyInstaller --noconsole --onefile --name KeyDeck keydeck.py
```

Your program is created at `dist\KeyDeck.exe`.

## Good to know

- Windows blocks injected keystrokes into programs running as administrator unless KeyDeck is also run as administrator.
- Key codes assume a US keyboard layout.
- Settings, loadouts and learned words are saved in `%APPDATA%\KeyDeck`, so they survive updates and rebuilds.
- Unsigned programs built with PyInstaller are sometimes flagged by antivirus software. Running `python keydeck.py` directly avoids that.
