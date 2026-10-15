"""
KeyDeck - a customizable on-screen keyboard for Windows.

Run:   python keydeck.py
Build: pip install pyinstaller && pyinstaller --noconsole --onefile keydeck.py

Highlights
  * Never steals focus - it types into whatever program you were using.
  * Any key can be HELD DOWN (letters, numbers, F-keys, everything):
      - Right-click a key to hold it; click it again to release.
      - Or switch on the "Hold" toolbar button: every left-click then toggles hold.
      - "Release all" lets go of everything.
  * Modifier keys (Shift/Ctrl/Alt/Win) are one-shot by default (release after the
    next key); right-click them to lock them down.
  * Edit Layout: drag keys, drag the bottom-right corner to resize, pick which key
    each button sends, change labels and colors, add / duplicate / delete keys.
  * Loadouts: save as many layouts as you like and switch between them.
  * Keys are sent as hardware scan codes by default (works in most games).
  * Predictive text: a bar of 3 suggestions using a larger built-in vocabulary, starter
    phrase patterns, context-aware ranking, and words/phrases learned as you type. It
    saves them to predict.json in the KeyDeck folder under %APPDATA%. Click a suggestion to type it;
    right-click a suggestion to make it forget that word.

Notes
  * Windows only. Layout of key codes assumes a US keyboard layout.
  * Windows blocks injected input into programs running as administrator, unless
    KeyDeck is also run as administrator.
"""

import atexit
import ctypes
import heapq
import json
import os
import sys
import time
import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog, ttk

IS_WIN = sys.platform == "win32"

# --------------------------------------------------------------------------
# Windows input plumbing
# --------------------------------------------------------------------------
if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetKeyState.argtypes = [ctypes.c_int]
    user32.GetKeyState.restype = ctypes.c_short
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


# --------------------------------------------------------------------------
# Key catalog: name -> (virtual-key code, needs extended flag)
# --------------------------------------------------------------------------
CATALOG = {}
LABELS = {}


def reg(name, vk, ext=False, label=None):
    CATALOG[name] = (vk, ext)
    LABELS[name] = label if label is not None else name


reg("Esc", 0x1B)
for i in range(1, 13):
    reg("F%d" % i, 0x6F + i)
for c in "`1234567890-=":
    reg(c, {"`": 0xC0, "-": 0xBD, "=": 0xBB}.get(c, ord(c) if c.isdigit() else 0))
reg("Backspace", 0x08)
reg("Tab", 0x09)
for c in "QWERTYUIOP":
    reg(c, ord(c))
reg("[", 0xDB)
reg("]", 0xDD)
reg("\\", 0xDC)
reg("Caps Lock", 0x14, label="Caps")
for c in "ASDFGHJKL":
    reg(c, ord(c))
reg(";", 0xBA)
reg("'", 0xDE)
reg("Enter", 0x0D)
reg("LShift", 0xA0, label="Shift")
for c in "ZXCVBNM":
    reg(c, ord(c))
reg(",", 0xBC)
reg(".", 0xBE)
reg("/", 0xBF)
reg("RShift", 0xA1, label="Shift")
reg("LCtrl", 0xA2, label="Ctrl")
reg("LWin", 0x5B, True, label="Win")
reg("LAlt", 0xA4, label="Alt")
reg("Space", 0x20, label="")
reg("RAlt", 0xA5, True, label="Alt")
reg("RWin", 0x5C, True, label="Win")
reg("Menu", 0x5D, True)
reg("RCtrl", 0xA3, True, label="Ctrl")
reg("PrtSc", 0x2C, True)
reg("ScrLk", 0x91)
reg("Pause", 0x13)
reg("Insert", 0x2D, True, label="Ins")
reg("Delete", 0x2E, True, label="Del")
reg("Home", 0x24, True)
reg("End", 0x23, True)
reg("PgUp", 0x21, True)
reg("PgDn", 0x22, True)
reg("Up", 0x26, True, label="\u25B2")
reg("Down", 0x28, True, label="\u25BC")
reg("Left", 0x25, True, label="\u25C0")
reg("Right", 0x27, True, label="\u25B6")
reg("Num Lock", 0x90, True, label="Num")
for d in "0123456789":
    reg("Num " + d, 0x60 + int(d), label=d)
reg("Num /", 0x6F, True, label="/")
reg("Num *", 0x6A, label="*")
reg("Num -", 0x6D, label="-")
reg("Num +", 0x6B, label="+")
reg("Num .", 0x6E, label=".")
reg("Num Enter", 0x0D, True, label="Enter")
for i in range(13, 25):
    reg("F%d" % i, 0x6F + i)
reg("Mute", 0xAD)
reg("Vol-", 0xAE)
reg("Vol+", 0xAF)
reg("Next", 0xB0)
reg("Prev", 0xB1)
reg("Stop", 0xB2)
reg("Play/Pause", 0xB3, label="Play")

# Keys that must be sent by virtual-key instead of scan code.
NO_SCAN = {0x13, 0x90, 0x2C, 0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}
MOD_VKS = {0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C, 0x10, 0x11, 0x12}
SHIFT_VKS = {0xA0, 0xA1, 0x10}


class KeySender:
    def __init__(self, scancode_mode=True):
        self.scancode_mode = scancode_mode

    def send(self, name, down):
        vk, ext = CATALOG[name]
        if not IS_WIN:
            print("%s %s" % (name, "down" if down else "up"))
            return
        sc = 0
        if self.scancode_mode and vk not in NO_SCAN:
            r = user32.MapVirtualKeyW(vk, 4)  # MAPVK_VK_TO_VSC_EX
            sc = r & 0xFF
            if (r >> 8) in (0xE0, 0xE1):
                ext = True
        flags = 0
        if sc:
            wvk, wscan = 0, sc
            flags |= KEYEVENTF_SCANCODE
        else:
            wvk, wscan = vk, 0
        if ext:
            flags |= KEYEVENTF_EXTENDEDKEY
        if not down:
            flags |= KEYEVENTF_KEYUP
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = KEYBDINPUT(wVk=wvk, wScan=wscan, dwFlags=flags, time=0, dwExtraInfo=0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), "KeyDeck")
LOADOUT_DIR = os.path.join(CONFIG_DIR, "loadouts")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PREDICT_FILE = os.path.join(CONFIG_DIR, "predict.json")
DEFAULT_SETTINGS = {"loadout": "", "unit": 38, "opacity": 1.0, "scancode": True,
                    "topmost": True, "oneshot": True, "repeat": True,
                    "predict": True, "learn": True}


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


def list_loadouts():
    try:
        return sorted(f[:-5] for f in os.listdir(LOADOUT_DIR) if f.lower().endswith(".json"))
    except Exception:
        return []


def safe_name(name):
    keep = "".join(ch for ch in name if ch.isalnum() or ch in " -_").strip()
    return keep


def new_key_dict(name, x, y, w=1.0, h=1.0, label=None, label2="", color="", fg=""):
    return {"key": name, "label": LABELS.get(name, name) if label is None else label,
            "label2": label2, "x": x, "y": y, "w": w, "h": h, "color": color, "fg": fg}


def default_layout():
    keys = []

    def add(name, x, y, w=1.0, h=1.0, label=None, label2=""):
        keys.append(new_key_dict(name, x, y, w, h, label, label2))

    add("Esc", 0, 0)
    for i in range(4):
        add("F%d" % (i + 1), 2 + i, 0)
    for i in range(4):
        add("F%d" % (i + 5), 6.5 + i, 0)
    for i in range(4):
        add("F%d" % (i + 9), 11 + i, 0)
    add("PrtSc", 15.25, 0)
    add("ScrLk", 16.25, 0)
    add("Pause", 17.25, 0)

    shifted = dict(zip("`1234567890-=", "~!@#$%^&*()_+"))
    for i, c in enumerate("`1234567890-="):
        add(c, i, 1.5, label2=shifted[c])
    add("Backspace", 13, 1.5, 2)
    add("Insert", 15.25, 1.5)
    add("Home", 16.25, 1.5)
    add("PgUp", 17.25, 1.5)

    add("Tab", 0, 2.5, 1.5)
    row = "QWERTYUIOP[]"
    sh2 = {"[": "{", "]": "}"}
    for i, c in enumerate(row):
        add(c, 1.5 + i, 2.5, label2=sh2.get(c, ""))
    add("\\", 13.5, 2.5, 1.5, label2="|")
    add("Delete", 15.25, 2.5)
    add("End", 16.25, 2.5)
    add("PgDn", 17.25, 2.5)

    add("Caps Lock", 0, 3.5, 1.75)
    sh3 = {";": ":", "'": '"'}
    for i, c in enumerate("ASDFGHJKL;'"):
        add(c, 1.75 + i, 3.5, label2=sh3.get(c, ""))
    add("Enter", 12.75, 3.5, 2.25)

    add("LShift", 0, 4.5, 2.25)
    sh4 = {",": "<", ".": ">", "/": "?"}
    for i, c in enumerate("ZXCVBNM,./"):
        add(c, 2.25 + i, 4.5, label2=sh4.get(c, ""))
    add("RShift", 12.25, 4.5, 2.75)
    add("Up", 16.25, 4.5)

    add("LCtrl", 0, 5.5, 1.25)
    add("LWin", 1.25, 5.5, 1.25)
    add("LAlt", 2.5, 5.5, 1.25)
    add("Space", 3.75, 5.5, 6.25)
    add("RAlt", 10, 5.5, 1.25)
    add("RWin", 11.25, 5.5, 1.25)
    add("Menu", 12.5, 5.5, 1.25)
    add("RCtrl", 13.75, 5.5, 1.25)
    add("Left", 15.25, 5.5)
    add("Down", 16.25, 5.5)
    add("Right", 17.25, 5.5)

    nx = 18.5
    add("Num Lock", nx, 1.5)
    add("Num /", nx + 1, 1.5)
    add("Num *", nx + 2, 1.5)
    add("Num -", nx + 3, 1.5)
    for i, d in enumerate("789"):
        add("Num " + d, nx + i, 2.5)
    add("Num +", nx + 3, 2.5, 1, 2)
    for i, d in enumerate("456"):
        add("Num " + d, nx + i, 3.5)
    for i, d in enumerate("123"):
        add("Num " + d, nx + i, 4.5)
    add("Num Enter", nx + 3, 4.5, 1, 2)
    add("Num 0", nx, 5.5, 2)
    add("Num .", nx + 2, 5.5)
    return keys


