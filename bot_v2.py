import asyncio, base64, io, json, os, re, shutil, subprocess, time, uuid, wave
import requests
try:
    import edge_tts
except ImportError:
    edge_tts = None
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
                      ReplyKeyboardMarkup, Update)
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, PreCheckoutQueryHandler, filters)

BASE = os.path.dirname(os.path.abspath(__file__))

# key গুলো config.env ফাইল থেকে আসে
def _load_cfg():
    c = {}
    p = os.path.join(BASE, "config.env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                c[k.strip()] = v.strip().strip('"').strip("'")
    return c
_CFG = _load_cfg()
def cfg(n): return _CFG.get(n) or os.environ.get(n, "")

TG_TOKEN = cfg("TG_TOKEN")
ELEVEN_API_KEY = cfg("ELEVEN_API_KEY")
GEMINI_API_KEY = cfg("GEMINI_API_KEY")
ADMIN_IDS = [8355700804, 8913084053]

# ============ প্রফেশনাল ভয়েস (Gemini) ============
STYLE_NEWS = ("very fast, urgent and emotional, like a Bengali investigative news reporter "
              "revealing shocking breaking news, intense and gripping")
STYLE_MYST = ("very fast, intense and mysterious with deep emotion, like the narrator of a viral Bengali "
              "mystery and true-story YouTube channel, suspenseful, dramatic, hooking the listener")
STYLE_EMO = "emotional, heartfelt and touching, voice full of feeling, moderately fast"
STYLE_DOC = "deep, serious and cinematic, like a documentary narrator, steady and powerful"
STYLE_FRIEND = "warm, friendly and lively, like talking to a close friend"

CATEGORIES = {
    "news": ("⚡ দ্রুত সাংবাদিক (আবেগী)", STYLE_NEWS,
             ["Charon", "Fenrir", "Orus", "Kore", "Alnilam", "Zephyr"]),
    "myst": ("🕵️ রহস্য গল্প (মায়াজাল স্টাইল)", STYLE_MYST,
             ["Algenib", "Umbriel", "Enceladus", "Gacrux", "Sulafat", "Algieba"]),
    "emo": ("💔 আবেগী কণ্ঠ", STYLE_EMO,
            ["Leda", "Aoede", "Achernar", "Vindemiatrix", "Laomedeia", "Callirrhoe"]),
    "doc": ("🎬 গম্ভীর ডকুমেন্টারি", STYLE_DOC,
            ["Rasalgethi", "Iapetus", "Schedar", "Sadaltager", "Zubenelgenubi", "Pulcherrima"]),
    "friend": ("😊 বন্ধুসুলভ", STYLE_FRIEND,
               ["Achird", "Autonoe", "Despina", "Erinome", "Sadachbia", "Puck"]),
}
VOICES = {}
for _ck, (_cn, _style, _names) in CATEGORIES.items():
    for _i, _n in enumerate(_names):
        VOICES[f"{_ck}_{_i}"] = {"name": f"{_cn.split(' ')[0]} {_n}", "engine": "gemini",
                                 "voice": _n, "style": _style, "cat": _ck}

# ============ ElevenLabs ভয়েস ============
VOICE_IDS = ["d532cgnzlrx7AWL3CD9i", "zVPU9Rf8bHDcntLKA3LY", "j5PhP1QJv2DvlhRv3mEv",
             "VizHiwkPO7hXc967v4tE", "YyFoWJwI20bOlOPfwy6X", "6fKdJFZHa5oCXNSVGieE",
             "MNuISDUw2Kqij2hI0QHV", "yBrGXLW1RaXDUjUf3kQi", "xi6A9YWXmGc3yDK4kXS9"]
# আরও ভয়েস যোগ করতে config.env-এ লিখুন: ELEVEN_EXTRA_IDS=id1,id2
VOICE_IDS += [x.strip() for x in cfg("ELEVEN_EXTRA_IDS").split(",") if x.strip()]
for _i, _vid in enumerate(VOICE_IDS):
    VOICES[f"eleven_{_i}"] = {"name": f"🎙️ ElevenLabs {_i + 1}", "id": _vid, "engine": "eleven", "cat": "eleven"}

# ============ ফ্রি AI ভয়েস ============
AI_VOICES = {
    "ai_f1": {"name": "🤖 নাবনিতা (নারী)", "id": "bn-BD-NabanitaNeural", "engine": "edge", "rate": "-2%"},
    "ai_f1s": {"name": "🤖 নাবনিতা (কোমল, ধীর)", "id": "bn-BD-NabanitaNeural", "engine": "edge", "rate": "-6%", "pitch": "-2Hz"},
    "ai_m1": {"name": "🤖 প্রদীপ (পুরুষ)", "id": "bn-BD-PradeepNeural", "engine": "edge", "rate": "-2%"},
    "ai_m1d": {"name": "🤖 প্রদীপ (গম্ভীর)", "id": "bn-BD-PradeepNeural", "engine": "edge", "rate": "-6%", "pitch": "-6Hz"},
    "ai_f2": {"name": "🤖 তানিশা (নারী, ভারত)", "id": "bn-IN-TanishaaNeural", "engine": "edge", "rate": "-2%"},
    "ai_m2d": {"name": "🤖 ভাস্কর (গম্ভীর, ভারত)", "id": "bn-IN-BashkarNeural", "engine": "edge", "rate": "-6%", "pitch": "-6Hz"},
}
VOICES.update(AI_VOICES)

MAX_CHARS_PRO, MAX_CHARS_AI, MAX_CHARS_ELEVEN = 1000, 1000, 300
MODEL_ID = "eleven_v3"
FREE_TRIAL_SECONDS = 120
FALLBACK_KEY = "ai_f1"
GEMINI_TTS_MODEL = "gemini-3.8-flash-tts"
GEM_DAILY_LIMIT = 5          # প্রতি ইউজার দিনে কয়টা প্রফেশনাল ভয়েস ফ্রি
PACK_STARS, PACK_VOICES, PACK_BDT = 50, 5, 50
PAY_METHODS = {"bkash": {"name": "বিকাশ", "number": "01703654292"},
               "upay": {"name": "উপায়", "number": "01341247842"}}
SAMPLE_TEXT = "এইমাত্র পাওয়া খবর! পুরো ঘটনাটা জানলে আপনি অবাক হয়ে যাবেন।"
DB_FILE = os.path.join(BASE, "users.json")
SAMPLE_DIR = os.path.join(BASE, "samples")
os.makedirs(SAMPLE_DIR, exist_ok=True)
LAST = {"err": ""}
DL_CACHE = {}

# ---------- ডেটাবেস ----------
def load_db():
    if os.path.exists(DB_FILE):
        try:
            return json.load(open(DB_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_db(db):
    json.dump(db, open(DB_FILE, "w", encoding="utf-8"))

def get_user(uid):
    db = load_db()
    u = db.get(str(uid))
    if not isinstance(u, dict):
        u = {"credits": 0}
        db[str(uid)] = u
        save_db(db)
    return u

def put_user(uid, u):
    db = load_db(); db[str(uid)] = u; save_db(db)

def add_balance(uid, n):
    u = get_user(uid); u["credits"] = u.get("credits", 0) + n; put_user(uid, u)

def daily_count(uid, feat):
    u = get_user(uid)
    return u.get(f"{feat}_n", 0) if u.get(f"{feat}_day") == time.strftime("%Y-%m-%d") else 0

def daily_add(uid, feat):
    u = get_user(uid); today = time.strftime("%Y-%m-%d")
    if u.get(f"{feat}_day") != today:
        u[f"{feat}_day"], u[f"{feat}_n"] = today, 0
    u[f"{feat}_n"] = u.get(f"{feat}_n", 0) + 1
    put_user(uid, u)

def trial_left(uid): return max(0, FREE_TRIAL_SECONDS - get_user(uid).get("trial_used", 0))
def can_generate(uid): return trial_left(uid) > 0 or get_user(uid).get("credits", 0) >= 1
def add_trial_used(uid, sec):
    u = get_user(uid); u["trial_used"] = u.get("trial_used", 0) + int(sec); put_user(uid, u)
def audio_seconds(b): return len(b) / 16000

def get_balance(uid):
    left = max(0, GEM_DAILY_LIMIT - daily_count(uid, "gem"))
    c = get_user(uid).get("credits", 0)
    t = trial_left(uid)
    return f"আজ ফ্রি Gemini ভয়েস বাকি {left}টা, ElevenLabs ফ্রি {t // 60} মিনিট {t % 60} সেকেন্ড, কেনা ব্যালেন্স {c}টা"

# ---------- ElevenLabs ----------
def tts(voice_id, text):
    try:
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                          headers={"xi-api-key": ELEVEN_API_KEY},
                          json={"text": text, "model_id": MODEL_ID}, timeout=90)
    except requests.RequestException as e:
        LAST["err"] = f"ElevenLabs নেটওয়ার্ক: {str(e)[:100]}"; return None
    if r.status_code != 200:
        print("ElevenLabs error:", r.status_code, r.text[:300])
        LAST["err"] = f"ElevenLabs {r.status_code} {r.text[:150]}"; return None
    return r.content

LABEL_BN = {"male": "পুরুষ", "female": "নারী", "mysterious": "রহস্যময়", "deep": "গম্ভীর",
            "calm": "শান্ত", "warm": "উষ্ণ", "energetic": "প্রাণবন্ত", "soft": "নরম",
            "raspy": "খসখসে", "confident": "আত্মবিশ্বাসী", "intense": "তীব্র",
            "classy": "মার্জিত", "casual": "সাধারণ", "professional": "পেশাদার"}

def _fill_name(v):
    try:
        r = requests.get(f"https://api.elevenlabs.io/v1/voices/{v['id']}",
                         headers={"xi-api-key": ELEVEN_API_KEY}, timeout=20)
        if r.status_code == 200:
            d = r.json(); lb = d.get("labels") or {}
            tags = [LABEL_BN.get(x, x) for x in (lb.get("descriptive"), lb.get("gender")) if x]
            v["name"] = "🎙️ " + d.get("name", v["name"]) + (" · " + " · ".join(tags) if tags else "")
        else:
            print("ভয়েস পাওয়া যায়নি:", v["id"], r.status_code)
    except requests.RequestException:
        pass

def load_voice_names():
    from concurrent.futures import ThreadPoolExecutor
    todo = [v for v in VOICES.values() if v.get("engine") == "eleven"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(_fill_name, todo))

# ---------- Gemini ----------
def gemini_call(model, body, timeout=120):
    for attempt in range(3):
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json=body, timeout=timeout)
        except requests.RequestException as e:
            LAST["err"] = f"Gemini নেটওয়ার্ক: {str(e)[:100]}"
            continue
        if r.status_code != 200:
            print("Gemini error:", r.status_code, r.text[:300])
            LAST["err"] = f"Gemini {r.status_code} {r.text[:120]}"
            if r.status_code in (429, 500, 503) and attempt < 2:
                time.sleep(20); continue
            return None
        try:
            return r.json()
        except Exception:
            return None
    return None

def pcm_to_wav(pcm, rate=24000):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return out.getvalue()

def gemini_tts(voice_name, style, text):
    prompt = f"Say in Bengali, {style}: {text}" if style else text
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}}}}
    d = gemini_call(GEMINI_TTS_MODEL, body)
    if not d: return None
    try:
        b64 = d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        return pcm_to_wav(base64.b64decode(b64))
    except Exception:
        LAST["err"] = "Gemini অডিও উত্তর বোঝা যায়নি"; return None

