class Projectile:
    def __init__(self, start_pos, end_pos, colour, speed=300.0):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.speed = speed  # pixels per second
        self.progress = 0.0  # 0.0 to 1.0
        self.colour = colour  # Store colour here

    def update(self, dt):
        dist = ((self.end_pos[0] - self.start_pos[0])**2 + (self.end_pos[1] - self.start_pos[1])**2)**0.5
        if dist == 0:
            self.progress = 1.0
            return
        self.progress += (self.speed * dt) / dist
        if self.progress > 1.0:
            self.progress = 1.0

    def get_position(self):
        x = self.start_pos[0] + (self.end_pos[0] - self.start_pos[0]) * self.progress
        y = self.start_pos[1] + (self.end_pos[1] - self.start_pos[1]) * self.progress
        return (x, y)

    def is_finished(self):
        return self.progress >= 1.0