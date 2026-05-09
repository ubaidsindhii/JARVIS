"""
JARVIS (She) — Cyberpunk Edition v5.1
Neon Purple/Pink · Reactor Core UI · All Systems Intact
LLM: Groq · STT: Groq Whisper · TTS: pyttsx3 (offline)
Zero OpenAI dependency — fully free
"""

import tkinter as tk
from tkinter import font as tkfont, messagebox
import threading
import datetime, webbrowser, subprocess, re
import os, sys, math, time, queue, random, json, io, wave
import asyncio, tempfile
import numpy as np
import sounddevice as sd
from groq import Groq
from dotenv import load_dotenv
try:
    from playsound import playsound
    PLAYSOUND_OK = True
except Exception:
    PLAYSOUND_OK = False
try:
    import edge_tts
    EDGE_TTS_OK = True
except Exception:
    EDGE_TTS_OK = False

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SPEAKER_VERIFY = False

def _check_pywhatkit():
    try:
        import pywhatkit
        return True
    except Exception:
        return False

WHATSAPP_OK = _check_pywhatkit()

def _check_tts():
    return EDGE_TTS_OK and PLAYSOUND_OK

TTS_AVAILABLE = _check_tts()

# ── API KEYS ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client  = Groq(api_key=GROQ_API_KEY)

# ── CONFIG ────────────────────────────────────────────────────────────────────
WAKE_WORD      = "jarvis"
GROQ_MODEL     = "llama-3.3-70b-versatile"
WHISPER_MODEL  = "whisper-large-v3"
OWNER_NAME     = "Boss"
CONTACTS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_contacts.json")
WORKSPACE_DIR  = os.path.expanduser("~/JarvisWorkspace")

SAMPLE_RATE       = 16000
SILENCE_THRESHOLD = 0.015
SILENCE_DURATION  = 1.2
MAX_RECORD_SECS   = 10
SPEAKER_DEVICE    = 3

def _auto_detect_mic():
    """Auto-detect the default input device. Returns device index or None (system default)."""
    try:
        devices = sd.query_devices()
        # Try sounddevice's default input first
        default_in = sd.default.device[0]
        if isinstance(default_in, int) and default_in >= 0:
            d = devices[default_in]
            if d['max_input_channels'] > 0:
                print(f"[MIC] Auto-selected: [{default_in}] {d['name']}")
                return default_in
        # Fallback: first device with input channels
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                print(f"[MIC] Fallback: [{i}] {d['name']}")
                return i
    except Exception as e:
        print(f"[MIC] Auto-detect failed: {e}")
    return None  # Let sounddevice use its own default

MIC_DEVICE = 1

SYSTEM_PROMPT = f"""You are JARVIS (Just A Rather Very Intelligent System), an advanced AI assistant with a female persona.
Personality: intelligent, sharp, slightly witty, professional yet warm.
Address the user as "{OWNER_NAME}" occasionally. Keep responses concise, helpful, and sharp.
You run locally in India. Never break character."""

# ── PALETTE  (Stitch-inspired dark teal) ──────────────────────────────────────
BG       = "#111417"   # surface
BG2      = "#1d2024"   # surface-container
BG3      = "#191c20"   # surface-container-low
BG4      = "#272a2e"   # surface-container-high
BG5      = "#0b0e12"   # surface-container-lowest
BG6      = "#323539"   # surface-container-highest
CYAN     = "#00dbe7"   # primary-fixed-dim (main accent)
CYAN2    = "#74f5ff"   # primary-fixed
CYAN3    = "#00f2ff"   # primary-container
WHITE    = "#e1e2e8"   # on-surface
WHITE2   = "#e1fdff"   # primary
OUTLINE  = "#3a494b"   # outline-variant
OUTLINE2 = "#849495"   # outline / muted text
MUTED    = "#b9cacb"   # on-surface-variant
RED      = "#ffb4ab"   # error
GREEN    = "#00ffaa"
GOLD     = "#ffba38"   # tertiary-fixed-dim
PINK     = "#c084fc"   # kept for ring colour variety
# Legacy aliases used in canvas drawing helpers
C1   = CYAN
C2   = CYAN
C3   = OUTLINE
C4   = BG2
GREY = OUTLINE2
GREY2= BG5

def blend(hex_color, alpha):
    h = hex_color.lstrip("#")
    r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f"#{max(0,min(255,int(r*alpha))):02x}{max(0,min(255,int(g*alpha))):02x}{max(0,min(255,int(b*alpha))):02x}"

# ── CONTACTS ──────────────────────────────────────────────────────────────────
def load_contacts():
    if os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE) as f:
            return json.load(f)
    c = {}; save_contacts(c); return c

def save_contacts(contacts):
    with open(CONTACTS_FILE,"w") as f: json.dump(contacts,f,indent=2)

def resolve_contact(name, contacts):
    n = name.lower().strip()
    for k,v in contacts.items():
        if k.lower()==n: return v
    return None