# --------------------------------------------------------------------------
# Predictive text
#
# A small word model that learns from what you type on KeyDeck:
#   uni  - how often each word was used
#   bi   - which word tends to follow a given word
#   tri  - which word tends to follow a given pair of words (your common phrases)
# A brand-new word has to be typed twice before it is learned, which keeps one-off
# typos and button-mashing out of the dictionary.
# --------------------------------------------------------------------------
SEED_WORDS = """
the be to of and a in that have i it for not on with he as you do at this but his by from
 they we say her she or an will my one all would there their what so up out if about who get
 which go me when make can like time no just him know take people into year your good some
 could them see other than then now look only come its over think also back after use two how
 our work first well way even new want because any these give day most us is was are were been
 has had did does said made went got here very where much through before right too mean old
 same tell boy follow came show small large every great still own under last never let begin
 life always those both between might next while found should home start help hand high keep
 away put need feel turn ask few part place world find thing many off again why live long little
 man cannot call really something nothing everything someone anyone yes okay ok sorry thanks
 thank please hello hi hey bye goodbye morning night evening today tomorrow tonight yesterday
 soon later already maybe probably definitely actually basically anyway however though although
 until since without within during against around another better best bad worse worst love hate
 happy sad glad funny sure true real nice cool awesome wait stop going doing being having making
 getting looking coming trying using working playing talk talking says asked told called text
 message email phone game play played player level farm crop crops collect harvest plant water grow
 money coin coins buy sell trade shop store item items quest team friend friends family mom dad
 brother sister school class teacher homework test study read write book watch movie video music
 song eat food lunch dinner breakfast drink hungry tired sleep bed late early busy free ready done
 finish finished started open close big short fast slow hard easy question answer idea problem reason
 point week month weekend minute minutes hour hours second seconds person name number things stuff
 lot lots kind sort type i'm i'll i've i'd you're you'll you've we're we'll we've they're they'll
 it's that's there's what's who's let's don't doesn't didn't can't couldn't won't wouldn't shouldn't
 isn't aren't wasn't weren't haven't hasn't hadn't

above accept account across act action activity add address adult advice afraid afternoon age ago agree
 ahead air allow almost alone along already although amazing amount animal answer appear apple area arm
 art artist ask attention aunt available avoid awake baby back background balance ball bank base basic
 beach beat beautiful became become bed bedroom begin behavior behind believe below benefit beside
 better beyond bicycle bill birthday black blue board body book borrow bottom box boy brain break bring
 build building business buy cake calculate camera camp car card care careful carry case cat catch cause
 center certain chair chance change character charge check child choice choose city claim clean clear
 client clock close clothes cloud code coffee cold college color come comfortable common company complete
 computer concern condition consider continue control conversation cook copy correct cost could count country
 couple course create creative cross crowd cry culture customer cut daily dance danger dark data date daughter
 dead deal death decide decision deep degree depend describe design desk detail develop device difference difficult
 dinner direction discover discuss disease doctor dog door download draw dream drive drop during each early earth
 east education effect effort eight either else end energy enjoy enough enter entire environment error especially
 establish even event ever every everybody everyone evidence example experience explain eye face fact fail fall family
 famous far farm father feature feel feeling few field figure fill film final finally financial finish fire first fish
 five floor fly focus follow food foot force form forward four free fresh friend front full fun future game garden gas
 general get girl give glass go goal god gold gone good government great green ground group grow guess gun guy
 habit half happen happy hard health hear heart heavy help high history hit hold hole holiday hope hospital hot hotel
 house however huge human hundred hurt idea identify image imagine important improve include increase indeed index
 individual industry information inside instead interest internet interview introduce invite involve issue item itself
 jacket job join joke journey joy judge jump just keep key kid kill kind kitchen knee know knowledge language large last
 late laugh law lead learn least leave left leg legal less lesson let letter level library lie life light likely line list
 listen little local location lock long lose loss loud low machine main major make male manage manager many map market
 matter may meal mean measure media medical meet memory mention message method middle might mile mind minute miss model
 modern moment money month mood morning mother mountain mouth move movement movie much music must name nation natural
 near necessary need neighbor never new news next nice night nine nobody noise none normal north note nothing notice
 number object obvious occur ocean offer office often okay old once one online only open opinion opportunity option order
 ordinary organization original other outside over own page pain paper parent park part party pass past path patient pattern
 pay peace people perfect perhaps period person personal phone photo physical picture piece place plan plant play player
 please point police policy poor popular position possible power practice prefer prepare present president press pretty
 prevent price primary print private problem process produce product program project promise proper protect prove provide
 public purpose push put quality question quick quickly quiet quite race raise range rate rather reach read reader ready
 real realize reason receive recent recognize record red reduce refer reflect regular relationship release remember
 remove rent repair repeat replace reply report request require research resource respect respond response rest result return
 review rich ride right rise risk road role room rule run safe safety same save say scene school science screen search season
 second section see seem sell send sense sentence separate serious serve service set seven several share she ship shirt shoe
 shoot shop short should shoulder show shut side sign simple simply since sing single sister sit site situation six size skill
 skin sleep small smart smile social society software solution someone something sometimes son song soon sound source south
 space speak special specific speed spend sport spring stand standard start state statement stay step still stock stop story
 street strong student study subject succeed success such suddenly suggest summer support sure surface system table take talk
 task taste teach teacher team technology tell ten term test than thank theory thing think third though thought thousand
 three through throw thus ticket time tiny title today together told tomorrow tone tool top topic total touch town track trade
 train training travel treat tree trial trip trouble true truth try turn twelve twenty twice two type understand unit university
 until update upon use useful user usual usually value various version video view visit voice wait walk wall want war warm
 watch water way we wear weather website wedding week weight welcome west what whatever wheel wheelchair when where whether
 which while white whole whose wide wife wild win wind window winter wish within woman wonder word work worker world worry
 worth write writer wrong yard year yellow yes yesterday yet young yourself

can't cannot won't wouldn't shouldn't couldn't isn't aren't wasn't weren't haven't hasn't hadn't doesn't don't didn't
 i've i'll i'd i'm you're you'll you've you'd we're we'll we've they'd they'll they're they'd it's that's there's what's
 who's let's here's would've could've should've would've would've would've
""".split()

# Lightweight built-in language model. Each line is a short, common sentence or phrase.
# These starter counts make context prediction useful before the user has taught it phrases.
SEED_PHRASES = """
i am happy
i am sorry
i am looking for
i need help
i need to
i want to
i would like to
i don't know
i don't think so
i can't do that
i can do it
i have a question
i have to go
i will be there
i'll be back
i'm going to
i'm trying to
i'm not sure
i think that
i think so
thank you very much
thank you for your help
how are you
how do you do
what do you mean
what do you think
what is this
what is that
where are you
where is it
when are you coming
can you help me
can you tell me
could you please
would you like to
let me know
let me see
as soon as possible
at the same time
one of the most
in order to
for example
on the other hand
because of that
I don't know
there is a way
there are many
it is important
it would be nice
that sounds good
that makes sense
have a good day
have a good night
good to know
nice to meet you
see you later
talk to you later
I'll let you know
I'm glad you
I'm going to be
I want to make
I need to get
I have been
I would have
if you want
do you want to
do you have a
are you sure
are you okay
it looks like
it seems like
this is the way
this is a good
this is not
I appreciate it
no problem at all
please let me know
thanks for your help
thanks for letting me know
what happened to
how much is
how long does
how long have
a little bit
more than that
less than that
as far as I know
I agree with you
I don't agree
I understand what you mean
I can see that
I was wondering if
the best way to
one thing at a time
make sure that
try to make it
would be able to
could be a good
it depends on
I have no idea
not sure what
the next time
in the future
right now
for a while
at least one
on my own
in front of me
out of the way
I hope you are
I hope that helps
""".lower().splitlines()

