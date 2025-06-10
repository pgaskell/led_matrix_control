import pygame, sys, os
import colorsys
from PIL import Image
import spidev
from ws2814 import WS2814
from gamma import init_gamma, apply_gamma
import tkinter as tk
from tkinter import filedialog


# ─── WALL / PANEL CONFIG ────────────────────────────────────────────────────
PANEL_WIDTH  = 8
PANEL_HEIGHT = 8

# how many panels across/down your “big” sprite editor can address:
X_PANELS = 3
Y_PANELS = 3

# the canvas in pixels is:
GRID_W = X_PANELS * PANEL_WIDTH   # e.g. 3×8 = 24
GRID_H = Y_PANELS * PANEL_HEIGHT  # e.g. 3×8 = 24

NUM_LEDS = PANEL_WIDTH*X_PANELS*PANEL_HEIGHT*Y_PANELS  # total LEDs wired up

tk_root = tk.Tk()
tk_root.withdraw()

init_gamma(
    gammas = {
        "r": 0.65,
        "g": 0.65,
        "b": 0.65,
        "w": 0.85
    },
    scales = {
        "r": 1.00,   # red is usually “normal”
        "g": 0.85,   # green looks a bit too bright
        "b": 0.80,   # blue tends to be dimmer
        "w": 0.90    # white LED is often very bright, so scale it way down
    }
)

