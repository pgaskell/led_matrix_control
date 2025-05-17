
import pygame
import random
import time
import importlib
import os
import json
import colorsys
from ws2814 import WS2814
from os.path import join, isfile
from PIL import Image
from lfo import evaluate_lfos, LFO_CONFIG, BPM
from audio_env import evaluate_env, ENV_CONFIG

PANEL_WIDTH  = 8    # pixels per panel in X
PANEL_HEIGHT = 8    # pixels per panel in Y
PANELS_X     = 3    # how many panels across
PANELS_Y     = 3    # how many panels down

WALL_W = PANEL_WIDTH  * PANELS_X   # e.g. 8*3 = 24
WALL_H = PANEL_HEIGHT * PANELS_Y   # e.g. 8*3 = 24

NUM_LEDS = PANEL_WIDTH*PANELS_X*PANEL_HEIGHT*PANELS_Y           # total LEDs wired up
NUM_LEDS = 64


led_matrix = WS2814('/dev/spidev0.0', NUM_LEDS, 800) 

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

def serpentine_index(x, y):
    """
    x,y are 0..(PANEL_WIDTH*PANELS_X -1), 0..(PANEL_HEIGHT*PANELS_Y -1)
    Panels wired column-major top→down, then next column.
    Inside each panel: each row is serpentine L→R then R→L.
    """
    # which panel
    px = x // PANEL_WIDTH
    py = y // PANEL_HEIGHT

    # local coords inside panel
    lx = x % PANEL_WIDTH
    ly = y % PANEL_HEIGHT

    # panel number in column-major, NO zig-zag at panel level
    panel_num = px * PANELS_Y + py

    # within-panel serpentine on rows
    if (ly % 2) == 0:
        cell_num = ly * PANEL_WIDTH + lx
    else:
        cell_num = ly * PANEL_WIDTH + (PANEL_WIDTH - 1 - lx)

    leds_per_panel = PANEL_WIDTH * PANEL_HEIGHT
    return panel_num * leds_per_panel + cell_num

def restore_patch(index,
                  pattern_names,
                  patterns,
                  lfo_panels,
                  env_panels,
                  pattern_dropdown,
                  colormap_dropdown,
                  sprite_dropdown,
                  create_sliders):
    """
    Load patch[index] from disk and restore:
      1. Switch to the saved pattern
      2. Rebuild sliders/dropdowns/checkboxes
      3. Restore each param’s modulatable flags
      4. Restore LFO_CONFIG into lfo_panels
      5. Restore ENV_CONFIG into env_panels
      6. Restore colormap & sprite dropdowns
    Returns: (new_index, pattern, sliders, dropdowns, mod_checkboxes)
    """
    patch = load_patch(index)

    # 1) Pattern switch
    new_index    = pattern_names.index(patch["pattern"])
    module       = patterns[pattern_names[new_index]]
    param_specs  = module.PARAMS
    params       = patch["params"].copy()
    pattern      = module.Pattern(WALL_W, WALL_H, params=params)

    # 2) UI elements
    sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)

    # 3) Modulation flags
    for name, m in patch["modulation"].items():
        meta = param_specs.get(name)
        if not meta: 
            continue
        meta["mod_active"] = m["mod_active"]
        meta["mod_source"] = m["mod_source"]
        meta["mod_mode"]   = m["mod_mode"]
        # sync checkbox
        for cb in mod_checkboxes:
            if cb.param_name == name:
                cb.active = (cb.source_id == m["mod_source"])

    # 4) LFOs
    import lfo
    lfo.LFO_CONFIG.update(patch["lfo_config"])
    for (lname, panel) in zip(("lfo1","lfo2"), lfo_panels):
        cfg = lfo.LFO_CONFIG[lname]
        panel.config.update(cfg)
        panel.waveform_dropdown.selected = cfg["waveform"]
        panel.depth_slider.value        = cfg["depth"]
        panel.offset_slider.value       = cfg.get("offset", 0.0)
        panel.config["offset"]          = cfg.get("offset", 0.0)
        panel.sync_mode                 = cfg["sync_mode"]
        if cfg["sync_mode"] == "free":
            panel.mhz_dropdown.selected  = str(int(cfg["hz"]*1000))
        else:
            panel.beat_dropdown.selected = panel._beats_label(cfg["period_beats"])

    # 5) Envelopes
    import audio_env
    audio_env.ENV_CONFIG.update(patch["env_config"])
    for (ename, panel) in zip(("envl","envh"), env_panels):
        cfg = audio_env.ENV_CONFIG[ename]
        panel.th_slider.value   = cfg["threshold_db"]
        panel.gn_slider.value   = cfg["gain_db"]
        panel.atk_dd.selected   = panel.attack_map[cfg["attack"]]
        panel.rel_dd.selected   = panel.release_map[cfg["release"]]
        panel.mode_dd.selected  = cfg["mode"]
        panel.config.update(cfg)

    # 6) Colormap & sprite
    pattern_dropdown.selected    = patch["pattern"]
    if "COLORMAP" in params:
        colormap_dropdown.selected = params["COLORMAP"]
    if "SPRITE" in params:
        sprite_dropdown.selected   = params["SPRITE"]

    # commit into the live pattern
    pattern.update_params(params)

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

