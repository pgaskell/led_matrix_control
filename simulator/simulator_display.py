import pygame
import sys

class Simulator:
    def __init__(self, width, height, pixel_size=20):
        pygame.init()
        self.width = width
        self.height = height
        self.pixel_size = pixel_size
        self.screen = pygame.display.set_mode((width * pixel_size, height * pixel_size))
        pygame.display.set_caption("LED Wall Simulator")
        self.closed = False  # Track if user closed the window

    def show(self, frame):
        if self.closed:
            return  # Skip rendering if window closed

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.closed = True
                pygame.quit()
                sys.exit(0)

        for y in range(self.height):
            for x in range(self.width):
                idx = y * self.width + x
                color = frame[idx]
                color_rgb = (color[0], color[1], color[2])
                pygame.draw.rect(
                    self.screen, color_rgb,
                    (x*self.pixel_size, y*self.pixel_size, self.pixel_size, self.pixel_size)
                )
        pygame.display.flip()
