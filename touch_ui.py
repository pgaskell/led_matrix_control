
import pygame
import time
import importlib
import os
import json
from os.path import join, isfile
from PIL import Image
from lfo import evaluate_lfos, LFO_CONFIG, BPM
from audio_env import evaluate_env, ENV_CONFIG

# --- Config ---
SCREEN_WIDTH = 1024
FULL_HEIGHT = 1080
UI_HEIGHT = 600
SIM_HEIGHT = 480
SLIDER_WIDTH = 30
SLIDER_MARGIN = 20
FONT_SIZE = 20
SLIDER_COLOR = (100, 200, 255)
BG_COLOR = (30, 30, 30)
instant_update = True

# --- Load Patterns ---
def load_patterns():
    patterns = {}
    pattern_dir = "patterns"
    for fname in os.listdir(pattern_dir):
        if fname.endswith(".py") and not fname.startswith("_"):
            modname = fname[:-3]
            try:
                module = importlib.import_module(f"patterns.{modname}")
                if hasattr(module, "Pattern") and hasattr(module, "PARAMS"):
                    patterns[modname] = module
            except Exception as e:
                print(f"Error loading pattern {modname}: {e}")
    return patterns

# --- Load Sprites ---
def load_sprites(folder="sprites"):
    sprites = {}
    sprite_names = []
    for fname in os.listdir(folder):
        if fname.lower().endswith(".png") or fname.lower().endswith(".gif"):
            name = os.path.splitext(fname)[0]
            path = os.path.join(folder, fname)
            if fname.lower().endswith(".png"):
                surface = pygame.image.load(path).convert_alpha()
                sprites[name] = [surface]  # wrap single frame in list
            elif fname.lower().endswith(".gif"):
                gif = Image.open(path)
                frames = []
                try:
                    while True:
                        frame = gif.convert("RGBA")
                        mode = frame.mode
                        size = frame.size
                        data = frame.tobytes()
                        surface = pygame.image.fromstring(data, size, mode).convert_alpha()
                        frames.append(surface)
                        gif.seek(gif.tell() + 1)
                except EOFError:
                    pass
                sprites[name] = frames
            sprite_names.append(name)
    return sprites, ["none"] + sprite_names

def save_patch(index, pattern_name, params, param_meta, lfo_config, env_config):
    patch = {
        "pattern":    pattern_name,
        "params":     params,
        "modulation": extract_mod_config(param_meta),
        "lfo_config": lfo_config,
        "env_config": env_config
    }
    with open(f"patches/patch_{index:02d}.json", "w") as f:
        json.dump(patch, f, indent=2)

def load_patch(index):
    with open(f"patches/patch_{index:02d}.json", "r") as f:
        return json.load(f)

def restore_patch(index,
                  pattern_names,
                  patterns,
                  lfo_panels,
                  env_panels,
                  create_sliders):
    """
    Load patch[index] from disk and:
      1. Switch to the saved pattern
      2. Rebuild sliders/dropdowns/checkboxes
      3. Restore each param’s modulatable flags
      4. Restore LFO_CONFIG into lfo_panels
      5. Restore ENV_CONFIG into env_panels
    Returns: (new_index, pattern, sliders, dropdowns, mod_checkboxes)
    """
    patch = load_patch(index)

    # 1) Pattern switch
    new_index    = pattern_names.index(patch["pattern"])
    module       = patterns[pattern_names[new_index]]
    param_specs  = module.PARAMS
    params       = patch["params"].copy()
    pattern      = module.Pattern(24, 24, params=params)

    # 2) UI elements
    sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)

    # 3) Modulation flags
    for name, m in patch["modulation"].items():
        meta = param_specs.get(name)
        if not meta: continue
        meta["mod_active"] = m["mod_active"]
        meta["mod_source"] = m["mod_source"]
        meta["mod_mode"]   = m["mod_mode"]
        # update the matching checkbox
        for cb in mod_checkboxes:
            if cb.param_name == name:
                cb.active = (cb.source_id == m["mod_source"])

    # 4) LFOs
    LFO_CONFIG.update(patch["lfo_config"])
    for lname, panel in zip(("lfo1","lfo2"), lfo_panels):
        cfg = LFO_CONFIG[lname]
        panel.config.update(cfg)
        panel.waveform_dropdown.selected = cfg["waveform"]
        panel.depth_slider.value        = cfg["depth"]
        panel.offset_slider.value       = cfg.get("offset", 0.0)
        panel.sync_mode                 = cfg["sync_mode"]
        # …and their mhz/beat dropdowns…

    # 5) Envelopes
    ENV_CONFIG.update(patch["env_config"])
    for pname, panel in zip(("envl","envh"), env_panels):
        cfg = ENV_CONFIG[pname]
        panel.th_slider.value    = cfg["threshold_db"]
        panel.gn_slider.value    = cfg["gain_db"]
        panel.atk_dd.selected    = cfg["attack"]
        panel.rel_dd.selected    = cfg["release"]
        panel.mode_dd.selected   = cfg["mode"]
        panel.config.update(cfg)

    # 6) Return everything needed back into launch_ui
    return new_index, pattern, sliders, dropdowns, mod_checkboxes

