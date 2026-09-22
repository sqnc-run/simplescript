# SimpleScript
[→ demo: vimeo.com/1228978442](https://vimeo.com/1228978442)

A desktop app (Python + tkinter) that connects to [sqnc.run](https://sqnc.run) over WebSocket, watches a live stream of 7x7 binary frames, and alerts you when a frame sequence you define ("trigger") shows up.

## What it does

- Connects to `wss://sqnc.run/ws` and receives a continuous stream of 7x7 binary frames.
- Lets you build a multi-frame trigger pattern in an in-app editor (up to 15 frames).
- Continuously compares incoming frames against the trigger while listening is active.
- On a match: plays a sound, flashes the UI, and (optionally) records the frames that follow to disk.
- Saved/recorded sequences can be reviewed, reloaded into the editor, or deleted from a "saved" view.
- Optional system-tray icon so the app can run minimized in the background.

## Requirements

- Python 3.9+
- Dependencies listed in `requirements.txt`

## Setup

```bash
pip install -r requirements.txt
python SimpleScript_v1.py
```

Add a notification sound at `assets/sell20ct.mp3` (rename your file to match), or edit `SOUND_PATH` in the script to use a different name or location.

## Notes

- Saved and recorded frame sequences are written to a `sqnc/` folder next to the script (created automatically on first run; not tracked in git).
- The system-tray icon feature (`pystray` + `Pillow`) is optional - the app still runs without it, just without the tray icon.

## API documentation

Full documentation for the sqnc.run WebSocket (listen) and HTTP (inject) API is in [`DOCS.md`](DOCS.md).
