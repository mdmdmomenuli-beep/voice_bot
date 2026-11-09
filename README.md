# Voice Studio Telegram Bot

বাংলা টেক্সট থেকে ভয়েস তৈরির Telegram বট।

- 🎙️ প্রফেশনাল ভয়েস: Google Gemini (৩০টা, ৫ ক্যাটাগরি) ও ElevenLabs
- 🤖 AI ভয়েস (ফ্রি): Microsoft Edge TTS, বাংলা ৬টা

## ফাইল
- `bot_v2.py`: পুরো বটের কোড
- `config.env.example`: key বসানোর নমুনা (এটা থেকে `config.env` বানান)
- `requirements.txt`: Python প্যাকেজ
- `install_termux.sh`: Termux-এ ইনস্টল ও key জিজ্ঞাসা
- `run.sh` / `stop.sh`: Termux-এ ব্যাকগ্রাউন্ডে চালু / বন্ধ
- `setup.sh` / `voicebot.service` / `update.sh`: Ubuntu সার্ভারে systemd দিয়ে চালু রাখা

## কোড যেভাবে key পড়ে
key কোডে লেখা নেই। `config.env` থেকে পড়া হয়। এই ফাইল GitHub-এ যায় না (`.gitignore`-এ আছে)।

## Termux-এ চালানো
```bash
bash install_termux.sh
bash run.sh
```

## সার্ভারে চালানো (Ubuntu)
```bash
git clone <repo-url> /root/voicebot && cd /root/voicebot
bash setup.sh        # প্রথমবার config.env বানাবে
nano config.env      # key বসান
bash setup.sh
```
কোড বদলালে: `bash update.sh`

## নিরাপত্তা
- Repo **Private** রাখুন।
- যেকোনো key ফাঁস হলে তখনই বাতিল করে নতুন নিন (Telegram: @BotFather `/revoke`, ElevenLabs ও Google AI Studio থেকে)।
