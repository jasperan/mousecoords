# mousecoords

GUI automation toolkit with computer vision, macro recording, and game automation.

What started as a 5-line coordinate grabber is now a full automation platform:

- **Computer Vision** — find buttons by template matching (OpenCV), not hardcoded pixels
- **OCR** — read numbers and text from the screen with Tesseract
- **Macro Record/Replay** — record mouse and keyboard, save as JSON, replay at any speed
- **Visual Overlay** — transparent HUD with crosshair, button markers, and status
- **State Machine** — structured game automation with named phases and transitions
- **Rich Dashboard** — live terminal UI with stats, event log, and button status
- **YAML Profiles** — resolution-independent, shareable configuration

## Installation

<!-- one-command-install -->
> **One-command install** — clone, configure, and run in a single step:
>
> ```bash
> curl -fsSL https://raw.githubusercontent.com/jasperan/mousecoords/main/install.sh | bash
> ```
>
> <details><summary>Advanced options</summary>
>
> Override install location:
> ```bash
> PROJECT_DIR=/opt/myapp curl -fsSL https://raw.githubusercontent.com/jasperan/mousecoords/main/install.sh | bash
> ```
>
> Or install manually:
> ```bash
> git clone https://github.com/jasperan/mousecoords.git
> cd mousecoords
> pip install -e ".[all]"
> ```
> </details>

### Optional dependencies

Install only what you need:

```bash
pip install -e ".[vision]"    # OpenCV template matching
pip install -e ".[ocr]"       # Tesseract OCR
pip install -e ".[record]"    # Macro recording (pynput)
pip install -e ".[tui]"       # Rich terminal dashboard
pip install -e ".[all]"       # Everything
```

For OCR, also install Tesseract system-wide:
```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr
# macOS
brew install tesseract
# Windows — download from https://github.com/UB-Mannheim/tesseract/wiki
```

## Usage

### Grab coordinates

```bash
mousecoords coords
# Press SPACE to capture position + RGB color, Q to quit
```

### Game automation

```bash
# Default profile (Antimatter Dimensions)
mousecoords automate

# Custom profile
mousecoords automate -p my_game

# With visual overlay and OCR
mousecoords automate --overlay --ocr

# Simple mode (no Rich dashboard)
mousecoords automate --simple
```

### Record and replay macros

```bash
# Record (press ESC to stop)
mousecoords record -o recordings/my_macro.json
mousecoords record --moves  # also capture mouse movement

# Replay
mousecoords play recordings/my_macro.json
mousecoords play recordings/my_macro.json -s 2.0        # 2x speed
mousecoords play recordings/my_macro.json -s 0.5 --loop # half speed, forever
```

### Template capture (for CV matching)

```bash
mousecoords capture -n galaxy_button
# Position mouse at top-left of button, SPACE
# Position mouse at bottom-right, SPACE
# Saves templates/galaxy_button.png
```

Then reference in your profile YAML:
```yaml
buttons:
  - name: Antimatter Galaxies
    template: templates/galaxy_button.png
    cooldown: 1.0
```

### OCR reader

```bash
mousecoords ocr
# Select screen region with two SPACE presses
# Reads and displays text + parsed number
```

### Profile management

```bash
mousecoords profile list       # list available profiles
mousecoords profile create     # generate default YAML
mousecoords profile show       # display profile contents
```

## Profiles

Profiles are YAML files in `profiles/` that define everything about an automation target:

```yaml
name: antimatter_dimensions
game: Antimatter Dimensions
resolution: [3840, 2160]      # coordinates are relative to this
poll_interval: 0.5            # seconds between screen checks
color_tolerance: 3            # RGB matching tolerance

buttons:
  - name: Dimension Boost
    x: 860
    y: 909
    color: [103, 196, 90]     # expected RGB when clickable
    cooldown: 1.0             # seconds between clicks
    # template: path/to.png   # use CV matching instead of color

states:
  - name: farming
    monitor_buttons: [Dimension Boost, Big Crunch, Max Ticks]
    transitions:
      Big Crunch: crunching   # when Big Crunch is clicked, go to "crunching"
    max_actions:
      Dimension Boost: 22    # limit per cycle

ocr_regions:
  antimatter_count: [700, 50, 400, 40]  # x, y, width, height
```

Profiles auto-scale coordinates when `resolution` differs from your screen.

## Architecture

```
mousecoords/
├── config.py          # YAML profile system with resolution scaling
├── vision.py          # OpenCV template matching + Tesseract OCR
├── recorder.py        # Input recording and replay engine
├── overlay.py         # Transparent tkinter HUD overlay
├── state_machine.py   # FSM with phases, limits, and transitions
├── tui.py             # Rich live dashboard
└── automator.py       # CLI entry point orchestrating everything
```

## Original tools

The original scripts are preserved at the repo root:

- `coords.py` — the original 5-line coordinate grabber
- `dimension_mini.py` — the original Antimatter Dimensions automator (Windows-only)

## License

[Mozilla Public License 2.0](LICENSE)
