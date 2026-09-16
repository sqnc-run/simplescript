# imports ─────────────────────────────────────

                    # websocket imports
import websocket    # WebSocket connection handler
import ssl          # handles wss:// encryption
import certifi      # trusted SSL certificates
import time         # used for reconnection delay (time.sleep(3))

                    # background tasks
import threading    # runs ws/beep/tray icon in separate threads, keeps the UI responsive

                        # gui imports
import tkinter as tk    # builds the desktop window/interface
from tkinter import font as tkfont   # needed to build a strikethrough font

                    # audio imports
import pygame       # loads and plays the notification sound

                                # system / files imports
import os                       # filesystem paths (SAVE_DIR, saved files)
import webbrowser               # opens sqnc.run in the default browser
from datetime import datetime   # timestamps for filenames and display

                    # optional: system tray icon
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# ─────────────────────────────────────────────

# config ──────────────────────────────────────

WS_URL   = "wss://sqnc.run/ws"  # websocket endpoint

# color theme              
BG       = "#000000"
C_OFF    = "#000000"
C_ON     = "#ffffff"
C_DIM    = "#222222"
C_MID    = "#555555"
C_BRIGHT = "#aaaaaa"
C_WHITE  = "#ffffff"
C_BORDER = "#333333"

# font
FONT     = ("Courier New", 10)
FONT_BTN = ("Courier New", 11)
FONT_SML = ("Courier New", 9)

# matrix
CELL   = 36
CELL_E = 33
GAP_E  = 3

MAT_W  = 7 * CELL
MAT_H  = 7 * CELL
MAT_WE = 7 * CELL_E + 6 * GAP_E + 1
MAT_HE = 7 * CELL_E + 6 * GAP_E + 1

WIN_W  = MAT_W + 48
WIN_H  = 620
MAX    = 15

# folder next to the script, not the cwd
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sqnc")
os.makedirs(SAVE_DIR, exist_ok=True) # create it if missing

# audio, path loaded by beep()
SOUND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sell20ct.mp3")

# ─────────────────────────────────────────────

# state variables ─────────────────────────────                            

                            # state variables updated by the WebSocket
current_frame = [0] * 49    # snapshot for live matrix refresh
frame_window  = []          # last 30 frames, used for trigger matching

trigger_pattern = None
trigger_len     = 0
listening       = False
sound_on        = False
record_on       = False
record_frames   = 15
recording       = False
rec_count       = 0
rec_buffer      = []

# ─────────────────────────────────────────────

# sound ───────────────────────────────────────

pygame.mixer.init() # initializes pygame's audio subsystem

def beep():         # loads and plays the notification sound
    try:
        pygame.mixer.music.load(SOUND_PATH)
        pygame.mixer.music.play()
    except: pass    # silently ignores errors
    
# ─────────────────────────────────────────────

# websocket ───────────────────────────────────

def start_ws():                     # start (or restart) the websocket connection in the background
    def on_message(ws, message):    # filters incoming ws messages, adds/drops frames in frame_window
        global current_frame, frame_window
        if len(message) == 49 and all(c in "01" for c in message):
            current_frame = [int(c) for c in message]
            frame_window.append(current_frame[:])
            if len(frame_window) > 30:
                frame_window.pop(0)
    def on_close(ws, *a):           # if connection lost, waits 3s then reconnects via start_ws()
        time.sleep(3)
        start_ws()
    def run():                      # opens the actual (SSL) connection and blocks
        ws = websocket.WebSocketApp(WS_URL, on_message=on_message, on_close=on_close)
        ctx = ssl.create_default_context(cafile=certifi.where())
        ws.run_forever(sslopt={"context": ctx})
    threading.Thread(target=run, daemon=True).start() # start listening
    
# ─────────────────────────────────────────────

# utils ───────────────────────────────────────

def ts():                           # ddmmyy_HHMMSS 290826_143000
    return datetime.now().strftime("%d%m%y_%H%M%S")

def ts_display():                   # 29-08-26 14:30
    return datetime.now().strftime("%d-%m-%y %H:%M")

def save_bits(bits, prefix):        # for saving "trggr"/"rcvd" in SAVE_DIR
    name = f"{prefix}_{ts()}.txt"
    path = os.path.join(SAVE_DIR, name)
    with open(path, "w") as f:
        f.write(bits)
    return name

def load_saved():                   # read SAVE_DIR
    if not os.path.exists(SAVE_DIR):
        return []
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith(".txt")]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(SAVE_DIR, f)), reverse=True)
    return files

def open_site():                    # just open the link
    webbrowser.open("https://sqnc.run")

# ─────────────────────────────────────────────

# app ─────────────────────────────────────────

VERSION = "1.0"

