from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QUrl, Qt, QCoreApplication
import os

# Simple sound manager using QSoundEffect. Non-blocking, suitable for short effects.
# Place .wav files in `assets/sounds/` (project-relative). Supported names: click, success, error, ding

_sounds = {}
_loaded = False
_sound_paths = {}

def _sound_dir():
    module_dir = os.path.dirname(__file__)
    return os.path.join(module_dir, 'assets', 'sounds')

def _best_key_for_filename(fn):
    # map common keywords in filenames to logical sound keys used by the app
    lname = fn.lower()
    if 'click' in lname or 'tap' in lname or 'press' in lname:
        return 'click'
    if 'success' in lname or 'correct' in lname or 'paid' in lname or 'payment' in lname:
        return 'success'
    if 'error' in lname or 'wrong' in lname or 'fail' in lname:
        return 'error'
    if 'ding' in lname or 'notify' in lname or 'notification' in lname:
        return 'ding'
    if 'receipt' in lname or 'print' in lname:
        return 'ding'
    # fallback: use base name without extension
    return os.path.splitext(fn)[0]

def load_sounds():
    """Preload any .wav files in `assets/sounds/` and map them to keys.
    Files are matched by keyword heuristics; unknown names are available by their basename.
    """
    global _loaded
    # Only attempt to create QSoundEffect instances when a Qt application exists
    if QCoreApplication.instance() is None:
        # Defer loading until a QApplication is running (prevents QEventLoop errors)
        return
    if _loaded:
        return
    _loaded = True
    sdir = _sound_dir()
    try:
        for fn in os.listdir(sdir):
            if not fn.lower().endswith('.wav'):
                continue
            src = os.path.join(sdir, fn)
            try:
                se = QSoundEffect()
                se.setSource(QUrl.fromLocalFile(src))
                se.setLoopCount(1)
                se.setVolume(0.9)
                key = _best_key_for_filename(fn)
                # if key already exists, keep the first mapping but also stash under full basename
                if key not in _sounds:
                    _sounds[key] = se
                # record the filesystem path for duration queries
                if key not in _sound_paths:
                    _sound_paths[key] = src
                # also allow lookup by the base filename (no spaces)
                base_key = os.path.splitext(fn)[0].replace(' ', '_')
                if base_key not in _sounds:
                    _sounds[base_key] = se
                if base_key not in _sound_paths:
                    _sound_paths[base_key] = src
            except Exception:
                continue
    except Exception:
        # sounds folder may not exist yet; ignore
        pass


def play(name):
    """Play a named sound if loaded. Safe no-op if not available."""
    try:
        # try direct lookup first, then sensible fallbacks
        candidates = [name, str(name).replace(' ', '_'), 'click', 'ding', 'success', 'error']
        se = None
        for c in candidates + list(_sounds.keys()):
            se = _sounds.get(c)
            if se is not None:
                break
        if se is not None:
            # restart if already playing
            try:
                if se.isPlaying():
                    se.stop()
            except Exception:
                pass
            se.play()
    except Exception:
        pass


def get_path(name):
    """Return the filesystem path for a loaded sound key or None."""
    try:
        return _sound_paths.get(name) or _sound_paths.get(str(name).replace(' ', '_'))
    except Exception:
        return None


def get_duration(name):
    """Return duration in seconds for the named WAV file, or None if unknown.
    This reads the WAV header directly and does not require a running Qt app.
    """
    p = get_path(name)
    if not p or not p.lower().endswith('.wav'):
        return None
    try:
        import wave
        with wave.open(p, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return frames / float(rate)
    except Exception:
        return None
    return None

# Do not auto-load sounds at import time: loading requires a running Qt application.