# ---------- ভয়েস বানানো ----------
def ext_of(v): return "wav" if v.get("engine") == "gemini" else "mp3"

def store_dl(audio, ext="mp3"):
    t = uuid.uuid4().hex[:10]; DL_CACHE[t] = (audio, ext)
    while len(DL_CACHE) > 40: DL_CACHE.pop(next(iter(DL_CACHE)))
    return t

def split_text(text, size):
    parts, cur = [], ""
    for piece in re.split(r"(?<=[।.!?\n])", text):
        if len(cur) + len(piece) > size and cur:
            parts.append(cur); cur = ""
        while len(piece) > size:
            parts.append(piece[:size]); piece = piece[size:]
        cur += piece
    if cur.strip(): parts.append(cur)
    return [p for p in parts if p.strip()]

async def edge_synth(vid, text, rate="-4%", pitch="+0Hz"):
    if edge_tts is None: return None
    try:
        buf = bytearray()
        async for ch in edge_tts.Communicate(text, vid, rate=rate, pitch=pitch).stream():
            if ch["type"] == "audio": buf += ch["data"]
        return bytes(buf) or None
    except Exception as e:
        print("AI voice error:", e); LAST["err"] = f"edge-tts: {str(e)[:100]}"; return None

AF_CHAIN = ("highpass=f=60,equalizer=f=140:t=q:w=1:g=2,equalizer=f=3500:t=q:w=1:g=-1.5,"
            "acompressor=threshold=-18dB:ratio=2.5:attack=5:release=80,"
            "aecho=0.85:0.5:55:0.12,loudnorm=I=-16:TP=-1.5:LRA=11")

