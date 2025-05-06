import pygame, sys, os
import colorsys
from PIL import Image
import spidev
from ws2814 import WS2814

try:
    from ws2814 import WS2814
    # we assume a 24×24 matrix wired in row‐major order
    MATRIX_SIZE = 24
    MATRIX_LEDS = MATRIX_SIZE * MATRIX_SIZE
    led = WS2814('/dev/spidev0.0', MATRIX_LEDS, 800)
    # for y in range(MATRIX_SIZE):
    #         for x in range(MATRIX_SIZE):
    #             led.set_led_color(y*MATRIX_SIZE + x, 0,0,0,0)
    # led.update_strip()
    use_led = True
    print("→ Sprite editor: LED matrix enabled (24×24).")
except Exception as e:
    use_led = False
    print("→ Sprite editor: LED matrix disabled:", e)

def rgb_to_rgbw(r, g, b):
    """Split out white channel as min(R,G,B)."""
    w = min(r, g, b)
    return (r - w, g - w, b - w, w)

def xy_to_index(x, y, width=24):
    # even rows run left→right, odd rows right→left
    if (y & 1) == 0:
        return y * width + x
    else:
        return y * width + (width - 1 - x)

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

# ─── CONFIG ──────────────────────────────────────────────────────────────
SPRITE_DIR = "sprites"
os.makedirs(SPRITE_DIR, exist_ok=True)
FPS        = 30
BASE_GRID_PX = 320
# two canvas sizes
CANVAS_SIZES = [16, 24]
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

def save_png(surface, grid_size, filename):
    fn = filename or next_filename(".png")
    if not fn.endswith(".png"):
        fn += ".png"
    path = os.path.join(SPRITE_DIR, fn)
    pygame.image.save(surface, path)
    print(f"Saved PNG → {path}")

def save_gif(frames, grid_size, filename):
    # build PIL RGBA frames
    pil_frames = []
    for surf in frames:
        raw = pygame.image.tostring(surf, "RGBA")
        img = Image.frombytes("RGBA", (grid_size, grid_size), raw)
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

