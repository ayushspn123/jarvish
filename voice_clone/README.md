# Voice cloning (OpenVoice v2)

JARVIS can speak in **your own voice**. Because the cloning models don't run on Python 3.13,
this lives in a separate Python 3.11 environment (`.venv-clone`) and runs as a small local
server that the main app talks to. On a CPU-only laptop, expect **~5 seconds per short reply**.

## What's here

| Path | Purpose |
|------|---------|
| `reference.wav` | A recording of **your** voice — what gets cloned. Make with `record_sample.py`. |
| `openvoice_server.py` | Loads MeloTTS + OpenVoice once, serves synthesis on `http://127.0.0.1:5111`. |
| `OpenVoice/` | The vendored OpenVoice repo (its `openvoice` Python module). |
| `checkpoints_v2/` | OpenVoice v2 model weights (converter + base-speaker fingerprints). |

## How it works

```
text ─▶ MeloTTS (fast base voice) ─▶ OpenVoice tone-color converter ─▶ your voice ─▶ .wav
```

The main app (`JARVIS_TTS_ENGINE=clone`) auto-starts this server, then POSTs text to `/tts`
and plays the returned audio. First launch loads the model + warms up (~40s); after that each
reply is a few seconds.

## Re-recording your voice

```powershell
.\.venv\Scripts\python.exe record_sample.py
```
Speak clearly in a quiet room for ~25s. Longer, cleaner samples clone better. Restart JARVIS
(or the clone server) afterward so it re-fingerprints the new recording.

## Rebuilding the environment from scratch

```powershell
# 1. Get Python 3.11 (via uv) and create the env
.\.venv\Scripts\python.exe -m pip install uv
.\.venv\Scripts\uv.exe python install 3.11
.\.venv\Scripts\uv.exe venv .venv-clone --python 3.11

# 2. Install the engine (CPU PyTorch must be 2.8 to avoid torchcodec)
.\.venv\Scripts\uv.exe pip install --python .venv-clone "torch==2.8.0" "torchaudio==2.8.0" --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\uv.exe pip install --python .venv-clone flask soundfile wavmark "git+https://github.com/myshell-ai/MeloTTS.git"
.\.venv-clone\Scripts\python.exe -m unidic download

# 3. Get OpenVoice code + weights
cd voice_clone
git clone --depth 1 https://github.com/myshell-ai/OpenVoice.git
.\..\.venv-clone\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='myshell-ai/OpenVoiceV2', local_dir='checkpoints_v2')"
cd ..

# 4. NLTK data for MeloTTS
.\.venv-clone\Scripts\python.exe -c "import nltk; [nltk.download(p) for p in ['averaged_perceptron_tagger_eng','cmudict','averaged_perceptron_tagger']]"
```

## Switching back to the fast neural voice

Set `JARVIS_TTS_ENGINE=edge` in `.env`. The cloned-voice server won't be used.