def enhance_audio(data):
    ff = shutil.which("ffmpeg")
    if not ff or not data: return data
    try:
        r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-af", AF_CHAIN,
                            "-f", "mp3", "-c:a", "libmp3lame", "-q:a", "3", "pipe:1"],
                           input=data, capture_output=True, timeout=90)
        if r.returncode == 0 and r.stdout: return r.stdout
    except Exception as e:
        print("ffmpeg error:", e)
    return data

def wav_concat(parts):
    if len(parts) == 1: return parts[0]
    out = io.BytesIO(); first = True
    with wave.open(out, "wb") as w:
        for p in parts:
            with wave.open(io.BytesIO(p), "rb") as r:
                if first: w.setparams(r.getparams()); first = False
                w.writeframes(r.readframes(r.getnframes()))
    return out.getvalue()

async def synth(voice, text):
    if voice.get("engine") == "edge":
        a = await edge_synth(voice["id"], text, voice.get("rate", "-2%"), voice.get("pitch", "+0Hz"))
        return await asyncio.to_thread(enhance_audio, a) if a else None
    if voice.get("engine") == "eleven":
        return await asyncio.to_thread(tts, voice["id"], text)
    return await asyncio.to_thread(gemini_tts, voice["voice"], voice.get("style", ""), text)

