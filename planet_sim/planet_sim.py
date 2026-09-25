"""
PlanetSimulation — N-body (colisões + zoom + partículas)
by Daniel Luis
github.com/danieldluis
"""

import pygame
import math
import random
import sys
from collections import deque

# ─── Config ───────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1024, 768
CENTER = (WIDTH // 2, HEIGHT // 2)
G = 0.01
DT = 0.1
TRAIL_LEN = 120
STAR_COUNT = 200
PARTICLES_PER_COLLISION = 20

SUN_COLOR = (255, 200, 50)
SUN_GLOW = (255, 150, 0)
PALETTE = [
    (100, 180, 255), (255, 120, 80), (120, 255, 140),
    (200, 100, 255), (255, 220, 100), (255, 80, 120),
]
BG = (5, 5, 15)
CULL_MARGIN = 5000


# ─── Estrelas ─────────────────────────────────────────────────────────────────
def make_star_surface():
    surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for _ in range(STAR_COUNT):
        x = random.randint(0, WIDTH - 1)
        y = random.randint(0, HEIGHT - 1)
        b = random.randint(80, 255)
        surf.fill((b, b, b), (x, y, 1, 1))
    return surf


# ─── Partícula ────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 3.0)
        self.x, self.y = x, y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = random.randint(30, 60)
        self.max_life = self.life
        self.color = color
        self.size = random.randint(1, 3)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.97
        self.vy *= 0.97
        self.life -= 1

    def draw(self, surface, cam_x, cam_y, zoom):
        if self.life <= 0:
            return
        sx, sy = world_to_screen(self.x, self.y, cam_x, cam_y, zoom)
        frac = self.life / self.max_life
        c = tuple(int(v * frac) for v in self.color)
        pygame.draw.circle(surface, c, (sx, sy), max(1, int(self.size * zoom * frac)))


# ─── Corpo ────────────────────────────────────────────────────────────────────
class Body:
    def __init__(self, mass, x, y, vx, vy, radius, color, is_sun=False):
        self.mass = mass
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.radius = radius
        self.color = color
        self.is_sun = is_sun
        self.trail = deque(maxlen=TRAIL_LEN)
        self.alive = True
        self.ax, self.ay = 0.0, 0.0

    @property
    def speed(self):
        return math.sqrt(self.vx ** 2 + self.vy ** 2)


# ─── Física ───────────────────────────────────────────────────────────────────
def compute_accelerations(bodies):
    for b in bodies:
        if not b.alive:
            continue
        ax, ay = 0.0, 0.0
        for other in bodies:
            if other is b or not other.alive:
                continue
            dx = other.x - b.x
            dy = other.y - b.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < 1:
                continue
            dist = math.sqrt(dist_sq)
            force = G * other.mass / dist_sq
            ax += force * dx / dist
            ay += force * dy / dist
        b.ax, b.ay = ax, ay


def step_physics(bodies):
    for b in bodies:
        if not b.alive:
            continue
        b.vx += 0.5 * b.ax * DT
        b.vy += 0.5 * b.ay * DT

    for b in bodies:
        if not b.alive:
            continue
        b.x += b.vx * DT
        b.y += b.vy * DT
        b.trail.append((b.x, b.y))

    compute_accelerations(bodies)

    for b in bodies:
        if not b.alive:
            continue
        b.vx += 0.5 * b.ax * DT
        b.vy += 0.5 * b.ay * DT


# ─── Colisão ──────────────────────────────────────────────────────────────────
def handle_collisions(bodies, particles):
    for i in range(len(bodies)):
        if not bodies[i].alive:
            continue
        for j in range(i + 1, len(bodies)):
            if not bodies[j].alive:
                continue
            a, b = bodies[i], bodies[j]
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < a.radius + b.radius:
                if a.mass >= b.mass:
                    survivor, absorbed = a, b
                else:
                    survivor, absorbed = b, a
                total_mass = survivor.mass + absorbed.mass
                survivor.vx = (survivor.vx * survivor.mass + absorbed.vx * absorbed.mass) / total_mass
                survivor.vy = (survivor.vy * survivor.mass + absorbed.vy * absorbed.mass) / total_mass
                survivor.x = (survivor.x * survivor.mass + absorbed.x * absorbed.mass) / total_mass
                survivor.y = (survivor.y * survivor.mass + absorbed.y * absorbed.mass) / total_mass
                survivor.mass = total_mass
                survivor.radius = int((survivor.radius**3 + absorbed.radius**3) ** (1/3))
                absorbed.alive = False
                for _ in range(PARTICLES_PER_COLLISION):
                    particles.append(Particle(survivor.x, survivor.y, absorbed.color))
    return [b for b in bodies if b.alive]


# ─── Cena ─────────────────────────────────────────────────────────────────────
def create_default_scene():
    sun = Body(mass=50000, x=CENTER[0], y=CENTER[1],
               vx=0, vy=0, radius=18, color=SUN_COLOR, is_sun=True)
    r = 150
    v = math.sqrt(G * sun.mass / r)
    earth = Body(mass=1, x=CENTER[0] + r, y=CENTER[1],
                 vx=0, vy=v, radius=5, color=PALETTE[0])
    r2 = 230
    v2 = math.sqrt(G * sun.mass / r2)
    mars = Body(mass=1, x=CENTER[0] - r2, y=CENTER[1],
                vx=0, vy=-v2, radius=4, color=PALETTE[1])
    r3 = 340
    v3 = math.sqrt(G * sun.mass / r3)
    jup = Body(mass=5, x=CENTER[0], y=CENTER[1] + r3,
               vx=-v3, vy=0, radius=9, color=PALETTE[3])
    return [sun, earth, mars, jup]


def get_sun(bodies):
    for b in bodies:
        if b.is_sun:
            return b
    return max(bodies, key=lambda b: b.mass) if bodies else None


def spawn_planet_at(bodies, r, radius, mass):
    sun = get_sun(bodies)
    if sun is None:
        return None
    angle = random.uniform(0, 2 * math.pi)
    x = sun.x + r * math.cos(angle)
    y = sun.y + r * math.sin(angle)
    v = math.sqrt(G * sun.mass / r)
    color = random.choice(PALETTE)
    return Body(mass, x, y, -v * math.sin(angle), v * math.cos(angle), radius, color)


def spawn_random_planet(bodies):
    r = random.uniform(80, 380)
    return spawn_planet_at(bodies, r, random.randint(3, 7), random.uniform(0.5, 5))


# ─── Câmara ───────────────────────────────────────────────────────────────────
def world_to_screen(x, y, cam_x, cam_y, zoom):
    return (int((x - cam_x) * zoom + WIDTH // 2),
            int((y - cam_y) * zoom + HEIGHT // 2))


def screen_to_world(sx, sy, cam_x, cam_y, zoom):
    return ((sx - WIDTH // 2) / zoom + cam_x,
            (sy - HEIGHT // 2) / zoom + cam_y)


# ─── Desenho ──────────────────────────────────────────────────────────────────
def draw_trail(surface, trail, color, cam_x, cam_y, zoom):
    if len(trail) < 2:
        return
    for i in range(1, len(trail)):
        frac = i / len(trail)
        c = (
            max(0, int(color[0] * frac)),
            max(0, int(color[1] * frac)),
            max(0, int(color[2] * frac)),
        )
        p0 = world_to_screen(trail[i-1][0], trail[i-1][1], cam_x, cam_y, zoom)
        p1 = world_to_screen(trail[i][0], trail[i][1], cam_x, cam_y, zoom)
        pygame.draw.line(surface, c, p0, p1, max(1, int(zoom)))


def draw_glow(surface, x, y, radius, color, zoom, layers=4):
    for i in range(layers, 0, -1):
        r = int((radius + i * 4) * zoom)
        c = (
            min(255, color[0] + i * 15),
            min(255, color[1] + i * 5),
            max(0, color[2] - i * 20),
        )
        pygame.draw.circle(surface, c, (x, y), r)


def draw_body(surface, body, cam_x, cam_y, zoom):
    x, y = world_to_screen(body.x, body.y, cam_x, cam_y, zoom)
    r = max(1, int(body.radius * zoom))
    if body.is_sun:
        draw_glow(surface, x, y, r, SUN_GLOW, zoom)
    pygame.draw.circle(surface, body.color, (x, y), r)


def draw_hover_info(surface, body, sun, cam_x, cam_y, zoom, font):
    sx, sy = world_to_screen(body.x, body.y, cam_x, cam_y, zoom)
    lines = [
        f"mass: {body.mass:.1f}",
        f"speed: {body.speed:.2f} px/f",
        f"radius: {body.radius}",
    ]
    if not body.is_sun and sun:
        d = math.sqrt((body.x - sun.x) ** 2 + (body.y - sun.y) ** 2)
        lines.append(f"dist to sun: {d:.0f}")

    box_x, box_y = sx + 15, sy - 10
    box_w, box_h = 160, len(lines) * 16 + 8

    if box_x + box_w > WIDTH:
        box_x = sx - box_w - 15
    if box_y + box_h > HEIGHT:
        box_y = sy - box_h
    if box_y < 0:
        box_y = 5

    pygame.draw.rect(surface, (15, 15, 30), (box_x, box_y, box_w, box_h), border_radius=4)
    pygame.draw.rect(surface, (80, 80, 120), (box_x, box_y, box_w, box_h), width=1, border_radius=4)
    for i, line in enumerate(lines):
        surface.blit(font.render(line, True, (200, 200, 220)), (box_x + 8, box_y + 6 + i * 16))


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("PlanetSimulation — N-body (colisões + zoom + partículas)")   
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 13)
    font_small = pygame.font.SysFont("monospace", 11)

    star_bg = make_star_surface()

    bodies = create_default_scene()
    compute_accelerations(bodies)
    particles = []
    paused = False
    running = True
    speed_mult = 1.0

    cam_x, cam_y = CENTER[0], CENTER[1]
    zoom = 1.0
    dragging = False
    drag_start = (0, 0)
    cam_start = (0, 0)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    bodies = create_default_scene()
                    compute_accelerations(bodies)
                    particles = []
                    cam_x, cam_y = CENTER[0], CENTER[1]
                    zoom = 1.0
                    speed_mult = 1.0
                    paused = False
                elif event.key in (pygame.K_EQUALS, pygame.K_KP_PLUS):
                    speed_mult = min(10.0, speed_mult * 2)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed_mult = max(0.25, speed_mult / 2)
                elif event.key == pygame.K_1:
                    p = spawn_planet_at(bodies, r=80, radius=3, mass=0.5)
                    if p: bodies.append(p)
                elif event.key == pygame.K_2:
                    p = spawn_planet_at(bodies, r=180, radius=5, mass=1)
                    if p: bodies.append(p)
                elif event.key == pygame.K_3:
                    p = spawn_planet_at(bodies, r=300, radius=9, mass=5)
                    if p: bodies.append(p)
                elif event.key == pygame.K_4:
                    p = spawn_planet_at(bodies, r=380, radius=11, mass=8)
                    if p: bodies.append(p)
                elif event.key == pygame.K_5:
                    p = spawn_random_planet(bodies)
                    if p: bodies.append(p)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    dragging = True
                    drag_start = event.pos
                    cam_start = (cam_x, cam_y)
                elif event.button == 4:
                    mx, my = pygame.mouse.get_pos()
                    wx, wy = screen_to_world(mx, my, cam_x, cam_y, zoom)
                    zoom = min(5.0, zoom * 1.15)
                    cam_x = wx - (mx - WIDTH // 2) / zoom
                    cam_y = wy - (my - HEIGHT // 2) / zoom
                elif event.button == 5:
                    mx, my = pygame.mouse.get_pos()
                    wx, wy = screen_to_world(mx, my, cam_x, cam_y, zoom)
                    zoom = max(0.2, zoom / 1.15)
                    cam_x = wx - (mx - WIDTH // 2) / zoom
                    cam_y = wy - (my - HEIGHT // 2) / zoom

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and dragging:
                    dragging = False
                    dx = event.pos[0] - drag_start[0]
                    dy = event.pos[1] - drag_start[1]
                    if dx * dx + dy * dy < 16:
                        wx, wy = screen_to_world(event.pos[0], event.pos[1], cam_x, cam_y, zoom)
                        sun = get_sun(bodies)
                        if sun:
                            ddx, ddy = wx - sun.x, wy - sun.y
                            r = math.sqrt(ddx * ddx + ddy * ddy)
                            if r > 30:
                                v = math.sqrt(G * sun.mass / r)
                                angle = math.atan2(ddy, ddx)
                                color = random.choice(PALETTE)
                                bodies.append(Body(
                                    mass=random.uniform(0.5, 5),
                                    x=wx, y=wy,
                                    vx=-v * math.sin(angle), vy=v * math.cos(angle),
                                    radius=random.randint(3, 6), color=color
                                ))

            elif event.type == pygame.MOUSEMOTION:
                if dragging:
                    dx = (event.pos[0] - drag_start[0]) / zoom
                    dy = (event.pos[1] - drag_start[1]) / zoom
                    cam_x = cam_start[0] - dx
                    cam_y = cam_start[1] - dy

        if not paused:
            steps = max(1, int(speed_mult * 10))
            for _ in range(steps):
                step_physics(bodies)
                bodies = handle_collisions(bodies, particles)
                bodies = [b for b in bodies
                          if abs(b.x - cam_x) < CULL_MARGIN and abs(b.y - cam_y) < CULL_MARGIN]
                if not bodies:
                    bodies = create_default_scene()
                    compute_accelerations(bodies)
                    break

            for p in particles:
                p.update()
            particles = [p for p in particles if p.life > 0]

        screen.fill(BG)
        screen.blit(star_bg, (0, 0))
        for b in bodies:
            draw_trail(screen, b.trail, b.color, cam_x, cam_y, zoom)
        for p in particles:
            p.draw(screen, cam_x, cam_y, zoom)
        for b in bodies:
            draw_body(screen, b, cam_x, cam_y, zoom)

        mouse_pos = pygame.mouse.get_pos()
        hovered = None
        for b in bodies:
            sx, sy = world_to_screen(b.x, b.y, cam_x, cam_y, zoom)
            r = max(1, int(b.radius * zoom)) + 5
            if (sx - mouse_pos[0]) ** 2 + (sy - mouse_pos[1]) ** 2 < r * r:
                hovered = b
                break
        if hovered:
            sun = get_sun(bodies)
            draw_hover_info(screen, hovered, sun, cam_x, cam_y, zoom, font_small)

        status = "PAUSED" if paused else "RUNNING"
        hud1 = f" {status} | bodies: {len(bodies)} | zoom: {zoom:.1f}x | speed: {speed_mult:.1f}x [+/-] speed "
        hud2 = "  [SPACE] pause  [R] reset  [1-5] spawn  [scroll] zoom  [drag] pan  [click] add"
        screen.blit(font.render(hud1, True, (180, 180, 200)), (10, 10))
        screen.blit(font.render(hud2, True, (110, 140, 160)), (6, 28))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()   