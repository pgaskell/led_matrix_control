#!/usr/bin/env python3
import pygame, sys, time, random
from ws2814 import WS2814

# ─── LED MATRIX CONFIG ─────────────────────────────────────────────────────
PANEL_WIDTH  = 8    # pixels per panel
PANEL_HEIGHT = 8
PANELS_X     = 3    # panels across
PANELS_Y     = 3    # panels down

WIDTH  = PANEL_WIDTH  * PANELS_X   # 16
HEIGHT = PANEL_HEIGHT * PANELS_Y   # 32
NUM_LEDS = WIDTH * HEIGHT

# initialize your strip
led = WS2814('/dev/spidev0.0', NUM_LEDS, 800)

def serpentine_index(x, y):
    """ column-major panels, each panel rows zig-zag """
    px = x // PANEL_WIDTH; py = y // PANEL_HEIGHT
    lx = x % PANEL_WIDTH;  ly = y % PANEL_HEIGHT
    panel = px * PANELS_Y + py
    if (ly & 1)==0:
        cell = ly * PANEL_WIDTH + lx
    else:
        cell = ly * PANEL_WIDTH + (PANEL_WIDTH -1 - lx)
    return panel * (PANEL_WIDTH*PANEL_HEIGHT) + cell

def push_to_led(board):
    """ board[y][x] is (r,g,b) or None """
    for y in range(HEIGHT):
        for x in range(WIDTH):
            idx = serpentine_index(x,y)
            color = board[y][x] or (0,0,0)
            led.set_led_color(idx, *color, 0)
    led.update_strip()

# ─── TETROMINO DEFINITIONS ──────────────────────────────────────────────────
# each piece: list of rotation states, each is list of (x,y) offsets
TETROMINOES = {
    'I': [ [(0,1),(1,1),(2,1),(3,1)],
           [(2,0),(2,1),(2,2),(2,3)] ],
    'O': [ [(1,0),(2,0),(1,1),(2,1)] ],
    'T': [ [(1,0),(0,1),(1,1),(2,1)],
           [(1,0),(1,1),(2,1),(1,2)],
           [(0,1),(1,1),(2,1),(1,2)],
           [(1,0),(0,1),(1,1),(1,2)] ],
    'S': [ [(1,0),(2,0),(0,1),(1,1)],
           [(1,0),(1,1),(2,1),(2,2)] ],
    'Z': [ [(0,0),(1,0),(1,1),(2,1)],
           [(2,0),(1,1),(2,1),(1,2)] ],
    'J': [ [(0,0),(0,1),(1,1),(2,1)],
           [(1,0),(2,0),(1,1),(1,2)],
           [(0,1),(1,1),(2,1),(2,2)],
           [(1,0),(1,1),(0,2),(1,2)] ],
    'L': [ [(2,0),(0,1),(1,1),(2,1)],
           [(1,0),(1,1),(1,2),(2,2)],
           [(0,1),(1,1),(2,1),(0,2)],
           [(0,0),(1,0),(1,1),(1,2)] ],
}

COLORS = {
    'I': (0,240,240), 'O': (240,240,0), 'T': (160,0,240),
    'S': (0,240,0),   'Z': (240,0,0),  'J': (0,0,240),
    'L': (240,160,0)
}

class Tetris:
    def __init__(self):
        self.board = [ [None]*WIDTH for _ in range(HEIGHT) ]
        self.spawn_new()
        self.drop_delay = 0.5
        self.last_drop = time.time()
        self.score = 0

    def spawn_new(self):
        self.shape = random.choice(list(TETROMINOES.keys()))
        self.rot   = 0
        self.x     = WIDTH//2 -2
        self.y     = 0
        self.blocks = TETROMINOES[self.shape]
        self.color  = COLORS[self.shape]

    def rotate(self):
        old = self.rot
        self.rot = (self.rot+1) % len(self.blocks)
        if self.collide(): self.rot = old

    def move(self, dx):
        self.x += dx
        if self.collide(): self.x -= dx

    def drop(self):
        self.y += 1
        if self.collide():
            self.y -= 1
            self.lock()

    def hard_drop(self):
        while not self.collide():
            self.y += 1
        self.y -= 1
        self.lock()

    def collide(self):
        for bx,by in self.blocks[self.rot]:
            x = self.x+bx; y = self.y+by
            if x<0 or x>=WIDTH or y<0 or y>=HEIGHT: return True
            if self.board[y][x] is not None: return True
        return False

    def lock(self):
        for bx,by in self.blocks[self.rot]:
            self.board[self.y+by][self.x+bx] = self.color
        self.clear_lines()
        self.spawn_new()
        if self.collide():
            self.game_over()

    def clear_lines(self):
        new = [ row for row in self.board if any(c is None for c in row) ]
        cleared = HEIGHT - len(new)
        if cleared>0:
            self.score += cleared*100
            self.board = [ [None]*WIDTH for _ in range(cleared) ] + new

    def game_over(self):
        print("Game Over!  Score:", self.score)
        pygame.quit(); sys.exit()

    def update(self):
        now = time.time()
        if now - self.last_drop > self.drop_delay:
            self.drop()
            self.last_drop = now

    def draw(self, surf):
        surf.fill((0,0,0))
        # draw locked
        for y,row in enumerate(self.board):
            for x,col in enumerate(row):
                if col:
                    pygame.draw.rect(surf, col,
                        (x*20, y*20, 20,20))
        # draw falling
        for bx,by in self.blocks[self.rot]:
            x,y = self.x+bx, self.y+by
            if 0<=y<HEIGHT:
                pygame.draw.rect(surf, self.color,
                    (x*20, y*20, 20,20))

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH*20, HEIGHT*20))
    pygame.display.set_caption("Tetris on LED Wall")
    clock = pygame.time.Clock()
    game = Tetris()

    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT:
                pygame.quit(); sys.exit()
            elif ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_LEFT:  game.move(-1)
                if ev.key==pygame.K_RIGHT: game.move( 1)
                if ev.key==pygame.K_UP:    game.rotate()
                if ev.key==pygame.K_DOWN:  game.drop()
                if ev.key==pygame.K_SPACE: game.hard_drop()

        game.update()
        game.draw(screen)
        pygame.display.flip()

        # push to LEDs
        # read back the Pygame surface pixels 1:1 into our board
        buf = pygame.surfarray.array3d(screen)
        # buf.shape == (WIDTH*20, HEIGHT*20, 3)
        # sample the center of each 20×20 cell
        led_board = [[ None for _ in range(WIDTH)] for __ in range(HEIGHT)]
        for y in range(HEIGHT):
            for x in range(WIDTH):
                r,g,b = buf[x*20+10, y*20+10]
                led_board[y][x] = (int(r),int(g),int(b))
        push_to_led(led_board)

        clock.tick(10)

if __name__=="__main__":
    main()