async def synth_long(voice, text):
    size = 3000 if voice.get("engine") == "edge" else (2500 if voice.get("engine") == "eleven" else 2000)
    out = []
    for part in split_text(text, size):
        a = await synth(voice, part)
        if not a: return None
        out.append(a)
    if not out: return None
    return wav_concat(out) if voice.get("engine") == "gemini" else b"".join(out)

async def alert_admins_error(ctx):
    for a in ADMIN_IDS:
        try: await ctx.bot.send_message(a, f"⚠️ সমস্যা: {LAST['err'] or 'অজানা'}")
        except Exception: pass

def main_voice_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎙️ প্রফেশনাল ভয়েস", callback_data="cat:pro")],
                                 [InlineKeyboardButton("🤖 AI ভয়েস (ফ্রি)", callback_data="cat:ai")]])

def pro_categories_menu():
    rows = []
    if any(v.get("engine") == "eleven" for v in VOICES.values()):
        rows.append([InlineKeyboardButton(f"🎙️ ElevenLabs ({len(VOICE_IDS)}টা ভয়েস)", callback_data="pcat:eleven")])
    rows += [[InlineKeyboardButton(v[0], callback_data=f"pcat:{k}")] for k, v in CATEGORIES.items()]
    return InlineKeyboardMarkup(rows)

def voices_menu(kind):
    rows = []
    for key, v in VOICES.items():
        if kind == "ai":
            if v.get("engine") != "edge": continue
        elif v.get("cat") != kind:
            continue
        rows.append([InlineKeyboardButton(v["name"], callback_data=f"pick:{key}"),
                     InlineKeyboardButton("▶️ শুনুন", callback_data=f"prev:{key}")])
    return InlineKeyboardMarkup(rows)

