import os
import pygame

EXPRESSIONS = {
    "neutral": "o_O",
    "happy":   "^_^",
    "sleep":   "-_-",
    "think":   "?_?",
    "listen":  "o_o",
    "talk":    "^_o",
}


class FaceDisplay:
    def __init__(self, width=800, height=480):
        if not pygame.get_init():
            pygame.init()
        flags = pygame.FULLSCREEN if os.environ.get("FULLSCREEN") == "1" else pygame.NOFRAME
        self.screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption("Nanito")
        self.font = pygame.font.Font(None, 160)
        self.current = "neutral"

    def show(self, expression="neutral"):
        self.current = expression

    def render(self):
        self.screen.fill((0, 0, 0))
        text = self.font.render(EXPRESSIONS.get(self.current, "o_o"), True, (255, 255, 255))
        rect = text.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
        self.screen.blit(text, rect)
        pygame.display.flip()
