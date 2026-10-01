# ModernHeredotus Reels Engine

Turn a history article (PDF or TXT) into a finished **Instagram Reel** (1080 x 1920, vertical) with a
Turkish voice-over, slowly moving pictures and big subtitles - fully automatically.

```
  your article            Step 1: Claude writes a              Step 2: the computer builds
  (PDF / TXT)    ───────► 60-second Turkish voice-over  ───────► the video from your pictures,
  inputs/documents         script (~130 words)                   a Turkish voice and subtitles
                           output/..._script.txt                 output/..._reel.mp4
```

**What you get**

- A dramatic, hook-filled narration script written by Claude (Anthropic's AI) from the most striking parts of your text.
- A natural Turkish voice-over (Microsoft Edge neural voices, via `edge-tts`).
- Every picture from `inputs/images` used as a video scene, with a slow **Ken Burns** zoom/pan so nothing is static.
- Picture changes timed to the voice-over, cut on the natural pauses of the narration.
- **Bold white subtitles with a black outline** in the centre of the screen, appearing word-group by word-group in sync with the voice.
- One `.mp4` file ready to upload (H.264 video + AAC audio, 1080x1920, 30 fps).

You do **not** need to know how to program. Follow the steps below one by one; each step says how to check that it worked.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Install Python](#2-install-python)
3. [Install FFmpeg](#3-install-ffmpeg)
4. [Get this project onto your computer](#4-get-this-project-onto-your-computer)
5. [Open a terminal in the project folder](#5-open-a-terminal-in-the-project-folder)
6. [Install the project libraries](#6-install-the-project-libraries)
7. [Get an Anthropic API key and set up the `.env` file](#7-get-an-anthropic-api-key-and-set-up-the-env-file)
8. [Add your document and your pictures](#8-add-your-document-and-your-pictures)
9. [Run it](#9-run-it)
10. [Everyday use (after the first time)](#10-everyday-use-after-the-first-time)
11. [Settings and options](#11-settings-and-options)
12. [Troubleshooting](#12-troubleshooting)
13. [How it works / project layout](#13-how-it-works--project-layout)
14. [Good to know](#14-good-to-know)

---

## 1. What you need

| You need | Notes |
|---|---|
| A computer with **Windows 10/11**, **macOS** or **Linux** | About 2 GB of free disk space, 8 GB RAM recommended |
| An **internet connection** | Used to talk to Claude and to the voice service |
| An **Anthropic API key** with a little credit | Creating the script costs roughly a few cents. See [step 7](#7-get-an-anthropic-api-key-and-set-up-the-env-file) |
| **Python 3.10 or newer** | [Step 2](#2-install-python) |
| **FFmpeg** (video tool) | [Step 3](#3-install-ffmpeg) |
| Your **article** as `.pdf` or `.txt` | Must contain real, selectable text (not just scanned page photos) |
| **Pictures** (JPG, PNG, WEBP...) | Manuscripts, maps, portraits, paintings. 8-15 pictures fit a 60-second video well |

Time: setup takes 20-30 minutes **once**. After that, each video takes a few minutes of rendering.

---

## 2. Install Python

Python is the programming language this project is written in. You only need to install it, not learn it.

### Windows

1. Go to <https://www.python.org/downloads/> and click the big yellow **Download Python 3.x** button
   (3.11 or 3.12 is ideal).
2. Open the downloaded installer.
3. **VERY IMPORTANT:** on the first screen, tick the box **"Add python.exe to PATH"** (at the bottom). Then click **Install Now**.
4. When it says "Setup was successful", click Close.
5. Check it: press the **Windows key**, type `cmd`, press Enter (a black window opens), type

   ```
   python --version
   ```

   and press Enter. You should see something like `Python 3.12.4`.
   If Windows says *"Python was not found"*, try `py --version` instead. If that works, use `py` wherever this guide says `python`.
   If neither works, run the installer again, choose **Modify**, and make sure "Add Python to environment variables" is ticked.

### macOS

1. Go to <https://www.python.org/downloads/macos/> and download the latest **macOS 64-bit universal2 installer**.
2. Open the `.pkg` file and click through the installer.
3. Open **Terminal** (press `Cmd + Space`, type `Terminal`, press Enter) and check:

   ```
   python3 --version
   ```

   You should see `Python 3.x.x`. **On macOS use `python3` and `pip3` wherever this guide says `python` and `pip`**
   (inside the virtual environment from step 6 plain `python` also works).

### Linux (Ubuntu / Debian)

```
sudo apt update
sudo apt install python3 python3-venv python3-pip
python3 --version
```

---

## 3. Install FFmpeg

FFmpeg is the free tool that creates the final video file. (The video library used here, MoviePy, even carries
a built-in copy as a fallback, but installing FFmpeg properly is the most reliable way and makes problems easier to fix.)

### Windows

**Easiest way** - in the black `cmd` window, type:

```
winget install ffmpeg
```

then **close the window and open a new one**. (If `winget` is not found, use the manual way below.)

**Manual way**

1. Go to <https://www.gyan.dev/ffmpeg/builds/> and download **ffmpeg-release-essentials.zip**.
2. Right-click the zip -> **Extract All**. Rename the extracted folder to `ffmpeg` and move it to `C:\` so that the file
   `C:\ffmpeg\bin\ffmpeg.exe` exists.
3. Press the Windows key, type **"environment variables"**, open **Edit the system environment variables** -> **Environment Variables...**
4. Under **User variables**, select **Path** -> **Edit** -> **New**, type `C:\ffmpeg\bin`, then OK, OK, OK.
5. Close all black windows and open a new one.

### macOS

Install Homebrew first if you do not have it (copy the one-line command from <https://brew.sh> into Terminal), then:

```
brew install ffmpeg
```

### Linux

```
sudo apt install ffmpeg
```

### Check that it worked (all systems)

Open a **new** terminal window and type:

```
ffmpeg -version
```

You should see several lines starting with `ffmpeg version ...`. If you see "not recognized" / "command not found",
the PATH step was missed - redo it (on Windows) or restart the terminal.

---

## 4. Get this project onto your computer

**Option A - download as a ZIP (easiest)**

1. Open the project page on GitHub: <https://github.com/akinukhull/modernheredotus-reels-engine>
2. Click the green **Code** button -> **Download ZIP**.
3. Unzip it (Windows: right-click -> Extract All). Move the folder somewhere simple, for example `C:\ModernHeredotus-reels-engine`
   or your Documents folder. **Avoid** folders that sync to the cloud while you work (OneDrive, iCloud Drive) - they can slow rendering.

**Option B - with git (if you know it)**

```
git clone https://github.com/akinukhull/modernheredotus-reels-engine.git
```

---

## 5. Open a terminal in the project folder

All commands from now on must be typed **inside the project folder** (the one containing `main.py`).

- **Windows:** open the project folder in File Explorer, click the **address bar** at the top, type `cmd`, press Enter.
  A black window opens already inside the folder.
- **macOS:** right-click the project folder in Finder -> **New Terminal at Folder**
  (if you do not see it: System Settings -> Keyboard -> Keyboard Shortcuts -> Services -> enable "New Terminal at Folder").
  Or type `cd ` in Terminal (with a space) and drag the folder onto the window, then press Enter.
- **Linux:** right-click inside the folder -> Open in Terminal.

Check you are in the right place: type `dir` (Windows) or `ls` (macOS/Linux). You should see `main.py`, `requirements.txt`, `README.md`...

---

## 6. Install the project libraries

We install the project's libraries into a private "virtual environment" so they cannot interfere with anything else on your computer.
You do this once.

**Windows (`cmd` window)**

```
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux**

```
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

What to expect:

- After the second command your line starts with **`(venv)`** - that means the environment is active.
- The last command downloads several libraries (moviepy, edge-tts, anthropic, PyPDF2, Pillow, numpy...). It takes 1-3 minutes and ends with
  `Successfully installed ...`.

> **Important:** the `(venv)` environment must be activated **every time you open a new terminal window** before running the program
> (the `venv\Scripts\activate` / `source venv/bin/activate` line). If you forget, you will see `ModuleNotFoundError`.
>
> Windows PowerShell users: if activation says *"running scripts is disabled"*, either use the plain `cmd` window as shown above,
> or run `Set-ExecutionPolicy -Scope Process Bypass` first and then `venv\Scripts\Activate.ps1`.

---

## 7. Get an Anthropic API key and set up the `.env` file

Step 1 uses Claude, which needs a personal **API key** (a long secret password that identifies your account).

### 7a. Create the key

1. Go to <https://console.anthropic.com> and sign up / log in.
2. Add a small amount of credit: **Settings -> Billing** (for example 5 USD is enough for many videos).
   A normal article costs only a few cents per script; a very long PDF (a whole book chapter) can cost a few tens of cents. See the current prices on Anthropic's site.
3. Open **API Keys** -> **Create Key**, give it any name, and **copy the key** (it starts with `sk-ant-`).
   You will only see it once - keep it private, never post it online or send it to anyone.

### 7b. Put the key in a `.env` file

The program reads the key from a small text file named **`.env`** in the project folder.

1. In the project folder you will find a file called **`.env.example`**. Make a **copy** of it and name the copy exactly **`.env`**
   (a dot, then `env`, nothing else - no `.txt` at the end).

   - **Windows (`cmd`):** `copy .env.example .env`
   - **macOS / Linux:** `cp .env.example .env`

   *Tip for Windows:* if you create the file with Notepad, choose **Save as type: All files** and name it `.env`, otherwise Windows saves `.env.txt`
   (turn on **View -> File name extensions** in File Explorer to check).
   *Tip for macOS:* files starting with a dot are hidden in Finder; press `Cmd + Shift + .` to show them.

2. Open `.env` with Notepad / TextEdit and replace `your_api_key_here` with your key, so the line looks like:

   ```
   ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

   No spaces around the `=`, no quote marks. Save the file.

The `.env` file is listed in `.gitignore`, so it is never uploaded if you share the project through git.

---

## 8. Add your document and your pictures

| Put this... | ...in this folder | Notes |
|---|---|---|
| Your article (`.pdf` or `.txt`) | `inputs/documents/` | If several files are there, the **most recently modified** one is used |
| Your pictures (`.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tif`) | `inputs/images/` | **All** of them are used |

Picture tips:

- **Order:** pictures appear in alphabetical/number order of their file names. Name them `01_map.jpg`, `02_manuscript.png`, `03_portrait.jpg`... to control the story.
- **Quantity:** about 8-15 pictures for a 60-second video (4-8 seconds each).
  With fewer pictures, they are reused (with different movements) so that nothing stays on screen too long. With many more, each one flashes by quickly.
- **Quality:** at least about 1080 pixels wide looks sharp. Huge museum scans are fine - they are shrunk automatically.
- **Wide pictures** (landscape manuscripts, panoramas) are shown **in full** on a blurred, darkened copy of themselves, so nothing important is cropped.
  **Tall pictures** fill the whole screen. You can change this - see `--fit` in [step 11](#11-settings-and-options).
- Only use pictures you are **allowed to use** (public-domain museum collections such as Wikimedia Commons, the Met, the British Library, etc.).

---

## 9. Run it

Make sure the terminal is in the project folder and shows `(venv)` (see step 6). Then type:

```
python main.py
```

(macOS/Linux outside a virtual environment: `python3 main.py`.)

You will see progress like this:

```
[1/2] Writing the voice-over script with Claude
  Reading: inputs/documents/my_article.pdf
  Asking Claude (claude-opus-5-5) to write the script - this takes about 10-30 seconds...
  Script ready: 131 words.
  Saved: output/my_article_script.txt

[2/2] Building the video
  Pictures: 12 found in inputs/images
  Creating the voice-over with Edge-TTS (tr-TR-AhmetNeural)...
  Voice-over length: 57.3 seconds
  Rendering 1080x1920 at 30 fps - this can take several minutes...
```

Then a progress bar runs. **Rendering usually takes about 3-10 minutes** depending on your computer - this is normal; do not close the window.

When it says **`Done`**, open the `output` folder:

| File | What it is |
|---|---|
| `my_article_reel.mp4` | **Your finished Reel** - ready to upload |
| `my_article_script.txt` | The narration text (you can read or edit it) |
| `my_article_voice.mp3` | The voice-over on its own |

---

## 10. Everyday use (after the first time)

1. Open a terminal in the project folder (step 5) and activate the environment:
   `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (macOS/Linux).
2. Put the new article in `inputs/documents` and the new pictures in `inputs/images` (remove the old pictures).
3. `python main.py`

**Want to check or edit the script before spending time on rendering?** Run the two steps separately:

```
python main.py --only script      # step 1 only - writes output/<name>_script.txt
```

Open `output/<name>_script.txt` in Notepad, change anything you like (keep it around 120-140 words), save, then:

```
python main.py --only video       # step 2 only - uses the newest script in output/
```

Each step can also be started directly: `python step1_generate_script.py` and `python step2_generate_video.py`.

---

## 11. Settings and options

### Command-line options

Add these after `python main.py`, for example `python main.py --voice tr-TR-EmelNeural --rate -5`.

| Option | Meaning |
|---|---|
| `--only script` / `--only video` | Run just step 1 or just step 2 |
| `--input FILE` | Use a specific PDF/TXT instead of the newest one in `inputs/documents` |
| `--script FILE` | Build the video from a specific script text file |
| `--voice NAME` | Voice. Turkish choices: `tr-TR-AhmetNeural` (male, default), `tr-TR-EmelNeural` (female) |
| `--rate N` | Speaking speed in percent: `--rate -10` = 10 % slower, `--rate 10` = faster |
| `--pitch N` | Pitch in Hz: `--pitch -5` = deeper voice |
| `--fit auto\|cover\|blur` | `auto` (default): wide pictures shown whole on a blurred background, tall ones fill the screen. `cover`: always fill the screen (crops wide pictures; the camera pans across them). `blur`: always show the whole picture |
| `--words N` | Maximum words on screen at once in the subtitles (default 3) |
| `--no-uppercase` | Subtitles in normal letter case instead of capitals |
| `--fps N` | Frames per second (default 30; use 24 for faster rendering) |
| `--model NAME` | Claude model used for the script (default `claude-opus-5-5`) |

### `.env` settings (optional)

The `.env` file can also hold `CLAUDE_MODEL`, `CLAUDE_FALLBACKS`, `TTS_VOICE`, `TTS_RATE`, `TTS_PITCH` and `SUBTITLE_FONT`.
They are explained in the comments inside `.env.example`. Command-line options win over `.env`.

- `CLAUDE_MODEL=claude-sonnet-5-5` uses a cheaper, faster model for the script.
- `CLAUDE_FALLBACKS` is **on** by default: if Anthropic's safety filter wrongly declines a harmless historical text,
  the API retries it on a backup model instead of failing. Set it to `off` if you ever get an error mentioning "fallbacks".

### Subtitle font

The program automatically looks for a bold font that supports Turkish letters (Arial Bold on Windows/macOS, DejaVu/Liberation on Linux).
To use your own look, put a `.ttf` or `.otf` font file into the **`fonts`** folder (the first file found is used), or set
`SUBTITLE_FONT=C:\path\to\font.ttf` in `.env`. Pick a **bold** font that includes the Turkish letters ğ ş ı İ ç ö ü.

### The prompt sent to Claude

The instruction Claude receives is stored in `step1_generate_script.py` (the `PROMPT` value at the top):
*"Sen uzman bir tarih belgeseli yapımcısı ve Instagram Reels içerik üreticisisin..."*. Your article is sent as the message.

---

## 12. Troubleshooting

| What you see | What to do |
|---|---|
| `'python' is not recognized...` / *Python was not found* (Windows) | Python is not on the PATH. Try `py` instead of `python`; otherwise re-run the Python installer -> **Modify** -> tick "Add Python to environment variables". Open a new black window afterwards. |
| `'pip' is not recognized` | Use `python -m pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named ...` or *A required library is missing* | The environment is not active, or the libraries are not installed. Activate it (`venv\Scripts\activate` / `source venv/bin/activate`) and run `pip install -r requirements.txt` again. |
| `error: externally-managed-environment` (macOS/Linux) | You skipped the virtual environment. Do step 6 exactly as written. |
| *No API key found* | The `.env` file is missing, misnamed (`.env.txt`?) or not in the same folder as `main.py`. See step 7b. |
| *Anthropic rejected the API key* | The key was copied incompletely, or contains spaces/quotes. Create a new key and paste it again. |
| Error mentioning **credit balance** / billing | Add credit in the Anthropic console (Settings -> Billing). |
| *Anthropic says there were too many requests* | Wait a minute and run again. |
| *Could not reach Anthropic* / *Could not create the voice-over with Edge-TTS* | Internet problem. Check your connection, turn off a VPN, or try another network (some company/school networks block the voice service). Updating also helps: `pip install -U edge-tts`. |
| *No text could be extracted ... scanned PDF* | The PDF is made of page photos. Run OCR on it (for example in Adobe Acrobat or an online OCR tool) or paste the text into a `.txt` file. |
| *No PDF or TXT file found in 'inputs/documents'* | Put your article in that folder (step 8). |
| *No usable pictures found in 'inputs/images'* | Put `.jpg` / `.png` / `.webp` files in that folder. |
| *No script found in 'output'* | You asked for `--only video` before step 1 produced a script. Run `python main.py` or `python main.py --only script` first. |
| Subtitles show empty squares instead of Turkish letters | The font lacks Turkish characters. Put a bold font that has them (Arial Bold, Montserrat, Roboto...) in the `fonts` folder. |
| Subtitles are timed slightly off | The voice service sometimes returns only sentence timings, so the program estimates the timing inside each sentence. Running again sometimes returns exact word timings. |
| The video is much longer/shorter than 60 s | The length follows the narration. Edit the script text (aim for 120-140 words), or use `--rate` to speak faster/slower, then run `python main.py --only video`. |
| Rendering is very slow | Close other programs, use `--fps 24`, or use fewer/smaller pictures. 3-10 minutes is normal. |
| The program stops with a long red error that is not listed here | Copy the **last 10 lines** of the message and send them to whoever helps you with the project (do **not** include the contents of your `.env` file). |

---

## 13. How it works / project layout

```
ModernHeredotus-reels-engine/
├── main.py                    # runs the whole pipeline (start here)
├── step1_generate_script.py   # Step 1: PDF/TXT -> Claude -> script text
├── step2_generate_video.py    # Step 2: voice-over + pictures + subtitles -> MP4
├── config.py                  # shared folders and helpers
├── requirements.txt           # libraries to install
├── .env.example               # template for your secret API key file (.env)
├── inputs/
│   ├── documents/             # <- put your PDF / TXT here
│   └── images/                # <- put your historical pictures here
├── fonts/                     # optional: your own subtitle font
└── output/                    # <- results appear here
```

**Step 1** reads the newest PDF/TXT (PyPDF2 for PDFs), sends the whole text to Claude through the official `anthropic` library with
the Turkish documentary-producer instruction, removes any formatting symbols from the answer and saves it as `output/<name>_script.txt`.

**Step 2**

1. `edge-tts` creates the Turkish voice-over (`.mp3`) and reports when each word is spoken.
2. The pictures are laid out over the voice-over's length; the changes are nudged to nearby pauses in the narration. Neighbouring pictures dissolve into each other.
3. Each picture gets a slow zoom and drift (alternating direction from picture to picture), calculated with sub-pixel precision so it looks smooth.
4. Short subtitle groups (3 words by default) are drawn in bold white with a thick black outline in the middle of the screen and appear exactly while spoken.
5. MoviePy combines everything and exports the MP4.

---

## 14. Good to know

- **Privacy:** your article text is sent to Anthropic (Claude) to write the script, and the script text is sent to Microsoft's online voice service to create the audio. Do not use confidential documents.
- **Voice service:** `edge-tts` uses the same online voices as Microsoft Edge's "Read aloud". It is free, but it is not an official paid API, so it needs internet and could change without notice.
  If it ever stops working, `pip install -U edge-tts` usually fixes it.
- **Accuracy:** Claude can make factual mistakes or over-dramatise. **Read the script** (`output/..._script.txt`) before publishing; use `--only script`, edit, then `--only video`.
- **Copyright:** make sure you have the right to use both the text and the pictures.
- **Updating:** to update the libraries later, activate the environment and run `pip install -U -r requirements.txt`.