def delete_patch(index):
    """
    Delete the JSON file for patch slot `index`, if it exists.
    """
    path = os.path.join("patches", f"patch_{index:02d}.json")
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

def make_thumbnail(pattern, frame, sprites, params, size):
    """
    Render a simulator snapshot + sprite overlay into a Surface of given size.
    - `pattern`: the Pattern instance (to know width/height)
    - `frame`: the raw LED frame list
    - `sprites`: dict mapping sprite_name -> list_of_surfaces
    - `params`: dict of params (holds 'SPRITE')
    - `size`: (w, h) target thumbnail size
    """
    # 1) Draw the LED grid at full resolution
    base = pygame.Surface((pattern.width, pattern.height), pygame.SRCALPHA)
    draw_simulator(base, frame, pattern.width, pattern.height,
                   pygame.Rect(0, 0, pattern.width, pattern.height))

    # 2) Overlay the sprite (first frame)
    sprite_name = params.get("SPRITE", "none")
    if sprite_name in sprites and sprites[sprite_name]:
        sprite_surf = sprites[sprite_name][0]
        sw, sh = sprite_surf.get_size()
        ox = (pattern.width  - sw) // 2
        oy = (pattern.height - sh) // 2
        # blit with alpha
        base.blit(sprite_surf, (ox, oy))

    # 3) Scale down to thumbnail size
    return pygame.transform.smoothscale(base, size)

def extract_mod_config(param_meta):
    """Pull out only the modulatable entries for saving."""
    mod_cfg = {}
    for name, meta in param_meta.items():
        if isinstance(meta, dict) and meta.get("modulatable"):
            mod_cfg[name] = {
                "mod_active": bool(meta.get("mod_source")),
                "mod_source": meta.get("mod_source"),
                "mod_mode":   meta.get("mod_mode", "add"),
            }
    return mod_cfg

