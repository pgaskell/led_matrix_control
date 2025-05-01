
import pygame
import time
import importlib
import os
from PIL import Image
from lfo import evaluate_lfos, LFO_CONFIG, BPM



# --- Config ---
SCREEN_WIDTH = 1024
FULL_HEIGHT = 1080
UI_HEIGHT = 600
SIM_HEIGHT = 480
SLIDER_WIDTH = 40
SLIDER_MARGIN = 25
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



class Slider:
    def __init__(self, name, default, min_val, max_val, step, x, y, height):
        self.name = name
        self.value = default
        self.min = min_val
        self.max = max_val
        self.step = step
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
            elif self.open:
                for i, opt in enumerate(self.options):
                    option_rect = pygame.Rect(self.x, self.y + self.height * (i + 1), self.width, self.height)
                    if option_rect.collidepoint(event.pos):
                        self.selected = opt
                        self.open = False
                        break
                else:
                    self.open = False

    def draw(self, screen, font):
        pygame.draw.rect(screen, (100, 100, 100), self.rect)
        display_text = self.label_map.get(self.selected, self.selected)
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
                                     x + 140, y + 5, 80)

        self.sync_button_rect = pygame.Rect(x, y + 35, 100, 25)

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
        if self.config["sync_mode"] == "free":
            self.config["hz"] = int(self.mhz_dropdown.selected) / 1000.0
        else:
            self.config["period_beats"] = self._beats_value(self.beat_dropdown.selected)

    def draw(self, screen, font):
        panel_height = 100

        pygame.draw.rect(screen, (40, 40, 40), pygame.Rect(self.x - 10, self.y - 30, 300, panel_height), border_radius=8)
        # LFO Title
        screen.blit(font.render(self.name.upper(), True, (255, 255, 255)), (self.x, self.y - 20))

        self.waveform_dropdown.draw(screen, font)
        self.depth_slider.draw(screen, font)

        # Sync mode toggle
        pygame.draw.rect(screen, (90, 90, 90), self.sync_button_rect)
        sync_label = "mHz" if self.config["sync_mode"] == "free" else "Q"
        screen.blit(font.render(sync_label, True, (255, 255, 255)),
                    (self.sync_button_rect.x + 8, self.sync_button_rect.y + 2))

        if self.config["sync_mode"] == "free":
            self.mhz_dropdown.draw(screen, font)
        else:
            self.beat_dropdown.draw(screen, font)


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
            default = spec["default"]
            min_val = spec.get("min", default / 2)
            max_val = spec.get("max", default * 2)
            step = spec.get("step", 0.1)
            height = int((UI_HEIGHT - 100) * 0.6)
            sliders.append(Slider(k, current_values[k], min_val, max_val, step, slider_x, slider_y, height))

            if spec.get("modulatable"):
                x_center = slider_x + SLIDER_WIDTH // 2 - 10
                y_start = slider_y + height + 10
                spacing = 24
                lfo_checkboxes.extend([
                    ModCheckbox(k, "lfo1", x_center, y_start + 0 * spacing, (100, 255, 255)),
                    ModCheckbox(k, "lfo2", x_center, y_start + 1 * spacing, (255, 100, 255)),
                    ModCheckbox(k, "audio1", x_center, y_start + 2 * spacing, (255, 255, 100)),
                    ModCheckbox(k, "audio2", x_center, y_start + 3 * spacing, (255, 150, 50))
                ])

            slider_x += SLIDER_WIDTH + SLIDER_MARGIN + 12

    return sliders, dropdowns, lfo_checkboxes






