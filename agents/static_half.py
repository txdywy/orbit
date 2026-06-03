import math
from collections import namedtuple


Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])
CENTER = 50.0
ROTATION_RADIUS_LIMIT = 50.0


def get(obs, key, default=None):
    return obs.get(key, default) if isinstance(obs, dict) else getattr(obs, key, default)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def is_static(planet):
    return distance((planet.x, planet.y), (CENTER, CENTER)) + planet.radius >= ROTATION_RADIUS_LIMIT


def agent(obs):
    player = get(obs, "player", 0)
    planets = [Planet(*p) for p in get(obs, "planets", []) if p[2] >= 0 and p[3] >= 0]
    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player and is_static(p)]
    moves = []

    if not targets:
        return moves

    for source in my_planets:
        if source.ships < 20:
            continue
        target = min(targets, key=lambda t: distance((source.x, source.y), (t.x, t.y)))
        ships = int(source.ships) // 2
        if ships >= 20:
            angle = math.atan2(target.y - source.y, target.x - source.x)
            moves.append([source.id, angle, ships])
    return moves