async def generate_audio(update, ctx, text):
    uid = update.effective_user.id
    key = ctx.user_data.get("voice")
    if key not in VOICES:
        await update.message.reply_text("আগে একটা ভয়েস বেছে নিন:", reply_markup=main_voice_menu())
        return None
    voice = VOICES[key]; eng = voice.get("engine"); is_admin = uid in ADMIN_IDS
    limit = {"eleven": MAX_CHARS_ELEVEN, "edge": MAX_CHARS_AI, "gemini": MAX_CHARS_PRO}[eng]
    if not is_admin and len(text) > limit:
        await update.message.reply_text(f"লেখা বড়। {limit} অক্ষরের মধ্যে পাঠান।"); return None
    if eng == "eleven" and not is_admin and not can_generate(uid):
        await update.message.reply_text("ElevenLabs ভয়েসের ব্যালেন্স শেষ। 💳 কিনুন চাপুন, অথবা Gemini বা 🤖 AI ভয়েস ব্যবহার করুন।",
                                        reply_markup=main_voice_menu())
        return None
    await update.message.chat.send_action("record_voice")
    paid = limit_hit = False
    if eng == "gemini" and not is_admin and daily_count(uid, "gem") >= GEM_DAILY_LIMIT:
        if get_user(uid).get("credits", 0) >= 1: paid = True
        else: limit_hit = True
    used, caption, audio = voice, voice["name"], None
    if not limit_hit:
        audio = await synth_long(voice, text)
        if audio and eng == "gemini" and not is_admin:
            if paid: add_balance(uid, -1)
            else: daily_add(uid, "gem")
    if not audio and eng != "edge":
        if not limit_hit: await alert_admins_error(ctx)
        fb = VOICES.get(FALLBACK_KEY)
        if fb:
            audio = await synth_long(fb, text)
            if audio:
                used = fb
                if eng == "eleven":
                    note = "ElevenLabs এখন সাময়িক বন্ধ, তাই ফ্রি AI ভয়েসে বানানো হলো। ব্যালেন্স কাটা হয়নি।"
                elif limit_hit:
                    note = f"আজকের ফ্রি Gemini ভয়েসের সীমা ({GEM_DAILY_LIMIT}টা) শেষ, তাই ফ্রি AI ভয়েসে বানানো হলো। 💳 কিনুন চেপে আরও নিন।"
                else:
                    note = "প্রফেশনাল ভয়েস এখন পাওয়া যাচ্ছে না, তাই ফ্রি AI ভয়েসে বানানো হলো।"
                caption = fb["name"] + "\nℹ️ " + note
    if not audio:
        await update.message.reply_text("ভয়েস বানানো যায়নি, আবার চেষ্টা করুন।"); return None
    if eng == "eleven" and used is voice and not is_admin:
        if trial_left(uid) > 0: add_trial_used(uid, audio_seconds(audio) + 1)
        else: add_balance(uid, -1)
    return audio, caption, ext_of(used)

async def send_audio_msg(update, audio, caption, ext):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"⬇️ ডাউনলোড ({ext.upper()})",
                                callback_data=f"dl:{store_dl(audio, ext)}")]])
    if ext == "wav":
        await update.message.reply_audio(io.BytesIO(audio), filename="voice.wav", title="ভয়েস",
                                         caption=caption[:1000], reply_markup=kb, write_timeout=120)
    else:
        await update.message.reply_voice(io.BytesIO(audio), caption=caption[:1000],
                                         reply_markup=kb, write_timeout=120)

# ---------- মেনু ----------
MENU_PRO, MENU_AI = "🎙️ প্রফেশনাল ভয়েস", "🤖 AI ভয়েস"
MENU_BUY, MENU_BAL, MENU_HELP = "💳 কিনুন", "💰 ব্যালেন্স", "ℹ️ সাহায্য"
MENU_CREDITS = "📊 ক্রেডিট (অ্যাডমিন)"
MENU_ALL = {MENU_PRO, MENU_AI, MENU_BUY, MENU_BAL, MENU_HELP, MENU_CREDITS}

def main_keyboard(uid):
    rows = [[MENU_PRO, MENU_AI], [MENU_BUY, MENU_BAL], [MENU_HELP]]
    if uid in ADMIN_IDS: rows.append([MENU_CREDITS])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True,
                               input_field_placeholder="এখানে বাংলা লেখা লিখুন...")

def buy_menu():
    rows = [[InlineKeyboardButton(f"⭐ Stars ({PACK_STARS}⭐ = {PACK_VOICES}টা)", callback_data="pay:stars")]]
    for k, m in PAY_METHODS.items():
        rows.append([InlineKeyboardButton(f"📱 {m['name']} ({PACK_BDT}৳ = {PACK_VOICES}টা)", callback_data=f"pay:{k}")])
    return InlineKeyboardMarkup(rows)

