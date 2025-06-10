import freenect
import numpy as np
import pygame
import colorsys
import sys
from ws2814 import WS2814

# ------------ CONFIGURATION CONSTANTS ------------
DEPTH_MIN = 500          # initial min depth (mm)
DEPTH_MAX = 800         # initial max depth (mm)
ROI_WIDTH = 50           # width of left/right ROI (pixels)
SENSOR_Y_MIN = 250       # min sensor Y for paddle mapping
SENSOR_Y_MAX = 350       # max sensor Y for paddle mapping
PADDLE_ALPHA = 0.5       # EMA smoothing factor for paddle motion

# ---------------- LED-Wall Setup ----------------
PANEL_WIDTH  = 8    # pixels per panel in X
PANEL_HEIGHT = 8    # pixels per panel in Y
PANELS_X     = 3    # how many panels across
PANELS_Y     = 3    # how many panels down
NUM_LEDS     = PANEL_WIDTH * PANEL_HEIGHT * PANELS_X * PANELS_Y

led_matrix = WS2814('/dev/spidev0.0', NUM_LEDS, 800)


def serpentine_index(x, y):
    px = x // PANEL_WIDTH
    py = y // PANEL_HEIGHT
    lx = x % PANEL_WIDTH
    ly = y % PANEL_HEIGHT
    panel_num = px * PANELS_Y + py
    if (ly % 2) == 0:
        cell_num = ly * PANEL_WIDTH + lx
    else:
        cell_num = ly * PANEL_WIDTH + (PANEL_WIDTH - 1 - lx)
    return panel_num * (PANEL_WIDTH * PANEL_HEIGHT) + cell_num

wall_w = PANEL_WIDTH * PANELS_X  # 24
wall_h = PANEL_HEIGHT * PANELS_Y  # 24

# ---------------- Kinect Helpers ----------------
def get_depth():
    depth, _ = freenect.sync_get_depth(format=freenect.DEPTH_REGISTERED)
    return depth.astype(np.uint16)

def find_hand_y(depth, side, dmin, dmax, roi_width=ROI_WIDTH):
    h, w = depth.shape
    if side == 'left':
        roi = depth[:, :roi_width]
    else:
        roi = depth[:, w-roi_width:]
    mask = (roi >= dmin) & (roi <= dmax)
    ys = np.nonzero(mask)[0]
    return ys.mean() if len(ys) else None