def rgb_to_rgbw_min(r, g, b):
    w = min(r, g, b)
    return r - w, g - w, b - w, w

def rgb_to_rgbw_extra(r, g, b):
    w = min(r, g, b)
    # don't subtract, just boost with white 
    return r , g , b , int(w/2)

def rgb_to_rgbw_luma(r, g, b):
    # Rec.709 luma formula
    w0 = 0.2126*r + 0.7152*g + 0.0722*b  
    w  = int(min(w0, r, g, b))
    return r - w, g - w, b - w, w

def rgb_to_rgbw_hsv(r, g, b):
    # normalize
    rn, gn, bn = r/255.0, g/255.0, b/255.0
    h, s, v    = colorsys.rgb_to_hsv(rn, gn, bn)

    # split into white vs. color
    w_frac = (1.0 - s) * v
    c_frac = s * v

    # rebuild a pure‐hue color at full saturation
    pr, pg, pb = colorsys.hsv_to_rgb(h, 1.0, 1.0)

    # scale back down
    r4 = int(pr * c_frac * 255)
    g4 = int(pg * c_frac * 255)
    b4 = int(pb * c_frac * 255)
    w4 = int(w_frac * 255)

    return (r4, g4, b4, w4)

def compensate_warm_white(r, g, b):
    """
    Simple tint‑correction for warm‑white LEDs:
      • slightly reduce red and green,
      • boost blue to pull back toward neutral.
    """
    rc = int(r * 0.92)
    gc = int(g * 0.96)
    bc = int(b * 1.10)
    return min(rc, 255), min(gc, 255), min(bc, 255)

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
    def __init__(self, name, options, default, x, y,
                 width=120, show_label=True, label_map=None,
                 dropup=False, max_visible=8):
        self.name         = name
        self.options      = options
        self.selected     = default
        self.x            = x
        self.y            = y
        self.width        = width
        self.show_label   = show_label
        self.label_map    = label_map or {}
        self.dropup       = dropup

        self.rect         = pygame.Rect(x, y, width, 25)
        self.entry_h      = self.rect.height
        self.open         = False

        # scrolling state
        self.max_visible  = max_visible
        self.start_index  = 0

        # up/down arrow buttons
        self.arrow_up_rect   = pygame.Rect(
            self.x, 
            self.y - self.entry_h if self.dropup else self.y + self.entry_h * (self.max_visible+1),
            self.width, self.entry_h
        )
        self.arrow_down_rect = pygame.Rect(
            self.x,
            self.y - self.entry_h*(self.max_visible+2) if self.dropup else self.y + self.entry_h * (self.max_visible+2),
            self.width, self.entry_h
        )

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # toggle if main box clicked
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
                return True

            if self.open:
                # wheel up/down
                # new, clamped‐scroll logic
                if event.button == 4 or event.button == 5:
                    # wheel-up is button 4, wheel-down is button 5
                    if event.button == 4:
                        # scroll up
                        self.start_index = max(0, self.start_index - 1)
                    else:
                        # scroll down
                        max_start = max(0, len(self.options) - self.max_visible)
                        self.start_index = min(max_start, self.start_index + 1)
                    return True

                # up arrow?
                if self.arrow_up_rect.collidepoint(event.pos):
                    if self.start_index > 0:
                        self.start_index -= 1
                    return True
                # down arrow?
                if self.arrow_down_rect.collidepoint(event.pos):
                    if self.start_index + self.max_visible < len(self.options):
                        self.start_index += 1
                    return True

                # clicking one of the visible entries
                for idx in range(self.start_index,
                                 min(len(self.options), self.start_index + self.max_visible)):
                    i = idx - self.start_index
                    offset = -self.entry_h*(i+1) if self.dropup else self.entry_h*(i+1)
                    entry_rect = pygame.Rect(self.x,
                                             self.y + offset,
                                             self.width,
                                             self.entry_h)
                    if entry_rect.collidepoint(event.pos):
                        self.selected = self.options[idx]
                        self.open = False
                        return True

                # click elsewhere closes
                self.open = False
                return True

        return False

    def draw(self, screen, font):
        # main box
        pygame.draw.rect(screen, (100, 100, 100), self.rect)
        txt = str(self.label_map.get(self.selected, self.selected))
        if len(txt) > 14:
             txt = txt[:11] + "..."
        screen.blit(font.render(txt, True, (255, 255, 255)),
                    (self.x + 6, self.y + 4))

        if self.show_label:
            lbl = self.name.split("_")[-1] + ":"
            surf = font.render(lbl, True, (160,160,160))
            screen.blit(surf, (self.x - surf.get_width() - 6, self.y + 4))

        if not self.open:
            return

        # draw the visible entries
        start = self.start_index
        end   = min(len(self.options), start + self.max_visible)

        for idx in range(start, end):
            i = idx - start
            offset = -self.entry_h*(i+1) if self.dropup else self.entry_h*(i+1)
            option_rect = pygame.Rect(self.x,
                                      self.y + offset,
                                      self.width,
                                      self.entry_h)
            pygame.draw.rect(screen, (70,70,70), option_rect)
            label = str(self.label_map.get(self.options[idx], self.options[idx]))
            if len(label) > 14:
                label = label[:11] + "..."
            screen.blit(font.render(label, True, (255,255,255)),
                        (self.x + 6, option_rect.y + 4))

        # now always draw both arrows, but grey them if disabled
        up_enabled   = (self.start_index > 0)
        down_enabled = (self.start_index + self.max_visible < len(self.options))

        # arrow background
        bg_color = (120,120,120)
        screen.fill(bg_color, self.arrow_up_rect)
        screen.fill(bg_color, self.arrow_down_rect)

        # arrow color: bright when enabled, dim when not
        en_col   = (200,200,200)
        dis_col  = (80,80,80)

        up_col   = en_col if up_enabled   else dis_col
        down_col = en_col if down_enabled else dis_col

        # draw the “↑” and “↓”
        up_txt   = font.render("↑", True, up_col)
        down_txt = font.render("↓", True, down_col)

        # center them in the arrow rects
        ux = self.arrow_up_rect.x   + (self.width - up_txt.get_width())//2
        uy = self.arrow_up_rect.y   + (self.entry_h - up_txt.get_height())//2
        dx = self.arrow_down_rect.x + (self.width - down_txt.get_width())//2
        dy = self.arrow_down_rect.y + (self.entry_h- down_txt.get_height())//2

        screen.blit(up_txt,   (ux, uy))
        screen.blit(down_txt, (dx, dy))



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
        #print(f"[{self.name}] depth={self.config['depth']:.2f}, offset={self.config['offset']:.2f}")

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

        self.attack_map = {
            0.001: "1ms",
            0.005: "5ms",
            0.010: "10ms",
            0.020: "20ms"
        }
        self.release_map = {
            0.025: "25ms",
            0.050: "50ms",
            0.100: "100ms",
            0.150: "150ms"
        }

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
    bold_bpm_font = pygame.font.SysFont("monospace", FONT_SIZE, bold=True)
    font = pygame.font.SysFont("monospace", FONT_SIZE)
    button_font = pygame.font.SysFont("monospace", FONT_SIZE)

    # — Patch grid setup —
    display_patch_mode = False
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
        "Pattern",
        pattern_names,
        pattern_names[current_index],
        20, 10,
        width=180, show_label=False,
        dropup=False,
        max_visible=20
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
    pattern = module.Pattern(WALL_W, WALL_H, params=params)
    sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)

    # — Fixed dropdowns (won’t be recreated on pattern change) —
    selected_colormap = params.get("COLORMAP", colormap_names[0])
    colormap_dropdown = Dropdown(
        "COLORMAP",
        colormap_names,
        selected_colormap,
        220, 10,
        width=180, show_label=False,
        max_visible=20
    )
    selected_sprite = params.get("SPRITE", "none")
    sprite_dropdown = Dropdown(
        "SPRITE",
        sprite_names,
        selected_sprite,
        420, 10,
        width=180, show_label=False,
        max_visible=20
    )
    # — UI button rectangles —
    BTN = 90
    SPACING = 10
 
    toggle_rect = pygame.Rect(SCREEN_WIDTH - BTN*8 - SPACING*6, UI_HEIGHT - BTN - SPACING, BTN, BTN)

    sim_button_rect  = pygame.Rect(SCREEN_WIDTH - 200, 10, 180, 25)


    save_button_rect  = pygame.Rect(SCREEN_WIDTH - BTN*2 - SPACING*3,
                                    UI_HEIGHT - BTN - SPACING,
                                    BTN, BTN)
    clear_button_rect = pygame.Rect(SCREEN_WIDTH - BTN*3 - SPACING*4,
                                    UI_HEIGHT - BTN - SPACING,
                                    BTN, BTN)
    tap_button_rect   = pygame.Rect(SCREEN_WIDTH - BTN - SPACING*2,
                                    UI_HEIGHT - BTN - SPACING,
                                    BTN, BTN)
    tap_times = []

        # –– Random-cycle controls ––
    random_cycle = False
    cycle_beats = 8
    last_cycle_time = time.time()

    # how many beats between random‐patch cycles?
    cycle_beats = 8