class SimpleScript(tk.Tk):          # the script is a tkinter window (inherits from tk.Tk)
    def __init__(self):             # runs once, when SimpleScript() is called
        tk.Tk.__init__(self)        # required: runs tk.Tk's own setup first
        
        self.overrideredirect(True) # removes the OS titlebar/borders
        self.configure(bg=BG, highlightthickness=1, highlightbackground="#444444")
        self.resizable(False, False)
        self.geometry(f"{WIN_W}x{WIN_H}")

        # center window on screen
        self.update_idletasks()     # force tkinter to update geometry info first
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - WIN_W) // 2
        y = (sh - WIN_H) // 2
        self.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")
        
        self._build_titlebar()      # custom titlebar (close/minimize/drag)
        self._build_home()          # builds the home screen (matrix, buttons, etc.)
        start_ws()                  # opens the websocket connection in the background
        self._tick()                # starts the main 200ms loop
        
        self._drag_x = 0            # overwritten by _drag_start(), avoids AttributeError
        self._drag_y = 0

    def _build_titlebar(self):
        bar = tk.Frame(self, bg=BG, height=28)
        bar.pack(fill="x")
        bar.pack_propagate(False)   # fix frame height to 28 (width is already fixed by fill="x")

        tk.Label(bar, text=f"SimpleScript {VERSION}",
            bg=BG, fg=C_BRIGHT, font=FONT_SML).pack(side="left", padx=10)

        # close button
        tk.Button(bar, text="×", font=("Courier New", 13),
            bg=BG, fg=C_BRIGHT, relief="flat", bd=0,
            activebackground=BG, activeforeground=C_WHITE,
            cursor="hand2", padx=8,
            command=self._confirm_exit).pack(side="right")

        # minimize to tray button
        tk.Button(bar, text="—", font=("Courier New", 11),
            bg=BG, fg=C_BRIGHT, relief="flat", bd=0,
            activebackground=BG, activeforeground=C_WHITE,
            cursor="hand2", padx=8,
            command=self._go_to_tray).pack(side="right")

        # drag window via titlebar
        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)

    def _drag_start(self, e):       # remember click position
        self._drag_x = e.x
        self._drag_y = e.y

    def _drag_move(self, e):        # move the window by the offset
        x = self.winfo_x() + e.x - self._drag_x
        y = self.winfo_y() + e.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _go_to_tray(self):          # hides the window; shows a tray icon if available, else minimizes normally
        self.withdraw()             # hides the window completely (not even in the taskbar)
        if TRAY_AVAILABLE:
            img = Image.new("RGB", (64,64), color="#000000")    # 64x64 icon image
            draw = ImageDraw.Draw(img)
            draw.rectangle([20,20,44,44], fill="#555555")       # draws a gray square on it

            def show(icon, item):   # callback: runs when the user clicks "open SimpleScript" in the tray menu
                icon.stop()
                self.after(0, lambda: (self.deiconify(), self.lift(), self.focus_force()))

            def run_tray():             # builds the tray icon and menu
                self._tray_icon = pystray.Icon("simplescript", img, "SimpleScript",
                    pystray.Menu(pystray.MenuItem("open SimpleScript", show)))
                self._tray_icon.run()   # blocking, like run_forever

            threading.Thread(target=run_tray, daemon=True).start()   # runs it in the background
        else:
            self.iconify()   # fallback: normal minimize

    def _confirm_exit(self):
        popup = tk.Toplevel(self)   # a separate child window, not just a frame
        popup.overrideredirect(True)
        popup.configure(bg=BG, highlightthickness=2, highlightbackground="#ffffff")
        popup.geometry("180x70")

        # centers the popup over the main window
        x = self.winfo_x() + WIN_W//2 - 90
        y = self.winfo_y() + WIN_H//2 - 35
        popup.geometry(f"+{x}+{y}")
        
        popup.grab_set()            # modal: blocks input to the main window until closed
        
        tk.Label(popup, text="exit?", bg=BG, fg=C_MID, font=FONT).pack(pady=(14,8))
        btn_row = tk.Frame(popup, bg=BG)
        btn_row.pack()
        tk.Button(btn_row, text="yes", font=FONT,
            bg=BG, fg=C_MID, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=C_BORDER,
            cursor="hand2", padx=10, pady=3,
            activebackground=BG, activeforeground=C_WHITE,
            command=self.destroy).pack(side="left", padx=(0,10))    # closes the whole app

        tk.Button(btn_row, text="no", font=FONT,
            bg=BG, fg=C_DIM, relief="flat", bd=0,
            cursor="hand2", padx=10, pady=3,
            activebackground=BG, activeforeground=C_MID,
            command=popup.destroy).pack(side="left")    # just closes the popup

# ─────────────────────────────────────────────