SEED_CAPS = {"i": "I", "i'm": "I'm", "i'll": "I'll", "i've": "I've", "i'd": "I'd"}

LEARN_W = 4
IDLE_RESET = 30.0   # seconds without typing before the word context is forgotten
CMD_VKS = {0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C}
IGNORED_KEYS = {"LShift", "RShift", "LCtrl", "RCtrl", "LAlt", "RAlt", "LWin", "RWin",
                "Caps Lock", "Num Lock", "ScrLk", "Pause", "PrtSc", "Mute", "Vol+",
                "Vol-", "Next", "Prev", "Stop", "Play/Pause"}
BASE_CHARS = "`1234567890-=[]\\;',./"
SHIFTED_CHARS = "~!@#$%^&*()_+{}|:\"<>?"
SHIFT_OF = dict(zip(BASE_CHARS, SHIFTED_CHARS))


class Predictor:
    def __init__(self):
        self.learning = True
        self.buffer = ""        # the word being typed right now (as typed)
        self.hist = []          # previous words, lowercase; "<s>" = sentence start
        self.undo = None        # (word, hist) so Backspace after a space restores the word
        self._since_save = 0
        self.uni, self.bi, self.tri, self.seq, self.caps, self.pending = {}, {}, {}, {}, {}, {}
        self.load()

    # ---------- storage ----------
    def clear_data(self):
        # Give common words a useful baseline weight; frequently used words rank higher.
        n = len(SEED_WORDS)
        self.uni = {}
        for rank, w in enumerate(SEED_WORDS):
            self.uni.setdefault(w, max(2, 10 - rank * 7 // max(1, n)))
        self.bi, self.tri, self.seq, self.pending = {}, {}, {}, {}
        self.caps = dict(SEED_CAPS)
        self._add_seed_phrases()

    def _add_seed_phrases(self):
        """Load modest starter phrase counts without overpowering personal learning."""
        for line in SEED_PHRASES:
            words = [w for w in line.split() if self.norm(w) is not None]
            for w in words:
                self.uni.setdefault(w, 2)
            prev = []
            for w in words:
                if prev:
                    key = prev[-1]
                    d = self.bi.setdefault(key, {})
                    d[w] = max(d.get(w, 0), 3)
                if len(prev) >= 2:
                    key = prev[-2] + " " + prev[-1]
                    d = self.tri.setdefault(key, {})
                    d[w] = max(d.get(w, 0), 5)
                # Remember longer phrase contexts too, so repeated personal wording
                # can be predicted beyond the last two words.
                for span in range(1, min(8, len(prev)) + 1):
                    context = " ".join(prev[-span:])
                    d = self.seq.setdefault(context, {})
                    d[w] = max(d.get(w, 0), 2 + span)
                prev.append(w)

    def load(self):
        try:
            with open(PREDICT_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.uni = {str(k): int(v) for k, v in d["uni"].items()}
            self.bi = {str(k): {str(a): int(b) for a, b in v.items()} for k, v in d["bi"].items()}
            self.tri = {str(k): {str(a): int(b) for a, b in v.items()} for k, v in d["tri"].items()}
            self.seq = {str(k): {str(a): int(b) for a, b in v.items()}
                        for k, v in d.get("seq", {}).items()}
            self.caps = {str(k): str(v) for k, v in d.get("caps", {}).items()}
            self.pending = {str(k): int(v) for k, v in d.get("pending", {}).items()}
            if not self.uni:
                raise ValueError("empty")
            # Upgrade older predict.json files in place: add new defaults while retaining
            # the user's existing counts, learned phrases, and capitalization choices.
            n = len(SEED_WORDS)
            for rank, w in enumerate(SEED_WORDS):
                self.uni.setdefault(w, max(2, 10 - rank * 7 // max(1, n)))
            seed_bi, seed_tri, seed_seq = self.bi, self.tri, self.seq
            self.bi, self.tri, self.seq = {}, {}, {}
            self._add_seed_phrases()
            for key, values in seed_bi.items():
                target = self.bi.setdefault(key, {})
                for word, count in values.items():
                    target[word] = max(target.get(word, 0), count)
            for key, values in seed_tri.items():
                target = self.tri.setdefault(key, {})
                for word, count in values.items():
                    target[word] = max(target.get(word, 0), count)
            for key, values in seed_seq.items():
                target = self.seq.setdefault(key, {})
                for word, count in values.items():
                    target[word] = max(target.get(word, 0), count)
            self.caps = {**SEED_CAPS, **self.caps}
        except Exception:
            self.clear_data()

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = PREDICT_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": 2, "uni": self.uni, "bi": self.bi, "tri": self.tri,
                           "seq": self.seq, "caps": self.caps, "pending": self.pending}, f)
            os.replace(tmp, PREDICT_FILE)
            self._since_save = 0
        except Exception:
            pass

    def forget_all(self):
        self.clear_data()
        self.reset()
        self.save()

    def forget(self, w):
        self.uni.pop(w, None)
        self.pending.pop(w, None)
        self.caps.pop(w, None)
        # Remove the forgotten word as a prediction target, but keep other words
        # learned after the same context.
        for table in (self.bi, self.tri, self.seq):
            for context in list(table):
                table[context].pop(w, None)
                if not table[context]:
                    del table[context]
        self._since_save += 1
        self.save()

    # ---------- learning ----------
    def norm(self, raw):
        """Return the lowercase word if it is worth tracking, else None."""
        w = raw.lower().strip("'")
        if not 1 <= len(w) <= 24:
            return None
        if not all(c.isascii() and (c.isalpha() or c == "'") for c in w):
            return None
        if len(w) == 1 and w not in ("a", "i"):
            return None
        if w not in self.uni:
            if not any(c in "aeiouy" for c in w):
                return None
            if any(w[i] == w[i + 1] == w[i + 2] == w[i + 3] for i in range(len(w) - 3)):
                return None
        return w

    def learn(self, raw):
        w = self.norm(raw)
        if w is None:
            return None
        if not self.learning:
            return w
        if w in self.uni:
            self.uni[w] += LEARN_W
        elif w in self.pending:
            del self.pending[w]
            self.uni[w] = LEARN_W * 2
        else:
            self.pending[w] = 1
            if len(self.pending) > 400:
                self.pending.pop(next(iter(self.pending)))
            return w
        if any(c.isupper() for c in raw[1:]) or (
                raw[0].isupper() and self.hist and self.hist[-1] != "<s>"):
            self.caps[w] = raw
        p1 = self.hist[-1] if self.hist else None
        if p1 and (p1 == "<s>" or p1 in self.uni):
            d = self.bi.setdefault(p1, {})
            d[w] = d.get(w, 0) + 1
            if len(self.hist) >= 2:
                p2 = self.hist[-2]
                if p2 == "<s>" or p2 in self.uni:
                    d = self.tri.setdefault(p2 + " " + p1, {})
                    d[w] = d.get(w, 0) + 1
            # Keep word-by-word continuation counts for contexts up to eight words.
            # This lets the model learn recurring sentence fragments and personal phrasing.
            for span in range(1, min(8, len(self.hist)) + 1):
                context_words = self.hist[-span:]
                if all(part == "<s>" or part in self.uni for part in context_words):
                    context = " ".join(context_words)
                    d = self.seq.setdefault(context, {})
                    d[w] = d.get(w, 0) + 1
        self._since_save += 1
        self.prune()
        if self._since_save >= 25:
            self.save()
        return w

    def prune(self):
        if len(self.uni) > 15000:
            keep = heapq.nlargest(12000, self.uni.items(), key=lambda kv: kv[1])
            self.uni = dict(keep)
        for table, cap in ((self.bi, 6500), (self.tri, 12000), (self.seq, 20000)):
            for key, d in list(table.items()):
                if len(d) > 40:
                    table[key] = dict(heapq.nlargest(30, d.items(), key=lambda kv: kv[1]))
            if len(table) > cap:
                ranked = sorted(table, key=lambda k: sum(table[k].values()), reverse=True)
                for key in ranked[int(cap * 0.8):]:
                    del table[key]

    # ---------- following the typing ----------
    def reset(self):
        self.buffer = ""
        self.hist = []
        self.undo = None

    def _finish(self, raw):
        prev = list(self.hist)
        w = self.learn(raw)
        self.hist = (self.hist + [w])[-8:] if w else []
        return prev

    @staticmethod
    def _char(name, shift, caps):
        if name == "Space":
            return " "
        if len(name) == 1:
            if name.isalpha():
                return name.upper() if shift != caps else name.lower()
            if name in SHIFT_OF:
                return SHIFT_OF[name] if shift else name
            return None
        if name.startswith("Num ") and len(name) == 5:
            return name[4]
        return None

    def feed(self, name, shift=False, caps=False):
        """Tell the model that key `name` was just typed."""
        undo, self.undo = self.undo, None
        if name in IGNORED_KEYS:
            self.undo = undo
            return
        if name == "Backspace":
            if self.buffer:
                self.buffer = self.buffer[:-1]
            elif undo:
                self.buffer, self.hist = undo[0], list(undo[1])
            else:
                self.hist = []
            return
        if name in ("Enter", "Num Enter"):
            if self.buffer:
                self._finish(self.buffer)
                self.buffer = ""
            self.hist = ["<s>"]
            return
        ch = self._char(name, shift, caps)
        if ch is None:                       # arrows, Tab, F-keys... cursor may have moved
            self.buffer = ""
            self.hist = []
            return
        if ch.isalpha() or (ch == "'" and self.buffer):
            self.buffer += ch
            if len(self.buffer) > 30:
                self.reset()
            return
        if ch == "'":
            return
        if ch == " ":
            if self.buffer:
                raw, self.buffer = self.buffer, ""
                self.undo = (raw, self._finish(raw))
            return
        if ch in ",;:-":
            if self.buffer:
                raw, self.buffer = self.buffer, ""
                self._finish(raw)
            return
        if ch in ".!?":
            if self.buffer:
                raw, self.buffer = self.buffer, ""
                self._finish(raw)
            self.hist = ["<s>"]
            return
        self.buffer = ""                     # digits and other symbols
        self.hist = []

    def accept(self, text):
        """A suggestion was typed for the user (followed by a space)."""
        self.buffer = ""
        self.undo = (text, self._finish(text))

    # ---------- suggestions ----------
    def display(self, w, cap_first, all_caps):
        s = self.caps.get(w, w)
        if all_caps:
            return s.upper()
        if cap_first and s[:1].islower():
            s = s[0].upper() + s[1:]
        return s

    def suggest(self, n=3):
        """Up to n (text to show, lowercase word) pairs."""
        buf = self.buffer
        p1 = self.hist[-1] if self.hist else None
        p2 = self.hist[-2] if len(self.hist) > 1 else None
        bi = self.bi.get(p1, {}) if p1 else {}
        tri = self.tri.get(p2 + " " + p1, {}) if (p1 and p2) else {}
        seq_scores = {}
        if self.hist:
            for span in range(1, min(8, len(self.hist)) + 1):
                context = " ".join(self.hist[-span:])
                for w, count in self.seq.get(context, {}).items():
                    # Longer matching contexts are more specific; a modest weight
                    # prevents a single rare observation from dominating everything.
                    seq_scores[w] = seq_scores.get(w, 0) + count * (2 + span * 1.5)
        if buf:
            pre = buf.lower()
            # Context gently breaks ties between completions; the prefix match stays primary.
            top = heapq.nlargest(n, ((c + 5 * bi.get(w, 0) + 12 * tri.get(w, 0)
                                       + 2 * seq_scores.get(w, 0), w)
                                     for w, c in self.uni.items()
                                     if w.startswith(pre) and w != pre))
        else:
            cand = {}
            # Trigrams are strongest, bigrams next, and a small unigram fallback keeps
            # the bar useful at sentence starts and for words not yet learned in context.
            for w, c in bi.items():
                cand[w] = cand.get(w, 0) + 4 * c
            for w, c in tri.items():
                cand[w] = cand.get(w, 0) + 9 * c
            for w, score in seq_scores.items():
                cand[w] = cand.get(w, 0) + score
            for w, c in self.uni.items():
                cand[w] = cand.get(w, 0) + max(1, c // 5)
            top = heapq.nlargest(n, ((score, w) for w, score in cand.items() if w in self.uni))
        cap_first = buf[:1].isupper() if buf else bool(self.hist and self.hist[-1] == "<s>")
        all_caps = len(buf) > 1 and buf.isupper()
        return [(self.display(w, cap_first, all_caps), w) for _s, w in top]


def type_word(sender, text, caps_on=False):
    """Type letters/apostrophes through `sender`, handling Shift and Caps Lock."""
    for ch in text:
        if ch == "'":
            sender.send("'", True)
            sender.send("'", False)
            continue
        name = ch.upper()
        if name not in CATALOG or not ch.isalpha():
            continue
        need_shift = ch.isupper() != caps_on
        if need_shift:
            sender.send("LShift", True)
        sender.send(name, True)
        sender.send(name, False)
        if need_shift:
            sender.send("LShift", False)


# --------------------------------------------------------------------------
# Theme
# --------------------------------------------------------------------------
BG = "#1b1b1f"
PANEL = "#24242b"
KEY_COLOR = "#34343c"
MOD_COLOR = "#2a3040"
KEY_EDGE = "#4a4a56"
SEL_EDGE = "#4aa3ff"
PRESS_COLOR = "#4a8fe8"
ONESHOT_COLOR = "#d9a400"
HOLD_COLOR = "#d9531e"
TEXT = "#f2f2f2"
PAD = 10


def rounded(x1, y1, x2, y2, r):
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def snap(v):
    return round(v * 4) / 4.0


# --------------------------------------------------------------------------
# The app
# --------------------------------------------------------------------------
class KeyDeck:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.sender = KeySender(self.settings["scancode"])
        self.keys = []
        self.states = {}          # key id -> "mom" | "oneshot" | "hold"
        self.pressing = None
        self.repeat_job = None
        self.edit_mode = False
        self.hold_mode = False
        self.sel = None
        self.drag = None
        self.loadout_name = ""    # "" means the built-in default
        self._loading = False
        self._next_id = 1
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.pad = int(PAD * self.scale)
        self.settings["unit"] = max(14, min(80, int(self.settings["unit"])))
        self.unit = int(self.settings["unit"] * self.scale)
        self.pt = Predictor()
        self.pt.learning = bool(self.settings["learn"])
        self.pt_fw = None
        self.pt_last = 0.0
        self.sugg = []

        root.title("KeyDeck")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.attributes("-topmost", bool(self.settings["topmost"]))
        try:
            root.attributes("-alpha", float(self.settings["opacity"]))
        except Exception:
            pass

        self.build_toolbar()
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.grid(row=2, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<Motion>", self.on_hover)
        self.build_suggest_bar()
        self.build_edit_panel()
        self.apply_ui_scale()

        self.load_loadout(self.settings["loadout"])
        self._last_caps_state = self.caps_on()
        self.root.after(150, self.poll_caps_state)
        root.update_idletasks()
        self.place_window()
        self.apply_noactivate(True)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        atexit.register(self.emergency_release)
        atexit.register(self.pt.save)

    # ---------------- window helpers ----------------
    def apply_noactivate(self, on):
        if not IS_WIN:
            return
        self.root.update_idletasks()
        # Tk's winfo_id() is usually the client HWND.  Its parent is the
        # actual top-level window, whose extended styles control taskbar
        # behavior.
        hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        # Keep KeyDeck non-activating so clicking its virtual keys does not
        # steal focus from the app receiving typed characters.  Explicitly
        # mark it as an application window, however, so Windows creates a
        # real taskbar button for the running window rather than only showing
        # the pinned shortcut (which can launch a second copy when clicked).
        style |= WS_EX_APPWINDOW
        style &= ~WS_EX_TOOLWINDOW
        if on:
            style |= WS_EX_NOACTIVATE
        else:
            style &= ~WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        # Tell Windows to recalculate the non-client/taskbar representation
        # after changing extended styles.  NOACTIVATE prevents this refresh
        # from taking focus away from the user's current app.
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)

    def place_window(self):
        r = self.root
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w, h = r.winfo_reqwidth(), r.winfo_reqheight()
        r.geometry("+%d+%d" % (max(0, (sw - w) // 2), max(0, sh - h - 90)))

    def keep_on_screen(self):
        r = self.root
        r.update_idletasks()
        sh = r.winfo_screenheight()
        bottom = r.winfo_y() + r.winfo_reqheight()
        if bottom > sh - 40:
            r.geometry("+%d+%d" % (max(0, r.winfo_x()), max(0, sh - r.winfo_reqheight() - 60)))

    # ---------------- toolbar ----------------
    def build_toolbar(self):
        tb = tk.Frame(self.root, bg=BG)
        tb.grid(row=0, column=0, sticky="ew")
        self.toolbar = tb

        def btn(text, cmd):
            b = tk.Button(tb, text=text, command=cmd, bg="#2b2b33", fg="#eeeeee",
                          activebackground="#3c3c48", activeforeground="#ffffff",
                          relief="flat", bd=0, padx=10, pady=4, font=("Segoe UI", 9),
                          takefocus=0)
            b.pack(side="left", padx=(6, 0), pady=6)
            return b

        def mbtn(text):
            m = tk.Menubutton(tb, text=text, bg="#2b2b33", fg="#eeeeee",
                              activebackground="#3c3c48", activeforeground="#ffffff",
                              relief="flat", bd=0, padx=10, pady=4, font=("Segoe UI", 9),
                              takefocus=0)
            m.pack(side="left", padx=(6, 0), pady=6)
            return m

        self.hold_btn = btn("Hold: OFF", self.toggle_hold)
        btn("Release all", self.release_all)
        self.edit_btn = btn("Edit layout", self.toggle_edit)

        lm = mbtn("Loadouts \u25BE")
        self.loadout_menu = tk.Menu(lm, tearoff=0, postcommand=self.rebuild_loadout_menu)
        lm["menu"] = self.loadout_menu
        self.v_loadout = tk.StringVar(value="")

        sm = mbtn("Settings \u25BE")
        menu = tk.Menu(sm, tearoff=0)
        sm["menu"] = menu
        self.v_unit = tk.IntVar(value=int(self.settings["unit"]))
        self.v_opacity = tk.DoubleVar(value=float(self.settings["opacity"]))
        self.v_topmost = tk.BooleanVar(value=bool(self.settings["topmost"]))
        self.v_scan = tk.BooleanVar(value=bool(self.settings["scancode"]))
        self.v_oneshot = tk.BooleanVar(value=bool(self.settings["oneshot"]))
        self.v_repeat = tk.BooleanVar(value=bool(self.settings["repeat"]))
        self.v_predict = tk.BooleanVar(value=bool(self.settings["predict"]))
        self.v_learn = tk.BooleanVar(value=bool(self.settings["learn"]))
        size_menu = tk.Menu(menu, tearoff=0)
        for label, val in (("Tiny", 22), ("Very small", 26), ("Small", 30), ("Medium", 38),
                           ("Large", 46), ("Extra large", 54)):
            size_menu.add_radiobutton(label=label, variable=self.v_unit, value=val,
                                      command=self.on_setting_change)
        size_menu.add_separator()
        size_menu.add_command(label="Custom…", command=self.custom_size)
        menu.add_cascade(label="Key size", menu=size_menu)
        op_menu = tk.Menu(menu, tearoff=0)
        for pct in (100, 90, 80, 70, 55):
            op_menu.add_radiobutton(label="%d%%" % pct, variable=self.v_opacity,
                                    value=pct / 100.0, command=self.on_setting_change)
        menu.add_cascade(label="Opacity", menu=op_menu)
        menu.add_separator()
        menu.add_checkbutton(label="Always on top", variable=self.v_topmost,
                             command=self.on_setting_change)
        menu.add_checkbutton(label="Send hardware scan codes (best for games)",
                             variable=self.v_scan, command=self.on_setting_change)
        menu.add_checkbutton(label="Modifiers release after the next key",
                             variable=self.v_oneshot, command=self.on_setting_change)
        menu.add_checkbutton(label="Auto-repeat when a key is pressed and held",
                             variable=self.v_repeat, command=self.on_setting_change)
        menu.add_separator()
        menu.add_checkbutton(label="Predictive text bar", variable=self.v_predict,
                             command=self.on_setting_change)
        menu.add_checkbutton(label="Learn words and phrases as I type",
                             variable=self.v_learn, command=self.on_setting_change)
        menu.add_command(label="Forget everything it learned…", command=self.forget_all)

        self.menus = [self.loadout_menu, menu, size_menu, op_menu]
        self.hint = tk.Label(tb, text="Right-click a key to hold it", bg=BG, fg="#80808c",
                             font=("Segoe UI", 9))
        self.update_hint()

    def update_hint(self):
        # The hint makes the toolbar wider; drop it at small sizes so the window can shrink.
        if int(self.settings["unit"]) < 34:
            self.hint.pack_forget()
        else:
            self.hint.pack(side="right", padx=max(4, round(self.unit * 0.26)))

    def apply_ui_scale(self):
        """Size every button, menu and bar to match the key size (self.unit)."""
        u = self.unit
        f = max(8, int(u * 0.32))            # text size in pixels (Medium = 12px, as before)
        big = max(9, int(u * 0.40))          # suggestion bar text
        px, py = max(3, round(u * 0.26)), max(1, round(u * 0.105))
        gap = max(2, round(u * 0.16))
        half = max(2, gap // 2)
        font = ("Segoe UI", -f)

        for w in self.toolbar.winfo_children():
            cls = w.winfo_class()
            if cls in ("Button", "Menubutton"):
                w.config(font=font, padx=px, pady=py)
                w.pack_configure(padx=(gap, 0), pady=gap)
            elif cls == "Label":
                w.config(font=font)
        for m in self.menus:
            try:
                m.config(font=font)
            except tk.TclError:
                pass

        for i, b in enumerate(self.sbtns):
            b.config(font=("Segoe UI", -big), pady=max(2, round(u * 0.13)))
            b.pack_configure(padx=(gap if i == 0 else half, half), pady=(0, gap))
        self.sreset.config(font=("Segoe UI", -big), padx=max(4, round(u * 0.21)),
                           pady=max(2, round(u * 0.13)))
        self.sreset.pack_configure(padx=(half, gap), pady=(0, gap))

        for fr in self.panel.winfo_children():
            for w in fr.winfo_children():
                cls = w.winfo_class()
                if cls == "Button":
                    w.config(font=font, padx=max(4, round(u * 0.24)),
                             pady=max(1, round(u * 0.08)))
                elif cls in ("Label", "Entry", "Spinbox"):
                    w.config(font=font)
        try:
            ttk.Style().configure("TCombobox", font=font)
            self.root.option_add("*TCombobox*Listbox.font", font)
        except Exception:
            pass

    def custom_size(self):
        val = simpledialog.askinteger(
            "Key size", "Key size in pixels (14 to 80). Medium is 38, Tiny is 22:",
            initialvalue=int(self.v_unit.get()), minvalue=14, maxvalue=80, parent=self.root)
        if val:
            self.v_unit.set(val)
            self.on_setting_change()

    def on_setting_change(self):
        s = self.settings
        s["unit"] = max(14, min(80, int(self.v_unit.get())))
        self.update_hint()
        s["opacity"] = float(self.v_opacity.get())
        s["topmost"] = bool(self.v_topmost.get())
        s["scancode"] = bool(self.v_scan.get())
        s["oneshot"] = bool(self.v_oneshot.get())
        s["repeat"] = bool(self.v_repeat.get())
        s["predict"] = bool(self.v_predict.get())
        s["learn"] = bool(self.v_learn.get())
        self.pt.learning = s["learn"]
        if not s["predict"]:
            self.pt.reset()
        self.refresh_bar()
        self.sender.scancode_mode = s["scancode"]
        self.root.attributes("-topmost", s["topmost"])
        try:
            self.root.attributes("-alpha", s["opacity"])
        except Exception:
            pass
        new_unit = int(s["unit"] * self.scale)
        if new_unit != self.unit:
            self.unit = new_unit
            self.apply_ui_scale()
            self.redraw()
            self.keep_on_screen()
        save_settings(s)

    # ---------------- edit panel ----------------
    def build_edit_panel(self):
        p = tk.Frame(self.root, bg=PANEL)
        p.grid(row=3, column=0, sticky="ew")
        p.grid_remove()
        self.panel = p
        self.v_key = tk.StringVar()
        self.v_label = tk.StringVar()
        self.v_label2 = tk.StringVar()
        self.v_w = tk.StringVar()
        self.v_h = tk.StringVar()

        def lbl(parent, text):
            tk.Label(parent, text=text, bg=PANEL, fg="#c8c8d0",
                     font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))

        def pbtn(parent, text, cmd):
            b = tk.Button(parent, text=text, command=cmd, bg="#33333d", fg="#eeeeee",
                          activebackground="#44444f", activeforeground="#ffffff",
                          relief="flat", bd=0, padx=9, pady=3, font=("Segoe UI", 9))
            b.pack(side="left", padx=(6, 0))
            return b

        r1 = tk.Frame(p, bg=PANEL)
        r1.pack(fill="x", padx=4, pady=(8, 3))
        lbl(r1, "Sends")
        cb = ttk.Combobox(r1, textvariable=self.v_key, values=list(CATALOG) + ["Shortcut"],
                          width=11, state="readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self.on_key_choice)
        lbl(r1, "Label")
        tk.Entry(r1, textvariable=self.v_label, width=10).pack(side="left")
        lbl(r1, "Shift label")
        tk.Entry(r1, textvariable=self.v_label2, width=6).pack(side="left")
        lbl(r1, "Width")
        sw = tk.Spinbox(r1, from_=0.25, to=20, increment=0.25, textvariable=self.v_w,
                        width=5, command=self.on_dim_edit)
        sw.pack(side="left")
        sw.bind("<Return>", lambda e: self.on_dim_edit())
        sw.bind("<FocusOut>", lambda e: self.on_dim_edit())
        lbl(r1, "Height")
        sh = tk.Spinbox(r1, from_=0.25, to=20, increment=0.25, textvariable=self.v_h,
                        width=5, command=self.on_dim_edit)
        sh.pack(side="left")
        sh.bind("<Return>", lambda e: self.on_dim_edit())
        sh.bind("<FocusOut>", lambda e: self.on_dim_edit())
        self.v_label.trace_add("write", self.on_label_edit)
        self.v_label2.trace_add("write", self.on_label_edit)

        r2 = tk.Frame(p, bg=PANEL)
        r2.pack(fill="x", padx=4, pady=(3, 8))
        pbtn(r2, "Key color\u2026", lambda: self.pick_color("color"))
        pbtn(r2, "Text color\u2026", lambda: self.pick_color("fg"))
        pbtn(r2, "Reset colors", self.reset_colors)
        pbtn(r2, "+ Add key", self.add_key)
        pbtn(r2, "Program shortcut…", self.configure_shortcut)
        pbtn(r2, "Duplicate", self.duplicate_key)
        pbtn(r2, "Delete", self.delete_key)
        pbtn(r2, "Clear all", self.clear_all_keys)
        pbtn(r2, "Save loadout", self.save_loadout)
        pbtn(r2, "Save as\u2026", self.save_loadout_as)
        tk.Label(r2, text="Drag keys to move \u2022 drag a corner to resize", bg=PANEL,
                 fg="#80808c", font=("Segoe UI", 9)).pack(side="right", padx=8)

    def load_props(self):
        self._loading = True
        k = self.sel
        if k:
            self.v_key.set(k["key"])
            self.v_label.set(k["label"])
            self.v_label2.set(k["label2"])
            self.v_w.set(("%g" % k["w"]))
            self.v_h.set(("%g" % k["h"]))
        else:
            for v in (self.v_key, self.v_label, self.v_label2, self.v_w, self.v_h):
                v.set("")
        self._loading = False

    def on_label_edit(self, *_):
        if self._loading or not self.sel:
            return
        self.sel["label"] = self.v_label.get()
        self.sel["label2"] = self.v_label2.get()
        self.refresh_key(self.sel)

    def on_key_choice(self, _e=None):
        k = self.sel
        if not k:
            return
        old, new = k["key"], self.v_key.get()
        if new == "Shortcut":
            self.configure_shortcut()
            return
        if new not in CATALOG:
            return
        if k["label"] in ("", LABELS.get(old)):
            k["label"] = LABELS[new]
            k["label2"] = ""
        k["key"] = new
        k.pop("shortcut", None)
        self.load_props()
        self.refresh_key(k)

    def on_dim_edit(self):
        k = self.sel
        if self._loading or not k:
            return
        try:
            w = max(0.25, min(20.0, snap(float(self.v_w.get()))))
            h = max(0.25, min(20.0, snap(float(self.v_h.get()))))
        except ValueError:
            self.load_props()
            return
        k["w"], k["h"] = w, h
        self.load_props()
        self.refresh_key(k)
        self.fit_canvas()

    def pick_color(self, field):
        k = self.sel
        if not k:
            return
        initial = k.get(field) or (KEY_COLOR if field == "color" else TEXT)
        res = colorchooser.askcolor(color=initial, parent=self.root,
                                    title="Key color" if field == "color" else "Text color")
        if res and res[1]:
            k[field] = res[1]
            self.refresh_key(k)

    def reset_colors(self):
        if self.sel:
            self.sel["color"] = ""
            self.sel["fg"] = ""
            self.refresh_key(self.sel)

    def new_id(self):
        i = self._next_id
        self._next_id += 1
        return i

    def add_key(self):
        bottom = max((k["y"] + k["h"] for k in self.keys), default=0)
        k = new_key_dict("A", 0, bottom + 0.5)
        k["id"] = self.new_id()
        self.keys.append(k)
        self.sel = k
        self.load_props()
        self.redraw()

    def duplicate_key(self):
        if not self.sel:
            return
        k = dict(self.sel)
        k["id"] = self.new_id()
        k["x"] = self.sel["x"] + 0.5
        k["y"] = self.sel["y"] + 0.5
        self.keys.append(k)
        self.sel = k
        self.load_props()
        self.redraw()

    def configure_shortcut(self):
        """Turn the selected button into a key that sends a modifier shortcut."""
        k = self.sel
        if not k:
            messagebox.showinfo("KeyDeck", "Select a key in Edit layout first.", parent=self.root)
            return
        current = k.get("shortcut", "Ctrl+Shift+Esc") if k.get("key") == "Shortcut" else "Ctrl+Shift+Esc"
        raw = simpledialog.askstring(
            "Program shortcut",
            "Enter a shortcut using + between keys, e.g. Ctrl+Shift+Esc or Alt+F4.\n"
            "Supported names include Ctrl, Shift, Alt, Win, letters, numbers, F1–F24, and other keyboard keys.\n"
            "Note: Windows blocks software-generated Ctrl+Alt+Delete.",
            initialvalue=current, parent=self.root)
        if raw is None:
            return
        parsed, error = self.parse_shortcut(raw)
        if error:
            messagebox.showwarning("KeyDeck", error, parent=self.root)
            return
        k["key"] = "Shortcut"
        k["shortcut"] = parsed
        k["label"] = raw.strip()
        k["label2"] = ""
        self.load_props()
        self.refresh_key(k)
        self.fit_canvas()

    def parse_shortcut(self, raw):
        aliases = {
            "ctrl": "LCtrl", "control": "LCtrl", "shift": "LShift",
            "alt": "LAlt", "win": "LWin", "windows": "LWin",
            "esc": "Esc", "escape": "Esc", "spacebar": "Space",
            "return": "Enter", "del": "Delete", "ins": "Insert",
            "pageup": "PgUp", "pagedown": "PgDn", "caps": "Caps Lock",
        }
        parts = [part.strip() for part in raw.split("+") if part.strip()]
        if len(parts) < 2:
            return None, "Enter at least two keys separated by +, such as Ctrl+Shift+Esc."
        names = []
        for part in parts:
            name = aliases.get(part.lower(), part)
            if name not in CATALOG:
                # Case-insensitive match for ordinary catalog names.
                name = next((n for n in CATALOG if n.lower() == part.lower()), name)
            if name not in CATALOG:
                return None, "I don't recognize the key '%s'." % part
            names.append(name)
        if len(set(names)) != len(names):
            return None, "A shortcut cannot contain the same key more than once."
        vks = [CATALOG[n][0] for n in names]
        if 0x2E in vks and 0xA2 in vks and 0xA4 in vks:
            return None, "Windows deliberately blocks software from generating Ctrl+Alt+Delete. Choose another shortcut, such as Ctrl+Shift+Esc for Task Manager."
        return names, None

    def clear_all_keys(self):
        if not messagebox.askyesno("Clear keyboard", "Remove every key from this layout?\nYou can add keys again or save it as a blank loadout.", parent=self.root):
            return
        self.release_all(redraw=False)
        self.keys = []
        self.sel = None
        self.load_props()
        self.redraw()

    def create_blank_layout(self):
        self.release_all(redraw=False)
        self.keys = []
        self.sel = None
        self.drag = None
        self.loadout_name = ""
        self.v_loadout.set("")
        self.load_props()
        self.redraw()
        self.keep_on_screen()

    def delete_key(self):
        if not self.sel:
            return
        self.keys = [k for k in self.keys if k is not self.sel]
        self.sel = None
        self.load_props()
        self.redraw()

    # ---------------- loadouts ----------------
    def rebuild_loadout_menu(self):
        m = self.loadout_menu
        m.delete(0, "end")
        self.v_loadout.set(self.loadout_name)
        m.add_radiobutton(label="Default (built-in)", variable=self.v_loadout, value="",
                          command=lambda: self.load_loadout(""))
        saved = list_loadouts()
        if saved:
            m.add_separator()
        for name in saved:
            m.add_radiobutton(label=name, variable=self.v_loadout, value=name,
                              command=lambda n=name: self.load_loadout(n))
        m.add_separator()
        m.add_command(label="Blank layout (edit from scratch)", command=self.create_blank_layout)
        m.add_command(label="Save", command=self.save_loadout)
        m.add_command(label="Save as\u2026", command=self.save_loadout_as)
        m.add_command(label="Delete current loadout", command=self.delete_loadout)
        m.add_command(label="Reset to default layout", command=lambda: self.load_loadout(""))
        if IS_WIN:
            m.add_separator()
            m.add_command(label="Open loadouts folder", command=self.open_folder)

    def open_folder(self):
        os.makedirs(LOADOUT_DIR, exist_ok=True)
        try:
            os.startfile(LOADOUT_DIR)
        except Exception:
            pass

    def load_loadout(self, name):
        self.release_all(redraw=False)
        keys = None
        if name:
            try:
                with open(os.path.join(LOADOUT_DIR, name + ".json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                keys = []
                for raw in data.get("keys", []):
                    if raw.get("key") not in CATALOG and raw.get("key") != "Shortcut":
                        continue
                    stored_key = raw["key"]
                    if stored_key == "Shortcut" and not isinstance(raw.get("shortcut"), list):
                        continue
                    k = new_key_dict(stored_key, float(raw.get("x", 0)), float(raw.get("y", 0)),
                                     max(0.25, float(raw.get("w", 1))),
                                     max(0.25, float(raw.get("h", 1))),
                                     raw.get("label", LABELS.get(raw["key"], raw["key"])),
                                     raw.get("label2", ""), raw.get("color", ""), raw.get("fg", ""))
                    if stored_key == "Shortcut":
                        parsed, error = self.parse_shortcut("+".join(raw.get("shortcut", [])))
                        if error:
                            continue
                        k["shortcut"] = parsed
                    keys.append(k)
            except Exception:
                keys = None
                name = ""
        if keys is None:
            keys = default_layout()
            name = ""
        self._next_id = 1
        for k in keys:
            k["id"] = self.new_id()
        self.keys = keys
        self.loadout_name = name
        self.sel = None
        self.states.clear()
        self.settings["loadout"] = name
        save_settings(self.settings)
        self.load_props()
        self.redraw()
        self.keep_on_screen()

    def write_loadout(self, name):
        os.makedirs(LOADOUT_DIR, exist_ok=True)
        data = {"version": 1, "keys": [{kk: vv for kk, vv in k.items() if kk != "id"}
                                       for k in self.keys]}
        with open(os.path.join(LOADOUT_DIR, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.loadout_name = name
        self.settings["loadout"] = name
        save_settings(self.settings)

    def save_loadout(self):
        if not self.loadout_name:
            return self.save_loadout_as()
        try:
            self.write_loadout(self.loadout_name)
        except Exception as e:
            messagebox.showerror("KeyDeck", "Could not save: %s" % e, parent=self.root)

    def save_loadout_as(self):
        raw = simpledialog.askstring("Save loadout", "Loadout name:", parent=self.root)
        if raw is None:
            return
        name = safe_name(raw)
        if not name:
            messagebox.showwarning("KeyDeck", "Please enter a name.", parent=self.root)
            return
        if name in list_loadouts() and name != self.loadout_name:
            if not messagebox.askyesno("KeyDeck", "Replace the existing loadout '%s'?" % name,
                                       parent=self.root):
                return
        try:
            self.write_loadout(name)
        except Exception as e:
            messagebox.showerror("KeyDeck", "Could not save: %s" % e, parent=self.root)

    def delete_loadout(self):
        if not self.loadout_name:
            messagebox.showinfo("KeyDeck", "The built-in default can't be deleted.",
                                parent=self.root)
            return
        if messagebox.askyesno("KeyDeck", "Delete loadout '%s'?" % self.loadout_name,
                               parent=self.root):
            try:
                os.remove(os.path.join(LOADOUT_DIR, self.loadout_name + ".json"))
            except Exception:
                pass
            self.load_loadout("")

    # ---------------- drawing ----------------
    def rect(self, k):
        u, p = self.unit, self.pad
        return (p + k["x"] * u, p + k["y"] * u,
                p + (k["x"] + k["w"]) * u, p + (k["y"] + k["h"]) * u)

    def key_at(self, x, y):
        for k in reversed(self.keys):
            x1, y1, x2, y2 = self.rect(k)
            if x1 <= x < x2 and y1 <= y < y2:
                return k
        return None

    def is_mod(self, k):
        return k.get("key") in CATALOG and CATALOG[k["key"]][0] in MOD_VKS

    def shift_active(self):
        for k in self.keys:
            if k.get("key") in CATALOG and self.states.get(k["id"]) in ("oneshot", "hold") and CATALOG[k["key"]][0] in SHIFT_VKS:
                return True
        return False

    def colors_for(self, k):
        base = k.get("color") or (MOD_COLOR if self.is_mod(k) else KEY_COLOR)
        fg = k.get("fg") or TEXT
        if self.edit_mode:
            return base, fg
        st = self.states.get(k["id"])
        if k.get("key") == "Caps Lock" and self.caps_on():
            return ONESHOT_COLOR, "#1a1a1a"
        if st == "mom":
            return PRESS_COLOR, "#ffffff"
        if st == "oneshot":
            return ONESHOT_COLOR, "#1a1a1a"
        if st == "hold":
            return HOLD_COLOR, "#ffffff"
        return base, fg

    def label_for(self, k):
        if k.get("label2") and self.shift_active():
            return k["label2"]
        return k["label"]

    def fit_text(self, k, text):
        """Pick a pixel font size so the label fits inside the key; clip it if it can't."""
        u = self.unit
        avail = max(6, k["w"] * u - max(6, u * 0.2))
        lines = text.split("\n")
        n = max(1, max(len(s) for s in lines))
        px = max(6, min(int(u * 0.38), int(k["h"] * u * 0.6), int(avail / (0.62 * n))))
        maxc = max(1, int(avail / (0.62 * px)))
        if n > maxc:
            text = "\n".join(s[:maxc] for s in lines)
        return ("Segoe UI", -px, "bold"), text

    def draw_key(self, k):
        c = self.canvas
        tag = "key%d" % k["id"]
        x1, y1, x2, y2 = self.rect(k)
        g = 2
        fill, fg = self.colors_for(k)
        selected = self.edit_mode and self.sel is k
        r = max(4, int(self.unit * 0.12))
        c.create_polygon(rounded(x1 + g, y1 + g, x2 - g, y2 - g, r), smooth=True,
                         fill=fill, outline=SEL_EDGE if selected else KEY_EDGE,
                         width=3 if selected else 1, tags=(tag,))
        text = self.label_for(k)
        if text:
            font, text = self.fit_text(k, text)
            c.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text, fill=fg,
                          font=font, justify="center", tags=(tag,))
        if selected:
            c.create_rectangle(x2 - g - 9, y2 - g - 9, x2 - g - 1, y2 - g - 1,
                               fill=SEL_EDGE, outline="", tags=(tag,))

    def refresh_key(self, k):
        self.canvas.delete("key%d" % k["id"])
        self.draw_key(k)

    def redraw(self):
        self.canvas.delete("all")
        for k in self.keys:
            self.draw_key(k)
        self.fit_canvas()

    def fit_canvas(self):
        u = self.unit
        mx = max((k["x"] + k["w"] for k in self.keys), default=10)
        my = max((k["y"] + k["h"] for k in self.keys), default=4)
        extra = 2 if self.edit_mode else 0
        w = int(self.pad * 2 + (mx + extra) * u)
        h = int(self.pad * 2 + (my + extra) * u)
        w = max(w, int(300 * self.scale))
        self.canvas.config(width=w, height=h)

    # ---------------- typing ----------------
    def press_key(self, k):
        if k.get("key") == "Shortcut":
            self.send_shortcut(k.get("shortcut", []))
        else:
            self.sender.send(k["key"], True)

    def release_key(self, k):
        if k.get("key") == "Shortcut":
            return
        self.sender.send(k["key"], False)

    def send_shortcut(self, names):
        """Tap a chord in modifier-first order, then release in reverse order."""
        if not names:
            return
        mods = [n for n in names if CATALOG[n][0] in MOD_VKS]
        regular = [n for n in names if n not in mods]
        # Press modifiers first; tap each non-modifier while they are held.
        pressed = []
        try:
            for name in mods:
                self.sender.send(name, True)
                pressed.append(name)
            for name in regular:
                self.sender.send(name, True)
                self.sender.send(name, False)
        finally:
            for name in reversed(pressed):
                self.sender.send(name, False)

    def set_state(self, k, st):
        was_shift = self.shift_active()
        if st is None:
            self.states.pop(k["id"], None)
        else:
            self.states[k["id"]] = st
        if self.is_mod(k) and CATALOG[k["key"]][0] in SHIFT_VKS and was_shift != self.shift_active():
            self.redraw()
        else:
            self.refresh_key(k)

    def key_by_id(self, kid):
        for k in self.keys:
            if k["id"] == kid:
                return k
        return None

    def release_latched(self, k):
        self.release_key(k)
        self.set_state(k, None)

    def release_oneshots(self):
        for kid, st in list(self.states.items()):
            if st == "oneshot":
                k = self.key_by_id(kid)
                if k:
                    self.release_latched(k)

    def release_all(self, redraw=True):
        self.cancel_repeat()
        for kid in list(self.states):
            k = self.key_by_id(kid)
            if k:
                self.release_key(k)
        self.states.clear()
        self.pressing = None
        if redraw:
            self.redraw()

    def emergency_release(self):
        try:
            for kid in list(self.states):
                k = self.key_by_id(kid)
                if k:
                    self.release_key(k)
        except Exception:
            pass

    def toggle_hold(self):
        self.hold_mode = not self.hold_mode
        self.hold_btn.config(text="Hold: ON" if self.hold_mode else "Hold: OFF",
                             bg=HOLD_COLOR if self.hold_mode else "#2b2b33")

    def cancel_repeat(self):
        if self.repeat_job:
            self.root.after_cancel(self.repeat_job)
            self.repeat_job = None

    def repeat_tick(self, k):
        if self.pressing is k and self.states.get(k["id"]) == "mom":
            self.press_key(k)
            self.predict_key(k)
            self.repeat_job = self.root.after(35, lambda: self.repeat_tick(k))

    # ---------------- mouse: typing mode ----------------
    def on_press(self, e):
        if self.edit_mode:
            return self.edit_press(e)
        k = self.key_at(e.x, e.y)
        if not k:
            return
        st = self.states.get(k["id"])
        if st in ("hold", "oneshot"):
            self.release_latched(k)
            return
        if self.hold_mode:
            self.press_key(k)
            self.set_state(k, "hold")
        elif self.is_mod(k):
            self.press_key(k)
            self.set_state(k, "oneshot" if self.settings["oneshot"] else "hold")
        else:
            self.press_key(k)
            self.pressing = k
            self.set_state(k, "mom")
            self.predict_key(k)
            if self.settings["repeat"]:
                self.cancel_repeat()
                self.repeat_job = self.root.after(450, lambda: self.repeat_tick(k))

    def on_release(self, e):
        if self.edit_mode:
            return self.edit_release(e)
        k = self.pressing
        if k is not None:
            self.cancel_repeat()
            self.pressing = None
            if self.states.get(k["id"]) == "mom":
                self.release_key(k)
                self.set_state(k, None)
                self.release_oneshots()

    def on_right_press(self, e):
        if self.edit_mode:
            return
        k = self.key_at(e.x, e.y)
        if not k:
            return
        if self.states.get(k["id"]) in ("hold", "oneshot"):
            self.release_latched(k)
        elif self.states.get(k["id"]) is None:
            self.press_key(k)
            self.set_state(k, "hold")

    # ---------------- mouse: edit mode ----------------
    def on_hover(self, e):
        if not self.edit_mode:
            return
        near = self.near_handle(e.x, e.y)
        self.canvas.config(cursor="size_nw_se" if near else "")

    def near_handle(self, x, y):
        k = self.sel
        if not (self.edit_mode and k):
            return False
        _x1, _y1, x2, y2 = self.rect(k)
        return abs(x - (x2 - 5)) <= 10 and abs(y - (y2 - 5)) <= 10

    def edit_press(self, e):
        if self.near_handle(e.x, e.y):
            self.drag = ("resize",)
            return
        k = self.key_at(e.x, e.y)
        if k:
            self.keys.remove(k)
            self.keys.append(k)
            x1, y1, _x2, _y2 = self.rect(k)
            self.sel = k
            self.drag = ("move", e.x - x1, e.y - y1)
        else:
            self.sel = None
            self.drag = None
        self.load_props()
        self.redraw()

    def on_motion(self, e):
        if not self.edit_mode or not self.drag or not self.sel:
            return
        k = self.sel
        u, p = self.unit, self.pad
        if self.drag[0] == "move":
            nx = max(0.0, snap((e.x - self.drag[1] - p) / u))
            ny = max(0.0, snap((e.y - self.drag[2] - p) / u))
            if nx != k["x"] or ny != k["y"]:
                self.canvas.move("key%d" % k["id"], (nx - k["x"]) * u, (ny - k["y"]) * u)
                k["x"], k["y"] = nx, ny
        else:
            nw = max(0.25, snap((e.x - p) / u - k["x"]))
            nh = max(0.25, snap((e.y - p) / u - k["y"]))
            if nw != k["w"] or nh != k["h"]:
                k["w"], k["h"] = nw, nh
                self.refresh_key(k)

    def edit_release(self, e):
        if self.drag:
            self.drag = None
            self.load_props()
            self.fit_canvas()

    def toggle_edit(self):
        self.release_all(redraw=False)
        self.edit_mode = not self.edit_mode
        self.sel = None
        self.drag = None
        self.load_props()
        self.edit_btn.config(text="Done editing" if self.edit_mode else "Edit layout",
                             bg="#2f6fb5" if self.edit_mode else "#2b2b33")
        if self.edit_mode:
            self.panel.grid()
            self.apply_noactivate(False)   # text boxes need keyboard focus
        else:
            self.panel.grid_remove()
            self.apply_noactivate(True)
            self.canvas.config(cursor="")
        self.pt.reset()
        self.refresh_bar()
        self.redraw()
        self.keep_on_screen()

    # ---------------- predictive text ----------------
    def build_suggest_bar(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.grid(row=1, column=0, sticky="ew")
        self.sbar = bar
        self.sbtns = []
        for i in range(3):
            b = tk.Button(bar, text="", width=12, bg="#2b2b33", fg="#f2f2f2",
                          activebackground="#3c3c48", activeforeground="#ffffff",
                          relief="flat", bd=0, pady=5, font=("Segoe UI", 11), takefocus=0,
                          command=lambda i=i: self.accept_suggestion(i))
            b.pack(side="left", fill="x", expand=True, padx=(6 if i == 0 else 3, 3),
                   pady=(0, 6))
            b.bind("<ButtonPress-3>", lambda e, i=i: self.forget_suggestion(i))
            self.sbtns.append(b)
        r = tk.Button(bar, text="↺", command=self.reset_prediction, bg="#2b2b33",
                      fg="#9a9aa6", activebackground="#3c3c48", activeforeground="#ffffff",
                      relief="flat", bd=0, padx=8, pady=5, font=("Segoe UI", 11),
                      takefocus=0)
        r.pack(side="left", padx=(3, 6), pady=(0, 6))
        self.sreset = r
        if not self.settings["predict"]:
            bar.grid_remove()

    def refresh_bar(self):
        if self.settings["predict"] and not self.edit_mode:
            self.sbar.grid()
        else:
            self.sbar.grid_remove()
        self.update_suggestions()
        self.keep_on_screen()

    def reset_prediction(self):
        self.pt.reset()
        self.update_suggestions()

    def forget_all(self):
        if messagebox.askyesno("KeyDeck", "Forget all the words and phrases KeyDeck has "
                               "learned from you?", parent=self.root):
            self.pt.forget_all()
            self.update_suggestions()

    def fg_window(self):
        return user32.GetForegroundWindow() if IS_WIN else 0

    def caps_on(self):
        return bool(user32.GetKeyState(0x14) & 1) if IS_WIN else False

    def poll_caps_state(self):
        """Keep Caps Lock visibly lit even when toggled outside KeyDeck."""
        try:
            current = self.caps_on()
            if current != self._last_caps_state:
                self._last_caps_state = current
                for k in self.keys:
                    if k.get("key") == "Caps Lock":
                        self.refresh_key(k)
        finally:
            if self.root.winfo_exists():
                self.root.after(150, self.poll_caps_state)

    def game_like(self):
        """Held-down letter keys mean a game, not typing: don't track those."""
        if self.hold_mode:
            return True
        for kid, st in self.states.items():
            if st == "hold":
                k = self.key_by_id(kid)
                if k and not self.is_mod(k):
                    return True
        return False

    def cmd_mod_active(self):
        for kid, st in self.states.items():
            if st in ("oneshot", "hold"):
                k = self.key_by_id(kid)
                if k and k.get("key") in CATALOG and CATALOG[k["key"]][0] in CMD_VKS:
                    return True
        return False

    def predict_key(self, k):
        if not self.settings["predict"] or self.edit_mode or k.get("key") == "Shortcut":
            return
        now = time.monotonic()
        fw = self.fg_window()
        if fw != self.pt_fw or now - self.pt_last > IDLE_RESET:
            self.pt.reset()          # switched windows or paused: cursor may have moved
        self.pt_fw, self.pt_last = fw, now
        if self.game_like() or self.cmd_mod_active():
            self.pt.reset()
        else:
            self.pt.feed(k["key"], self.shift_active(), self.caps_on())
        self.update_suggestions()

    def update_suggestions(self):
        items = []
        if self.settings["predict"] and not self.edit_mode and not self.game_like():
            items = self.pt.suggest()
        self.sugg = items
        for i, b in enumerate(self.sbtns):
            b.config(text=items[i][0] if i < len(items) else "")

    def tap(self, name):
        self.sender.send(name, True)
        self.sender.send(name, False)

    def accept_suggestion(self, i):
        if i >= len(self.sugg):
            return
        text = self.sugg[i][0]
        if not text:
            return
        capitalize = self.shift_active() and not self.pt.buffer
        for kid, st in list(self.states.items()):       # injected letters must not be shifted
            k = self.key_by_id(kid)
            if k and k.get("key") in CATALOG and st in ("oneshot", "hold") and CATALOG[k["key"]][0] in SHIFT_VKS:
                self.release_latched(k)
        if capitalize:
            text = text[0].upper() + text[1:]
        for _ in range(len(self.pt.buffer)):
            self.tap("Backspace")
        type_word(self.sender, text, self.caps_on())
        self.tap("Space")
        self.pt_last = time.monotonic()
        self.pt.accept(text)
        self.update_suggestions()

    def forget_suggestion(self, i):
        if i < len(self.sugg):
            self.pt.forget(self.sugg[i][1])
            self.update_suggestions()

    # ---------------- shutdown ----------------
    def on_close(self):
        self.release_all(redraw=False)
        save_settings(self.settings)
        self.pt.save()
        self.root.destroy()


def main():
    if IS_WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        
        # --- ADD THESE 3 LINES HERE ---
        try:
            myappid = "com.keydeck.app.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
        # ------------------------------

    root = tk.Tk()
    KeyDeck(root)
    root.mainloop()


if __name__ == "__main__":
    main()