# dropdown right to left: place it just to the left of your clear button
    SP = 10  # same SPACING you’re using
    DD_W = 100

    cycle_dropdown = Dropdown(
        "Beats",
        ["2","4","8","16","32"],
        str(cycle_beats),
        clear_button_rect.x - 70,
        clear_button_rect.y,
        width=60,
        show_label=False,
        dropup=True
    )

    # a square toggle to the left of the slider
    random_button_rect = pygame.Rect(
        clear_button_rect.x - 170,
        save_button_rect.y,
        BTN, BTN
    )

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
            temp = mod.Pattern(WALL_W, WALL_H, params=params)
            frame = temp.render(lfo_signals={})
            patch_icons[i] = make_thumbnail(
                temp, frame,
                sprites, params,
                (SLOT_SIZE, SLOT_SIZE)
            )

    while running:
        screen.fill(BG_COLOR)

    # Random‐cycle check
        if random_cycle:
            now = time.time()
            # how many beats since last cycle?
            beats_elapsed = (now - last_cycle_time) * (BPM / 60.0)
            if beats_elapsed >= cycle_beats:
                last_cycle_time = now

                # pick one of your saved slots at random
                saved = [i for i, has in enumerate(patches) if has]
                if saved:
                    slot = random.choice(saved)

                    # call your shared restore function:
                    (current_index,
                    pattern,
                    sliders,
                    dropdowns,
                    mod_checkboxes) = restore_patch(
                        slot,
                        pattern_names,
                        patterns,
                        [lfo1_panel, lfo2_panel],
                        [envl_panel, envh_panel],
                        pattern_dropdown,
                        colormap_dropdown,
                        sprite_dropdown,
                        create_sliders
                    )

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

                # N-Beats slider
            if cycle_dropdown.handle_event(event):
                cycle_beats = int(cycle_dropdown.selected)
                continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                # First, let the top dropdowns handle it
                # (pattern dropdown, colormap dropdown, sprite dropdown)
                if pattern_dropdown.handle_event(event):
                    continue
                if colormap_dropdown.handle_event(event):
                    continue
                if sprite_dropdown.handle_event(event):
                    continue
                if toggle_rect.collidepoint(event.pos):
                    display_patch_mode = not display_patch_mode
                    continue 
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
                
                if random_button_rect.collidepoint(event.pos):
                    random_cycle = not random_cycle
                    last_cycle_time = time.time()
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
                                pattern = module.Pattern(WALL_W, WALL_H, params=params)
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
            pattern = module.Pattern(WALL_W, WALL_H, params=params)
        
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
    
        # Output to the LED Matrix!
        wall_w = PANEL_WIDTH * PANELS_X
        wall_h = PANEL_HEIGHT * PANELS_Y

        for y in range(wall_h):
            for x in range(wall_w):
                # compute the index into your frame buffer:
                linear = y * wall_w + x
                if linear >= len(frame):
                    continue
                r, g, b, _ = frame[linear]
                r, g, b = compensate_warm_white(r, g, b)
                r4, g4, b4, w = rgb_to_rgbw_luma(r, g, b)

                idx = serpentine_index(x, y)
                if idx < NUM_LEDS:
                    led_matrix.set_led_color(idx, r4, g4, b4, w)
        led_matrix.update_strip()

        # Mode Buttons (Save-mode, Tap-tempo, Show/Hide) ————————
        pygame.draw.rect(screen, (200,80,80) if save_mode else (80,200,80),
                         save_button_rect)
        screen.blit(font.render(
            "SAVE" if not save_mode else "SELECT", True, (255,255,255)),
            (save_button_rect.x+10, save_button_rect.y+10))

        pygame.draw.rect(screen, (200,80,80) if clear_mode else (80,80,200),
                         clear_button_rect)
        screen.blit(font.render(
            "CLEAR" if not clear_mode else "SELECT", True, (255,255,255)),
            (clear_button_rect.x+10, clear_button_rect.y+10))

        # Random-cycle toggle (red when ON, gray when OFF)
        col = (200,80,80) if random_cycle else (80,80,80)
        pygame.draw.rect(screen, col, random_button_rect)
        screen.blit(font.render("RND", True, (255,255,255)),
                    (random_button_rect.x+6, random_button_rect.y+8))

        


        pygame.draw.rect(screen, (90,90,90), tap_button_rect)
        screen.blit(font.render("TAP", True, (255,255,255)),
                    (tap_button_rect.x+20, tap_button_rect.y+10))

        pygame.draw.rect(screen, (90,90,90), sim_button_rect)
        screen.blit(button_font.render("Show/Hide", True, (255,255,255)),
                    (sim_button_rect.x+10, sim_button_rect.y+5))

        if not display_patch_mode and not save_mode:
            # Pattern-mode: show your normal simulator
            sim_rect = pygame.Rect(265, 55,
                                   440, 440)
            draw_simulator(screen, frame,
                           pattern.width, pattern.height,
                           sim_rect)
        else:
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
        
        # — Draw the Mode-Toggle button itself —
        pygame.draw.rect(screen, (80,80,80), toggle_rect)
        bw, bh = toggle_rect.width, toggle_rect.height
        pw, ph = pattern.width, pattern.height
        pixel_size = min(bw // pw, bh // ph)
        # total icon size
        icon_w = pixel_size * pw
        icon_h = pixel_size * ph

        # center it inside the button
        off_x = toggle_rect.x + (bw - icon_w)//2
        off_y = toggle_rect.y + (bh - icon_h)//2


        if display_patch_mode:
            # Pattern-mode: draw the full‐pattern thumbnail
            for y in range(ph):
                for x in range(pw):
                    idx = y*pw + x
                    r,g,b,_ = frame[idx]
                    rect = pygame.Rect(
                        off_x + x*pixel_size,
                        off_y + y*pixel_size,
                        pixel_size, pixel_size
                    )
                    pygame.draw.rect(screen, (r,g,b), rect)
        else:
            # Patch-mode: draw an 8×8 grid icon
            rows, cols = PATCH_ROWS, PATCH_COLS  # 8,8
            # reuse pixel_size if you like, or recompute a grid‐cell size
            cell = min(bw // cols, bh // rows)
            grid_w = cell * cols
            grid_h = cell * rows
            gx = toggle_rect.x + (bw - grid_w)//2
            gy = toggle_rect.y + (bh - grid_h)//2

            for i in range(rows*cols):
                row, col = divmod(i, cols)
                cell_r = pygame.Rect(
                    gx + col*cell,
                    gy + row*cell,
                    cell, cell
                )
                # filled = slot has a patch?
                colr = (200,80,80) if patches[i] else (50,50,50)
                pygame.draw.rect(screen, colr, cell_r)
                pygame.draw.rect(screen, (0,0,0), cell_r, 1)
        
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
        bpm_text = f"{int(lfo.BPM)} BPM"
        screen.blit(
            bold_bpm_font.render(bpm_text, True, (127,255,0)),
            (tap_button_rect.x+2, tap_button_rect.y - FONT_SIZE + 80)
)

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
        # N-Beats slider
        cycle_dropdown.draw(screen, font)
        pattern_dropdown.draw(screen, font)
        colormap_dropdown.draw(screen, font)
        sprite_dropdown.draw(screen, font)


        # Final Flip 
        pygame.display.flip()
        clock.tick(30)

    for i in range(min(NUM_LEDS, len(frame))):
        led_matrix.set_led_color(i, 0, 0, 0, 0)
    led_matrix.update_strip()
    pygame.quit()


if __name__ == "__main__":
    launch_ui()