# helpers ─────────────────────────────────────

    # builds a styled button, unpacked
    def _mkbtn(self, parent, label, cmd, dim=False, small=False):
        f = FONT_SML if small else FONT_BTN             # pick font size
        fg = C_DIM if dim else C_MID                    # pick text color
        hb = "#111111" if dim else C_BORDER             # pick border color
        return tk.Button(parent, text=label, font=f,
            bg=BG, fg=fg,
            activebackground=BG, activeforeground=C_WHITE,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=hb,
            cursor="hand2", padx=14, pady=4,
            command=cmd)

    # builds a text-link-style button
    def _mklink(self, parent, label, cmd):          
        return tk.Button(parent, text=label, font=FONT_SML,
            bg=BG, fg=C_DIM,
            activebackground=BG, activeforeground=C_MID,
            relief="flat", bd=0, cursor="hand2",
            command=cmd)

    # builds a styled checkbox
    def _mkcheck(self, parent, label, var, cmd):
        return tk.Checkbutton(parent, text=label, variable=var,
            bg=BG, fg=C_DIM, selectcolor=BG,
            activebackground=BG, activeforeground=C_MID,
            font=FONT, cursor="hand2", command=cmd)

    # builds the bottom/right bar
    def _bottom_bar(self, parent, back_cmd=None):
        bar = tk.Frame(parent, bg=BG)
        bar.pack(side="bottom", fill="x", padx=24, pady=12)

        if back_cmd:    # editor/saved view: show a "← back" link instead of "recorded"
            bottom_row = tk.Frame(bar, bg=BG)
            bottom_row.pack(fill="x")
            self._mklink(bottom_row, "sqnc.run", open_site).pack(side="left")
            self._mklink(bottom_row, "← back", back_cmd).pack(side="right")

        else:           # home screen: show "recorded", clickable only if saved files exist
            bottom_row = tk.Frame(bar, bg=BG)
            bottom_row.pack(fill="x")
            self._mklink(bottom_row, "sqnc.run", open_site).pack(side="left")
            has_files = len(load_saved()) > 0
            if has_files:
                tk.Button(bottom_row, text="recorded", font=FONT_SML,
                    bg=BG, fg=C_MID,
                    activebackground=BG, activeforeground=C_BRIGHT,
                    relief="flat", bd=0, cursor="hand2",
                    command=self._open_saved_view).pack(side="right")   # opens saved view
            else:
                # overstrike is a font attribute, not a widget option - keep a reference so Tk doesn't garbage-collect it
                self._recorded_strike_font = tkfont.Font(family=FONT_SML[0], size=FONT_SML[1], overstrike=True)
                tk.Label(bottom_row, text="recorded", font=self._recorded_strike_font,
                    bg=BG, fg="#333333").pack(side="right")   # greyed out, no files yet

        return bar

    def _refresh_home_bar(self):   # rebuilds the home bottom bar so "recorded" reflects new saved files
        self.home_bar.destroy()
        self.home_bar = self._bottom_bar(self.home)


# ─────────────────────────────────────────────

