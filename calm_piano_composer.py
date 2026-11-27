import os
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

# ============================
# MUSICAL THEORY & CONSTANTS
# ============================
NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

SCALES = {
    "Major (Peaceful)":      [0, 2, 4, 5, 7, 9, 11],
    "Natural Minor (Calm)":  [0, 2, 3, 5, 7, 8, 10],
    "Lydian (Dreamy)":       [0, 2, 4, 6, 7, 9, 11],
    "Dorian (Warm)":         [0, 2, 3, 5, 7, 9, 10],
    "Major Pentatonic":      [0, 2, 4, 7, 9],
}

# Classic relaxing piano chord progressions (0-indexed scale degrees)
PROGRESSIONS = {
    "Peaceful (I - V - vi - IV)":      [0, 4, 5, 3],
    "Emotional (vi - IV - I - V)":     [5, 3, 0, 4],
    "Floating (IV - I - V - vi)":      [3, 0, 4, 5],
    "Nostalgic (I - iii - IV - V)":    [0, 2, 3, 4],
    "Meditation (I - IV - I - IV)":    [0, 3, 0, 3],
    "Rainy Day (ii - V - I - vi)":     [1, 4, 0, 5],
}

SCENES = [
    {"name": "Scene 1: Intro",   "bars": 8,  "melody_mult": 0.0, "arp": True,  "pad": False, "octave_lift": 0},
    {"name": "Scene 2: Verse",   "bars": 16, "melody_mult": 0.7, "arp": True,  "pad": False, "octave_lift": 0},
    {"name": "Scene 3: Chorus",  "bars": 16, "melody_mult": 1.0, "arp": True,  "pad": True,  "octave_lift": 12},
    {"name": "Scene 4: Outro",   "bars": 8,  "melody_mult": 0.3, "arp": True,  "pad": True,  "octave_lift": 0},
]

TPB = 480  # Ticks per beat


def scale_note(root_midi, scale_intervals, degree):
    """Return a MIDI note number for a given scale degree (supports negative & >octave)."""
    n = len(scale_intervals)
    octave_shift = degree // n
    idx = degree % n
    return root_midi + octave_shift * 12 + scale_intervals[idx]


def build_calm_voicing(root_midi, scale_intervals, degree):
    """Build an open add9 / sus2 style voicing for relaxing piano."""
    root = scale_note(root_midi, scale_intervals, degree)
    third = scale_note(root_midi, scale_intervals, degree + 2)
    fifth = scale_note(root_midi, scale_intervals, degree + 4)
    ninth = scale_note(root_midi, scale_intervals, degree + 8)  # add9 color
    return {
        "bass": [root - 12, fifth - 12, root],
        "chord": [root, fifth, ninth, third + 12],
        "pad": [root, fifth, third + 12],
    }


def events_to_track(name, channel, events, program=0, bpm=None):
    """Convert absolute-tick events into a valid delta-time Mido MidiTrack."""
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=name, time=0))
    if bpm is not None:
        track.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(Message("program_change", program=program, channel=channel, time=0))

    # Sort: tick asc, then note_off before control_change before note_on
    priority = {"note_off": 0, "control_change": 1, "note_on": 2}
    events.sort(key=lambda e: (e[0], priority.get(e[1].type, 1)))

    last_tick = 0
    for tick, msg in events:
        tick = max(0, int(tick))
        delta = max(0, tick - last_tick)
        msg.time = delta
        track.append(msg)
        last_tick = tick

    track.append(MetaMessage("end_of_track", time=0))
    return track