async def start(update, ctx):
    uid = update.effective_user.id
    bal = "সীমাহীন" if uid in ADMIN_IDS else get_balance(uid)
    await update.message.reply_text(
        f"স্বাগতম! এখানে বাংলা লেখাকে ভয়েসে বদলে নিন।\n{bal}\n\n"
        "১) 🎙️ বা 🤖 চেপে ভয়েস বেছে নিন (▶️ চাপলে নমুনা শোনা যায়)\n২) তারপর বাংলা লেখা পাঠান।",
        reply_markup=main_keyboard(uid))
    await update.message.reply_text("ভয়েস বেছে নিন:", reply_markup=main_voice_menu())

async def handle_menu(update, ctx, text):
    uid = update.effective_user.id
    if text == MENU_PRO:
        await update.message.reply_text("🎙️ প্রফেশনাল ভয়েস, ক্যাটাগরি বেছে নিন:", reply_markup=pro_categories_menu())
    elif text == MENU_AI:
        await update.message.reply_text("🤖 AI ভয়েস (ফ্রি):", reply_markup=voices_menu("ai"))
    elif text == MENU_BUY:
        await update.message.reply_text("কীভাবে কিনবেন?", reply_markup=buy_menu())
    elif text == MENU_BAL:
        bal = "সীমাহীন" if uid in ADMIN_IDS else get_balance(uid)
        await update.message.reply_text(f"আপনার ব্যালেন্স: {bal}")
    elif text == MENU_HELP:
        await update.message.reply_text("🎙️ বা 🤖 চেপে ভয়েস বেছে নিন, তারপর বাংলা লেখা পাঠান। ভয়েস তৈরি হয়ে এলে ⬇️ চেপে ডাউনলোড করুন।")
    elif text == MENU_CREDITS and uid in ADMIN_IDS:
        db = load_db()
        tot = sum(u.get("credits", 0) for u in db.values() if isinstance(u, dict))
        await update.message.reply_text(f"মোট ইউজার: {len(db)}\nমোট কেনা ব্যালেন্স: {tot}")

async def on_text(update, ctx):
    text = (update.message.text or "").strip()
    if not text: return
    if text in MENU_ALL: return await handle_menu(update, ctx, text)
    if ctx.user_data.get("mode") == "trx":
        uid = update.effective_user.id
        m = ctx.user_data.pop("pay_method", "?")
        ctx.user_data["mode"] = "voice"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ অনুমোদন (+{PACK_VOICES})", callback_data=f"ok:{uid}")]])
        for a in ADMIN_IDS:
            try: await ctx.bot.send_message(a, f"💰 পেমেন্ট অনুরোধ\nইউজার: {uid}\nমাধ্যম: {m}\nTrxID/তথ্য: {text}", reply_markup=kb)
            except Exception: pass
        await update.message.reply_text("✅ অ্যাডমিনকে জানানো হয়েছে। যাচাই হলেই ব্যালেন্স যোগ হবে।"); return
    res = await generate_audio(update, ctx, text)
    if res: await send_audio_msg(update, *res)

# ---------- বাটন ----------
async def on_cat(update, ctx):
    q = update.callback_query; await q.answer()
    if q.data.split(":")[1] == "pro":
        await q.message.reply_text("🎙️ প্রফেশনাল ভয়েস, ক্যাটাগরি বেছে নিন:", reply_markup=pro_categories_menu())
    else:
        await q.message.reply_text("🤖 AI ভয়েস (ফ্রি):", reply_markup=voices_menu("ai"))

async def on_pcat(update, ctx):
    q = update.callback_query; await q.answer()
    ck = q.data.split(":")[1]
    if ck == "eleven":
        await q.message.reply_text("🎙️ ElevenLabs (সবচেয়ে বাস্তবসম্মত, ব্যালেন্স লাগে):", reply_markup=voices_menu(ck))
    elif ck in CATEGORIES:
        await q.message.reply_text(CATEGORIES[ck][0] + ":", reply_markup=voices_menu(ck))

async def on_button(update, ctx):
    q = update.callback_query; await q.answer()
    action, key = q.data.split(":")
    voice = VOICES.get(key)
    if not voice: return
    if action == "pick":
        ctx.user_data["voice"] = key
        ctx.user_data["mode"] = "voice"
        await q.message.reply_text(f"✅ {voice['name']} বাছাই হয়েছে। এবার আপনার লেখা পাঠান।"); return
    ext = ext_of(voice); path = os.path.join(SAMPLE_DIR, f"{key}.{ext}")
    if not os.path.exists(path):
        audio = await synth(voice, SAMPLE_TEXT)
        if not audio:
            await q.message.reply_text("নমুনা বানানো যায়নি: " + LAST.get("err", "")[:200]); return
        open(path, "wb").write(audio)
    with open(path, "rb") as f:
        if ext == "wav": await q.message.reply_audio(f, filename="sample.wav", title=voice["name"][:60], caption=voice["name"])
        else: await q.message.reply_voice(f, caption=voice["name"])