# ── TTS ENGINE (Edge TTS — natural online voices) ────────────────────────────
class TTSEngine:
    VOICE = "en-US-AriaNeural"   # English female — change if preferred

    def __init__(self):
        self._queue    = queue.Queue()
        self._speaking = False
        self._thread   = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            text = self._queue.get()
            if text is None:
                self._queue.task_done()
                break
            try:
                self._speaking = True
                asyncio.run(self._speak_async(text))
            except Exception as e:
                print(f"[TTS ERROR] {e}")
            finally:
                self._speaking = False
                self._queue.task_done()

    async def _speak_async(self, text):
        tmp_path = None
        try:
            communicate = edge_tts.Communicate(text, self.VOICE)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                tmp_path = f.name
            await communicate.save(tmp_path)
            if PLAYSOUND_OK:
                playsound(tmp_path)
        except Exception as e:
            print(f"[TTS ASYNC ERROR] {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except: pass

    def speak(self, text):
        self._queue.put(text)

    def is_speaking(self):
        return self._speaking or not self._queue.empty()

# ── AUDIO RECORDING ───────────────────────────────────────────────────────────
def record_until_silence():
    chunk_size   = int(SAMPLE_RATE * 0.1)
    max_silent   = int(SILENCE_DURATION / 0.1)
    max_chunks   = int(MAX_RECORD_SECS  / 0.1)
    audio_chunks = []
    silent_count = 0
    speaking     = False

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype='float32', device=MIC_DEVICE) as stream:
            for _ in range(max_chunks):
                chunk, _ = stream.read(chunk_size)
                volume   = float(np.abs(chunk).mean())
                if volume > SILENCE_THRESHOLD:
                    speaking     = True
                    silent_count = 0
                    audio_chunks.append(chunk.copy())
                elif speaking:
                    audio_chunks.append(chunk.copy())
                    silent_count += 1
                    if silent_count >= max_silent:
                        break
    except Exception as e:
        print(f"[MIC ERROR] {e}")
        return None

    if not audio_chunks or not speaking:
        return None

    audio_np = np.concatenate(audio_chunks, axis=0)
    wav_buf  = io.BytesIO()
    with wave.open(wav_buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((audio_np * 32767).astype(np.int16).tobytes())
    wav_buf.seek(0)
    wav_buf.name = "audio.wav"
    return wav_buf

def listen_for_wake_word():
    chunk_size = int(SAMPLE_RATE * 0.1)
    max_silent = int(SILENCE_DURATION / 0.1)
    max_chunks = int(MAX_RECORD_SECS  / 0.1)

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype='float32', device=MIC_DEVICE) as stream:
            while True:
                audio_chunks = []
                silent_count = 0
                speaking     = False

                for _ in range(max_chunks):
                    chunk, _ = stream.read(chunk_size)
                    volume   = float(np.abs(chunk).mean())
                    if volume > SILENCE_THRESHOLD:
                        speaking     = True
                        silent_count = 0
                        audio_chunks.append(chunk.copy())
                    elif speaking:
                        audio_chunks.append(chunk.copy())
                        silent_count += 1
                        if silent_count >= max_silent:
                            break

                if not audio_chunks or not speaking:
                    continue

                audio_np = np.concatenate(audio_chunks, axis=0)
                wav_buf  = io.BytesIO()
                with wave.open(wav_buf, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes((audio_np * 32767).astype(np.int16).tobytes())
                wav_buf.seek(0)
                wav_buf.name = "audio.wav"

                try:
                    result = groq_client.audio.transcriptions.create(
                        model=WHISPER_MODEL, file=wav_buf, language="en")
                    text = result.text.strip()
                    if text:
                        return text
                except Exception as e:
                    print(f"[STT ERROR] {e}")
                    continue

    except Exception as e:
        print(f"[MIC LOOP ERROR] {e}")
        return None

# ── FILE COMMANDS ─────────────────────────────────────────────────────────────
def handle_file_command(text):
    t = text.lower().strip()
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    m = re.search(r"(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?file(?:\s+called|\s+named)?\s+([^\s].+?)(?:\s+(?:in|inside|at)\s+.+)?$", t)
    if m:
        name = m.group(1).strip().rstrip(".")
        if "." not in name: name += ".txt"
        open(os.path.join(WORKSPACE_DIR, name), "a").close()
        return f"File '{name}' created."
    m = re.search(r"(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?(?:folder|directory|dir)(?:\s+called|\s+named)?\s+([^\s].+?)$", t)
    if m:
        name = m.group(1).strip().rstrip(".")
        os.makedirs(os.path.join(WORKSPACE_DIR, name), exist_ok=True)
        return f"Folder '{name}' created."
    if any(x in t for x in ["list files","show files","list workspace","files in workspace","show workspace"]):
        items = os.listdir(WORKSPACE_DIR)
        if not items: return "Workspace is empty."
        return "Workspace: " + ", ".join(sorted(items)[:25])
    if "open workspace" in t:
        if sys.platform == "win32": os.startfile(WORKSPACE_DIR)
        else: subprocess.Popen(["xdg-open", WORKSPACE_DIR])
        return "Workspace folder opened."
    return None

# ── WHATSAPP ──────────────────────────────────────────────────────────────────
def handle_whatsapp_command(text, contacts):
    t = text.lower().strip()
    if not any(x in t for x in ["whatsapp","watsapp","whats app"]): return None
    try: import pywhatkit as pwk
    except ImportError: return f"pywhatkit not installed, {OWNER_NAME}."
    patterns = [
        r"(?:message|msg|text|send|tell)\s+([\w\s]+?)\s+on\s+(?:whatsapp|watsapp|whats app)(?:\s+saying|\s+that|\s+with)?\s+(.+)",
        r"send\s+(?:a\s+)?(?:whatsapp|watsapp|whats app)\s+(?:message\s+)?(?:to\s+)?([\w\s]+?)(?:\s+saying|\s+that|\s+with)?\s+(.+)",
    ]
    name, message = None, None
    for pat in patterns:
        m = re.search(pat, t)
        if m: name = m.group(1).strip(); message = m.group(2).strip(); break
    if not name or not message: return f"I need a contact name and message, {OWNER_NAME}."
    phone = resolve_contact(name, contacts)
    if not phone: return f"Contact '{name}' not found."
    if not phone.startswith("+"): phone = "+91" + phone.lstrip("0")
    try:
        pwk.sendwhatmsg_instantly(phone_no=phone, message=message, wait_time=15, tab_close=True, close_time=5)
        return f"WhatsApp message sent to {name.title()}."
    except Exception as e: return f"WhatsApp failed: {str(e)[:80]}"

# ── CONTACT MANAGEMENT ────────────────────────────────────────────────────────
def handle_contact_command(text, contacts):
    t = text.lower().strip()
    m = re.search(r"add\s+(?:contact\s+)?(\w+)\s+(\+?[\d\s\-]{7,})", t)
    if m:
        name   = m.group(1).strip()
        number = re.sub(r"[\s\-]", "", m.group(2).strip())
        if not number.startswith("+"): number = "+91" + number.lstrip("0")
        contacts[name.lower()] = number; save_contacts(contacts)
        return f"Contact '{name.title()}' saved as {number}."
    if any(x in t for x in ["list contacts","show contacts","my contacts"]):
        if not contacts: return "No contacts saved yet."
        return "Contacts: " + ", ".join(f"{k.title()} ({v})" for k,v in contacts.items())
    m = re.search(r"(?:delete|remove)\s+contact\s+(\w+)", t)
    if m:
        name = m.group(1).strip().lower()
        if name in contacts:
            del contacts[name]; save_contacts(contacts)
            return f"Contact '{name.title()}' removed."
        return f"Contact '{name.title()}' not found."
    return None

# ── LOCAL COMMAND ROUTER ──────────────────────────────────────────────────────
def handle_local_command(text, contacts=None):
    if contacts is None: contacts = {}
    t = text.lower().strip()
    if any(w in t for w in ["what time","current time","time now","what's the time"]):
        return f"The time is {datetime.datetime.now().strftime('%I:%M %p')}, {OWNER_NAME}."
    if any(w in t for w in ["what date","today's date","what day","what is today"]):
        return f"Today is {datetime.datetime.now().strftime('%A, %d %B %Y')}."
    cc = handle_contact_command(text, contacts)
    if cc: return cc
    wa = handle_whatsapp_command(text, contacts)
    if wa: return wa
    fc = handle_file_command(text)
    if fc: return fc
    if any(w in t for w in ["open browser","open chrome","launch browser"]):
        webbrowser.open("https://www.google.com")
        return f"Browser launched, {OWNER_NAME}."
    if re.search(r"\bsearch\b.+(google|for)\b|\bgoogle\s+search\b", t):
        q = t
        for r in ["search google for","search for","google search","google"]: q = q.replace(r,"").strip()
        webbrowser.open(f"https://www.google.com/search?q={q.replace(' ','+')}")
        return f"Google search for '{q}' is open."
    if re.search(r"play\s+(?:the\s+)?song\b|play\s+song\b|play\s+me\b|play\s+\w", t):
        song = re.sub(r"play\s+(?:the\s+)?(?:song|me)?\s*", "", t).strip()
        song = re.sub(r"\bon\s+youtube\b|\bfor\s+me\b", "", song).strip()
        if song:
            try:
                import pywhatkit; pywhatkit.playonyt(song)
                return f"Playing '{song}' on YouTube, {OWNER_NAME}."
            except: pass
            webbrowser.open(f"https://www.youtube.com/results?search_query={song.replace(' ','+')}")
            return f"Playing '{song}' on YouTube, {OWNER_NAME}."
    if any(w in t for w in ["open youtube","launch youtube"]):
        webbrowser.open("https://www.youtube.com"); return "YouTube is open."
    if any(w in t for w in ["open notepad","notepad"]):
        subprocess.Popen("notepad.exe" if sys.platform=="win32" else ["gedit"])
        return "Text editor opened."
    if any(w in t for w in ["open calculator","calculator"]):
        subprocess.Popen("calc.exe" if sys.platform=="win32" else ["gnome-calculator"])
        return "Calculator opened."
    if any(w in t for w in ["take a screenshot","screenshot"]):
        try:
            import pyautogui
            path = os.path.join(WORKSPACE_DIR, f"screenshot_{int(time.time())}.png")
            pyautogui.screenshot(path); return "Screenshot saved."
        except ImportError: return "pyautogui not installed."
    if any(w in t for w in ["shutdown","goodbye","bye jarvis","exit","quit","close"]):
        return "__EXIT__"
    # ── Phone call commands ───────────────────────────────────────────────────
    if re.search(r"\b(pick\s*up|answer(\s+the)?\s+call|accept\s+call)\b", t):
        if re.search(r"\bsay\b|\bbusy\b|\btell\b", t):
            return "__ANSWER_SPEAK__"
        return "__ANSWER_CALL__"
    m_reject = re.search(r"\b(decline|reject|hang\s*up|end\s+call|ignore\s+call)\b", t)
    if m_reject:
        busy_msg = ""
        m_msg = re.search(r"(?:say|tell|message|text)\s+(?:him|her|them)?\s*(?:that\s+)?(?:i(?:'m|\s+am)\s+)(.+)", t)
        if m_msg:
            busy_msg = f"I'm {m_msg.group(1).strip()}"
        elif "busy" in t:
            busy_msg = "I'm busy right now, will call you later."
        return f"__REJECT_CALL__{busy_msg}"
    return None


# ── PHONE CALL MONITOR (via ADB) ──────────────────────────────────────────────
# Requirements: Android phone with USB debugging ON + ADB installed on PC.
# Works over USB or wireless ADB (run: adb connect <phone-ip>:5555).
class PhoneCallMonitor:
    IDLE    = 0   # no call
    RINGING = 1   # incoming ringing
    OFFHOOK = 2   # call active

    def answer_and_speak(self, message, tts_engine):
        self.answer_call()
        time.sleep(2.5)          # wait for call to connect
        tts_engine.speak(message)
        while tts_engine.is_speaking():
            time.sleep(0.3)
        time.sleep(0.8)
        self._adb("telecom end-call")

    def __init__(self, app):
        self.app            = app
        self._last_state    = self.IDLE
        self.current_number = ""
        self.current_name   = ""
        self._running       = True
        self._adb_ok        = self._adb_check()
        if self._adb_ok:
            threading.Thread(target=self._poll, daemon=True).start()
        else:
            app.root.after(2000, lambda: app._log_system(
                "Phone monitor: ADB not found or no device. "
                "Connect phone via USB with USB Debugging ON."))

    def _adb_check(self):
        try:
            r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            return "device" in r.stdout
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def _adb(self, cmd_str):
        try:
            r = subprocess.run(["adb", "shell"] + cmd_str.split(),
                               capture_output=True, text=True, timeout=6)
            return r.stdout
        except Exception:
            return ""

    def _get_call_state(self):
        out    = self._adb("dumpsys telephony.registry")
        state  = self.IDLE
        number = ""
        for line in out.splitlines():
            if "mCallState" in line:
                m = re.search(r"mCallState=(\d+)", line)
                if m: state = int(m.group(1))
            if "mCallIncomingNumber" in line:
                m = re.search(r'mCallIncomingNumber="?([^"\s]+)"?', line)
                if m and m.group(1) not in ("null", ""):
                    number = m.group(1)
        return state, number

    def _resolve_name(self, number):
        clean = re.sub(r"[\s\-\+]", "", number)
        for name, num in self.app.contacts.items():
            cnum = re.sub(r"[\s\-\+]", "", num)
            if cnum.endswith(clean[-10:]) or clean.endswith(cnum[-10:]):
                return name.title()
        return number

    def answer_call(self):
        self._adb("telecom accept-ringing-call")   # KEYCODE_CALL

    def reject_call(self, busy_message=""):
        self._adb("telecom end-call")
        if busy_message and self.current_number:
            num = self.current_number
            msg = busy_message.replace('"', '')
            self._adb(f'am start -a android.intent.action.SENDTO '
                      f'-d smsto:{num} --es sms_body "{msg}" --ez exit_on_sent true')

    def _poll(self):
        self.app.root.after(0, lambda: self.app._log_system(
            "Phone monitor: ADB connected. Call detection active."))
        while self._running:
            try:
                state, number = self._get_call_state()
                if state == self.RINGING and self._last_state != self.RINGING:
                    self.current_number = number
                    caller = self._resolve_name(number) if number else "Unknown number"
                    self.current_name   = caller
                    msg = (f"Incoming call from {caller}. "
                           f"Say 'pick up' to answer or 'decline' to reject.")
                    self.app.root.after(0, lambda m=msg: self.app._log_system(m))
                    self.app.tts.speak(
                        f"Incoming call from {caller}, {OWNER_NAME}.")
                    self.app.root.after(0, lambda: self.app.set_state("LISTENING"))
                elif state == self.IDLE and self._last_state == self.RINGING:
                    self.current_number = ""
                    self.current_name   = ""
                    self.app.root.after(0, lambda: self.app.set_state("IDLE"))
                self._last_state = state
            except Exception:
                pass
            time.sleep(1.5)

    def stop(self):
        self._running = False


# ── LLM — GROQ ────────────────────────────────────────────────────────────────
def ask_groq(prompt, history, on_token=None):
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs.extend(history[-6:])
    msgs.append({"role": "user", "content": prompt})
    try:
        full   = ""
        stream = groq_client.chat.completions.create(
            model=GROQ_MODEL, messages=msgs, stream=True, max_tokens=512, temperature=0.7)
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            full += token
            if on_token and token:
                on_token(token)
        return full.strip()
    except Exception as e:
        return f"Neural network offline, {OWNER_NAME}. Error: {str(e)[:80]}"

# ── MAIN APP ──────────────────────────────────────────────────────────────────
class JarvisApp:
    def __init__(self, root):
        self.root     = root
        self.tts      = TTSEngine()
        self.contacts = load_contacts()
        self.history  = []
        self.state    = "IDLE"
        self.running  = True

        self._t            = 0.0
        self._rot1         = 0.0
        self._rot2         = 0.0
        self._rot3         = 0.0
        self._mic_wave     = [0.0]*50
        self._core_glow    = 0.0
        self._core_target  = 0.3
        self._net_data     = [random.uniform(0.1,0.5) for _ in range(30)]
        self._mini_data    = [random.uniform(0.3,0.7) for _ in range(30)]
        self._msg_count    = 0
        self._start_time   = time.time()
        self._net_speed    = {"up":"0.0","dn":"0.0"}
        self._weather_info = {"temp":"28°C","cond":"CLEAR"}
        self._particles    = []

        self._build_ui()
        self._init_particles()
        self._animate()
        self._start_listener()
        self._start_weather_updater()
        self.phone_monitor = PhoneCallMonitor(self)  # ADB call detection

        greeting = self._greeting()
        self._log_jarvis(greeting)
        threading.Thread(target=self.tts.speak, args=(greeting,), daemon=True).start()
        self.root.after(2500, lambda: self._log_system(
            "STT: Groq Whisper  ·  TTS: Edge TTS  ·  LLM: Groq  ·  No OpenAI needed"))

    def _greeting(self):
        h    = datetime.datetime.now().hour
        part = "morning" if h<12 else "afternoon" if h<17 else "evening"
        return f"Good {part}, {OWNER_NAME}. All systems nominal. Groq online. Ready."

    def _build_ui(self):
        self.root.title("J.A.R.V.I.S  (She)  v5.1  |  System Dashboard")
        self.root.geometry("1440x900")
        self.root.minsize(1200,750)
        self.root.configure(bg=BG)

        self.fn_tiny  = tkfont.Font(family="Courier New", size=7,  weight="bold")
        self.fn_small = tkfont.Font(family="Courier New", size=9)
        self.fn_mono  = tkfont.Font(family="Courier New", size=10)
        self.fn_med   = tkfont.Font(family="Courier New", size=11, weight="bold")
        self.fn_big   = tkfont.Font(family="Courier New", size=13, weight="bold")
        self.fn_label = tkfont.Font(family="Courier New", size=8,  weight="bold")

        # ── TOP BAR ──────────────────────────────────────────────────────────
        self.topbar = tk.Frame(self.root, bg=BG4, height=72)
        self.topbar.pack(fill=tk.X, side=tk.TOP)
        self.topbar.pack_propagate(False)

        logo_f = tk.Frame(self.topbar, bg=BG4)
        logo_f.pack(side=tk.LEFT, padx=16, pady=10)
        icon_c = tk.Canvas(logo_f, width=48, height=48, bg=BG4,
                           highlightthickness=2, highlightbackground=CYAN3)
        icon_c.pack(side=tk.LEFT, padx=(0,10))
        icon_c.create_oval(6,6,42,42, outline=CYAN, width=1)
        icon_c.create_text(24,24, text="⬡", font=("Courier New",18,"bold"), fill=CYAN)
        title_f = tk.Frame(logo_f, bg=BG4)
        title_f.pack(side=tk.LEFT)
        tk.Label(title_f, text="J.A.R.V.I.S (She) v5.1",
                 font=self.fn_big, fg=WHITE2, bg=BG4).pack(anchor="w")
        tk.Label(title_f, text="JUST A RATHER VERY INTELLIGENT SYSTEM",
                 font=self.fn_label, fg=OUTLINE2, bg=BG4).pack(anchor="w")

        # status pill (centre)
        self._status_var = tk.StringVar(value="STANDBY")
        status_f = tk.Frame(self.topbar, bg=BG5, padx=14, pady=6,
                            highlightthickness=1, highlightbackground=blend(CYAN,0.3))
        status_f.pack(side=tk.LEFT, expand=True, padx=60)
        tk.Label(status_f, text="AI STATUS", font=self.fn_label,
                 fg=OUTLINE2, bg=BG5).pack(side=tk.LEFT, padx=(0,8))
        self._status_dot_c = tk.Canvas(status_f, width=10, height=10,
                                       bg=BG5, highlightthickness=0)
        self._status_dot_c.pack(side=tk.LEFT)
        self._status_dot_c.create_oval(1,1,9,9, fill=CYAN, outline="", tags="dot")
        self._status_lbl = tk.Label(status_f, textvariable=self._status_var,
                                    font=self.fn_med, fg=CYAN, bg=BG5)
        self._status_lbl.pack(side=tk.LEFT, padx=(6,14))
        # mini waveform bars
        for h_val, opacity in [(5,.3),(10,.5),(16,.8),(4,.2)]:
            bar_c = tk.Canvas(status_f, width=5, height=16, bg=BG5, highlightthickness=0)
            bar_c.pack(side=tk.LEFT, padx=1)
            col = blend(CYAN, opacity)
            bar_c.create_rectangle(0, 16-h_val, 5, 16, fill=col, outline="")

        # right: model info + clock
        right_top = tk.Frame(self.topbar, bg=BG4)
        right_top.pack(side=tk.RIGHT, padx=16)
        info_f = tk.Frame(right_top, bg=BG4)
        info_f.pack(side=tk.LEFT, padx=(0,14))
        for row, (lbl, val) in enumerate([("GROQ LLM","llama-3.3-70b"),("WHISPER STT","large-v3")]):
            tk.Label(info_f, text=lbl, font=self.fn_label, fg=OUTLINE2,
                     bg=BG4).grid(row=0, column=row*2, sticky="e", padx=(0,4))
            tk.Label(info_f, text=val, font=self.fn_small, fg=CYAN,
                     bg=BG4).grid(row=1, column=row*2, sticky="e", padx=(0,4))
            if row == 0:
                tk.Label(info_f, text="⚙", font=("Courier New",14),
                         fg=OUTLINE2, bg=BG4).grid(row=0, column=1, rowspan=2, padx=6)
        tk.Frame(right_top, bg=OUTLINE, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8, padx=8)
        clock_f = tk.Frame(right_top, bg=BG4)
        clock_f.pack(side=tk.LEFT)
        self._clock_lbl = tk.Label(clock_f, text="00:00:00",
                                   font=self.fn_big, fg=CYAN, bg=BG4)
        self._clock_lbl.pack(anchor="e")
        self._date_lbl  = tk.Label(clock_f, text="",
                                   font=self.fn_label, fg=OUTLINE2, bg=BG4)
        self._date_lbl.pack(anchor="e")

        tk.Frame(self.root, bg=OUTLINE, height=1).pack(fill=tk.X)

        # ── MAIN AREA ────────────────────────────────────────────────────────
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill=tk.BOTH, expand=True)

        # LEFT SIDEBAR
        self.left_panel = tk.Frame(main, bg=BG, width=286)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)
        tk.Frame(main, bg=OUTLINE, width=1).pack(side=tk.LEFT, fill=tk.Y)
        self._build_left_sidebar(self.left_panel)

        # RIGHT PANEL  — pack before center so center gets expand
        self.right_panel = tk.Frame(main, bg=BG3, width=340)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)
        tk.Frame(main, bg=OUTLINE, width=1).pack(side=tk.RIGHT, fill=tk.Y)
        self._build_right_panel(self.right_panel)

        # CENTER (reactor canvas + command bar)
        center_frame = tk.Frame(main, bg=BG5,
                                highlightthickness=1, highlightbackground=blend(CYAN,0.15))
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.center_hud = tk.Canvas(center_frame, bg=BG5, highlightthickness=0)
        self.center_hud.pack(fill=tk.BOTH, expand=True)
        self._build_command_bar(center_frame)

        tk.Frame(self.root, bg=OUTLINE, height=1).pack(fill=tk.X)
        self._build_footer()
        self._update_clock()

    # ── LEFT SIDEBAR ─────────────────────────────────────────────────────────
    def _build_left_sidebar(self, parent):
        pad = {"padx":6,"pady":3,"fill":tk.X}

        def section(bg_color=BG3, bd_color=OUTLINE):
            f = tk.Frame(parent, bg=bg_color, highlightthickness=1,
                         highlightbackground=bd_color)
            f.pack(fill=tk.X, padx=6, pady=3)
            return f

        def sec_header(parent_f, icon, title):
            hdr = tk.Frame(parent_f, bg=parent_f["bg"])
            hdr.pack(fill=tk.X, padx=10, pady=(8,4))
            tk.Label(hdr, text=icon, font=("Courier New",11), fg=CYAN,
                     bg=parent_f["bg"]).pack(side=tk.LEFT)
            tk.Label(hdr, text=title, font=self.fn_label, fg=WHITE,
                     bg=parent_f["bg"]).pack(side=tk.LEFT, padx=6)
            tk.Frame(parent_f, bg=OUTLINE, height=1).pack(fill=tk.X, padx=10, pady=(0,6))

        # ── Telemetry ──
        tel_f = section()
        sec_header(tel_f, "◉", "TELEMETRY")
        self._tele_bars = {}
        for key, label, pct in [("cpu","CPU Usage",32),("ram","RAM Usage",61),("temp","Temperature",48)]:
            row = tk.Frame(tel_f, bg=BG3)
            row.pack(fill=tk.X, padx=10, pady=(0,6))
            top = tk.Frame(row, bg=BG3)
            top.pack(fill=tk.X)
            tk.Label(top, text=label, font=self.fn_label, fg=MUTED, bg=BG3).pack(side=tk.LEFT)
            val_lbl = tk.Label(top, text=f"{pct}{'°C' if key=='temp' else '%'}",
                               font=self.fn_label, fg=CYAN, bg=BG3)
            val_lbl.pack(side=tk.RIGHT)
            track = tk.Canvas(row, height=5, bg=BG6, highlightthickness=0)
            track.pack(fill=tk.X, pady=(2,0))
            fill_w = int((track.winfo_reqwidth() or 260) * pct/100)
            bar_id = track.create_rectangle(0,0,fill_w,5, fill=CYAN, outline="")
            self._tele_bars[key] = {"lbl":val_lbl,"track":track,"bar":bar_id,"pct":pct}
        tk.Frame(tel_f, height=4, bg=BG3).pack()

        # ── AI Metrics ──
        ai_f = section()
        sec_header(ai_f, "⚙", "AI METRICS")
        metrics = [("LLM Provider","Groq"),("Active Model","llama-3.3-70b"),
                   ("STT Engine","Whisper-v3"),("TTS Status","Edge TTS")]
        grid_f = tk.Frame(ai_f, bg=BG3)
        grid_f.pack(fill=tk.X, padx=10, pady=(0,8))
        for i,(k,v) in enumerate(metrics):
            if k == "TTS Status":
                col = GREEN if TTS_AVAILABLE else RED
                v   = "Edge TTS ✓" if TTS_AVAILABLE else "Edge TTS ✗"
            else:
                col = WHITE
            tk.Label(grid_f, text=k, font=self.fn_label, fg=OUTLINE2,
                     bg=BG3).grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(grid_f, text=v, font=self.fn_label, fg=col,
                     bg=BG3).grid(row=i, column=1, sticky="e", pady=2)
            grid_f.columnconfigure(0, weight=1)
            grid_f.columnconfigure(1, weight=1)

        # ── Weather ──
        wx_f = section()
        sec_header(wx_f, "☁", "WEATHER")
        wx_body = tk.Frame(wx_f, bg=BG3)
        wx_body.pack(fill=tk.X, padx=10, pady=(0,4))
        wx_left = tk.Frame(wx_body, bg=BG3)
        wx_left.pack(side=tk.LEFT)
        tk.Label(wx_left, text="Ahmedabad, IN", font=self.fn_label, fg=MUTED, bg=BG3).pack(anchor="w")
        self._wx_temp_lbl = tk.Label(wx_left, text=self._weather_info["temp"],
                                     font=("Courier New",22,"bold"), fg=CYAN, bg=BG3)
        self._wx_temp_lbl.pack(anchor="w")
        self._wx_cond_lbl = tk.Label(wx_left, text=self._weather_info["cond"],
                                     font=self.fn_label, fg=OUTLINE2, bg=BG3)
        self._wx_cond_lbl.pack(anchor="w")
        tk.Label(wx_body, text="🌤", font=("Arial",32), bg=BG3).pack(side=tk.RIGHT)
        tk.Frame(wx_f, bg=OUTLINE, height=1).pack(fill=tk.X, padx=10, pady=4)
        wx_grid = tk.Frame(wx_f, bg=BG3)
        wx_grid.pack(fill=tk.X, padx=10, pady=(0,8))
        for col_i,(lbl,val) in enumerate([("Humidity","44%"),("Wind","18km/h"),("Feels Like","37°C")]):
            cf = tk.Frame(wx_grid, bg=BG3)
            cf.grid(row=0, column=col_i, sticky="nsew")
            wx_grid.columnconfigure(col_i, weight=1)
            tk.Label(cf, text=lbl, font=self.fn_label, fg=OUTLINE2, bg=BG3).pack()
            tk.Label(cf, text=val, font=self.fn_label, fg=WHITE,   bg=BG3).pack()

        # ── Audio Input (mic waveform) ──
        mic_f = tk.Frame(parent, bg=BG5, highlightthickness=2,
                         highlightbackground=blend(CYAN,0.2))
        mic_f.pack(fill=tk.X, padx=6, pady=3, side=tk.BOTTOM)
        mic_inner = tk.Frame(mic_f, bg=BG5)
        mic_inner.pack(fill=tk.X, padx=10, pady=8)
        mic_icon_f = tk.Frame(mic_inner, bg=BG5)
        mic_icon_f.pack(side=tk.LEFT, padx=(0,8))
        mic_ring = tk.Canvas(mic_icon_f, width=36, height=36, bg=BG5, highlightthickness=1,
                             highlightbackground=CYAN)
        mic_ring.pack()
        mic_ring.create_oval(3,3,33,33, outline=CYAN, width=0)
        mic_ring.create_text(18,18, text="🎙", font=("Arial",14))
        mic_right = tk.Frame(mic_inner, bg=BG5)
        mic_right.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(mic_right, text="AUDIO INPUT STREAM", font=self.fn_label,
                 fg=OUTLINE2, bg=BG5).pack(anchor="w")
        self.mic_canvas = tk.Canvas(mic_right, height=28, bg=BG5, highlightthickness=0)
        self.mic_canvas.pack(fill=tk.X, pady=(3,0))

    # ── RIGHT PANEL (conversation terminal) ──────────────────────────────────
    def _build_right_panel(self, parent):
        # header
        hdr = tk.Frame(parent, bg=BG3,
                       highlightthickness=0)
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=OUTLINE, height=1).pack(fill=tk.X, side=tk.BOTTOM)
        hdr_inner = tk.Frame(hdr, bg=BG3)
        hdr_inner.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(hdr_inner, text="💬  CONVERSATION TERMINAL",
                 font=self.fn_label, fg=WHITE, bg=BG3).pack(side=tk.LEFT)
        online_f = tk.Frame(hdr_inner, bg=BG3)
        online_f.pack(side=tk.RIGHT)
        online_dot = tk.Canvas(online_f, width=8, height=8, bg=BG3, highlightthickness=0)
        online_dot.pack(side=tk.LEFT)
        online_dot.create_oval(1,1,7,7, fill=CYAN, outline="")
        tk.Label(online_f, text="ONLINE", font=self.fn_label,
                 fg=CYAN, bg=BG3).pack(side=tk.LEFT, padx=(4,0))

        # chat log
        log_frame = tk.Frame(parent, bg=BG3)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(log_frame, bg=BG3, fg=WHITE, font=self.fn_mono,
                           wrap=tk.WORD, relief=tk.FLAT, padx=12, pady=10,
                           state=tk.DISABLED, cursor="arrow",
                           insertbackground=CYAN, selectbackground=blend(CYAN,0.3),
                           spacing1=2, spacing2=1, spacing3=8)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(log_frame, command=self.log.yview,
                          bg=BG4, troughcolor=BG4, activebackground=CYAN, width=4)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.configure(yscrollcommand=sb.set)

        # text tags
        tag_defs = {
            "you_label":  {"foreground": GOLD,              "font": self.fn_label},
            "you_body":   {"foreground": WHITE,             "font": self.fn_mono,  "lmargin1":16,"lmargin2":16},
            "ja_label":   {"foreground": blend(GOLD,0.65),  "font": self.fn_label},
            "ja_body":    {"foreground": CYAN,              "font": self.fn_mono,  "lmargin1":16,"lmargin2":16},
            "sys_label":  {"foreground": GOLD,              "font": self.fn_label},
            "sys_body":   {"foreground": GOLD,              "font": self.fn_label, "lmargin1":16,"lmargin2":16},
            "warn_body":  {"foreground": RED,               "font": self.fn_label, "lmargin1":16,"lmargin2":16},
            "divider":    {"foreground": OUTLINE,           "font": self.fn_label},
            "timestamp":  {"foreground": OUTLINE2,          "font": self.fn_label},
            "stream":     {"foreground": CYAN,              "font": self.fn_mono,  "lmargin1":16,"lmargin2":16},
            "syslog_bar": {"background": blend(CYAN,0.06),  "font": self.fn_label},
        }
        for tag, cfg in tag_defs.items():
            self.log.tag_config(tag, **cfg)

        # input bar
        tk.Frame(parent, bg=OUTLINE, height=1).pack(fill=tk.X)
        inp_f = tk.Frame(parent, bg=BG4, pady=8, padx=10)
        inp_f.pack(fill=tk.X)
        self.entry = tk.Entry(inp_f, bg=BG3, fg=WHITE, font=self.fn_mono,
                              relief=tk.FLAT, insertbackground=CYAN,
                              highlightthickness=0)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.entry.bind("<Return>", self._on_submit)
        self.entry.insert(0, "Type command...")
        self.entry.bind("<FocusIn>",  lambda e: self.entry.delete(0,tk.END) if self.entry.get()=="Type command..." else None)
        self.entry.bind("<FocusOut>", lambda e: self.entry.insert(0,"Type command...") if not self.entry.get() else None)
        self.entry.focus_set()
        send_btn = tk.Button(inp_f, text="➤", font=self.fn_med,
                             fg=CYAN, bg=BG4, relief=tk.FLAT,
                             activebackground=BG4, activeforeground=WHITE,
                             cursor="hand2", bd=0, command=self._on_submit)
        send_btn.pack(side=tk.RIGHT, padx=(6,0))

    # ── COMMAND BAR (below reactor canvas) ───────────────────────────────────
    def _build_command_bar(self, parent):
        tk.Frame(parent, bg=OUTLINE, height=1).pack(fill=tk.X)
        cmd_f = tk.Frame(parent, bg=BG4, pady=10, padx=14)
        cmd_f.pack(fill=tk.X)
        cmd_row = tk.Frame(cmd_f, bg=BG4)
        cmd_row.pack(fill=tk.X)
        tk.Label(cmd_row, text="⬛", font=("Courier New",12), fg=blend(CYAN,0.4),
                 bg=BG4).pack(side=tk.LEFT, padx=(0,6))
        self.cmd_entry = tk.Entry(cmd_row, bg=BG5, fg=WHITE, font=self.fn_mono,
                                  relief=tk.FLAT, insertbackground=CYAN,
                                  highlightthickness=1, highlightbackground=blend(CYAN,0.3),
                                  highlightcolor=CYAN)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        self.cmd_entry.insert(0,"ENTER SYSTEM COMMAND...")
        self.cmd_entry.bind("<FocusIn>",  lambda e: self.cmd_entry.delete(0,tk.END) if self.cmd_entry.get()=="ENTER SYSTEM COMMAND..." else None)
        self.cmd_entry.bind("<FocusOut>", lambda e: self.cmd_entry.insert(0,"ENTER SYSTEM COMMAND...") if not self.cmd_entry.get() else None)
        self.cmd_entry.bind("<Return>", self._on_cmd_submit)
        exec_btn = tk.Button(cmd_row, text="EXECUTE ▶", font=self.fn_label,
                             fg=BG, bg=CYAN, relief=tk.FLAT,
                             activebackground=CYAN2, activeforeground=BG,
                             cursor="hand2", bd=0, padx=16, pady=8,
                             command=self._on_cmd_submit)
        exec_btn.pack(side=tk.RIGHT, padx=(8,0))

        # status strip
        status_row = tk.Frame(cmd_f, bg=BG4)
        status_row.pack(fill=tk.X, pady=(6,0))
        self._cmd_status_lbl = tk.Label(status_row,
            text=f"CURRENT STATUS: STANDBY   |   ACTIVE MODEL: {GROQ_MODEL.upper()[:24]}",
            font=self.fn_label, fg=OUTLINE2, bg=BG4)
        self._cmd_status_lbl.pack(side=tk.LEFT)
        tk.Label(status_row, text="SYSTEM ID: JARVIS-V5.1-0XFA4",
                 font=self.fn_label, fg=OUTLINE2, bg=BG4).pack(side=tk.RIGHT)

        # quick buttons
        tk.Frame(parent, bg=OUTLINE, height=1).pack(fill=tk.X)
        quick_f = tk.Frame(parent, bg=BG4, pady=5, padx=14)
        quick_f.pack(fill=tk.X)
        tk.Label(quick_f, text="QUICK:", font=self.fn_label, fg=OUTLINE2, bg=BG4).pack(side=tk.LEFT)
        for lbl, cmd in [("TIME","what time is it"),("DATE","what's today's date"),
                         ("YT","open youtube"),("CALC","open calculator"),
                         ("FILES","list files"),("CONTACTS","list contacts"),("EXIT","goodbye jarvis")]:
            tk.Button(quick_f, text=lbl, font=self.fn_label, fg=CYAN, bg=BG5,
                      relief=tk.FLAT, padx=8, pady=3, cursor="hand2", bd=0,
                      activebackground=BG6, activeforeground=CYAN2,
                      command=lambda c=cmd: self._quick_cmd(c)).pack(side=tk.LEFT, padx=3)

    # ── FOOTER ───────────────────────────────────────────────────────────────
    def _build_footer(self):
        footer = tk.Frame(self.root, bg=BG6, height=106)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # launcher icons row
        launcher_f = tk.Frame(footer, bg=BG6)
        launcher_f.pack(fill=tk.X, pady=(6,0))

        launch_items = [
            ("🌐","CHROME",   False, lambda: webbrowser.open("https://www.google.com")),
            ("▶","YOUTUBE",  False, lambda: webbrowser.open("https://www.youtube.com")),
            ("📝","NOTEPAD",  False, lambda: subprocess.Popen("notepad.exe" if sys.platform=="win32" else ["gedit"])),
            ("🔢","CALC",    False, lambda: subprocess.Popen("calc.exe" if sys.platform=="win32" else ["gnome-calculator"])),
            ("📁","FILES",   False, lambda: os.startfile(WORKSPACE_DIR) if sys.platform=="win32" else subprocess.Popen(["xdg-open",WORKSPACE_DIR])),
            ("⏻","EXIT",     True,  lambda: self._quick_cmd("goodbye jarvis")),
        ]
        for icon, label, danger, cmd in launch_items:
            btn_f = tk.Frame(launcher_f, bg=BG6)
            btn_f.pack(side=tk.LEFT, expand=True)
            bg_c  = blend(RED,0.1) if danger else BG3
            bd_c  = blend(RED,0.3) if danger else OUTLINE
            fg_c  = RED            if danger else CYAN
            btn = tk.Button(btn_f, text=icon, font=("Arial",16),
                            fg=fg_c, bg=bg_c, relief=tk.FLAT,
                            activebackground=blend(CYAN,0.15), activeforeground=CYAN2,
                            cursor="hand2", bd=0, width=3, height=1,
                            highlightthickness=1, highlightbackground=bd_c,
                            command=cmd)
            btn.pack()
            lbl_w = tk.Label(btn_f, text=label, font=self.fn_label,
                             fg=fg_c, bg=BG6)
            lbl_w.pack()
            lbl_w.config(fg=blend(fg_c,0.0))  # hidden initially
            def _enter(e, lw=lbl_w, fc=fg_c): lw.config(fg=fc)
            def _leave(e, lw=lbl_w, fc=fg_c): lw.config(fg=blend(fc,0.0))
            btn_f.bind("<Enter>", _enter)
            btn.bind("<Enter>", _enter)
            btn_f.bind("<Leave>", _leave)
            btn.bind("<Leave>", _leave)

        # status strip
        tk.Frame(footer, bg=OUTLINE, height=1).pack(fill=tk.X)
        strip = tk.Frame(footer, bg=BG5)
        strip.pack(fill=tk.X, ipady=4)
        left_s = tk.Frame(strip, bg=BG5)
        left_s.pack(side=tk.LEFT, padx=12)
        self._wake_lbl   = tk.Label(left_s, text=f'🎙 WAKE WORD: {WAKE_WORD.upper()}',
                                    font=self.fn_label, fg=OUTLINE2, bg=BG5)
        self._wake_lbl.pack(side=tk.LEFT, padx=(0,16))
        self._msgs_lbl   = tk.Label(left_s, text="✉ MESSAGES: 0",
                                    font=self.fn_label, fg=OUTLINE2, bg=BG5)
        self._msgs_lbl.pack(side=tk.LEFT)

        right_s = tk.Frame(strip, bg=BG5)
        right_s.pack(side=tk.RIGHT, padx=12)
        self._uptime_lbl = tk.Label(right_s, text="⟳ UPTIME: 00:00:00",
                                    font=self.fn_label, fg=OUTLINE2, bg=BG5)
        self._uptime_lbl.pack(side=tk.LEFT, padx=(0,16))
        self._net_lbl    = tk.Label(right_s, text="⇅ NETWORK: ↓ 0.0 KB/s",
                                    font=self.fn_label, fg=OUTLINE2, bg=BG5)
        self._net_lbl.pack(side=tk.LEFT, padx=(0,16))
        self._cost_lbl   = tk.Label(right_s, text="💰 COST: FREE ✓",
                                    font=self.fn_label, fg=CYAN, bg=BG5)
        self._cost_lbl.pack(side=tk.LEFT)

    # ── CLOCK / STATUS UPDATE ─────────────────────────────────────────────────
    def _update_clock(self):
        now = datetime.datetime.now()
        self._clock_lbl.config(text=now.strftime("%H:%M:%S"))
        self._date_lbl.config(text=now.strftime("%A, %d %B %Y").upper())
        self._uptime_lbl.config(text=f"⟳ UPTIME: {self._uptime()}")
        self._msgs_lbl.config(text=f"✉ MESSAGES: {self._msg_count}")
        dn = f"{random.uniform(10,120):.1f}"
        self._net_lbl.config(text=f"⇅ NETWORK: ↓ {dn} KB/s")
        # update weather labels
        self._wx_temp_lbl.config(text=self._weather_info["temp"])
        self._wx_cond_lbl.config(text=self._weather_info["cond"])
        # update telemetry bars every tick
        self._update_tele_bars()
        self.root.after(1000, self._update_clock)

    def _update_tele_bars(self):
        vals = {
            "cpu":  (20 + int(8*math.sin(self._t*1.3)), "%"),
            "ram":  (68 + int(3*math.sin(self._t*0.7)), "%"),
            "temp": (42 + int(2*math.sin(self._t*0.5)), "°C"),
        }
        for key,(pct,unit) in vals.items():
            info = self._tele_bars[key]
            info["lbl"].config(text=f"{pct}{unit}")
            info["pct"] = pct
            track = info["track"]
            track.update_idletasks()
            w = track.winfo_width() or 260
            filled = int(w * min(pct,100)/100)
            track.delete("all")
            track.create_rectangle(0,0,w,5,   fill=BG6,  outline="")
            track.create_rectangle(0,0,filled,5, fill=CYAN, outline="")


    # ── ANIMATION (reactor core on canvas) ────────────────────────────────────
    def _init_particles(self):
        self._particles = []  # not used in new UI but kept for compat

    def _start_weather_updater(self):
        def _update():
            while self.running:
                self._weather_info["temp"] = f"{28+random.randint(-1,2)}°C"
                self._weather_info["cond"] = random.choice(["CLEAR","PARTLY CLOUDY","HUMID","HAZY"])
                time.sleep(30)
        threading.Thread(target=_update, daemon=True).start()

    def _animate(self):
        if not self.running: return
        self._t += 0.03; t = self._t
        s1,s2,s3 = {"LISTENING":(1.4,-1.0,0.7),"THINKING":(0.7,-1.4,1.1),
                     "SPEAKING":(1.1,-0.6,1.8)}.get(self.state,(0.35,-0.25,0.15))
        self._rot1 += s1; self._rot2 += s2; self._rot3 += s3
        self._core_target = 1.0 if self.state in ("SPEAKING","LISTENING") else \
                            0.5+0.5*abs(math.sin(t*3)) if self.state=="THINKING" else 0.35
        self._core_glow += (self._core_target - self._core_glow) * 0.1
        nv = random.uniform(0.3,1.0) if self.state=="LISTENING" else \
             0.35+0.55*abs(math.sin(t*8+random.uniform(-0.2,0.2))) if self.state=="SPEAKING" else \
             random.uniform(0.02,0.07)
        self._mic_wave.append(nv); self._mic_wave.pop(0)
        self._net_data.append(random.uniform(0.1,0.9)); self._net_data.pop(0)
        self._net_speed["dn"] = f"{random.uniform(0.5,8.5):.1f}"
        self._net_speed["up"] = f"{random.uniform(0.1,2.0):.1f}"
        self._draw_center_hud(t)
        self._draw_mic_wave()
        self.root.after(33, self._animate)

    def _sc(self):
        return {"IDLE":CYAN,"LISTENING":CYAN2,"THINKING":GOLD,"SPEAKING":CYAN3}.get(self.state,CYAN)

    def _draw_mic_wave(self):
        try:
            c = self.mic_canvas
            c.delete("all")
            w = c.winfo_width() or 240
            h = c.winfo_height() or 28
            data = self._mic_wave[-40:]
            n = len(data)
            if n < 2: return
            pts = []
            for i, v in enumerate(data):
                x = int(i * w / (n-1))
                y = int(h//2 + (v-0.5)*(h-4))
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(*pts, fill=CYAN, width=1, smooth=True)
        except Exception:
            pass

    def _draw_center_hud(self, t):
        try:
            c = self.center_hud; c.delete("all")
        except Exception:
            return
        W = c.winfo_width()  or 700
        H = c.winfo_height() or 500
        sc = self._sc()
        c.create_rectangle(0,0,W,H, fill=BG5, outline="")

        # dot grid
        for gx in range(0,W,28):
            for gy in range(0,H,28):
                d = math.sqrt((gx-W//2)**2+(gy-H//2)**2)
                a = max(0.04, 0.18-d/900)
                col = blend(OUTLINE,a*4)
                c.create_oval(gx-1,gy-1,gx+1,gy+1, fill=col, outline="")

        cx, cy = W//2, H//2 - 20

        # subtle glow halos
        for r,a in [(200,0.01),(175,0.02),(155,0.035)]:
            c.create_oval(cx-r,cy-r,cx+r,cy+r, fill=blend(sc,a), outline="")

        # tick ring
        R_tick = 155
        c.create_oval(cx-R_tick,cy-R_tick,cx+R_tick,cy+R_tick,
                      outline=blend(sc,0.15), width=1)
        for i in range(120):
            ang = math.radians(i*3)
            if   i%30==0: r1,r2,lw,la = R_tick-14,R_tick,2,0.8
            elif i%10==0: r1,r2,lw,la = R_tick-9, R_tick,1,0.5
            elif i%5==0:  r1,r2,lw,la = R_tick-5, R_tick,1,0.3
            else:          r1,r2,lw,la = R_tick-2, R_tick,1,0.1
            c.create_line(cx+r1*math.cos(ang),cy+r1*math.sin(ang),
                          cx+r2*math.cos(ang),cy+r2*math.sin(ang),
                          fill=blend(sc,la), width=lw)

        # spinning rings
        for R,n,ext_big,ext_small,col_big,col_small,w_big in [
            (135, 10, 22, 7,  sc,         blend(sc,0.35),   3),
            (110, 8,  30, 9,  CYAN2,      blend(CYAN2,0.3), 2),
            (88,  6,  38, 38, blend(sc,0.6), blend(sc,0.18),2)]:
            for i in range(n):
                ang_s = (self._rot1 if R==135 else self._rot2 if R==110 else self._rot3*2)+i*(360//n)
                ext = ext_big if i%2==0 else ext_small
                col = col_big if i%2==0 else col_small
                lw  = w_big  if i%2==0 else 1
                c.create_arc(cx-R,cy-R,cx+R,cy+R,
                             start=ang_s, extent=ext, outline=col, width=lw, style=tk.ARC)

        # inner square (rotated) + spoke lines
        sq = 56
        for i in range(8):
            ang = math.radians(i*45 + self._rot1*0.15)
            r1=60; r2=88+4*math.sin(t*2+i)
            c.create_line(cx+r1*math.cos(ang),cy+r1*math.sin(ang),
                          cx+r2*math.cos(ang),cy+r2*math.sin(ang),
                          fill=blend(sc,0.3), width=1)
        for r,lw in [(sq,2),(sq-12,1)]:
            ang45 = math.radians(45+self._rot1*0.25)
            pts = []
            for i in range(4):
                a = ang45 + i*math.pi/2
                pts.extend([cx+r*math.cos(a), cy+r*math.sin(a)])
            c.create_polygon(pts, outline=blend(sc,0.5), fill="", width=lw)

        # pulsing core glow
        glow = self._core_glow; pulse = 0.88+0.12*math.sin(t*4)
        for r,a in [(24,0.04*glow),(18,0.09*glow),(13,0.18*glow),(9,0.35*glow),(6,0.6*glow),(3,0.9*glow)]:
            c.create_oval(cx-r,cy-r,cx+r,cy+r, fill=blend(sc,a*pulse), outline="")
        c.create_oval(cx-3,cy-3,cx+3,cy+3, fill=sc, outline="")

        # floating data labels
        def float_label(x,y,title,val,anchor="w"):
            c.create_text(x,y,   text=title, font=self.fn_label, fill=OUTLINE2, anchor=anchor)
            c.create_text(x,y+16,text=val,   font=("Courier New",16,"bold"), fill=sc, anchor=anchor)

        float_label(cx-W//3, cy-60, "CORE TEMP",      "48.2°C")
        float_label(cx+W//3, cy-60, "ENERGY LEVEL",   "87%",    anchor="e")
        float_label(cx-W//3, cy+44, "CORE STABILITY",  "99.9%")
        float_label(cx+W//3, cy+44, "PROCESSOR LOAD", f"{20+int(8*math.sin(t*1.3))}%", anchor="e")

        # state label below core
        state_labels = {
            "IDLE":      "◈  STANDBY  ◈",
            "LISTENING": "◉  LISTENING  ◉",
            "THINKING":  "⟳  PROCESSING  ⟳",
            "SPEAKING":  "▶  SPEAKING  ▶",
        }
        c.create_text(cx, cy+190, text=state_labels.get(self.state, self.state),
                      font=("Courier New",11,"bold"), fill=sc)
        c.create_text(cx, cy+207,
                      text=f"GROQ  ·  {GROQ_MODEL.upper()[:22]}  ·  STT: GROQ WHISPER",
                      font=self.fn_label, fill=blend(sc,0.35))

        # border corners
        s=18
        for px,py,dx,dy in [(0,0,1,1),(W,0,-1,1),(0,H,1,-1),(W,H,-1,-1)]:
            c.create_line(px,py,px+dx*s,py,  fill=sc, width=2)
            c.create_line(px,py,px,py+dy*s, fill=sc, width=2)

    def _hex(self, c, cx, cy, r, color, width, rot=0):
        pts = []
        for i in range(6):
            a = math.radians(60*i+rot); pts.extend([cx+r*math.cos(a), cy+r*math.sin(a)])
        c.create_polygon(pts, outline=color, fill="", width=width)

    def _uptime(self):
        s = int(time.time()-self._start_time)
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    # ── STATE ─────────────────────────────────────────────────────────────────
    def set_state(self, s):
        self.state = s
        state_map = {
            "IDLE":      ("STANDBY",    CYAN),
            "LISTENING": ("LISTENING",  CYAN2),
            "THINKING":  ("PROCESSING", GOLD),
            "SPEAKING":  ("SPEAKING",   CYAN3),
        }
        txt, col = state_map.get(s, (s, CYAN))
        try:
            self._status_var.set(txt)
            self._status_lbl.config(fg=col)
            self._cmd_status_lbl.config(
                text=f"CURRENT STATUS: {txt}   |   ACTIVE MODEL: {GROQ_MODEL.upper()[:24]}")
        except Exception:
            pass

    # ── LOGGING ───────────────────────────────────────────────────────────────
    def _log_jarvis(self, text): self._log_msg("JARVIS", text, "ja_label", "ja_body", "◈")
    def _log_you(self, text):
        self._log_msg("YOU", text, "you_label", "you_body", "▶")
        self._msg_count += 1

    def _log_system(self, text):
        def _do():
            self.log.config(state=tk.NORMAL)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.log.insert(tk.END, f"\n  [{ts}] SYS: ", "sys_label")
            self.log.insert(tk.END, f"{text}\n", "sys_body")
            self.log.config(state=tk.DISABLED); self.log.see(tk.END)
        self.root.after(0, _do)

    def _log_warn(self, text):
        def _do():
            self.log.config(state=tk.NORMAL)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.log.insert(tk.END, f"\n  [{ts}] WARN: ", "sys_label")
            self.log.insert(tk.END, f"{text}\n", "warn_body")
            self.log.config(state=tk.DISABLED); self.log.see(tk.END)
        self.root.after(0, _do)

    def _log_msg(self, speaker, text, label_tag, body_tag, icon):
        def _do():
            self.log.config(state=tk.NORMAL)
            ts = datetime.datetime.now().strftime("%H:%M")
            self.log.insert(tk.END, "\n", "divider")
            self.log.insert(tk.END, f" {icon} {speaker}  ", label_tag)
            self.log.insert(tk.END, f"[{ts}]\n", "timestamp")
            self.log.insert(tk.END, f"  {text}\n", body_tag)
            self.log.config(state=tk.DISABLED); self.log.see(tk.END)
        self.root.after(0, _do)

    def _stream_start(self):
        def _do():
            self.log.config(state=tk.NORMAL)
            ts = datetime.datetime.now().strftime("%H:%M")
            self.log.insert(tk.END, "\n", "divider")
            self.log.insert(tk.END, " ◈ JARVIS  ", "ja_label")
            self.log.insert(tk.END, f"[{ts}]\n", "timestamp")
            self.log.insert(tk.END, "  ", "stream")
            self.log.config(state=tk.DISABLED); self.log.see(tk.END)
        self.root.after(0, _do)

    def _stream_token(self, token):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, token, "stream")
        self.log.config(state=tk.DISABLED); self.log.see(tk.END)

    def _stream_end(self):
        def _do():
            self.log.config(state=tk.NORMAL)
            self.log.insert(tk.END, "\n", "stream")
            self.log.config(state=tk.DISABLED); self.log.see(tk.END)
        self.root.after(0, _do)

    # ── LISTENER ──────────────────────────────────────────────────────────────
    def _start_listener(self):
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        self.root.after(0, lambda: self._log_system(
            f'Mic ready (device {MIC_DEVICE}). Say "{WAKE_WORD}" to activate.'))
        while self.running:
            try:
                self.set_state("IDLE")
                text = listen_for_wake_word()
                if not text: continue
                if WAKE_WORD.lower() not in text.lower(): continue
                q = re.sub(re.escape(WAKE_WORD), "", text, flags=re.IGNORECASE).strip()
                q = re.sub(r'^[\s,\.]+', '', q).strip()
                if not q:
                    self.set_state("LISTENING")
                    self.tts.speak(f"Yes, {OWNER_NAME}?")
                turns = 0; max_turns = 5
                while self.running and turns < max_turns:
                    if not q:
                        wav = record_until_silence()
                        if not wav: turns += 1; continue
                        try:
                            result = groq_client.audio.transcriptions.create(
                                model=WHISPER_MODEL, file=wav, language="en")
                            q = result.text.strip()
                        except Exception as e:
                            self.root.after(0, lambda e=e: self._log_system(f"STT error: {e}"))
                            turns += 1; continue
                    if not q: turns += 1; continue
                    if any(w in q.lower() for w in ["goodbye","bye jarvis","exit","quit","close"]):
                        captured = q
                        self.root.after(0, lambda t=captured: self._log_you(t))
                        self._process(q); break
                    captured = q
                    self.root.after(0, lambda t=captured: self._log_you(t))
                    self._process_async(q)
                    q = ""; turns += 1; time.sleep(0.4)
            except Exception as e:
                self.root.after(0, lambda e=e: self._log_system(f"Listener error: {e}"))
                time.sleep(2)

    def _process(self, query):
        threading.Thread(target=self._process_async, args=(query,), daemon=True).start()

    def _process_async(self, query):
        self.set_state("THINKING")
        response = handle_local_command(query, self.contacts)
        if response == "__EXIT__":
            msg = f"Shutting down. Goodbye, {OWNER_NAME}."
            self._log_jarvis(msg)
            self.set_state("SPEAKING")
            self.tts.speak(msg)
            time.sleep(2.5)
            self.root.after(0, self.root.destroy)
            return
        # ── Phone call actions ────────────────────────────────────────────────
        if response == "__ANSWER_CALL__":
            self.phone_monitor.answer_call()
            reply = "Answering the call."
            self._log_jarvis(reply); self.set_state("SPEAKING"); self.tts.speak(reply)
            while self.tts.is_speaking(): time.sleep(0.3)
            self.set_state("IDLE"); return
        if response == "__ANSWER_SPEAK__":
            msg = "Boss is busy right now, please try again later."
            self._log_jarvis(f"Answering and saying: {msg}")
            threading.Thread(target=self.phone_monitor.answer_and_speak,
            args=(msg, self.tts), daemon=True).start()
            return
    
        if isinstance(response, str) and response.startswith("__REJECT_CALL__"):
            busy_msg = response[len("__REJECT_CALL__"):]
            self.phone_monitor.reject_call(busy_msg)
            if busy_msg:
                reply = f"Call declined. Opening SMS with: '{busy_msg}'"
            else:
                reply = "Call declined."
            self._log_jarvis(reply); self.set_state("SPEAKING"); self.tts.speak(reply)
            while self.tts.is_speaking(): time.sleep(0.3)
            self.set_state("IDLE"); return
        if response:
            self._log_jarvis(response)
            self.set_state("SPEAKING")
            self.tts.speak(response)
        else:
            self._stream_start()
            response = ask_groq(
                query, self.history,
                on_token=lambda tok: self.root.after(0, lambda t=tok: self._stream_token(t)),
            )
            self._stream_end()
            self.set_state("SPEAKING")
            self.tts.speak(response)
        self.history.append({"role": "user",      "content": query})
        self.history.append({"role": "assistant",  "content": response})
        while self.tts.is_speaking():
            time.sleep(0.3)
        self.set_state("IDLE")

    def _on_submit(self, event=None):
        q = self.entry.get().strip()
        if not q or q == "Type command...": return
        self.entry.delete(0, tk.END)
        self._log_you(q); self._process(q)

    def _on_cmd_submit(self, event=None):
        q = self.cmd_entry.get().strip()
        if not q or q == "ENTER SYSTEM COMMAND...": return
        self.cmd_entry.delete(0, tk.END)
        self._log_you(q); self._process(q)

    def _quick_cmd(self, cmd):
        self._log_you(cmd); self._process(cmd)

    def on_close(self):
        self.running = False
        if hasattr(self, 'phone_monitor'):
            self.phone_monitor.stop()
        self.root.destroy()


if __name__ == "__main__":
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    root = tk.Tk()
    app  = JarvisApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()