# ---------------- Pong + UI ----------------
class Pong:
    def __init__(self):
        self.W, self.H = 24, 24       # game resolution
        self.S = 10                  # display scale
        self.ui_height = 60           # extra UI space
        pygame.init()
        self.screen = pygame.display.set_mode((self.W*self.S, self.H*self.S + self.ui_height))
        pygame.display.set_caption("Kinect Pong (24×24)")
        self.clock = pygame.time.Clock()

        # paddle geometry
        self.pw, self.ph = 2, 6
        mid = (self.H - self.ph)//2
        self.p1_y = self.p2_y = mid
        self.p1_y_raw = self.p2_y_raw = mid

        # dynamic depth thresholds
        self.depth_min = DEPTH_MIN
        self.depth_max = DEPTH_MAX

        # sensor vertical mapping range
        self.sensor_y_min = SENSOR_Y_MIN
        self.sensor_y_max = SENSOR_Y_MAX

        # ball state (floats) & speed
        self.bx = float(self.W//2)
        self.by = float(self.H//2)
        self.vx, self.vy = 0.2, 0.2

        # slider UI
        self.slider_rect = pygame.Rect(10, self.H*self.S+10, self.W*self.S-20, 20)
        self.knob_radius = 8
        self.knob_min_x = self.slider_rect.left
        self.knob_max_x = self.slider_rect.right
        self.drag_min = self.drag_max = False

        # scores
        self.score1 = 0
        self.score2 = 0

    def map_hand_to_paddle(self, y):
        y_clamped = max(self.sensor_y_min, min(self.sensor_y_max, y))
        norm = (y_clamped - self.sensor_y_min) / (self.sensor_y_max - self.sensor_y_min)
        return int(norm * (self.H - self.ph))

    def step(self):
        depth = get_depth()
        depth = np.fliplr(depth)

        y1 = find_hand_y(depth, 'left', self.depth_min, self.depth_max)
        if y1 is not None:
            tgt1 = self.map_hand_to_paddle(y1)
            self.p1_y_raw = tgt1
            self.p1_y = int(PADDLE_ALPHA*self.p1_y_raw + (1-PADDLE_ALPHA)*self.p1_y)

        y2 = find_hand_y(depth, 'right', self.depth_min, self.depth_max)
        if y2 is not None:
            tgt2 = self.map_hand_to_paddle(y2)
            self.p2_y_raw = tgt2
            self.p2_y = int(PADDLE_ALPHA*self.p2_y_raw + (1-PADDLE_ALPHA)*self.p2_y)

        self.p1_y = max(0, min(self.H-self.ph, self.p1_y))
        self.p2_y = max(0, min(self.H-self.ph, self.p2_y))

        self.bx += self.vx
        self.by += self.vy
        if self.by <= 0 or self.by >= self.H-1:
            self.vy *= -1

        if self.bx <= self.pw:
            if self.p1_y <= self.by <= self.p1_y+self.ph:
                self.vx *= -1
            else:
                self.score2 += 1
                self.reset()
        if self.bx >= self.W-self.pw-1:
            if self.p2_y <= self.by <= self.p2_y+self.ph:
                self.vx *= -1
            else:
                self.score1 += 1
                self.reset()

    def reset(self):
        self.bx, self.by = float(self.W//2), float(self.H//2)
        self.vx *= -1

    def handle_ui(self, ev):
        mx, my = pygame.mouse.get_pos()
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if (mx-self.knob_min_x)**2 + (my-self.slider_rect.centery)**2 < self.knob_radius**2:
                self.drag_min = True
            if (mx-self.knob_max_x)**2 + (my-self.slider_rect.centery)**2 < self.knob_radius**2:
                self.drag_max = True
        elif ev.type == pygame.MOUSEBUTTONUP:
            self.drag_min = self.drag_max = False
        elif ev.type == pygame.MOUSEMOTION:
            if self.drag_min:
                self.knob_min_x = max(self.slider_rect.left, min(mx, self.knob_max_x))
            if self.drag_max:
                self.knob_max_x = min(self.slider_rect.right, max(mx, self.knob_min_x))
            span = self.slider_rect.width
            self.depth_min = int((self.knob_min_x - self.slider_rect.left)/span * 2047)
            self.depth_max = int((self.knob_max_x - self.slider_rect.left)/span * 2047)

    def draw_sliders(self):
        pygame.draw.rect(self.screen, (100,100,100), self.slider_rect, 3)
        cy = self.slider_rect.centery
        pygame.draw.circle(self.screen, (200,50,50), (self.knob_min_x, cy), self.knob_radius)
        pygame.draw.circle(self.screen, (50,200,50), (self.knob_max_x, cy), self.knob_radius)
        font = pygame.font.SysFont(None, 18)
        t1 = font.render(f"min:{self.depth_min}", True, (200,50,50))
        t2 = font.render(f"max:{self.depth_max}", True, (50,200,50))
        self.screen.blit(t1, (self.slider_rect.left, cy+15))
        self.screen.blit(t2, (self.slider_rect.right - t2.get_width(), cy+15))

    def draw(self):
        # 1) draw depth map on a small surf
        depth = get_depth()
        depth = np.fliplr(depth)
        # map and color
        surf = pygame.Surface((self.W, self.H))
        for yy in range(self.H):
            for xx in range(self.W):
                # sample corresponding depth region
                di = int(yy * (depth.shape[0]/self.H))
                dj = int(xx * (depth.shape[1]/self.W))
                val = depth[di, dj]
                t = (val - self.depth_min) / (self.depth_max - self.depth_min)
                t = max(0.0, min(1.0, t))
                # rainbow hsv→rgb
                r, g, b = colorsys.hsv_to_rgb(t*0.7, 1.0, 1.0)
                surf.set_at((xx, yy), (int(r*255), int(g*255), int(b*255)))

        # overlay paddles and ball
        pygame.draw.rect(surf, (255,255,255), (0, self.p1_y, self.pw, self.ph))
        pygame.draw.rect(surf, (255,255,255), (self.W-self.pw, self.p2_y, self.pw, self.ph))
        surf.set_at((int(self.bx), int(self.by)), (255,255,255))

        # send to LED wall
        frame = []
        for yy in range(self.H):
            for xx in range(self.W):
                c = surf.get_at((xx, yy))
                frame.append((c.r, c.g, c.b, 0))
        for y in range(wall_h):
            for x in range(wall_w):
                lin = y*wall_w + x
                if lin < len(frame):
                    r, g, b, _ = frame[lin]
                    idx = serpentine_index(x, y)
                    led_matrix.set_led_color(idx, r, g, b, 0)
        led_matrix.update_strip()

        # draw scaled view + UI
        disp = pygame.transform.scale(surf, (self.W*self.S, self.H*self.S))
        self.screen.blit(disp, (0,0))
        self.draw_sliders()
        pygame.display.flip()

    def run(self):
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    freenect.sync_stop()
                    pygame.quit()
                    sys.exit()
                self.handle_ui(ev)
            self.step()
            self.draw()
            self.clock.tick(30)

if __name__ == '__main__':
    Pong().run()