def launch_ui():
    pygame.init()

    show_simulator = True
    current_height = FULL_HEIGHT
    screen = pygame.display.set_mode((SCREEN_WIDTH, current_height), pygame.RESIZABLE)
    pygame.display.set_caption("LED Wall Touch UI")
    font = pygame.font.SysFont("monospace", FONT_SIZE)


    lfo1_panel = LFOControlPanel("lfo1", SCREEN_WIDTH - 300, 90, LFO_CONFIG["lfo1"])
    lfo2_panel = LFOControlPanel("lfo2", SCREEN_WIDTH - 300, 200, LFO_CONFIG["lfo2"])

    patterns = load_patterns()
    pattern_names = sorted(patterns.keys())
    current_index = 0
    
    # --- Load and Register Sprites---
    sprites, sprite_names = load_sprites("sprites")

    from colormaps import COLORMAPS
    colormap_names = list(COLORMAPS.keys())

    # pattern/module initialization
    module = patterns[pattern_names[current_index]]
    param_specs = module.PARAMS
    params = {k: v["default"] for k, v in param_specs.items()}
    if "SPRITE" in param_specs:
        param_specs["SPRITE"]["options"] = sprite_names
    pattern = module.Pattern(24, 24, params=params)
    sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)
    
    # Add colormap dropdown directly, to sit next to pattern dropdown
    selected_colormap = "jet"
    colormap_dropdown = Dropdown("COLORMAP", colormap_names, selected_colormap, 280, 10, width=250, show_label=False)

    # Add sprite dropdown next to colormap
    selected_sprite = "none"
    sprite_dropdown = Dropdown("SPRITE", sprite_names, selected_sprite, 550, 10, width=250, show_label=False)

    button_font = pygame.font.SysFont("monospace", FONT_SIZE)
    button_label = "Hide Simulator"
    button_rect = pygame.Rect(SCREEN_WIDTH - 200, 10, 180, 30)
    dropdown_rect = pygame.Rect(20, 10, 240, 30)
    dropdown_open = False
    tap_button_rect = pygame.Rect(SCREEN_WIDTH - 220, UI_HEIGHT - 90, 180, 45)
    tap_times = []

    clock = pygame.time.Clock()
    running = True

    while running:
        screen.fill(BG_COLOR)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if button_rect.collidepoint(event.pos):
                    show_simulator = not show_simulator
                    button_label = "Hide Simulator" if show_simulator else "Show Simulator"
                elif dropdown_rect.collidepoint(event.pos):
                    dropdown_open = not dropdown_open
                elif dropdown_open:
                    for i, name in enumerate(pattern_names):
                        entry_rect = pygame.Rect(dropdown_rect.x, dropdown_rect.y + 30 * (i+1), 240, 30)
                        if entry_rect.collidepoint(event.pos):
                            current_index = i
                            module = patterns[name]
                            param_specs = module.PARAMS

                            # Fresh default values
                            params = {k: v["default"] for k, v in param_specs.items()}

                            # Inject persistent UI state
                            params["COLORMAP"] = colormap_dropdown.selected
                            params["SPRITE"] = sprite_dropdown.selected

                            # 🔁 Disable modulation on pattern switch
                            for key, spec in param_specs.items():
                                if isinstance(spec, dict) and spec.get("modulatable"):
                                    spec["mod_active"] = False
                                    spec["mod_source"] = None

                            # Rebuild UI elements
                            sliders, dropdowns, mod_checkboxes = create_sliders(param_specs, params)
                            pattern = module.Pattern(24, 24, params=params)

                            dropdown_open = False
                            break

                elif tap_button_rect.collidepoint(event.pos):
                    now = time.time()
                    tap_times.append(now)
                    tap_times = [t for t in tap_times if now - t < 3.0]  # keep recent taps
                    if len(tap_times) >= 2:
                        intervals = [b - a for a, b in zip(tap_times, tap_times[1:])]
                        avg_interval = sum(intervals) / len(intervals)
                        if avg_interval > 0:
                            from lfo import __dict__ as lfo_globals
                            lfo_globals["BPM"] = 60.0 / avg_interval
        
            lfo1_panel.handle_event(event)
            lfo2_panel.handle_event(event)

            for s in sliders:
                s.handle_event(event)
                if not instant_update and event.type == pygame.MOUSEBUTTONUP:
                    params[s.name] = s.value
                    pattern.update_params(params)
            if instant_update:
                for s in sliders:
                    params[s.name] = s.value
                pattern.update_params(params)
            for d in dropdowns:
                d.handle_event(event)
                params[d.name] = d.selected
                pattern.update_params(params)
            for c in mod_checkboxes:
                if c.handle_event(event):
                    meta = pattern.param_meta.get(c.param_name)
                    if meta and meta.get("modulatable"):
                        if c.active:
                            meta["mod_active"] = True
                            meta["mod_source"] = c.source_id
                            # Deactivate other sources
                            for other in mod_checkboxes:
                                if other.param_name == c.param_name and other != c:
                                    other.active = False
                        else:
                            meta["mod_active"] = False
                            meta["mod_source"] = None
        
        colormap_dropdown.handle_event(event)
        params["COLORMAP"] = colormap_dropdown.selected
        pattern.update_params(params)

        sprite_dropdown.handle_event(event)
        params["SPRITE"] = sprite_dropdown.selected
        pattern.update_params(params)

        lfo_signals = evaluate_lfos()
        #print("LFO1:", round(lfo_signals["lfo1"], 3), "LFO2:", round(lfo_signals["lfo2"], 3))
        frame = pattern.render(lfo_signals=lfo_signals)

        sprite_name = params.get("SPRITE", "none")
        if sprite_name != "none" and sprite_name in sprites:
            sprite_frames = sprites[sprite_name]
            bps = BPM / 60.0
            num_frames = len(sprite_frames)
            beats_per_frame = 1.0
            elapsed = pygame.time.get_ticks() / 1000.0
            beat_number = elapsed * bps
            frame_idx = int(beat_number / beats_per_frame) % num_frames
            sprite_surface = sprite_frames[frame_idx]

            sprite_w, sprite_h = sprite_surface.get_size()
            offset_x = (pattern.width - sprite_w) // 2
            offset_y = (pattern.height - sprite_h) // 2

            for y in range(sprite_h):
                for x in range(sprite_w):
                    sx, sy = x + offset_x, y + offset_y
                    if 0 <= sx < pattern.width and 0 <= sy < pattern.height:
                        rgba = sprite_surface.get_at((x, y))
                        if rgba[3] > 0:  # alpha > 0
                            idx = sy * pattern.width + sx
                            frame[idx] = (rgba[0], rgba[1], rgba[2], 0)

        if show_simulator:
            sim_rect = pygame.Rect(0, FULL_HEIGHT - SIM_HEIGHT, SCREEN_WIDTH, SIM_HEIGHT)
            draw_simulator(screen, frame, pattern.width, pattern.height, sim_rect)


        # Draw LFOs
        lfo1_panel.draw(screen, font)
        lfo2_panel.draw(screen, font)

        # Draw sliders
        for s in sliders:
            s.draw(screen, font)

        # Draw dropdowns
        for d in dropdowns:
            d.draw(screen, font)

        # ✅ Draw modulation checkboxes
        for c in mod_checkboxes:
            c.draw(screen)

        # redraw open dropdowns again last
        if lfo1_panel.waveform_dropdown.open:
            lfo1_panel.waveform_dropdown.draw(screen, font)
        if lfo2_panel.waveform_dropdown.open:
            lfo2_panel.waveform_dropdown.draw(screen, font)
        if lfo1_panel.config["sync_mode"] == "free" and lfo1_panel.mhz_dropdown.open:
            lfo1_panel.mhz_dropdown.draw(screen, font)
        if lfo2_panel.config["sync_mode"] == "free" and lfo2_panel.mhz_dropdown.open:
            lfo2_panel.mhz_dropdown.draw(screen, font)

        pygame.draw.rect(screen, (90, 90, 90), button_rect)
        screen.blit(button_font.render(button_label, True, (255, 255, 255)), (button_rect.x + 10, button_rect.y + 5))

        # Draw tap tempo button
        pygame.draw.rect(screen, (90, 90, 90), tap_button_rect)
        screen.blit(font.render("Tap Tempo", True, (255, 255, 255)), (tap_button_rect.x + 20, tap_button_rect.y + 10))

        # Draw the LFO output
        pygame.draw.rect(screen, (50, 50, 50), (20, UI_HEIGHT - 100, 200, 20))
        pygame.draw.rect(screen, (100, 200, 255), (20, UI_HEIGHT - 100, int(200 * lfo_signals["lfo1"]), 20))
        screen.blit(font.render("LFO1", True, (255, 255, 255)), (230, UI_HEIGHT - 100))

        pygame.draw.rect(screen, (50, 50, 50), (20, UI_HEIGHT - 70, 200, 20))
        pygame.draw.rect(screen, (255, 100, 200), (20, UI_HEIGHT - 70, int(200 * lfo_signals["lfo2"]), 20))
        screen.blit(font.render("LFO2", True, (255, 255, 255)), (230, UI_HEIGHT - 70))

        # Show current BPM
        from lfo import BPM
        screen.blit(font.render(f"{int(BPM)} BPM", True, (200, 255, 200)), (tap_button_rect.x + 20, tap_button_rect.y - 20))
                
        pygame.draw.rect(screen, (120, 120, 120), dropdown_rect)
        screen.blit(font.render(pattern_names[current_index], True, (255, 255, 255)), (dropdown_rect.x + 10, dropdown_rect.y + 5))
        colormap_dropdown.draw(screen, font)
        sprite_dropdown.draw(screen, font)

        if dropdown_open:
            for i, name in enumerate(pattern_names):
                entry_rect = pygame.Rect(dropdown_rect.x, dropdown_rect.y + 30 * (i+1), 240, 30)
                pygame.draw.rect(screen, (70, 70, 70), entry_rect)
                screen.blit(font.render(name, True, (255, 255, 255)), (entry_rect.x + 10, entry_rect.y + 5))

        new_height = FULL_HEIGHT if show_simulator else UI_HEIGHT
        if screen.get_height() != new_height:
            screen = pygame.display.set_mode((SCREEN_WIDTH, new_height), pygame.RESIZABLE)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    launch_ui()