async def on_download(update, ctx):
    q = update.callback_query
    item = DL_CACHE.get(q.data.split(":")[1])
    if not item:
        await q.answer("ফাইলটা আর নেই, আবার বানিয়ে নিন।", show_alert=True); return
    audio, ext = item; await q.answer()
    await q.message.reply_document(io.BytesIO(audio), filename=f"voice.{ext}")

# ---------- পেমেন্ট ----------
async def on_pay(update, ctx):
    q = update.callback_query; await q.answer()
    m = q.data.split(":")[1]
    if m == "stars":
        await ctx.bot.send_invoice(chat_id=q.message.chat_id, title="ভয়েস প্যাক",
            description=f"{PACK_VOICES}টা প্রফেশনাল ভয়েস", payload="pack",
            provider_token="", currency="XTR", prices=[LabeledPrice("ভয়েস প্যাক", PACK_STARS)])
        return
    info = PAY_METHODS[m]
    ctx.user_data["mode"] = "trx"; ctx.user_data["pay_method"] = info["name"]
    await q.message.reply_text(f"{info['name']} নম্বর: {info['number']}\n(Send Money) {PACK_BDT} টাকা পাঠিয়ে "
                               "TrxID অথবা যে নম্বর থেকে পাঠিয়েছেন সেটা এখানে লিখুন।")

async def on_precheckout(update, ctx):
    await update.pre_checkout_query.answer(ok=True)

async def on_paid(update, ctx):
    add_balance(update.effective_user.id, PACK_VOICES)
    await update.message.reply_text(f"✅ পেমেন্ট সফল! {PACK_VOICES}টা ভয়েস যোগ হয়েছে।")

async def on_approve(update, ctx):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("অনুমতি নেই", show_alert=True); return
    uid = int(q.data.split(":")[1]); add_balance(uid, PACK_VOICES)
    await q.answer("যোগ হয়েছে")
    await q.edit_message_text(q.message.text + "\n\n✅ অনুমোদিত")
    try: await ctx.bot.send_message(uid, f"✅ পেমেন্ট যাচাই হয়েছে। {PACK_VOICES}টা ভয়েস যোগ হয়েছে।")
    except Exception: pass

async def add_cmd(update, ctx):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        uid, n = int(ctx.args[0]), int(ctx.args[1]); add_balance(uid, n)
        await update.message.reply_text(f"{uid} কে {n} যোগ হয়েছে।")
    except Exception:
        await update.message.reply_text("ব্যবহার: /add ইউজার_আইডি সংখ্যা")

async def on_error(update, ctx):
    print("ERROR:", ctx.error)

def main():
    if not TG_TOKEN:
        raise SystemExit("config.env এ TG_TOKEN বসান।")
    if not ELEVEN_API_KEY:
        print("সতর্কতা: ELEVEN_API_KEY নেই, ElevenLabs ভয়েস কাজ করবে না।")
    if not GEMINI_API_KEY:
        print("সতর্কতা: GEMINI_API_KEY নেই, প্রফেশনাল ভয়েস কাজ করবে না।")
    if ELEVEN_API_KEY: load_voice_names()
    app = Application.builder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CallbackQueryHandler(on_cat, pattern=r"^cat:"))
    app.add_handler(CallbackQueryHandler(on_pcat, pattern=r"^pcat:"))
    app.add_handler(CallbackQueryHandler(on_button, pattern=r"^(pick|prev):"))
    app.add_handler(CallbackQueryHandler(on_download, pattern=r"^dl:"))
    app.add_handler(CallbackQueryHandler(on_pay, pattern=r"^pay:"))
    app.add_handler(CallbackQueryHandler(on_approve, pattern=r"^ok:"))
    app.add_handler(PreCheckoutQueryHandler(on_precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_paid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    print("বট চালু হয়েছে ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