def layout(grid_size):
    """
    Compute cell and window dimensions so that:
      cell_size * grid_size == BASE_GRID_PX
    """
    # 1) pick a cell size so grid exactly fills BASE_GRID_PX
    cell_size = max(1, BASE_GRID_PX // grid_size)
    grid_px   = cell_size * grid_size

    # 2) sidebar and overall window
    sidebar_x = MARGIN + grid_px + MARGIN
    win_w     = sidebar_x + SIDEBAR_W + MARGIN
    win_h     = MARGIN + grid_px + MARGIN + BUTTON_H + INPUT_H + 10

    return cell_size, grid_px, sidebar_x, win_w, win_h

def paint_cell(frames, cur_frame, gx, gy, grid_size, tool, color):
    """Draw or erase a single cell if inside the grid."""
    if 0 <= gx < grid_size and 0 <= gy < grid_size:
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

    # — initial canvas size —
    grid_size  = CANVAS_SIZES[0]
    pixel_size, grid_px, sidebar_x, win_w, win_h = layout(grid_size)

    def make_frame():
        s = pygame.Surface((grid_size, grid_size), pygame.SRCALPHA)
        s.fill((0,0,0,0))
        return s

    frames     = [make_frame()]
    cur_frame  = 0

    # UI state
    pixel_size = 20

    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption("Sprite Editor")

    # Tools
    # Tools: Pencil, Toggle Size, Eraser, Clear
    tool_buttons = [
        Button(sidebar_x,                   MARGIN,              BUTTON_W, BUTTON_H, "Pencil"),
        Button(sidebar_x + BUTTON_W + 5,    MARGIN,              BUTTON_W, BUTTON_H, "Toggle Size"),
        Button(sidebar_x,                   MARGIN + BUTTON_H+5, BUTTON_W, BUTTON_H, "Eraser"),
        Button(sidebar_x + BUTTON_W + 5,    MARGIN + BUTTON_H+5, BUTTON_W, BUTTON_H, "Clear"),
    ]
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
    btn_prev      = Button(MARGIN,       MARGIN+grid_px+5, BUTTON_W, BUTTON_H, "← Prev")
    btn_copy      = Button(MARGIN+100,   MARGIN+grid_px+5, BUTTON_W, BUTTON_H, "Copy ←")
    btn_next      = Button(MARGIN+200,   MARGIN+grid_px+5, BUTTON_W, BUTTON_H, "Next →")
    btn_png       = Button(MARGIN+300,   MARGIN+grid_px+5, BUTTON_W, BUTTON_H, "Save PNG")
    btn_gif       = Button(MARGIN+400,   MARGIN+grid_px+5, BUTTON_W, BUTTON_H, "Save GIF")
    input_rect    = pygame.Rect( MARGIN, MARGIN+grid_px+5+BUTTON_H+5,
                                 200, INPUT_H )
    filename_text = ""
    input_active  = False

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
                                        grid_size*pixel_size,
                                        grid_size*pixel_size)
                if grid_rect.collidepoint(mx,my):
                    painting = True
                    paint_cell(frames, cur_frame,
                            (mx - MARGIN)//pixel_size,
                            (my - MARGIN)//pixel_size,
                            grid_size, cur_tool, cur_color)

                # 2) Tool buttons (Pencil, Toggle Size, Eraser, Clear)
                if tool_buttons[0].hit(ev.pos):
                    cur_tool = "pencil"
                elif tool_buttons[1].hit(ev.pos):
                    # toggle size and clear frames
                    grid_size = CANVAS_SIZES[(CANVAS_SIZES.index(grid_size)+1) % len(CANVAS_SIZES)]
                    frames[:] = [make_frame()]
                    cur_frame = 0
                    pixel_size, grid_px, sidebar_x, win_w, win_h = layout(grid_size)
                    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                elif tool_buttons[2].hit(ev.pos):
                    cur_tool = "eraser"
                elif tool_buttons[3].hit(ev.pos):
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

                elif btn_copy.hit(ev.pos):
                    if cur_frame > 0:
                        frames[cur_frame].blit(frames[cur_frame-1], (0, 0))

                elif btn_next.hit(ev.pos):
                    if cur_frame == len(frames) - 1:
                        frames.append(make_frame())
                    cur_frame += 1

                elif btn_png.hit(ev.pos):
                    # build full‐res surface and save
                    save_surf = pygame.Surface((grid_size, grid_size), pygame.SRCALPHA)
                    save_surf.blit(frames[cur_frame], (0, 0))
                    save_png(save_surf, grid_size, filename_text)

                elif btn_gif.hit(ev.pos):
                    save_gif(frames, grid_size, filename_text)

                # 5) Filename text entry
                elif input_rect.collidepoint(ev.pos):
                    input_active = True
                else:
                    input_active = False

            elif ev.type == pygame.MOUSEBUTTONUP:
                    painting = False

            elif ev.type == pygame.MOUSEMOTION:
                if painting:
                    mx,my = ev.pos
                    if grid_rect.collidepoint(mx,my):
                        paint_cell(frames, cur_frame,
                                (mx - MARGIN)//pixel_size,
                                (my - MARGIN)//pixel_size,
                                grid_size, cur_tool, cur_color)

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
        for y in range(grid_size):
            for x in range(grid_size):
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

        # grid lines
        for i in range(grid_size+1):
            off = MARGIN + i*pixel_size
            pygame.draw.line(screen,(80,80,80),(off,MARGIN),(off,MARGIN+grid_size*pixel_size))
            pygame.draw.line(screen,(80,80,80),(MARGIN,off),(MARGIN+grid_size*pixel_size,off))

        # sidebar: tools
        for btn in tool_buttons:
            btn.draw(screen, font, active=(btn.label.lower()==cur_tool))

        # palette
        for rect,col in palette_buttons:
            pygame.draw.rect(screen, col, rect)
            if col==cur_color:
                pygame.draw.rect(screen,(255,255,255), rect,2)

        # bottom buttons
        for btn in (btn_prev, btn_copy, btn_next, btn_png, btn_gif):
            btn.draw(screen, font)

        # filename input box
        pygame.draw.rect(screen, (255,255,255) if input_active else (200,200,200),
                         input_rect,2)
        txt = font.render(filename_text, True, (255,255,255))
        screen.blit(txt, (input_rect.x+5, input_rect.y+5))

        # frame indicator
        info = font.render(f"Frame {cur_frame+1}/{len(frames)}", True, (255,255,255))
        screen.blit(info, (btn_gif.rect.right+20, btn_gif.rect.y+5))

        if use_led and grid_size == MATRIX_SIZE:
            surf = frames[cur_frame]
            # row‐major mapping: y=0..23, x=0..23
            # this is actually not correct.
            for y in range(MATRIX_SIZE):
                for x in range(MATRIX_SIZE):
                    r, g, b, a = surf.get_at((x, y))
                    # skip fully transparent pixels (optional)
                    if a == 0:
                        # you could set LED black or leave previous
                        led.set_led_color(y*MATRIX_SIZE + x, 0, 0, 0, 0)
                    else:
                        # simple RGB→RGBW: all white = min(r,g,b)
                        r, g, b, w = rgb_to_rgbw_hsv(r, g, b)
                        # optionally compensate for warm white here…
                        led.set_led_color(y*MATRIX_SIZE + x, r, g, b, w)
            led.update_strip()

        pygame.display.flip()
        clock.tick(FPS)


    pygame.quit()
    for y in range(MATRIX_SIZE):
        for x in range(MATRIX_SIZE):
            led.set_led_color(y*MATRIX_SIZE + x, 0,0,0,0)
    led.update_strip()
    sys.exit()

if __name__ == "__main__":
    main()