# ============================
# GENERATOR ENGINE
# ============================
def generate_calm_arrangement(settings):
    """Generate 4 tracks of relaxing piano MIDI + preview data."""
    root_idx = NOTE_NAMES.index(settings["key"])
    scale = SCALES[settings["scale"]]
    prog = PROGRESSIONS[settings["progression"]]
    bpm = settings["bpm"]
    density = settings["density"] / 100.0
    humanize = settings["humanize"] / 100.0
    use_sustain = settings["sustain"]

    # Base C3 = 48
    root_midi = 48 + root_idx

    lh_events = []      # Track 1: Left Hand Bass
    arp_events = []     # Track 2: Right Hand Chords / Arp
    mel_events = []     # Track 3: Right Hand Melody
    pad_events = []     # Track 4: Ambient Pad

    # For canvas preview: list of (track_idx, start_beat, dur_beats, pitch)
    preview_notes = []

    def add_note(ev_list, track_idx, ch, start_tick, dur_tick, pitch, vel):
        jitter = int(random.uniform(-22, 22) * humanize)
        t_on = max(0, start_tick + jitter)
        t_off = max(t_on + 30, t_on + dur_tick)
        v = max(25, min(92, int(vel + random.uniform(-7, 7) * humanize)))
        p = max(24, min(108, int(pitch)))
        ev_list.append((t_on, Message("note_on", note=p, velocity=v, channel=ch)))
        ev_list.append((t_off, Message("note_off", note=p, velocity=0, channel=ch)))
        preview_notes.append((track_idx, t_on / TPB, (t_off - t_on) / TPB, p))

    # Create a 2-bar melodic motif (beat offsets & scale degree offsets)
    motif_beats = [0.0, 1.5, 2.5, 4.0, 5.5, 7.0]
    motif_degrees = [random.choice([0, 2, 4, 5, 7, 9]) for _ in motif_beats]

    current_bar = 0
    bar_ticks = TPB * 4

    for scene in SCENES:
        for b in range(scene["bars"]):
            bar_start = current_bar * bar_ticks
            deg = prog[b % len(prog)]
            voicing = build_calm_voicing(root_midi, scale, deg)

            # Automatic Sustain Pedal (CC64) per bar
            if use_sustain:
                for ch_idx, ev_list in [(0, lh_events), (1, arp_events), (2, mel_events)]:
                    ev_list.append((bar_start, Message("control_change", control=64, value=0, channel=ch_idx)))
                    ev_list.append((bar_start + 20, Message("control_change", control=64, value=127, channel=ch_idx)))

            # --- Track 1: Left Hand Bass (Warm Root + 5th) ---
            if settings["track_lh"]:
                bass_root, bass_fifth, bass_oct = voicing["bass"]
                add_note(lh_events, 0, 0, bar_start, int(bar_ticks * 0.95), bass_root, 54)
                add_note(lh_events, 0, 0, bar_start + TPB, int(bar_ticks * 0.72), bass_fifth, 48)
                if random.random() < 0.65:
                    add_note(lh_events, 0, 0, bar_start + TPB * 2, int(bar_ticks * 0.48), bass_oct, 45)

            # --- Track 2: Right Hand Chords / Gentle Arpeggio ---
            if settings["track_arp"] and scene["arp"]:
                chord_notes = voicing["chord"]
                if random.random() < 0.7:
                    # Broken calm arpeggio across 8th/quarter notes
                    pattern = [0, 1, 2, 3, 2, 1]
                    for step_i, idx in enumerate(pattern):
                        if random.random() > 0.88:
                            continue
                        step_tick = bar_start + int(step_i * (TPB * 0.5)) + TPB
                        if step_tick < bar_start + bar_ticks - 60:
                            add_note(arp_events, 1, 1, step_tick, int(TPB * 1.4), chord_notes[idx], 46)
                else:
                    # Soft rolled chord on beat 1
                    for r_i, note_p in enumerate(chord_notes):
                        roll_offset = r_i * int(28 + 15 * humanize)
                        add_note(arp_events, 1, 1, bar_start + roll_offset, int(bar_ticks * 0.9), note_p, 48)

            # --- Track 3: Sparse Lyrical Melody (Motif-based) ---
            if settings["track_mel"] and scene["melody_mult"] > 0:
                effective_density = density * scene["melody_mult"]
                is_second_bar_of_pair = (b % 2 == 1)
                for m_i, beat_pos in enumerate(motif_beats):
                    if is_second_bar_of_pair and beat_pos < 4.0:
                        continue
                    if not is_second_bar_of_pair and beat_pos >= 4.0:
                        continue

                    local_beat = beat_pos % 4.0
                    if random.random() < effective_density:
                        # Slightly vary last note of phrase
                        deg_offset = motif_degrees[m_i]
                        if b % 4 == 3 and m_i == len(motif_beats) - 1:
                            deg_offset += random.choice([-1, 0, 1, 2])
                        mel_pitch = scale_note(root_midi + 12 + scene["octave_lift"], scale, deg + deg_offset)
                        # Keep melody in sweet piano register (C4 to C6)
                        while mel_pitch > 84:
                            mel_pitch -= 12
                        while mel_pitch < 60:
                            mel_pitch += 12
                        dur = int(TPB * random.choice([1.5, 2.0, 2.5]))
                        add_note(mel_events, 2, 2, bar_start + int(local_beat * TPB), dur, mel_pitch, 62)

            # --- Track 4: Ambient Pad (Whole-bar sustained chords) ---
            if settings["track_pad"] and scene["pad"]:
                for p_note in voicing["pad"]:
                    add_note(pad_events, 3, 3, bar_start, int(bar_ticks * 0.98), p_note, 42)

            current_bar += 1

    # Release sustain at the very end
    end_tick = current_bar * bar_ticks
    if use_sustain:
        for ch_idx, ev_list in [(0, lh_events), (1, arp_events), (2, mel_events)]:
            ev_list.append((end_tick, Message("control_change", control=64, value=0, channel=ch_idx)))

    mid = MidiFile(ticks_per_beat=TPB)
    mid.tracks.append(events_to_track("1 - Left Hand Bass", 0, lh_events, program=0, bpm=bpm))
    mid.tracks.append(events_to_track("2 - RH Chords Arp", 1, arp_events, program=0))
    mid.tracks.append(events_to_track("3 - RH Melody", 2, mel_events, program=0))
    mid.tracks.append(events_to_track("4 - Ambient Pad", 3, pad_events, program=89))  # Warm Pad GM

    return mid, preview_notes, current_bar