def serpentine_index(x, y):
    """
    x,y are 0..(PANEL_WIDTH*X_PANELS -1), 0..(PANEL_HEIGHT*Y_PANELS -1)
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
    panel_num = px * Y_PANELS + py

    # within-panel serpentine on rows
    if (ly % 2) == 0:
        cell_num = ly * PANEL_WIDTH + lx
    else:
        cell_num = ly * PANEL_WIDTH + (PANEL_WIDTH - 1 - lx)

    leds_per_panel = PANEL_WIDTH * PANEL_HEIGHT
    return panel_num * leds_per_panel + cell_num

try:
    from ws2814 import WS2814
    # we assume a 24×24 matrix wired in row‐major order
    led = WS2814('/dev/spidev0.0', NUM_LEDS, 800)
    use_led = True
    print("→ Sprite editor: LED matrix enabled (24×24).")
except Exception as e:
    use_led = False
    print("→ Sprite editor: LED matrix disabled:", e)

def rgb_to_rgbw(r, g, b):
    """Split out white channel as min(R,G,B)."""
    w = min(r, g, b)
    return (r - w, g - w, b - w, w)

def rgb_to_rgbw_hsv(r, g, b):
    # normalize
    rn, gn, bn = r/255.0, g/255.0, b/255.0
    h, s, v    = colorsys.rgb_to_hsv(rn, gn, bn)

    # split into white vs. color_size
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

def ask_sprite_filename():
    # 1) release Pygame’s grab so Tkinter can grab focus
    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)

    # 2) fire up a hidden Tk root to host the standard file dialog
    root = tk.Tk()
    root.withdraw()               # hide the empty root window
    root.attributes("-topmost", 1)  # make sure it pops up in front
    root.update()                 # allow geometry/focus to settle

    # 3) actually ask for a file
    filename = filedialog.askopenfilename(
        title="Open Sprite",
        filetypes=[("PNG images", "*.png"), ("GIF animations", "*.gif")],
    )

    # 4) clean up the Tk window
    root.destroy()

    # 5) restore Pygame’s grab if you want it back
    pygame.event.set_grab(True)
    # you can hide the mouse again if that’s your normal behavior
    # pygame.mouse.set_visible(False)

    return filename


# ─── CONFIG ──────────────────────────────────────────────────────────────
SPRITE_DIR = "sprites"
os.makedirs(SPRITE_DIR, exist_ok=True)
FPS        = 30
BASE_GRID_PX = 320
# two canvas sizes
# 1) Define 8 “nice” hues (degrees): red, orange, yellow, green, cyan, blue, magenta, pink
hue_degrees = [  0,  30,  60, 120, 180, 240, 300, 330 ]
hue_steps   = [h / 360.0 for h in hue_degrees]

# 2) Brightness levels for the top 7 rows (1.0 down to ~0.1429)
hue_brightness = [1.0 - i/7 for i in range(7)]  # [1.0, 0.857…, …, 0.1429]

import colorsys

# ─── PALETTE BUILDING ────────────────────────────────────────────────────────

PALETTE = []

# 1) Eight “nice” hues (in degrees)
hue_degrees = [  0,  30,  60, 120, 180, 240, 300, 330 ]
hue_steps   = [h/360.0 for h in hue_degrees]

# 2) Brightness levels for the 9 color‑rows (row 0 = almost white, row 8 = almost black)
#    We'll go from 1.0 down to 0.1 in nine equal steps.
brightness_levels = [0.6 - (i/5) for i in range(3)]  # [1.0, 0.8875, …, 0.1]
sat_levels = [0.1 + (i/5) for i in range(4)]
# Build the 9 color‑rows
for sat in sat_levels:
    for hue in hue_steps:
        r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
        PALETTE.append((int(r*255), int(g*255), int(b*255)))

for hue in hue_steps:
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    PALETTE.append((int(r*255), int(g*255), int(b*255)))

for bri in brightness_levels:
    for hue in hue_steps:
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, bri)
        PALETTE.append((int(r*255), int(g*255), int(b*255)))

# 3) Bottom grayscale row (row 9): left→right from black→white
for i in range(8):
    v = i / 7
    c = int(v*255)
    PALETTE.append((c, c, c))

# Now PALETTE has 9*8 + 8 = 80 entries, arranged as 10 rows of 8 columns.

MARGIN     = 20
SIDEBAR_W  = 200
BUTTON_W   = 80
BUTTON_H   = 30
PALETTE_SW = 20
INPUT_H    = 30

# ─── HELPERS ─────────────────────────────────────────────────────────────
def next_filename(ext):
    existing = os.listdir(SPRITE_DIR)
    nums = []
    for fn in existing:
        if fn.startswith("tmp") and fn.endswith(ext) and fn[3:5].isdigit():
            nums.append(int(fn[3:5]))
    nxt = max(nums)+1 if nums else 1
    return f"tmp{nxt:02d}{ext}"

def save_png(surface, w, h, filename):
    # Find tight bbox of any non-zero alpha
    xs, ys = w, h
    xe, ye = 0, 0
    for y in range(h):
        for x in range(w):
            if surface.get_at((x,y)).a:
                xs = min(xs, x); ys = min(ys, y)
                xe = max(xe, x); ye = max(ye, y)
    if xe < xs or ye < ys:
        # nothing drawn: fallback to full canvas
        xs, ys, xe, ye = 0, 0, w-1, h-1

    crop = pygame.Rect(xs, ys, xe-xs+1, ye-ys+1)
    sub  = surface.subsurface(crop).copy()
    fn   = filename or next_filename(".png")
    if not fn.endswith(".png"): fn += ".png"
    path = os.path.join(SPRITE_DIR, fn)
    pygame.image.save(sub, path)
    print(f"Saved PNG → {path}")

def save_gif(frames, grid_w, grid_h, filename):
    # compute union bbox of all frames
    xs, ys = grid_w, grid_h
    xe, ye = 0, 0
    for surf in frames:
        for y in range(grid_h):
            for x in range(grid_w):
                if surf.get_at((x,y)).a:
                    xs = min(xs, x); ys = min(ys, y)
                    xe = max(xe, x); ye = max(ye, y)
    if xe < xs or ye < ys:
        xs, ys, xe, ye = 0, 0, grid_w-1, grid_h-1
    w_box, h_box = xe-xs+1, ye-ys+1
    
    pil_frames = []
    for surf in frames:
        raw = pygame.image.tostring(surf.subsurface((xs,ys,w_box,h_box)), "RGBA")
        img = Image.frombytes("RGBA", (w_box, h_box), raw)
        # convert to palette mode with a transparent index
        p = img.convert("RGBA")
        p_pal = p.convert("P", palette=Image.ADAPTIVE, colors=256)
        # ensure palette index 0 is transparent
        p_pal.info["transparency"] = 0
        pil_frames.append(p_pal)

    # figure out the filename
    fn = filename or next_filename(".gif")
    base, ext = os.path.splitext(fn)
    if not ext:
        ext = ".gif"
    fn = f"{base}_G{ext}"
    path = os.path.join(SPRITE_DIR, fn)

    # set disposal=2 on *all* frames so each one is drawn on a clean canvas
    for f in pil_frames:
        f.info["disposal"] = 2

    # save!
    pil_frames[0].save(
        path,
        save_all=True,
        append_images=pil_frames[1:],
        loop=0,
        duration=200,
        disposal=2
    )
    print(f"Saved GIF → {path}")

def layout(grid_w, grid_h):
    """
    Compute:
      • pixel_size so that both grid_w and grid_h * pixel_size
        fit within BASE_GRID_PX, and
      • the window size accordingly.
    """
    # choose a pixel size so that the longer dimension still fits
    cell_size = max(1, BASE_GRID_PX // max(grid_w, grid_h))
    grid_px_w = cell_size * grid_w
    grid_px_h = cell_size * grid_h

    sidebar_x = MARGIN + grid_px_w + MARGIN
    win_w     = sidebar_x + SIDEBAR_W + MARGIN
    win_h     = MARGIN + grid_px_h + MARGIN + BUTTON_H + INPUT_H + 10

    return cell_size, grid_px_w, grid_px_h, sidebar_x, win_w, win_h

def paint_cell(frames, cur_frame, gx, gy, tool, color):
    """Draw or erase a single cell if inside the grid."""
    if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
        surf = frames[cur_frame]
        if tool == "pencil":
            surf.set_at((gx, gy), (*color, 255))
        else:
            # eraser → transparent
            surf.set_at((gx, gy), (0, 0, 0, 0))

class Button:
    def __init__(self, x,y,w,h,label):
        self.rect  = pygame.Rect(x,y,w,h)
        self.label = label
    def draw(self, surf, font, active=False):
        col = (100,100,100) if not active else (150,150,150)
        pygame.draw.rect(surf, col, self.rect)
        txt = font.render(self.label, True, (255,255,255))
        surf.blit(txt, txt.get_rect(center=self.rect.center))
    def hit(self, pos):
        return self.rect.collidepoint(pos)

# ─── MAIN EDITOR ─────────────────────────────────────────────────────────
def main():
    pygame.init()
    clock = pygame.time.Clock()
    font  = pygame.font.SysFont(None, 20)

    # Setup our “big” canvas from panel counts:
    grid_w, grid_h = GRID_W, GRID_H
    pixel_size, grid_px_w, grid_px_h, sidebar_x, win_w, win_h = layout(grid_w, grid_h)

    def make_frame():
        # now make frames exactly grid_w×grid_h
        s = pygame.Surface((grid_px_w, grid_px_h), pygame.SRCALPHA)
        s.fill((0,0,0,0))
        return s

    frames    = [make_frame()]
    cur_frame = 0
    frame_update = False # start true so we get an initial update 

    # UI state
    pixel_size = 12

    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption("Sprite Editor")

    # Tools
    # Tools: Pencil, Toggle Size, Eraser, Clear
    tool_buttons = [
        Button(sidebar_x,                   MARGIN,              BUTTON_W, BUTTON_H, "Pencil"),
        Button(sidebar_x,                   MARGIN + BUTTON_H+5, BUTTON_W, BUTTON_H, "Eraser"),
        Button(sidebar_x + BUTTON_W + 5,    MARGIN + BUTTON_H+5, BUTTON_W, BUTTON_H, "Clear"),
    ]

    open_btn = Button(sidebar_x + BUTTON_W + 5, MARGIN, BUTTON_W, BUTTON_H, "Open...")

    cur_tool = "pencil"

    # Palette matrix: 4×4
    palette_buttons = []
    cols = 8
    for idx, col in enumerate(PALETTE):
        r = idx // cols
        c = idx % cols
        x = sidebar_x + c*(PALETTE_SW+4)
        y = MARGIN + 2*(BUTTON_H+5) + 20 + r*(PALETTE_SW+4)
        palette_buttons.append((pygame.Rect(x,y,PALETTE_SW,PALETTE_SW), col))
    cur_color = PALETTE[0]

    # bottom controls
    btn_prev      = Button(MARGIN,       MARGIN+grid_px_w+5, BUTTON_W, BUTTON_H, "← Prev")
    btn_copy      = Button(MARGIN+100,   MARGIN+grid_px_w+5, BUTTON_W, BUTTON_H, "Copy ←")
    btn_delete    = Button(MARGIN+200,   MARGIN+grid_px_w+5, BUTTON_W, BUTTON_H, "Del")
    btn_next      = Button(MARGIN+300,   MARGIN+grid_px_w+5, BUTTON_W, BUTTON_H, "Next →")
    btn_png       = Button(MARGIN+400,   MARGIN+grid_px_w+5, BUTTON_W, BUTTON_H, "Save PNG")
    btn_gif       = Button(MARGIN+500,   MARGIN+grid_px_w+5, BUTTON_W, BUTTON_H, "Save GIF")
    input_rect    = pygame.Rect( MARGIN, MARGIN+grid_px_w+5+BUTTON_H+5,
                                 200, INPUT_H )
    filename_text = ""
    input_active  = False

    SPRITE_EXTS = (".png", ".gif")
    sprite_files = sorted(f for f in os.listdir(SPRITE_DIR)
                      if f.lower().endswith(SPRITE_EXTS))

    running = True
    painting = False
    while running:
        
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.MOUSEBUTTONDOWN:
                mx,my = ev.pos
                # 1) Did we click _inside_ the grid?
                grid_rect = pygame.Rect(MARGIN, MARGIN,
                                        GRID_W*pixel_size,
                                        GRID_H*pixel_size)
                if grid_rect.collidepoint(mx,my):
                    painting = True
                    x = (mx - MARGIN)//pixel_size
                    y = (my - MARGIN)//pixel_size
                    paint_cell(frames, cur_frame, x, y, cur_tool, cur_color)
                    #TODO: update LEDs live here
                    if use_led:
                        surf = frames[cur_frame]
                        for y in range(grid_h):
                            for x in range(grid_w):
                                idx = serpentine_index(x, y)
                                if(idx < NUM_LEDS):
                                    r, g, b, a = surf.get_at((x,y))
                                    if a == 0:
                                    # you could set LED black or leave previous
                                        led.set_led_color(idx, 0, 0, 0, 0)
                                    else:
                                        # simple RGB→RGBW: all white = min(r,g,b)
                                        r, g, b, w = rgb_to_rgbw_hsv(r, g, b)
                                        r_corr, g_corr, b_corr, w_corr = apply_gamma(r, g, b, w)
                                        led.set_led_color(idx, r_corr, g_corr, b_corr, w_corr)
                        led.update_strip()

                # 2) Tool buttons (Pencil, Eraser, Clear)
                if tool_buttons[0].hit(ev.pos):
                    cur_tool = "pencil"
                elif tool_buttons[1].hit(ev.pos):
                    cur_tool = "eraser"
                elif tool_buttons[2].hit(ev.pos):
                    # clear current frame
                    frames[cur_frame].fill((0, 0, 0, 0))

                # 3) Palette selection
                for rect, col in palette_buttons:
                    if rect.collidepoint(ev.pos):
                        cur_color = col

                # 4) Bottom controls: Prev, Copy, Next, Save PNG, Save GIF
                if btn_prev.hit(ev.pos):
                    if cur_frame > 0:
                        cur_frame -= 1
                    frame_update = True

                elif btn_copy.hit(ev.pos):
                    if cur_frame > 0:
                        frames[cur_frame].blit(frames[cur_frame-1], (0, 0))
                    frame_update = True
                
                elif btn_delete.hit(ev.pos):
                    # remove the current frame
                    if len(frames) > 1:
                        frames.pop(cur_frame)
                        # clamp current index
                        cur_frame = min(cur_frame, len(frames)-1)
                    else:
                        # if only one frame, just clear it
                        frames[0].fill((0,0,0,0))
                    frame_update = True
                
                elif btn_next.hit(ev.pos):
                    if cur_frame == len(frames) - 1:
                        frames.append(make_frame())
                    cur_frame += 1
                    frame_update = True

                elif btn_png.hit(ev.pos):
                    # build full‐res surface and save
                    save_surf = pygame.Surface((GRID_W, GRID_H), pygame.SRCALPHA)
                    save_surf.blit(frames[cur_frame], (0, 0))
                    save_png(save_surf, grid_w, grid_h, filename_text)

                elif btn_gif.hit(ev.pos):
                    save_gif(frames, grid_w, grid_h, filename_text)

                elif open_btn.hit(ev.pos):
                    path = ask_sprite_filename()
                    if path:
                        # …your existing code to load the PNG/GIF into frames…
                        frames.clear()
                        cur_frame = 0
                        if path.lower().endswith(".png"):
                            surf = pygame.image.load(path).convert_alpha()
                            surf = pygame.transform.scale(surf, (GRID_W, GRID_H))
                            frames.append(surf)
                        else:
                            gif = Image.open(path)
                            try:
                                while True:
                                    f = gif.convert("RGBA")
                                    data = f.tobytes()
                                    surf = pygame.image.fromstring(data, f.size, f.mode).convert_alpha()
                                    surf = pygame.transform.scale(surf, (GRID_W, GRID_H))
                                    frames.append(surf)
                                    gif.seek(gif.tell() + 1)
                            except EOFError:
                                pass

                    frame_update = True

                # 5) Filename text entry
                elif input_rect.collidepoint(ev.pos):
                    input_active = True
                else:
                    input_active = False

            elif ev.type == pygame.MOUSEBUTTONUP:
                    painting = False
                    frame_update = True

            elif ev.type == pygame.MOUSEMOTION:
                if painting:
                    mx,my = ev.pos
                    x = (mx - MARGIN)//pixel_size
                    y = (my - MARGIN)//pixel_size
                    if grid_rect.collidepoint(mx,my):
                        paint_cell(frames, cur_frame, x, y, cur_tool, cur_color)
                        if use_led:
                            r, g, b, a = surf.get_at((x,y))
                            idx = serpentine_index(x, y)
                            if(idx < NUM_LEDS):
                                if a == 0:
                                    # you could set LED black or leave previous
                                    led.set_led_color(idx, 0, 0, 0, 0)
                                else:
                                    # simple RGB→RGBW: all white = min(r,g,b)
                                    r, g, b, w = rgb_to_rgbw_hsv(r, g, b)
                                    r_corr, g_corr, b_corr, w_corr = apply_gamma(r, g, b, w)
                                    # optionally compensate for warm white here…
                                    led.set_led_color(idx, r_corr, g_corr, b_corr, w_corr)
                            led.update_strip()

            elif ev.type == pygame.KEYDOWN and input_active:
                if ev.key == pygame.K_BACKSPACE:
                    filename_text = filename_text[:-1]
                elif ev.key == pygame.K_RETURN:
                    input_active = False
                else:
                    filename_text += ev.unicode   

        # — DRAW —————————————————————————————————————————————
        screen.fill((50,50,50))

        # grid cells (with checker for transparent)
        for y in range(grid_h):
            for x in range(grid_w):
                px = MARGIN + x*pixel_size
                py = MARGIN + y*pixel_size
                rect = pygame.Rect(px, py, pixel_size, pixel_size)
                col = frames[cur_frame].get_at((x,y))
                if col.a==0:
                    # draw checkerboard
                    sq = pixel_size//2
                    c1, c2 = (200,200,200), (100,100,100)
                    pygame.draw.rect(screen, c1, (px,py,sq,sq))
                    pygame.draw.rect(screen, c2, (px+sq,py,sq,sq))
                    pygame.draw.rect(screen, c2, (px,py+sq,sq,sq))
                    pygame.draw.rect(screen, c1, (px+sq,py+sq,sq,sq))
                else:
                    pygame.draw.rect(screen, (col.r,col.g,col.b), rect)

        # sidebar: tools
        for btn in tool_buttons:
            btn.draw(screen, font, active=(btn.label.lower()==cur_tool))

        # palette
        for rect,col in palette_buttons:
            pygame.draw.rect(screen, col, rect)
            if col==cur_color:
                pygame.draw.rect(screen,(255,255,255), rect,2)

        # bottom buttons
        for btn in (btn_prev, btn_copy, btn_delete, btn_next, btn_png, btn_gif):
            btn.draw(screen, font)
        
        open_btn.draw(screen, font)

        # filename input box
        pygame.draw.rect(screen, (255,255,255) if input_active else (200,200,200),
                         input_rect,2)
        txt = font.render(filename_text, True, (255,255,255))
        screen.blit(txt, (input_rect.x+5, input_rect.y+5))

        # frame indicator
        info = font.render(f"Frame {cur_frame+1}/{len(frames)}", True, (255,255,255))
        screen.blit(info, (btn_gif.rect.right+20, btn_gif.rect.y+5))

        if use_led and frame_update:
            surf = frames[cur_frame]
            for y in range(grid_h):
                for x in range(grid_w):
                    r, g, b, a = surf.get_at((x, y))
                    idx = serpentine_index(x, y)
                    if(idx < NUM_LEDS):
                        if a == 0:
                            led.set_led_color(idx, 0,0,0,0)
                        else:
                            r, g, b, w = rgb_to_rgbw_hsv(r, g, b)
                            r_corr, g_corr, b_corr, w_corr = apply_gamma(r, g, b, w)
                            # optionally compensate for warm white here…
                            led.set_led_color(idx, r_corr, g_corr, b_corr, w_corr)
            led.update_strip()
            frame_update = False

        pygame.display.flip()
        clock.tick(FPS)


    pygame.quit()
    for y in range(grid_h):
        for x in range(grid_w):
            idx = serpentine_index(x, y)
            if(idx < NUM_LEDS):
                led.set_led_color(idx, 0,0,0,0)
    led.update_strip()
    sys.exit()

if __name__ == "__main__":
    main()