# home ────────────────────────────────────────

    def _build_home(self):
        self.home = tk.Frame(self, bg=BG)
        self.home.pack(fill="both", expand=True)

        self.home_bar = self._bottom_bar(self.home) #place bottom bar before the content

        content = tk.Frame(self.home, bg=BG, padx=24, pady=20)
        content.pack(fill="both", expand=True)

        # live matrix
        self.canvas = tk.Canvas(content, width=MAT_W, height=MAT_H,
            bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(anchor="w", pady=(0,16))
        self.cells = []
        for r in range(7):
            for c in range(7):
                rect = self.canvas.create_rectangle(
                    c*CELL, r*CELL, c*CELL+CELL, r*CELL+CELL,
                    fill=C_OFF, outline="")
                self.cells.append(rect)

        # readonly text box
        self.notif_frame = tk.Frame(content, bg=BG) # shown later by _add_match()
        self.notif_text = tk.Text(self.notif_frame,
            height=5, width=30,
            bg=BG, fg=C_BRIGHT, font=FONT,
            relief="flat", bd=0,
            highlightthickness=0,
            state="disabled",   # read-only
            wrap="none")
        self.notif_text.pack(fill="x", expand=True)
        self.notif_text.bind("<MouseWheel>",
            lambda e: self.notif_text.yview_scroll(int(-1*(e.delta/120)), "units")) # mouse wheel scroll
        self.notif_arrow = tk.Label(self.notif_frame, text="▼",
            bg=BG, fg=C_DIM, font=FONT_SML, anchor="center")        # ▼ 
        self.notif_matches = []                                     # timestamps of recorded matches

        # status
        self.status_lbl = tk.Label(content, text="— no trigger set",
            bg=BG, fg=C_DIM, font=FONT, anchor="w") # updated live by _tick(), _do_listen(), _do_stop()
        self.status_lbl.pack(anchor="w", pady=(0,12))

        # btns
        btn_row = tk.Frame(content, bg=BG)                          # container side by side buttons
        btn_row.pack(anchor="w", pady=(0,14))
        
        self.btn_set_trigger = self._mkbtn(btn_row, "set_trigger", self._open_editor)   # opens editor
        self.btn_set_trigger.pack(side="left", padx=(0,8))  # saved on self: _do_listen() disables it while listening
        self.btn_stop = self._mkbtn(btn_row, "stop_seek", self._do_stop)    # stops listening/recording
        self.btn_stop.pack(side="left")

        # opts
        opts = tk.Frame(content, bg=BG)
        opts.pack(anchor="w", pady=(0,14))
        
        self.sound_var = tk.BooleanVar()    # tracks the "sound" checkbox state
        self.record_var = tk.BooleanVar()   # tracks the "record" checkbox state
        
        self._mkcheck(opts, "sound", self.sound_var, self._toggle_sound).pack(anchor="w")
        
        rec_row = tk.Frame(opts, bg=BG)     # row: record checkbox + frame count stepper
        rec_row.pack(anchor="w", pady=(4,0))
        self._mkcheck(rec_row, "record", self.record_var, self._toggle_record).pack(side="left")
        
        self.fr_frame = tk.Frame(rec_row, bg=BG)    # shown/hidden by _toggle_record()
        tk.Button(self.fr_frame, text="-", font=FONT, bg=BG, fg=C_DIM,
            relief="flat", bd=0, cursor="hand2",
            activebackground=BG, activeforeground=C_MID,
            command=lambda: self._fr_change(-1)).pack(side="left")  # lambda passes -1 to _fr_change
        
        self.fr_lbl = tk.Label(self.fr_frame, text="15", bg=BG, fg=C_MID, font=FONT, width=3)
        self.fr_lbl.pack(side="left")
        
        tk.Button(self.fr_frame, text="+", font=FONT, bg=BG, fg=C_DIM,
            relief="flat", bd=0, cursor="hand2",
            activebackground=BG, activeforeground=C_MID,
            command=lambda: self._fr_change(1)).pack(side="left")   # lambda passes +1 to _fr_change
        
        tk.Label(self.fr_frame, text=" frame", bg=BG, fg=C_DIM, font=FONT).pack(side="left")

# ─────────────────────────────────────────────

# home actions ────────────────────────────────

    def _add_match(self, ora):                                  # logs a match timestamp
        self.notif_matches.append(ora)
        if len(self.notif_matches) > 50:                        # cap history at 50 entries
            self.notif_matches.pop(0)
        self.notif_text.configure(state="normal")               # briefly re-enable to write
        self.notif_text.insert("1.0", f"— matched  {ora}\n")    # newest on top
        if len(self.notif_matches) > 50:
            self.notif_text.delete("end-2l", "end")             # trim the oldest line off the bottom     
        self.notif_text.configure(state="disabled")             # back to read-only
        self.notif_frame.pack(anchor="w", pady=(0,6))           # reveal the box on first mat
        if len(self.notif_matches) > 5:
            self.notif_arrow.pack(pady=(2,0))                   # show "more to scroll" arrow
        else:
            self.notif_arrow.pack_forget()

    def _toggle_sound(self):    # syncs the checkbox into the global sound_on flag
        global sound_on
        sound_on = self.sound_var.get()

    def _toggle_record(self):   # syncs the checkbox + shows/hides the frame-count stepper
        global record_on
        record_on = self.record_var.get()
        if record_on: self.fr_frame.pack(side="left")
        else: self.fr_frame.pack_forget()

    def _fr_change(self, d):    # +1/-1 to record_frames, clamped between 1 and MAX
        global record_frames
        record_frames = max(1, min(MAX, record_frames + d))
        self.fr_lbl.config(text=str(record_frames))

# ─────────────────────────────────────────────

# editor ──────────────────────────────────────

    def _open_editor(self):     # swaps home for the trigger-editing screen
        self.home.pack_forget()
        self.editor = tk.Frame(self, bg=BG)
        self.editor.pack(fill="both", expand=True)

        content = tk.Frame(self.editor, bg=BG, padx=24, pady=20)
        content.pack(fill="both", expand=True)

        self.e_frames = [[0]*49]    # the sequence being edited, starts with one blank frame
        self.e_cur = 0              # index of the frame currently shown

        # nav
        nav = tk.Frame(content, bg=BG)
        nav.pack(anchor="w", pady=(0,12))
        self.e_prev = tk.Button(nav, text="‹", font=("Courier New",18),
            bg=BG, fg=C_MID, relief="flat", bd=0, cursor="hand2",
            activebackground=BG, activeforeground=C_WHITE,
            command=lambda: self._e_go(-1))
        self.e_prev.pack(side="left")
        self.e_label = tk.Label(nav, text="frame 1 / 1", bg=BG, fg=C_MID, font=FONT)
        self.e_label.pack(side="left", padx=10)
        self.e_next = tk.Button(nav, text="›", font=("Courier New",18),
            bg=BG, fg=C_MID, relief="flat", bd=0, cursor="hand2",
            activebackground=BG, activeforeground=C_WHITE,
            command=lambda: self._e_go(1))
        self.e_next.pack(side="left")
        tk.Button(nav, text="+", font=FONT, bg=BG, fg=C_MID, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=C_BORDER,
            cursor="hand2", padx=6, pady=2,
            activebackground=BG, activeforeground=C_WHITE,
            command=self._e_add).pack(side="left", padx=(12,4))
        tk.Button(nav, text="−", font=FONT, bg=BG, fg=C_MID, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=C_BORDER,
            cursor="hand2", padx=6, pady=2,
            activebackground=BG, activeforeground=C_WHITE,
            command=self._e_del).pack(side="left")  # delete current frame

        # editable 7x7 grid
        self.e_canvas = tk.Canvas(content, width=MAT_WE, height=MAT_HE,
            bg=BG, highlightthickness=0, bd=0)
        self.e_canvas.pack(anchor="w", pady=(0,14))
        self.e_cells = []
        for r in range(7):
            for c in range(7):
                x0 = c*(CELL_E+GAP_E); y0 = r*(CELL_E+GAP_E)
                idx = r*7+c
                rect = self.e_canvas.create_rectangle(
                    x0, y0, x0+CELL_E, y0+CELL_E,
                    fill=C_OFF, outline="#222222")
                self.e_canvas.tag_bind(rect, "<Button-1>",
                    lambda e, i=idx: self._e_toggle(i)) # click toggles that cell; i is frozen per-cell
                self.e_cells.append(rect)
        self._e_render()

        # bottom row: listen button (left) + hamburger menu (right)
        btn_row = tk.Frame(content, bg=BG)
        btn_row.pack(fill="x", pady=(0,8))

        self._mkbtn(btn_row, "listen", self._do_listen).pack(side="left")

        self.e_menu_btn = tk.Button(btn_row, text="≡", font=("Courier New", 15),
            bg=BG, fg=C_MID, relief="flat", bd=0,
            highlightthickness=0,
            cursor="hand2", padx=12, pady=5,
            activebackground=BG, activeforeground=C_WHITE,
            command=self._toggle_e_menu)
        self.e_menu_btn.pack(side="right")

        # dropdown menu (built once, shown/hidden via place/place_forget)
        self.e_menu = tk.Frame(content, bg="#0a0a0a",
            highlightthickness=1, highlightbackground="#333333")
        self.e_menu_visible = False
        self.e_menu_items = {}
        self._menu_cmds = {}

        items = [
            ("copy frame",     self._e_copy_frame),
            ("copy sequence",  self._e_copy_seq),
            ("paste frame",    self._e_paste_frame),
            ("paste sequence", self._e_paste_seq),
            ("save sequence",  self._e_save_seq),
            ("clear frame",    self._e_clear_frame),
            ("clear sequence", self._e_clear_seq),
        ]
        for i, (label, cmd) in enumerate(items):                    # builds one menu row per item
            self._menu_cmds[label] = cmd
            btn = tk.Button(self.e_menu, text=label, font=FONT,
                bg="#0a0a0a", fg="#555555",
                activebackground="#111111", activeforeground=C_BRIGHT,
                relief="flat", bd=0, anchor="w",
                padx=14, cursor="hand2",
                command=lambda c=cmd: (self._hide_e_menu(), c())    # hide menu, then run the action
            )
            btn.grid(row=i, column=0, sticky="ew", ipady=3)
            self.e_menu_items[label] = btn
        self.e_menu.columnconfigure(0, weight=1)

        # error/status message under the buttons
        self.e_msg_lbl = tk.Label(content, text="", bg=BG, fg=C_DIM, font=FONT,
            wraplength=MAT_WE, justify="left")
        self.e_msg_lbl.pack(anchor="w", pady=(4,0))

        self._bottom_bar(self.editor, back_cmd=self._close_editor)

    def _close_editor(self):        # tears down the editor, returns to home
        self.editor.pack_forget()
        self.editor.destroy()
        self.home.pack(fill="both", expand=True)

    def _e_go(self, d):             # moves to the previous/next frame, clamped to valid range
        self.e_cur = max(0, min(len(self.e_frames)-1, self.e_cur+d))
        self._e_render(); self._e_nav_update()

    def _e_add(self):               # inserts a blank frame after the current one (up to MAX)
        if len(self.e_frames) >= MAX: return
        self.e_frames.insert(self.e_cur+1, [0]*49)
        self.e_cur += 1
        self._e_render(); self._e_nav_update()

    def _e_del(self):               # deletes the current frame (keeps at least 1)
        if len(self.e_frames) == 1: return
        del self.e_frames[self.e_cur]
        self.e_cur = min(self.e_cur, len(self.e_frames)-1)
        self._e_render(); self._e_nav_update()

    def _e_toggle(self, i):         # flips one cell (0<->1) in the current frame
        self.e_frames[self.e_cur][i] ^= 1
        self._e_render()

    def _e_render(self):            # redraws the grid to match the current frame's bits
        frame = self.e_frames[self.e_cur]
        for i, rect in enumerate(self.e_cells):
            self.e_canvas.itemconfig(rect,
                fill=C_ON if frame[i] else C_OFF,
                outline="#222222")

    def _e_nav_update(self):        # updates the "frame X / Y" label and prev/next button state
        self.e_label.config(text=f"frame {self.e_cur+1} / {len(self.e_frames)}")
        self.e_prev.config(state="normal" if self.e_cur > 0 else "disabled")
        self.e_next.config(state="normal" if self.e_cur < len(self.e_frames)-1 else "disabled")

    def _toggle_e_menu(self):       # shows/hides the hamburger dropdown, positioned above the canvas
        if self.e_menu_visible: self._hide_e_menu()
        else:
            self.e_menu.update_idletasks()
            menu_h = self.e_menu.winfo_reqheight()
            menu_w = self.e_menu.winfo_reqwidth()
            btn_x = self.e_menu_btn.winfo_rootx() - self.winfo_rootx()
            canvas_y = self.e_canvas.winfo_rooty() - self.winfo_rooty()
            canvas_h = self.e_canvas.winfo_height()
            y = canvas_y + canvas_h - menu_h
            x = btn_x - menu_w
            x = x - 20
            y = y + 160
            self.e_menu.place(x=x, y=y)     # absolute positioning (not pack/grid)
            self.e_menu.lift()              # bring it above other widgets
            self.e_menu_visible = True

    def _update_menu_state(self): pass      # unused, dead code (never called)

    def _hide_e_menu(self):
        self.e_menu.place_forget()
        self.e_menu_visible = False

    def _e_copy_frame(self):
        t = "".join(str(b) for b in self.e_frames[self.e_cur])  # copies the current frame's bits to the clipboard
        self.clipboard_clear(); self.clipboard_append(t)

    def _e_copy_seq(self):                  # copies the whole sequence (all frames concatenated) to the clipboard
        t = "".join("".join(str(b) for b in f) for f in self.e_frames)
        self.clipboard_clear(); self.clipboard_append(t)

    def _e_paste_frame(self):               # replaces the current frame with 49 bits from the clipboard
        try:
            t = self.clipboard_get().strip().replace(" ","").replace("\n","")
            if not all(c in "01" for c in t):
                self._e_show_msg("only 0 and 1 allowed")
                return
            if len(t) != 49:
                self._e_show_msg("frame: exactly 49 characters")
                return
            self.e_frames[self.e_cur] = [int(c) for c in t]
            self._e_render()
        except: pass                        # e.g. clipboard empty or not text

    def _e_paste_seq(self):                 # overwrites/appends frames from a longer clipboard sequence
        try:
            t = self.clipboard_get().strip().replace(" ","").replace("\n","")
            if not all(c in "01" for c in t):
                self._e_show_msg("only 0 and 1 allowed")
                return
            if len(t) % 49 != 0:
                self._e_show_msg("sequence: multiple of 49")
                return
            if len(t) < 98:
                self._e_show_msg("sequence: min 2 frames (98 chars)")
                return
            n = min(len(t)//49, MAX)
            new_frames = [[int(c) for c in t[i*49:(i+1)*49]] for i in range(n)] # starting at the current position: overwrite existing frames, append the rest
            pos = self.e_cur
            for i, f in enumerate(new_frames):
                if pos + i < len(self.e_frames):
                    self.e_frames[pos + i] = f
                else:
                    if len(self.e_frames) < MAX:
                        self.e_frames.append(f)
            self._e_render(); self._e_nav_update()
        except: pass

    def _e_show_msg(self, msg):         # shows a message under the buttons, auto-clears after 2s
        self.e_msg_lbl.config(text=msg)
        self.after(2000, lambda: self.e_msg_lbl.config(text=""))

    def _e_save_frame(self):            # unused, dead code (no menu item calls this - only "save sequence" is wired)
        bits = "".join(str(b) for b in self.e_frames[self.e_cur])
        save_bits(bits, "trggr")

    def _e_save_seq(self):              # saves the whole sequence to disk with the "trggr" prefix
        bits = "".join("".join(str(b) for b in f) for f in self.e_frames)
        name = save_bits(bits, "trggr")
        self._refresh_home_bar()   # "recorded" is now clickable since a file was just saved
        self.e_msg_lbl.config(text=f"saved as {name}", fg=C_BRIGHT)
        self.after(2000, lambda: self.e_msg_lbl.config(text="", fg=C_DIM))

    def _e_clear_frame(self):           # resets the current frame to all zeros
        self.e_frames[self.e_cur] = [0]*49
        self._e_render()

    def _e_clear_seq(self):             # resets the whole sequence back to one blank frame
        self.e_frames = [[0]*49]; self.e_cur = 0
        self._e_render(); self._e_nav_update()

# ─────────────────────────────────────────────

# listen ──────────────────────────────────────

    def _do_listen(self):   # loads the sequence into the trigger
        global listening, trigger_pattern, trigger_len
        if len(self.e_frames) < 2:
            self.e_msg_lbl.config(text="min 2 frames")
            return
        trigger_pattern = [list(f) for f in self.e_frames]  # copy, so later edits don't affect it
        trigger_len = len(self.e_frames)
        listening = True
        self._close_editor()
        self.status_lbl.config(text="— seeking trigger", fg=C_DIM)
        self.btn_set_trigger.config(state="disabled", fg="#1a1a1a",
            disabledforeground="#1a1a1a", highlightbackground="#111111")

    def _do_stop(self):     # disarms the trigger and resets state back to idle
        global listening, trigger_pattern, trigger_len, recording
        listening = False; recording = False
        trigger_pattern = None; trigger_len = 0
        self.status_lbl.config(text="— no trigger set", fg=C_DIM)
        self.btn_set_trigger.config(state="normal", fg=C_MID,
            highlightbackground=C_BORDER, cursor="hand2",
            command=self._open_editor)

# ─────────────────────────────────────────────

# saved view ──────────────────────────────────

    def _open_saved_view(self):         # swaps home for a scrollable list of saved sequences
        self.home.pack_forget()
        self.saved_view = tk.Frame(self, bg=BG)
        self.saved_view.pack(fill="both", expand=True)

        content = tk.Frame(self.saved_view, bg=BG, padx=24, pady=20)
        content.pack(fill="both", expand=True)

        # Scroll container
        sc = tk.Canvas(content, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(content, orient="vertical", command=sc.yview)
        inner = tk.Frame(sc, bg=BG)
        inner.bind("<Configure>", lambda e: sc.configure(scrollregion=sc.bbox("all")))
        sc.create_window((0,0), window=inner, anchor="nw")
        sc.configure(yscrollcommand=sb.set)
        sc.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        sc.bind_all("<MouseWheel>",     # scroll the list with the mouse wheel
            lambda e: sc.yview_scroll(int(-1*(e.delta/120)), "units") if sc.winfo_exists() else None)

        files = load_saved()
        if not files:
            tk.Label(inner, text="— empty", bg=BG, fg=C_DIM, font=FONT).pack(anchor="w")
        else:
            for fn in files:
                self._render_saved_entry(inner, fn, sc)     # one row per saved file

        self._bottom_bar(self.saved_view, back_cmd=self._close_saved_view)

    def _render_saved_entry(self, parent, fn, scroll_canvas):   # expandable row for saved file
        prefix = fn.split("_")[0]
        color = "#555555"
        entry = tk.Frame(parent, bg=BG)
        entry.pack(anchor="w", fill="x", pady=(0,10))

        hdr = tk.Frame(entry, bg=BG)
        hdr.pack(anchor="w", fill="x")
        hdr.columnconfigure(1, weight=1)

        expanded = tk.BooleanVar(value=False)       # whether the mini-matrix preview is shown
        mini_container = tk.Frame(entry, bg=BG)

        def toggle_expand():            # callback: expand/collapse the preview on arrow click
            if expanded.get():
                mini_container.pack_forget()
                expanded.set(False)
                arrow_btn.config(text="▶")
            else:
                mini_container.pack(anchor="w", pady=(4,0))
                expanded.set(True)
                arrow_btn.config(text="▼")
                scroll_canvas.after(50, lambda: scroll_canvas.configure(
                    scrollregion=scroll_canvas.bbox("all")))

        arrow_btn = tk.Button(hdr, text="▶", font=FONT_SML,
            bg=BG, fg=C_DIM, relief="flat", bd=0, cursor="hand2",
            activebackground=BG, activeforeground=C_MID,
            command=toggle_expand)
        arrow_btn.grid(row=0, column=0, sticky="w", padx=(0,4))

        display_name = fn[:-4] if fn.endswith(".txt") else fn   # strip the .txt extension for display
        tk.Label(hdr, text=display_name, bg=BG, fg=color, font=FONT).grid(row=0, column=1, sticky="w")

        # Copy
        def copy_seq(f=fn):     # reads the file and copies its bits to the clipboard
            path = os.path.join(SAVE_DIR, f)
            try:
                with open(path) as fp:
                    bits = fp.read().strip()
                self.clipboard_clear(); self.clipboard_append(bits)
            except: pass

        tk.Button(hdr, text="copy", font=FONT_SML,
            bg=BG, fg=C_DIM, relief="flat", bd=0, cursor="hand2",
            activebackground=BG, activeforeground=C_MID,
            command=copy_seq).grid(row=0, column=2, sticky="e", padx=(8,4))

        tk.Button(hdr, text="×", font=FONT,
            bg=BG, fg=C_DIM, relief="flat", bd=0, cursor="hand2",
            activebackground=BG, activeforeground=C_MID,
            command=lambda f=fn: (self._del_saved(f), self._close_saved_view(), self._open_saved_view())
            ).grid(row=0, column=3, sticky="e")     # delete then rebuild the whole view

        # saved mini-matrix
        path = os.path.join(SAVE_DIR, fn)
        try:
            with open(path) as f:
                bits = f.read().strip().replace("\n","")
            n = min(len(bits) // 49, MAX)
            mini_row = None
            for i in range(n):
                if i % 5 == 0:
                    mini_row = tk.Frame(mini_container, bg=BG) # new row every 5 mini-matrices
                    mini_row.pack(anchor="w", pady=(0,4))
                frame_bits = [int(b) for b in bits[i*49:(i+1)*49]]
                c = tk.Canvas(mini_row, width=42, height=42,
                    bg=BG, highlightthickness=0, bd=0)
                c.pack(side="left", padx=(0,4))
                for ri in range(7):
                    for ci in range(7):
                        x0 = ci*6; y0 = ri*6
                        col = "#666666" if frame_bits[ri*7+ci] else "#111111"
                        c.create_rectangle(x0,y0,x0+6,y0+6,fill=col,outline="")
        except: pass

    def _close_saved_view(self):    # tears down the saved view, returns to home
        self.unbind_all("<MouseWheel>")
        try:
            self.saved_view.pack_forget()
            self.saved_view.destroy()
        except: pass
        self.home.pack(fill="both", expand=True)

    def _del_saved(self, fn):       # deletes one saved file from disk
        path = os.path.join(SAVE_DIR, fn)
        if os.path.exists(path):
            os.remove(path)
        self._refresh_home_bar()   # "recorded" goes back to greyed out if that was the last file

    def _render_saved(self): pass   # unused, dead code (never called)

# ─────────────────────────────────────────────

# match ───────────────────────────────────────

    def _check_match(self): # compares the last trigger_len frames against trigger_pattern
        if trigger_pattern is None or len(frame_window) < trigger_len:
            return False
        window = frame_window[-trigger_len:]    # most recent frames, same length as the pattern
        return all(window[i][j] == trigger_pattern[i][j]
                   for i in range(trigger_len) for j in range(49))  # exact match, every bit

# ─────────────────────────────────────────────

# render ──────────────────────────────────────

    def _render_live(self, frame, flash=False): # paints the live matrix from a frame's bits
        for i, rect in enumerate(self.cells):
            color = C_ON if (flash or frame[i]) else C_OFF  # flash=True forces everything white (match feedback)
            self.canvas.itemconfig(rect, fill=color)
            
# ─────────────────────────────────────────────

# tick ────────────────────────────────────────

    def _tick(self):    # main loop, 200ms delay via self.after
        global recording, rec_count, rec_buffer, frame_window

        self._render_live(current_frame) # keep the live matrix in sync

        if listening and not recording and self._check_match():     # trigger just fired
            if sound_on:
                threading.Thread(target=beep, daemon=True).start()  # non-blocking beep
            self._render_live(current_frame, flash=True)            # visual flash feedback
            ora = ts_display()
            self._add_match(ora)
            frame_window.clear()    # avoid immediately re-matching the same frames
            if record_on:
                recording = True; rec_count = 0; rec_buffer = []
                self.status_lbl.config(text="— recording...", fg=C_BRIGHT)
            else:
                self.status_lbl.config(text="— seeking trigger", fg=C_DIM)

        elif recording:     # capturing frames after a match
            rec_buffer.append(current_frame[:])
            rec_count += 1
            self.status_lbl.config(text=f"— recording {rec_count}/{record_frames}", fg=C_BRIGHT)
            if rec_count >= record_frames:
                recording = False
                bits = "".join("".join(str(b) for b in f) for f in rec_buffer)
                save_bits(bits, "rcvd")
                self._refresh_home_bar()   # "recorded" is now clickable since a file was just saved
                self.status_lbl.config(text="— seeking trigger", fg=C_DIM)

        self.after(200, self._tick)     # reschedules itself, keeps the loop going

# ─────────────────────────────────────────────

# run ───────────────────────────────────────

if __name__ == "__main__":
    app = SimpleScript()
    app.mainloop()
