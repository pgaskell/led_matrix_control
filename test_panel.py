from ws2814 import WS2814
from gamma import init_gamma, apply_gamma
import time
PANEL_WIDTH  = 8    # pixels per panel in X
PANEL_HEIGHT = 8    # pixels per panel in Y
PANELS_X     = 3    # how many panels across
PANELS_Y     = 3    # how many panels down

WALL_W = PANEL_WIDTH  * PANELS_X   # e.g. 8*3 = 24
WALL_H = PANEL_HEIGHT * PANELS_Y   # e.g. 8*3 = 24

NUM_LEDS = PANEL_WIDTH*PANELS_X*PANEL_HEIGHT*PANELS_Y
panel = WS2814('/dev/spidev0.0', NUM_LEDS, 800)

init_gamma(
    gammas = {
        "r": 0.65,
        "g": 0.65,
        "b": 0.65,
        "w": 0.65
    },
    scales = {
        "r": 1.25,   # red is usually “normal”
        "g": 1.25,   # green looks a bit too bright
        "b": 1.25,   # blue tends to be dimmer
        "w": 1.25    # white LED is often very bright, so scale it way down
    }
)

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

def main():
    panel.clear_strip()
    panel.update_strip()
    #panel.fill_strip(0, 0, 0, 0) # R G B W
    for i in range(WALL_W):
        r_corr, g_corr, b_corr, w_corr = apply_gamma(i * int(255/WALL_W),0,255 - i * int(255/WALL_W),0)
        for j in range(WALL_H): 
            panel.set_led_color(serpentine_index(i, j), r_corr, g_corr, b_corr, w_corr)
        print((r_corr, g_corr, b_corr, w_corr))
    panel.update_strip()

if __name__ == "__main__":
    main()