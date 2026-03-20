"""
Script Generator Bot — Bot 4
Features:
- Short, Long-form, Documentary scripts
- Multiple styles (Documentary, Funny, Serious, Dramatic, Wholesome, Educational, Storytelling, Motivational)
- Replicate feature — paste a transcript, rewrite in any style
- Viral angle suggester
- CTA included in every script
- Powered by Claude API
"""

import os
import sqlite3
import logging
from anthropic import Anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DB_PATH = "scriptbot.db"

client = Anthropic(api_key=ANTHROPIC_API_KEY)

STYLES = [
    "documentary", "funny", "serious", "dramatic",
    "wholesome", "educational", "storytelling", "motivational"
]

FORMATS = ["short", "long", "documentary"]

# ── DATABASE ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id INTEGER PRIMARY KEY,
            default_style TEXT DEFAULT 'documentary',
            default_niche TEXT DEFAULT 'general',
            awaiting_replicate INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_prefs(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT default_style, default_niche, awaiting_replicate FROM user_prefs WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"style": row[0], "niche": row[1], "awaiting_replicate": row[2]}
    return {"style": "documentary", "niche": "general", "awaiting_replicate": 0}

def set_pref(user_id, key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO user_prefs (user_id) VALUES (?)", (user_id,))
    c.execute(f"UPDATE user_prefs SET {key}=? WHERE user_id=?", (value, user_id))
    conn.commit()
    conn.close()

def set_awaiting_replicate(user_id, val):
    set_pref(user_id, "awaiting_replicate", val)

# ── CLAUDE AI ─────────────────────────────────────────────────────────────────
def ask_claude(prompt, max_tokens=2000):
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

# ── SCRIPT PROMPTS ────────────────────────────────────────────────────────────
def build_short_prompt(topic, style, niche):
    return f"""You are an expert YouTube Shorts scriptwriter specializing in {style} content for the {niche} niche.

Write a complete YouTube Shorts script for the topic: "{topic}"

The script must be exactly 45-60 seconds when read aloud (roughly 120-150 words for voiceover).

Format your response EXACTLY like this:

🎬 TITLE OPTIONS:
1. [title 1]
2. [title 2]
3. [title 3]

🪝 HOOK (first 3 seconds — must stop the scroll):
[hook line]

📝 FULL VOICEOVER SCRIPT:
[complete word-for-word script in {style} style]

🎯 CTA:
[strong call to action — subscribe, comment, follow]

🎭 SCENE DESCRIPTIONS:
[brief visual direction for each section]

#️⃣ HASHTAGS:
[10 relevant hashtags]

Style: {style.upper()}. Make it engaging, fast-paced, optimized for retention."""

def build_long_prompt(topic, style, niche):
    return f"""You are an expert YouTube scriptwriter specializing in {style} content for the {niche} niche.

Write a complete long-form YouTube script for the topic: "{topic}"

Target length: 8-12 minutes when read aloud (roughly 1200-1800 words for voiceover).

Format your response EXACTLY like this:

🎬 TITLE OPTIONS:
1. [title 1]
2. [title 2]
3. [title 3]

🪝 HOOK (first 30 seconds — must keep viewer watching):
[hook]

📝 INTRO (30-60 seconds):
[intro script]

📌 SECTION 1 — [Section Title]:
[script]

📌 SECTION 2 — [Section Title]:
[script]

📌 SECTION 3 — [Section Title]:
[script]

📌 SECTION 4 — [Section Title]:
[script]

📌 SECTION 5 — [Section Title]:
[script]

🎯 OUTRO + CTA:
[strong outro with subscribe CTA, comment prompt, next video tease]

🎭 SCENE DESCRIPTIONS:
[visual direction for each section]

#️⃣ HASHTAGS:
[15 relevant hashtags]

Style: {style.upper()}. Make it deeply engaging with storytelling, facts, and emotional beats."""

def build_doc_prompt(topic, style, niche):
    return f"""You are an expert documentary YouTube scriptwriter. Your style is cinematic, narrative-driven, and deeply researched.

Write a full documentary-style YouTube script about: "{topic}"

Target: 12-15 minutes (1800-2200 words). Niche: {niche}. Tone overlay: {style}.

Format EXACTLY like this:

🎬 TITLE OPTIONS:
1. [title 1]
2. [title 2]
3. [title 3]

🎙️ COLD OPEN (cinematic hook — no context yet, just intrigue):
[script]

📖 ACT 1 — THE SETUP:
[establish the story, who/what/why]

📖 ACT 2 — THE CONFLICT:
[the rise, the struggle, the turning point]

📖 ACT 3 — THE REVELATION:
[the truth, the twist, the lesson]

🎯 OUTRO + CTA:
[reflective close + subscribe CTA + comment question for engagement]

🎭 VISUAL SOURCING GUIDE:
[shot-by-shot visual direction]

#️⃣ HASHTAGS:
[15 relevant hashtags]

Make it feel like a Netflix documentary narration. Cinematic language, dramatic pacing."""

def build_replicate_prompt(transcript, style, fmt, niche):
    format_map = {
        "short": "YouTube Shorts (45-60 seconds)",
        "long": "long-form YouTube (8-12 minutes)",
        "documentary": "documentary-style YouTube (12-15 minutes)"
    }
    return f"""You are an expert content strategist and scriptwriter.

A creator has shared this transcript from a video they liked:

---TRANSCRIPT START---
{transcript}
---TRANSCRIPT END---

Your job: Analyze the structure, pacing, and storytelling approach of this transcript, then write a COMPLETELY ORIGINAL script inspired by it — NOT a copy.

Requirements:
- Format: {format_map.get(fmt, "YouTube Shorts")}
- Style: {style.upper()}
- Niche: {niche}
- Keep the same energy and structure that made the original effective
- All topics, examples, and content must be 100% original

Format your response EXACTLY like this:

📊 WHAT MADE THE ORIGINAL WORK:
[2-3 sentences on the structure/style you detected]

🎬 TITLE OPTIONS:
1. [title 1]
2. [title 2]
3. [title 3]

🪝 HOOK:
[hook]

📝 FULL SCRIPT:
[complete original script in {style} style]

🎯 CTA:
[strong call to action]

🎭 SCENE DESCRIPTIONS:
[visual direction]

#️⃣ HASHTAGS:
[relevant hashtags]"""

def build_angles_prompt(topic, niche):
    return f"""You are a viral YouTube content strategist.

Topic: "{topic}"
Niche: {niche}

Generate 5 different viral angle approaches for this topic. Each angle should feel completely different from the others.

Format EXACTLY like this:

🎯 VIRAL ANGLES FOR: {topic}

1. 🔥 [Angle Name] — [Style: Documentary/Funny/Serious etc]
Hook: "[example hook line]"
Why it works: [1 sentence]

2. 💡 [Angle Name] — [Style]
Hook: "[example hook line]"
Why it works: [1 sentence]

3. 😮 [Angle Name] — [Style]
Hook: "[example hook line]"
Why it works: [1 sentence]

4. 🎭 [Angle Name] — [Style]
Hook: "[example hook line]"
Why it works: [1 sentence]

5. 💰 [Angle Name] — [Style]
Hook: "[example hook line]"
Why it works: [1 sentence]

Make each angle genuinely different — vary the emotion, the framing, and the audience it targets."""

def build_rewrite_prompt(script, style, niche):
    return f"""You are an expert scriptwriter. Rewrite and dramatically improve the following script.

Original script:
---
{script}
---

Requirements:
- Style: {style.upper()}
- Niche: {niche}
- Keep the core topic but make it significantly more engaging
- Sharpen the hook, improve flow, add better storytelling
- Include a strong CTA at the end

Format:
🎬 IMPROVED TITLE:
[better title]

📝 REWRITTEN SCRIPT:
[full improved script]

🎯 CTA:
[strong call to action]

🔑 WHAT YOU CHANGED:
[3 bullet points on key improvements made]"""

# ── TELEGRAM COMMANDS ─────────────────────────────────────────────────────────
async def cmd_start(update: Update, context):
    msg = (
        "✍️ *Script Generator Bot*\n\n"
        "Generate complete scripts for any format and style.\n\n"
        "*Script Commands:*\n"
        "/shortscript `<topic>` — 45-60s Shorts script\n"
        "/longscript `<topic>` — 8-12 min YouTube script\n"
        "/docscript `<topic>` — Documentary style script\n"
        "/replicate — Paste a transcript to rewrite in your style\n"
        "/rewrite `<script>` — Improve an existing script\n"
        "/angles `<topic>` — Get 5 viral angles for a topic\n\n"
        "*Settings:*\n"
        "/setstyle `<style>` — Set default style\n"
        "/settopic `<niche>` — Set default niche\n"
        "/mysettings — See your current settings\n\n"
        f"*Available styles:* {', '.join(STYLES)}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_shortscript(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: /shortscript NBA player gets ejected")
        return
    topic = " ".join(context.args)
    prefs = get_prefs(update.effective_user.id)
    await update.message.reply_text(f"✍️ Writing Shorts script for: *{topic}*...", parse_mode="Markdown")
    try:
        result = ask_claude(build_short_prompt(topic, prefs["style"], prefs["niche"]))
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_longscript(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: /longscript The rise of Elon Musk")
        return
    topic = " ".join(context.args)
    prefs = get_prefs(update.effective_user.id)
    await update.message.reply_text(f"✍️ Writing long-form script for: *{topic}*...", parse_mode="Markdown")
    try:
        result = ask_claude(build_long_prompt(topic, prefs["style"], prefs["niche"]), max_tokens=3000)
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_docscript(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: /docscript Theo Albrecht the invisible billionaire")
        return
    topic = " ".join(context.args)
    prefs = get_prefs(update.effective_user.id)
    await update.message.reply_text(f"🎬 Writing documentary script for: *{topic}*...", parse_mode="Markdown")
    try:
        result = ask_claude(build_doc_prompt(topic, prefs["style"], prefs["niche"]), max_tokens=3500)
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_replicate(update: Update, context):
    prefs = get_prefs(update.effective_user.id)
    set_awaiting_replicate(update.effective_user.id, 1)

    style_list = ", ".join(STYLES)
    fmt_list = ", ".join(FORMATS)

    await update.message.reply_text(
        f"📋 *Replicate Mode ON*\n\n"
        f"Paste the transcript you want to replicate.\n\n"
        f"Add your preferred style and format at the end like this:\n"
        f"`[style: funny] [format: short]`\n\n"
        f"Available styles: {style_list}\n"
        f"Available formats: {fmt_list}\n\n"
        f"Or just paste the transcript and I'll use your defaults "
        f"(style: *{prefs['style']}*, format: *short*)",
        parse_mode="Markdown"
    )

async def cmd_rewrite(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: /rewrite <paste your script here>")
        return
    script = " ".join(context.args)
    prefs = get_prefs(update.effective_user.id)
    await update.message.reply_text("✍️ Rewriting your script...")
    try:
        result = ask_claude(build_rewrite_prompt(script, prefs["style"], prefs["niche"]))
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_angles(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: /angles Elon Musk bankruptcy")
        return
    topic = " ".join(context.args)
    prefs = get_prefs(update.effective_user.id)
    await update.message.reply_text(f"🎯 Finding viral angles for: *{topic}*...", parse_mode="Markdown")
    try:
        result = ask_claude(build_angles_prompt(topic, prefs["niche"]))
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_setstyle(update: Update, context):
    if not context.args:
        await update.message.reply_text(f"Usage: /setstyle funny\nAvailable: {', '.join(STYLES)}")
        return
    style = context.args[0].lower()
    if style not in STYLES:
        await update.message.reply_text(f"❌ Unknown style. Available: {', '.join(STYLES)}")
        return
    set_pref(update.effective_user.id, "default_style", style)
    await update.message.reply_text(f"✅ Default style set to: *{style}*", parse_mode="Markdown")

async def cmd_settopic(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: /settopic wildlife")
        return
    niche = " ".join(context.args)
    set_pref(update.effective_user.id, "default_niche", niche)
    await update.message.reply_text(f"✅ Default niche set to: *{niche}*", parse_mode="Markdown")

async def cmd_mysettings(update: Update, context):
    prefs = get_prefs(update.effective_user.id)
    await update.message.reply_text(
        f"⚙️ *Your Settings:*\n\n"
        f"🎭 Style: *{prefs['style']}*\n"
        f"🎯 Niche: *{prefs['niche']}*",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context):
    await cmd_start(update, context)

# ── HANDLE REPLICATE TEXT INPUT ───────────────────────────────────────────────
async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    prefs = get_prefs(user_id)

    if prefs["awaiting_replicate"]:
        set_awaiting_replicate(user_id, 0)
        text = update.message.text

        # Parse optional style/format tags
        import re
        style_match = re.search(r'\[style:\s*(\w+)\]', text, re.IGNORECASE)
        format_match = re.search(r'\[format:\s*(\w+)\]', text, re.IGNORECASE)

        style = style_match.group(1).lower() if style_match else prefs["style"]
        fmt = format_match.group(1).lower() if format_match else "short"

        if style not in STYLES:
            style = prefs["style"]
        if fmt not in FORMATS:
            fmt = "short"

        # Clean transcript
        transcript = re.sub(r'\[style:[^\]]+\]|\[format:[^\]]+\]', '', text).strip()

        if len(transcript) < 50:
            await update.message.reply_text("❌ Transcript too short. Please paste more content.")
            return

        await update.message.reply_text(
            f"🔄 Replicating in *{style}* style as a *{fmt}* format script...",
            parse_mode="Markdown"
        )
        try:
            result = ask_claude(
                build_replicate_prompt(transcript, style, fmt, prefs["niche"]),
                max_tokens=3000
            )
            for i in range(0, len(result), 4000):
                await update.message.reply_text(result[i:i+4000])
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    else:
        await update.message.reply_text(
            "Use a command to get started. Type /help to see all commands."
        )

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("shortscript", cmd_shortscript))
    app.add_handler(CommandHandler("longscript", cmd_longscript))
    app.add_handler(CommandHandler("docscript", cmd_docscript))
    app.add_handler(CommandHandler("replicate", cmd_replicate))
    app.add_handler(CommandHandler("rewrite", cmd_rewrite))
    app.add_handler(CommandHandler("angles", cmd_angles))
    app.add_handler(CommandHandler("setstyle", cmd_setstyle))
    app.add_handler(CommandHandler("settopic", cmd_settopic))
    app.add_handler(CommandHandler("mysettings", cmd_mysettings))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Script Generator Bot running.")
    app.run_polling()

if __name__ == "__main__":
    main()