# ============================
# DARK-MODE UI (INSTACOMPOSER STYLE)
# ============================
class CalmPianoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Calm Piano Composer — Relaxing Piano + Nature MIDI Generator")
        self.root.geometry("980x620")
        self.root.configure(bg="#181a1f")

        self.current_midi = None
        self.preview_notes = []
        self.total_bars = 48

        self._setup_styles()
        self._build_ui()
        self.on_generate()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame", background="#181a1f")
        style.configure("Panel.TFrame", background="#21252b")
        style.configure("Dark.TLabel", background="#21252b", foreground="#dcdfe4", font=("Segoe UI", 9))
        style.configure("Header.TLabel", background="#181a1f", foreground="#61afef", font=("Segoe UI", 13, "bold"))
        style.configure("Go.TButton", background="#3b82f6", foreground="#ffffff", font=("Segoe UI", 11, "bold"), padding=8)
        style.map("Go.TButton", background=[("active", "#2563eb")])
        style.configure("Export.TButton", background="#10b981", foreground="#ffffff", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Export.TButton", background=[("active", "#059669")])

    def _build_ui(self):
        # Top Header Bar
        top = ttk.Frame(self.root, style="Dark.TFrame", padding=(14, 10))
        top.pack(fill="x")
        ttk.Label(top, text="CALM PIANO COMPOSER", style="Header.TLabel").pack(side="left")
        self.info_label = ttk.Label(top, text="48 Bars • ~2:49 @ 68 BPM", background="#181a1f", foreground="#9ca3af", font=("Segoe UI", 9))
        self.info_label.pack(side="left", padx=16)
        ttk.Button(top, text="Export Multi-Track MIDI (.mid)", style="Export.TButton", command=self.on_export).pack(side="right")

        # Main Piano-Roll Preview Canvas
        canvas_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=(14, 4))
        canvas_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#111317", highlightthickness=1, highlightbackground="#2c313a")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw_preview())

        # Bottom Control Deck (InstaComposer inspired)
        deck = ttk.Frame(self.root, style="Panel.TFrame", padding=14)
        deck.pack(fill="x", padx=14, pady=(6, 14))

        # Column 1: GO Button & Track Toggles
        col1 = ttk.Frame(deck, style="Panel.TFrame")
        col1.grid(row=0, column=0, sticky="ns", padx=(0, 18))

        ttk.Button(col1, text="GO  (Generate)", style="Go.TButton", width=16, command=self.on_generate).pack(pady=(0, 10))

        self.var_lh = tk.BooleanVar(value=True)
        self.var_arp = tk.BooleanVar(value=True)
        self.var_mel = tk.BooleanVar(value=True)
        self.var_pad = tk.BooleanVar(value=True)
        self.var_sustain = tk.BooleanVar(value=True)

        for text, var, color in [
            ("1. Left Hand Bass", self.var_lh, "#60a5fa"),
            ("2. RH Chords / Arp", self.var_arp, "#34d399"),
            ("3. RH Melody", self.var_mel, "#fbbf24"),
            ("4. Ambient Pad", self.var_pad, "#c084fc"),
            ("Auto Sustain (CC64)", self.var_sustain, "#9ca3af"),
        ]:
            cb = tk.Checkbutton(col1, text=text, variable=var, bg="#21252b", fg=color,
                                selectcolor="#111317", activebackground="#21252b", activeforeground=color, font=("Segoe UI", 9))
            cb.pack(anchor="w")

        # Column 2: Key, Scale, Progression
        col2 = ttk.Frame(deck, style="Panel.TFrame")
        col2.grid(row=0, column=1, sticky="ns", padx=14)

        ttk.Label(col2, text="Key", style="Dark.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        self.var_key = tk.StringVar(value="C")
        ttk.Combobox(col2, textvariable=self.var_key, values=NOTE_NAMES, state="readonly", width=24).grid(row=0, column=1, padx=8, pady=3)

        ttk.Label(col2, text="Scale / Mood", style="Dark.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        self.var_scale = tk.StringVar(value="Major (Peaceful)")
        ttk.Combobox(col2, textvariable=self.var_scale, values=list(SCALES.keys()), state="readonly", width=24).grid(row=1, column=1, padx=8, pady=3)

        ttk.Label(col2, text="Progression", style="Dark.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        self.var_prog = tk.StringVar(value="Peaceful (I - V - vi - IV)")
        ttk.Combobox(col2, textvariable=self.var_prog, values=list(PROGRESSIONS.keys()), state="readonly", width=24).grid(row=2, column=1, padx=8, pady=3)

        # Column 3: Sliders (BPM, Melody Density, Humanize)
        col3 = ttk.Frame(deck, style="Panel.TFrame")
        col3.grid(row=0, column=2, sticky="ns", padx=14)

        self.var_bpm = tk.IntVar(value=64)
        self.var_density = tk.IntVar(value=50)
        self.var_humanize = tk.IntVar(value=70)

        self._add_slider(col3, "Tempo (BPM):", self.var_bpm, 50, 90, 0)
        self._add_slider(col3, "Melody Population (%):", self.var_density, 15, 90, 1)
        self._add_slider(col3, "Humanize & Roll (%):", self.var_humanize, 0, 100, 2)

    def _add_slider(self, parent, label, var, lo, hi, row):
        ttk.Label(parent, text=label, style="Dark.TLabel").grid(row=row, column=0, sticky="w", pady=5)
        scale = tk.Scale(parent, from_=lo, to=hi, orient="horizontal", variable=var,
                         bg="#21252b", fg="#dcdfe4", highlightthickness=0, troughcolor="#111317", length=180)
        scale.grid(row=row, column=1, padx=8, pady=2)

    def get_settings(self):
        return {
            "key": self.var_key.get(),
            "scale": self.var_scale.get(),
            "progression": self.var_prog.get(),
            "bpm": self.var_bpm.get(),
            "density": self.var_density.get(),
            "humanize": self.var_humanize.get(),
            "sustain": self.var_sustain.get(),
            "track_lh": self.var_lh.get(),
            "track_arp": self.var_arp.get(),
            "track_mel": self.var_mel.get(),
            "track_pad": self.var_pad.get(),
        }

    def on_generate(self):
        settings = self.get_settings()
        self.current_midi, self.preview_notes, self.total_bars = generate_calm_arrangement(settings)
        total_seconds = int((self.total_bars * 4 / settings["bpm"]) * 60)
        mins, secs = divmod(total_seconds, 60)
        self.info_label.config(text=f"{self.total_bars} Bars  •  ~{mins}:{secs:02d} @ {settings['bpm']} BPM  •  {settings['key']} {settings['scale']}")
        self.draw_preview()

    def draw_preview(self):
        c = self.canvas
        c.delete("all")
        w = max(400, c.winfo_width())
        h = max(240, c.winfo_height())

        lane_h = (h - 24) / 4
        colors = ["#60a5fa", "#34d399", "#fbbf24", "#c084fc"]
        labels = ["Track 1: Left Hand Bass", "Track 2: RH Chords / Arp", "Track 3: RH Melody", "Track 4: Ambient Pad"]

        total_beats = self.total_bars * 4

        # Draw 4 horizontal track lanes
        for i in range(4):
            y0 = 24 + i * lane_h
            c.create_rectangle(0, y0, w, y0 + lane_h, fill="#16191f" if i % 2 == 0 else "#12151a", outline="#262b33")
            c.create_text(10, y0 + 12, text=labels[i], anchor="w", fill=colors[i], font=("Segoe UI", 8, "bold"))

        # Draw Scene dividers along the top
        bar_cursor = 0
        for sc in SCENES:
            x = (bar_cursor / self.total_bars) * w
            c.create_line(x, 0, x, h, fill="#374151", dash=(3, 3))
            c.create_text(x + 6, 12, text=sc["name"], anchor="w", fill="#9ca3af", font=("Segoe UI", 8, "bold"))
            bar_cursor += sc["bars"]

        # Draw MIDI notes
        for track_idx, start_b, dur_b, pitch in self.preview_notes:
            x1 = (start_b / total_beats) * w
            x2 = max(x1 + 2, ((start_b + dur_b) / total_beats) * w)
            # Map pitch within lane
            norm = (pitch - 36) / 52.0
            norm = max(0.08, min(0.92, norm))
            y_base = 24 + track_idx * lane_h
            y = y_base + (1.0 - norm) * (lane_h - 18) + 12
            c.create_rectangle(x1, y - 2, x2, y + 2, fill=colors[track_idx], outline="")

    def on_export(self):
        if not self.current_midi:
            return
        settings = self.get_settings()
        default_name = f"CalmPiano_{settings['key']}_{settings['bpm']}bpm.mid"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".mid",
            initialfile=default_name,
            filetypes=[("MIDI Files", "*.mid")],
            title="Save Calm Piano MIDI Arrangement"
        )
        if filepath:
            self.current_midi.save(filepath)
            messagebox.showinfo("Exported", f"Saved 4-track MIDI file:\n{os.path.basename(filepath)}\n\nDrag this file into your DAW to split across your piano & pad tracks.")


if __name__ == "__main__":
    root = tk.Tk()
    app = CalmPianoApp(root)
    root.mainloop()