def draw_mod_indicator(screen, font, signals, label, key, color, idx):
    """
    Draw a centered bipolar bar for `signals[key]` in row `idx`.
    - signals: dict of {"lfo1":…, "lfo2":…, "envl":…, "envh":…}
    - label: text to show (“LFO1”, “ENVL”, etc.)
    - key: the dict key
    - color: bar fill color
    - idx: which row [0…3]
    """
    # geometry
    bar_x = 25
    bar_w = 210
    bar_h = 10
    spacing = 4
    bar_y = (UI_HEIGHT - 100) + idx * (bar_h + spacing)

    # background
    pygame.draw.rect(screen, (50,50,50), (bar_x, bar_y, bar_w, bar_h))

    # center zero‐line
    cx = bar_x + bar_w // 2
    pygame.draw.line(screen, (200,200,200),
                     (cx, bar_y), (cx, bar_y + bar_h))

    # get & clamp signal
    val = signals.get(key, 0.0)
    val = max(-1.0, min(1.0, val))
    length = int(val * (bar_w // 2))

    # compute rect
    if length >= 0:
        rect = pygame.Rect(cx, bar_y, length, bar_h)
    else:
        rect = pygame.Rect(cx + length, bar_y, -length, bar_h)

    # fill
    pygame.draw.rect(screen, color, rect)

    # label
    #screen.blit(font.render(label, True, (255,255,255)),
    #            (bar_x + bar_w + 10, bar_y))

class Slider:
    def __init__(self, name, default, min_val, max_val, step, x, y, height, valid_values=None):
        self.name = name
        self.value = default
        self.min = min_val
        self.max = max_val
        self.step = step
        self.valid_values = valid_values
        self.rect = pygame.Rect(x, y, SLIDER_WIDTH, height)
        self.active = False

    def draw(self, screen, font):
        pygame.draw.rect(screen, (80,80,80), self.rect)
        ratio = (self.value - self.min) / (self.max - self.min)
        handle_y = self.rect.y + self.rect.height * (1.0 - ratio)
        handle = pygame.Rect(self.rect.x, handle_y - 5, SLIDER_WIDTH, 10)
        pygame.draw.rect(screen, SLIDER_COLOR, handle)
        for i, char in enumerate(self.name):
            char_img = font.render(char, True, (255,255,255))
            screen.blit(char_img, (self.rect.x + SLIDER_WIDTH + 4, self.rect.y + i * (FONT_SIZE - 2)))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.active = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
        elif event.type == pygame.MOUSEMOTION and self.active:
            rel_y = event.pos[1] - self.rect.y
            ratio = max(0.0, min(1.0, rel_y / self.rect.height))
            raw_value = self.max - ratio * (self.max - self.min)
            stepped_value = round(raw_value / self.step) * self.step
            self.value = min(max(stepped_value, self.min), self.max)
            if self.valid_values:
                # snap to the nearest entry in valid_values
                closest = min(self.valid_values, key=lambda v: abs(v - raw_value))
                self.value = closest
            else:
                stepped = round(raw_value / self.step) * self.step
                self.value = min(max(stepped, self.min), self.max)

class HorizontalSlider:
    HEIGHT = 20

    def __init__(self, name, default, min_val, max_val, step, x, y, width):
        self.name = name
        self.value = default
        self.min = min_val
        self.max = max_val
        self.step = step
        self.rect = pygame.Rect(x, y, width, self.HEIGHT)
        self.active = False

    def draw(self, screen, font):
        pygame.draw.rect(screen, (80, 80, 80), self.rect)
        ratio = (self.value - self.min) / (self.max - self.min)
        handle_x = self.rect.x + int(ratio * self.rect.width)
        handle = pygame.Rect(handle_x - 5, self.rect.y, 10, self.HEIGHT)
        pygame.draw.rect(screen, SLIDER_COLOR, handle)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.active = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
        elif event.type == pygame.MOUSEMOTION and self.active:
            rel_x = event.pos[0] - self.rect.x
            ratio = max(0.0, min(1.0, rel_x / self.rect.width))
            raw_value = self.min + ratio * (self.max - self.min)
            stepped_value = round(raw_value / self.step) * self.step
            self.value = min(max(stepped_value, self.min), self.max)


class ModCheckbox:
    SIZE = 20

    def __init__(self, param_name, source_id, x, y, color):
        self.param_name = param_name
        self.source_id = source_id  # e.g., 'lfo1'
        self.rect = pygame.Rect(x, y, self.SIZE, self.SIZE)
        self.color = color
        self.active = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect, 0 if self.active else 2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.active = not self.active
            return True
        return False

class Dropdown:
    def __init__(self, name, options, default, x, y, width=120, show_label=True, label_map=None):
        self.name = name
        self.options = options
        self.selected = default
        self.x = x
        self.y = y
        self.width = width
        self.show_label = show_label
        self.label_map = label_map or {}
        self.open = False
        self.height = 30
        self.rect = pygame.Rect(x, y, width, self.height)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
                return True
            
            if self.open:
                entry_h = self.rect.height
                for i, opt in enumerate(self.options):
                    entry_rect = pygame.Rect(
                        self.x,
                        self.y + entry_h * (i + 1),
                        self.width,
                        entry_h
                    )
                    if entry_rect.collidepoint(event.pos):
                        self.selected = opt
                        self.open = False
                        return True
            
                self.open = False
                return True
            
            return False

    def draw(self, screen, font):
        pygame.draw.rect(screen, (100, 100, 100), self.rect)
        display_text = self.label_map.get(self.selected, self.selected)
        display_text = str(display_text)
        screen.blit(font.render(display_text, True, (255, 255, 255)), (self.x + 6, self.y + 4))

        if self.show_label:
            label_text = self.name.split("_")[-1] + ":"
            label_surface = font.render(label_text, True, (160, 160, 160))
            screen.blit(label_surface, (self.x - label_surface.get_width() - 6, self.y + 4))

        if self.open:
            for i, opt in enumerate(self.options):
                option_rect = pygame.Rect(self.x, self.y + self.height * (i + 1), self.width, self.height)
                pygame.draw.rect(screen, (70, 70, 70), option_rect)
                opt_label = self.label_map.get(opt, opt)
                screen.blit(font.render(opt_label, True, (255, 255, 255)), (self.x + 6, option_rect.y + 4))


class LFOControlPanel:
    def __init__(self, name, x, y, config):
        self.name = name
        self.x = x
        self.y = y
        self.config = config
        self.wave_labels = {"sine": "sin", "square": "sqr", "triangle": "tri", "saw": "saw"}

        self.waveform_dropdown = Dropdown(name + "_wave",
                                  ["sine", "square", "triangle", "saw"],
                                  config["waveform"],
                                  x, y,
                                  show_label=False,
                                  label_map=self.wave_labels)

        self.depth_slider = HorizontalSlider(name + "_depth", config["depth"], 0.0, 1.0, 0.01,
                                     x + 140, y + 5, 60)

        self.offset_slider = HorizontalSlider(
                name + "_offset",
                config.get("offset", 0.0),
                -1.0, 1.0, 0.01,
                x + 210, y + 5,
                60
            )

        self.sync_button_rect = pygame.Rect(x, y + 35, 100, 30)

        self.mhz_dropdown = Dropdown(
            name + "_mhz", ["50", "100", "200", "500", "1000"],
            str(int(config["hz"] * 1000)),  # convert Hz to mHz for default selection
            x + 140, y + 35,
            show_label=False)

        self.beat_dropdown = Dropdown(name + "_beats", ["1/4", "1/2", "1", "2", "4"],
                                      self._beats_label(config["period_beats"]),
                                      x + 140, y + 35,
                                      show_label=False)

    def _beats_label(self, value):
        return {0.25: "1/4", 0.5: "1/2", 1.0: "1", 2.0: "2", 4.0: "4"}.get(value, "1")

    def _beats_value(self, label):
        return {"1/4": 0.25, "1/2": 0.5, "1": 1.0, "2": 2.0, "4": 4.0}.get(label, 1.0)

    def handle_event(self, event):
        self.waveform_dropdown.handle_event(event)
        self.depth_slider.handle_event(event)
        self.offset_slider.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and self.sync_button_rect.collidepoint(event.pos):
            self.config["sync_mode"] = (
                "quantized" if self.config["sync_mode"] == "free" else "free"
            )

        if self.config["sync_mode"] == "free":
            self.mhz_dropdown.handle_event(event)
        else:
            self.beat_dropdown.handle_event(event)

        # Immediate update of config dict
        self.config["waveform"] = self.waveform_dropdown.selected
        self.config["depth"] = self.depth_slider.value
        self.config["offset"]   = self.offset_slider.value
        if self.config["sync_mode"] == "free":
            self.config["hz"] = int(self.mhz_dropdown.selected) / 1000.0
        else:
            self.config["period_beats"] = self._beats_value(self.beat_dropdown.selected)

    def draw(self, screen, font):
    #Background
        pygame.draw.rect(screen, (40, 40, 40), pygame.Rect(self.x-10, self.y-10, 300, 100), border_radius=4)
        # LFO Title
        screen.blit(font.render(self.name.upper(), True, (255, 255, 255)), (self.x, self.y - 20))
        self.depth_slider.draw(screen, font)
        self.offset_slider.draw(screen, font)

        # Sync mode toggle
        pygame.draw.rect(screen, (90, 90, 90), self.sync_button_rect)
        sync_label = "mHz" if self.config["sync_mode"] == "free" else "Q"
        screen.blit(font.render(sync_label, True, (255, 255, 255)),
                    (self.sync_button_rect.x + 8, self.sync_button_rect.y + 2))
        self.waveform_dropdown.draw(screen, font)
        if self.config["sync_mode"] == "free":
            self.mhz_dropdown.draw(screen, font)
        else:
            self.beat_dropdown.draw(screen, font)

class EnvelopeControlPanel:
    def __init__(self, name, x, y, config):
        """
        name:     "envl" or "envh"
        x, y:     top-left of panel
        config:   the dict from ENV_CONFIG[name]
        """
        self.name   = name
        self.x      = x
        self.y      = y
        self.config = config

        # — Mapping for ms dropdowns → seconds —
        self._atk_map = {"1ms":0.001,  "5ms":0.005,  "10ms":0.010, "20ms":0.020}
        self._rel_map = {"25ms":0.025,"50ms":0.050,"100ms":0.100,"150ms":0.150}

        # — COLUMN POSITIONS —
        col1_x = x
        col2_x = x + 100
        col3_x = x + 200
        row0  = y
        row1  = y + 40

        # — Gain slider: –20 dB … +20 dB —
        self.gn_slider = HorizontalSlider(
            f"{name}_gain",
            config.get("gain_db", 0),         # store gain in dB
            -40, 10, 1,
            col1_x, row0,
            90
        )

        # — Threshold slider: –40 dB … 0 dB —
        self.th_slider = HorizontalSlider(
            f"{name}_thr",
            config.get("threshold_db", 0),    # store threshold in dB
            -40, 20, 1,                        # min, max, step in dB
            col1_x, row1,                     # pos
            90                               # width
        )

        # — Attack dropdown —
        atk_default = next(
            (lbl for lbl,val in self._atk_map.items() if abs(val - config["attack"])<1e-6),
            "10ms"
        )
        self.atk_dd = Dropdown(
            f"{name}_atk",
            list(self._atk_map.keys()),
            atk_default,
            col2_x+10, row0,
            width=80,
            show_label=False
        )

        # — Release dropdown —
        rel_default = next(
            (lbl for lbl,val in self._rel_map.items() if abs(val - config["release"])<1e-6),
            "100ms"
        )
        self.rel_dd = Dropdown(
            f"{name}_rel",
            list(self._rel_map.keys()),
            rel_default,
            col3_x, row0,
            width=80,
            show_label=False
        )

        # — Mode dropdown —
        self.mode_dd = Dropdown(
            f"{name}_mode",
            ["up", "down", "updown"],
            config["mode"],
            col3_x, row1,
            width=80,
            show_label=False
        )

    def handle_event(self, event):
        # sliders
        self.th_slider.handle_event(event)
        self.gn_slider.handle_event(event)
        # dropdowns
        self.atk_dd .handle_event(event)
        self.rel_dd .handle_event(event)
        self.mode_dd.handle_event(event)
        # write back into config
        self.config["threshold_db"] = self.th_slider.value
        self.config["gain_db"]      = self.gn_slider.value
        self.config["attack"]       = self._atk_map[self.atk_dd.selected]
        self.config["release"]      = self._rel_map[self.rel_dd.selected]
        self.config["mode"]         = self.mode_dd.selected

    def draw(self, screen, font):
        # panel background
        pygame.draw.rect(
            screen,
            (40,40,40),
            (self.x-10, self.y-10, 300, 100),
            border_radius=4
        )
        # title
        screen.blit(
            font.render(self.name.upper(), True, (255,255,255)),
            (self.x, self.y-20)
        )
        # draw controls
        self.th_slider.draw(screen, font)
        self.gn_slider.draw(screen, font)
        self.mode_dd .draw(screen, font)
        self.atk_dd  .draw(screen, font)
        self.rel_dd  .draw(screen, font)
        


def draw_simulator(screen, frame, grid_w, grid_h, rect):
    # Determine square pixel size that fits
    pixel_size = min(rect.width // grid_w, rect.height // grid_h)

    # Calculate drawing area size
    draw_width = pixel_size * grid_w
    draw_height = pixel_size * grid_h

    # Calculate top-left corner to center the pattern
    offset_x = rect.x + (rect.width - draw_width) // 2
    offset_y = rect.y + (rect.height - draw_height) // 2

    for y in range(grid_h):
        for x in range(grid_w):
            idx = y * grid_w + x
            r, g, b, *_ = frame[idx]
            pygame.draw.rect(
                screen,
                (r, g, b),
                pygame.Rect(
                    offset_x + x * pixel_size,
                    offset_y + y * pixel_size,
                    pixel_size,
                    pixel_size
                )
            )


def create_sliders(param_specs, current_values):
    sliders = []
    dropdowns = []
    lfo_checkboxes = []
    slider_count = 0
    dropdown_x = SLIDER_MARGIN
    dropdown_y = 20
    slider_x = SLIDER_MARGIN
    slider_y = 80

    for k, spec in param_specs.items():
        if k in ["COLORMAP", "SPRITE"]:
            continue  # handled manually in launch_ui()

        if isinstance(spec, dict) and "options" in spec:
            dropdowns.append(Dropdown(k, spec["options"], current_values[k], dropdown_x, dropdown_y))
            dropdown_x += 200

        elif isinstance(spec, dict):
            if slider_count >= 4:
                continue
            slider_count += 1
            default = spec["default"]
            min_val = spec.get("min", default / 2)
            max_val = spec.get("max", default * 2)
            step = spec.get("step", 0.1)
            height = int((UI_HEIGHT - 100) * 0.6)
            
            if "valid" in spec:
                valid_vals = spec["valid"]
                # slider will snap to those
                min_val, max_val = min(valid_vals), max(valid_vals)
                step = 1
                sliders.append(
                Slider(k, current_values[k], min_val, max_val, step,
                        slider_x, slider_y, height,
                        valid_values=valid_vals)
                )
            else:
                default = spec["default"]
                min_val = spec.get("min", default/2)
                max_val = spec.get("max", default*2)
                step    = spec.get("step", 0.1)
                sliders.append(
                Slider(k, current_values[k], min_val, max_val, step,
                        slider_x, slider_y, height)
                )

            if spec.get("modulatable"):
                x_center = slider_x + SLIDER_WIDTH // 2 - 10
                y_start = slider_y + height + 10
                spacing = 24
                lfo_checkboxes.extend([
                    ModCheckbox(k, "lfo1", x_center, y_start + 0 * spacing, (100, 255, 255)),
                    ModCheckbox(k, "lfo2", x_center, y_start + 1 * spacing, (255, 100, 255)),
                    ModCheckbox(k, "envl", x_center, y_start + 2 * spacing, (255, 255, 100)),
                    ModCheckbox(k, "envh", x_center, y_start + 3 * spacing, (255, 150, 50))
                ])

            slider_x += SLIDER_WIDTH + SLIDER_MARGIN + 12

    return sliders, dropdowns, lfo_checkboxes






def launch_ui():
    pygame.init()
    from lfo import BPM
    # — Basic setup —
    show_simulator = False
    screen = pygame.display.set_mode((SCREEN_WIDTH, UI_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("LED Wall Touch UI")
    font = pygame.font.SysFont("monospace", FONT_SIZE)
    button_font = pygame.font.SysFont("monospace", FONT_SIZE)

    # — Patch grid setup —
    PATCH_ROWS, PATCH_COLS = 8, 8
    TOTAL_SLOTS = PATCH_ROWS * PATCH_COLS
    patches = [None] * TOTAL_SLOTS
    patch_icons = [None] * TOTAL_SLOTS
    save_mode = False
    clear_mode = False

    # — MOD panels —
    lfo1_panel = LFOControlPanel("lfo1", SCREEN_WIDTH - 300, 70, LFO_CONFIG["lfo1"])
    lfo2_panel = LFOControlPanel("lfo2", SCREEN_WIDTH - 300, 180, LFO_CONFIG["lfo2"])
    envl_panel = EnvelopeControlPanel("envl", SCREEN_WIDTH - 300, 290, ENV_CONFIG["envl"])
    envh_panel = EnvelopeControlPanel("envh", SCREEN_WIDTH - 300, 400, ENV_CONFIG["envh"])

    # — Patterns & sprites & colormaps —
    patterns = load_patterns()
    pattern_names = sorted(patterns.keys())
    current_index = 0
    pattern_dropdown = Dropdown(
        "PATTERN",
        pattern_names,
        pattern_names[current_index],
        20, 10,
        width=240,
        show_label=False
    )

    sprites, sprite_names = load_sprites("sprites")
    from colormaps import COLORMAPS
    colormap_names = list(COLORMAPS.keys())

    # — Initial pattern instance —
    module = patterns[pattern_names[current_index]]
    param_specs = module.PARAMS
    params = {k: v["default"] for k, v in param_specs.items()}
    if "SPRITE" in param_specs:
        param_specs["SPRITE"]["options"] = sprite_names
    pattern = module.Pattern(24, 24, params=params)
    sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)

    # — Fixed dropdowns (won’t be recreated on pattern change) —
    selected_colormap = params.get("COLORMAP", colormap_names[0])
    colormap_dropdown = Dropdown("COLORMAP", colormap_names, selected_colormap, 280, 10, width=250, show_label=False)

    selected_sprite = params.get("SPRITE", "none")
    sprite_dropdown  = Dropdown("SPRITE",  sprite_names,  selected_sprite,  550, 10, width=250, show_label=False)

    # — UI button rectangles —
    sim_button_rect  = pygame.Rect(SCREEN_WIDTH - 200, 10, 180, 30)
    save_button_rect = pygame.Rect(SCREEN_WIDTH - 420, UI_HEIGHT - 90, 180, 45)
    clear_button_rect = pygame.Rect(SCREEN_WIDTH - 620, UI_HEIGHT - 90, 180, 45)
    tap_button_rect  = pygame.Rect(SCREEN_WIDTH - 220, UI_HEIGHT - 90, 180, 45)
    tap_times = []

    GRID_X = 270
    GRID_Y = 60
    SLOT_SIZE = 50
    SLOT_SP   = 4

    patch_rects = []
    for row in range(PATCH_ROWS):
        for col in range(PATCH_COLS):
            x = GRID_X + col*(SLOT_SIZE + SLOT_SP)
            y = GRID_Y + row*(SLOT_SIZE + SLOT_SP)
            patch_rects.append(pygame.Rect(x, y, SLOT_SIZE, SLOT_SIZE))

    clock = pygame.time.Clock()
    running = True
    frame = None

    # load patches
    for i in range(TOTAL_SLOTS):
        fn = join("patches/", f"patch_{i:02d}.json")
        if isfile(fn):
            patches[i] = True
            # Recreate thumbnail from saved params:
            p = load_patch(i)
            mod = patterns[p["pattern"]]
            ps  = mod.PARAMS
            params = p["params"]
            temp = mod.Pattern(24, 24, params=params)
            frame = temp.render(lfo_signals={})
            patch_icons[i] = make_thumbnail(
                temp, frame,
                sprites, params,
                (SLOT_SIZE, SLOT_SIZE)
            )

    while running:
        screen.fill(BG_COLOR)

        # — Event loop —
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # 1) First, let *every* UI control see *every* event:
            # pattern_dropdown.handle_event(event) 
            # colormap_dropdown.handle_event(event)
            # sprite_dropdown .handle_event(event)
            for d in dropdowns: d.handle_event(event)
            for s in sliders: s.handle_event(event)
            for c in mod_checkboxes:
                if c.handle_event(event):
                    meta = pattern.param_meta.get(c.param_name)
                    if not meta or not meta.get("modulatable"):
                        continue

                    # Turn modulation on/off
                    meta["mod_active"] = c.active

                    if c.active:
                        # Set this checkbox’s source and clear others
                        meta["mod_source"] = c.source_id
                        for other in mod_checkboxes:
                            if other is not c and other.param_name == c.param_name:
                                other.active = False
                    else:
                        # No source if you turned it off
                        meta["mod_source"] = None
            
            lfo1_panel.handle_event(event)
            lfo2_panel.handle_event(event)
            envl_panel.handle_event(event)
            envh_panel.handle_event(event)


            if event.type == pygame.MOUSEBUTTONDOWN:
                # First, let the top dropdowns handle it
                # (pattern dropdown, colormap dropdown, sprite dropdown)
                if pattern_dropdown.handle_event(event):
                    continue
                if colormap_dropdown.handle_event(event):
                    continue
                if sprite_dropdown.handle_event(event):
                    continue
           # Tap tempo
                if tap_button_rect.collidepoint(event.pos):
                    now = time.time()
                    tap_times.append(now)
                    tap_times = [t for t in tap_times if now - t < 3.0]
                    if len(tap_times) >= 2:
                        intervals = [b - a for a, b in zip(tap_times, tap_times[1:])]
                        avg = sum(intervals) / len(intervals)
                        if avg > 0:
                            from lfo import BPM as _; import lfo; lfo.BPM = 60.0 / avg
                    continue

                # Simulator toggle
                if sim_button_rect.collidepoint(event.pos):
                    show_simulator = not show_simulator
                    continue

                # Toggle save mode
                if save_button_rect.collidepoint(event.pos):
                    save_mode = not save_mode
                    continue
                # Toggle clear mode
                if clear_button_rect.collidepoint(event.pos):
                   clear_mode = not clear_mode
                   continue
                
                # — Patch grid clicks —
                for i, slot in enumerate(patch_rects):
                    if slot.collidepoint(event.pos):
                        
                        # — SAVE MODE —
                        if save_mode:
                            # Gather LFO settings
                            lfo_config = {
                                "lfo1": lfo1_panel.config.copy(),
                                "lfo2": lfo2_panel.config.copy(),
                            }
                            # Gather ENV settings
                            env_config = {
                                "envl": envl_panel.config.copy(),
                                "envh": envh_panel.config.copy(),
                            }

                            # Save everything
                            save_patch(
                                i,
                                pattern_names[current_index],
                                params,
                                pattern.param_meta,
                                lfo_config,
                                env_config
                            )

                            # capture thumbnail
                            thumb = pygame.Surface((pattern.width, pattern.height))
                            draw_simulator(
                                thumb,
                                frame or [],
                                pattern.width,
                                pattern.height,
                                pygame.Rect(0, 0, pattern.width, pattern.height)
                            )
                            patch_icons[i] = pygame.transform.smoothscale(
                                thumb, (slot.width, slot.height)
                            )
                            patches[i] = True
                            save_mode = False

                        # — CLEAR MODE —
                        elif clear_mode:
                            delete_patch(i)
                            patches[i]     = None
                            patch_icons[i] = None
                            clear_mode     = False

                        # — LOAD / RECALL MODE —
                        else:
                            if patches[i]:
                                patch = load_patch(i)

                                # 1) Switch to saved pattern
                                pattern_name   = patch["pattern"]
                                current_index  = pattern_names.index(pattern_name)
                                pattern_dropdown.selected = pattern_name

                                module      = patterns[pattern_name]
                                param_specs = module.PARAMS

                                # 2) Restore params (including COLORMAP & SPRITE)
                                params = patch["params"].copy()
                                if "COLORMAP" in params:
                                    colormap_dropdown.selected = params["COLORMAP"]
                                if "SPRITE" in params:
                                    sprite_dropdown.selected  = params["SPRITE"]

                                # 3) Disable all modulatable defaults
                                for meta in param_specs.values():
                                    if isinstance(meta, dict) and meta.get("modulatable"):
                                        meta["mod_active"] = False
                                        meta["mod_source"] = None

                                # 4) Rebuild UI controls
                                sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)
                                pattern = module.Pattern(24, 24, params=params)
                                pattern.param_meta = param_specs

                                # 5) Restore each param’s saved modulation flags
                                for key, m in patch["modulation"].items():
                                    if key in param_specs:
                                        param_specs[key]["mod_active"] = m["mod_active"]
                                        param_specs[key]["mod_source"] = m["mod_source"]
                                        param_specs[key]["mod_mode"]   = m["mod_mode"]
                                        # sync checkbox visuals
                                        for c in mod_checkboxes:
                                            if (c.param_name == key
                                                and c.source_id == m["mod_source"]):
                                                c.active = True

                                # 6) Restore LFO configuration
                                for name, saved_cfg in patch["lfo_config"].items():
                                    if name in LFO_CONFIG:
                                        LFO_CONFIG[name].clear()
                                        LFO_CONFIG[name].update(saved_cfg)
                                for name, panel in (("lfo1", lfo1_panel), ("lfo2", lfo2_panel)):
                                    cfg = LFO_CONFIG[name]
                                    panel.config.update(cfg)
                                    panel.waveform_dropdown.selected = cfg["waveform"]
                                    panel.depth_slider.value         = cfg["depth"]
                                    panel.offset_slider.value         = cfg.get("offset", 0.0)
                                    panel.sync_mode                  = cfg["sync_mode"]
                                    if cfg["sync_mode"] == "free":
                                        panel.mhz_dropdown.selected    = str(int(cfg["hz"]*1000))
                                    else:
                                        panel.beat_dropdown.selected   = panel._beats_label(cfg["period_beats"])
                                
                                # — Restore ENV configuration —
                                for name, saved_cfg in patch["env_config"].items():
                                    if name in ENV_CONFIG:
                                        ENV_CONFIG[name].clear()
                                        ENV_CONFIG[name].update(saved_cfg)
                                # Sync each envelope panel to the newly restored ENV_CONFIG
                                for name, panel in (("envl", envl_panel),
                                                    ("envh", envh_panel)):
                                    cfg = ENV_CONFIG[name]
                                    # sliders
                                    panel.th_slider.value = cfg["threshold_db"]
                                    panel.gn_slider.value = cfg["gain_db"]
                                    panel.atk_dd.selected = next(
                                        lbl for lbl,sec in panel._atk_map.items()
                                        if abs(sec - cfg["attack"]) < 1e-6
                                    )
                                    panel.rel_dd.selected = next(
                                        lbl for lbl,sec in panel._rel_map.items()
                                        if abs(sec - cfg["release"]) < 1e-6
                                    )
                                    panel.mode_dd.selected = cfg["mode"]
                    
                                    # finally update panel.config so future handle_event sees it
                                    panel.config.update(cfg)

                                # 8) Finalize: update pattern.params so .render() sees everything
                                pattern.update_params(params)

                            break
        
        # Show/Hide the Simulator
        # pick the target size based on whether we’re showing the simulator
        if show_simulator:
            target_size = (SCREEN_WIDTH, FULL_HEIGHT)
        else:
            target_size = (SCREEN_WIDTH, UI_HEIGHT)

        # only recreate the window if something’s changed
        if screen.get_size() != target_size:
            screen = pygame.display.set_mode(target_size, pygame.RESIZABLE)


        # If you want “instant” updates as you drag:
        if instant_update:
            for s in sliders:
                params[s.name] = s.value
            pattern.update_params(params)

        # — After events: update dropdown-based params —
        new_pat = pattern_dropdown.selected
        if new_pat != pattern_names[current_index]:
            current_index = pattern_names.index(new_pat)
            module = patterns[new_pat]
            param_specs = module.PARAMS

            # reset params & inject colormap/sprite
            params = {k: v["default"] for k, v in param_specs.items()}
            params["COLORMAP"] = colormap_dropdown.selected
            params["SPRITE"]   = sprite_dropdown.selected

            # disable all modulation defaults
            for meta in param_specs.values():
                if isinstance(meta, dict) and meta.get("modulatable"):
                    meta["mod_active"] = False
                    meta["mod_source"] = None

            sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)
            pattern = module.Pattern(24, 24, params=params)
        
        params["COLORMAP"] = colormap_dropdown.selected
        params["SPRITE"]   = sprite_dropdown.selected
        pattern.update_params(params)

        # — Evaluate LFOs & render frame —
        mod_signals = evaluate_lfos()
        mod_signals.update(evaluate_env())
        #print("DEBUG vals:", {k: round(v,3) for k,v in mod_signals.items()})
        
        frame = pattern.render(lfo_signals=mod_signals)

        # — Sprite overlay (static or animated GIF) —
        sprite_name = params.get("SPRITE", "none")
        if sprite_name in sprites and sprites[sprite_name]:
            frames = sprites[sprite_name]
            # sync to BPM: 1 beat per frame
            from lfo import BPM
            bps = BPM / 60.0
            beat = (pygame.time.get_ticks()/1000.0) * bps
            idx = int(beat) % len(frames)
            sprite_surf = frames[idx]
            w,h = sprite_surf.get_size()
            ox = (pattern.width - w)//2
            oy = (pattern.height - h)//2
            for yy in range(h):
                for xx in range(w):
                    rgba = sprite_surf.get_at((xx,yy))
                    if rgba[3]>0:
                        frame[ (oy+yy)*pattern.width + (ox+xx) ] = (rgba.r,rgba.g,rgba.b,0)
        
        ## Drawing Section 
        # Simulator (background) ——————————————————————————————
        if show_simulator:
            sim_rect = pygame.Rect(0, FULL_HEIGHT - SIM_HEIGHT,
                                   SCREEN_WIDTH, SIM_HEIGHT)
            draw_simulator(screen, frame,
                           pattern.width, pattern.height,
                           sim_rect)



        # Mode Buttons (Save-mode, Tap-tempo, Show/Hide) ————————
        pygame.draw.rect(screen, (200,80,80) if save_mode else (80,200,80),
                         save_button_rect)
        screen.blit(font.render(
            "SAVE" if not save_mode else "SELECT SLOT", True, (255,255,255)),
            (save_button_rect.x+10, save_button_rect.y+10))

        pygame.draw.rect(screen, (200,80,80) if clear_mode else (80,80,200),
                         clear_button_rect)
        screen.blit(font.render(
            "CLEAR" if not clear_mode else "SELECT SLOT", True, (255,255,255)),
            (clear_button_rect.x+10, clear_button_rect.y+10))

        pygame.draw.rect(screen, (90,90,90), tap_button_rect)
        screen.blit(font.render("Tap Tempo", True, (255,255,255)),
                    (tap_button_rect.x+20, tap_button_rect.y+10))

        pygame.draw.rect(screen, (90,90,90), sim_button_rect)
        screen.blit(button_font.render("Show/Hide", True, (255,255,255)),
                    (sim_button_rect.x+10, sim_button_rect.y+5))

        # Patch Grid Slots ——————————————————————————————
        for i, slot in enumerate(patch_rects):
            # slot background
            pygame.draw.rect(screen, (50,50,50), slot)
            # thumbnail icon
            icon = patch_icons[i]
            if icon:
                ir = icon.get_rect(center=slot.center)
                screen.blit(icon, ir)
            # slot border (red if saving, gray otherwise)
            border_col = (200,80,80) if (save_mode or clear_mode) else (100,100,100)
            pygame.draw.rect(screen, border_col, slot, 2)

        # LFO Outputs & BPM —————————————————————————————

        # row 0: LFO1 (cyan)
        draw_mod_indicator(screen, font, mod_signals,
                        "LFO1", "lfo1", (100,200,255), 0)
        # row 1: LFO2 (magenta)
        draw_mod_indicator(screen, font, mod_signals,
                        "LFO2", "lfo2", (255,100,200), 1)
        # row 2: ENVL (yellow)
        draw_mod_indicator(screen, font, mod_signals,
                        "ENVL", "envl", (255,255,100), 2)
        # row 3: ENVH (orange)
        draw_mod_indicator(screen, font, mod_signals,
                        "ENVH", "envh", (255,150, 50), 3)
        # BPM text
        import lfo
        screen.blit(font.render(f"{int(lfo.BPM)} BPM", True, (200,255,200)),
                    (tap_button_rect.x+20, tap_button_rect.y-20))

        # LFO + RMS Control Panels, Sliders & Mod-Checkboxes —————————
        for s in sliders:
            s.draw(screen, font)
        for c in mod_checkboxes:
            c.draw(screen)
        

        envh_panel.draw(screen, font)
        envl_panel.draw(screen, font)
        lfo2_panel.draw(screen, font)
        lfo1_panel.draw(screen, font)

        # Parameter Dropdowns (closed first, then open on top) —————
        for d in dropdowns:
            if not d.open:
                d.draw(screen, font)
        for d in dropdowns:
            if d.open:
                d.draw(screen, font)
        
        # Fixed Dropdowns (pattern / colormap / sprite) ———————
        pattern_dropdown.draw(screen, font)
        colormap_dropdown.draw(screen, font)
        sprite_dropdown.draw(screen, font)


        # Final Flip 
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    launch_ui()
