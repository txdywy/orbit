import math
from collections import namedtuple


Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])
Fleet = namedtuple("Fleet", ["id", "owner", "x", "y", "angle", "from_planet_id", "ships"])

BOARD_SIZE = 100.0
CENTER = 50.0
SUN_RADIUS = 10.0
ROTATION_RADIUS_LIMIT = 50.0
MAX_SPEED = 6.0
GAME_LENGTH = 500


def get(obs, key, default=None):
    if isinstance(obs, dict):
        return obs.get(key, default)
    return getattr(obs, key, default)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_to_segment_distance(point, start, end):
    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    length2 = dx * dx + dy * dy
    if length2 <= 1e-12:
        return dist(point, start)
    t = ((px - sx) * dx + (py - sy) * dy) / length2
    t = max(0.0, min(1.0, t))
    return dist(point, (sx + t * dx, sy + t * dy))


def line_crosses_sun(start, end, buffer=0.35):
    return point_to_segment_distance((CENTER, CENTER), start, end) <= SUN_RADIUS + buffer


def fleet_speed(ships):
    ships = max(1, int(ships))
    speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000)) ** 1.5
    return min(MAX_SPEED, speed)


def is_orbiting(planet):
    return dist((planet.x, planet.y), (CENTER, CENTER)) + planet.radius < ROTATION_RADIUS_LIMIT


def planet_position_at(planet, initial_by_id, angular_velocity, future_step, comet_ids):
    if planet.id in comet_ids:
        return (planet.x, planet.y)
    initial = initial_by_id.get(planet.id)
    if initial is None:
        return (planet.x, planet.y)
    orbital_radius = dist((initial.x, initial.y), (CENTER, CENTER))
    if orbital_radius + initial.radius >= ROTATION_RADIUS_LIMIT:
        return (planet.x, planet.y)
    initial_angle = math.atan2(initial.y - CENTER, initial.x - CENTER)
    angle = initial_angle + angular_velocity * future_step
    return (
        CENTER + orbital_radius * math.cos(angle),
        CENTER + orbital_radius * math.sin(angle),
    )


def parse_planets(raw_planets):
    return [Planet(*p) for p in raw_planets]


def fleet_hits_planet(fleet, planet):
    start = (fleet.x, fleet.y)
    end = (
        fleet.x + math.cos(fleet.angle) * 130.0,
        fleet.y + math.sin(fleet.angle) * 130.0,
    )
    return point_to_segment_distance((planet.x, planet.y), start, end) <= planet.radius + 0.6


def capture_need(target, owner_is_enemy, travel_turns):
    need = int(target.ships) + 1
    if owner_is_enemy:
        need += int(math.ceil(travel_turns * target.production))
    return need


def comet_remaining_turns(comet_id, comets_data):
    if not comets_data:
        return 0
    for cg in comets_data:
        if comet_id in cg.get("planet_ids", []):
            paths = cg.get("paths", [])
            pi = cg.get("path_index", 0)
            if paths and pi < len(paths[0]):
                return len(paths[0]) - pi
    return 0


def total_ships_by_player(planets, fleets, player_ids):
    totals = {pid: 0 for pid in player_ids}
    for p in planets:
        if p.owner in totals:
            totals[p.owner] += int(p.ships)
    for f in fleets:
        if f.owner in totals:
            totals[f.owner] += int(f.ships)
    return totals


def compute_threat_map(fleets, my_planets, player):
    incoming = {}
    for f in fleets:
        if f.owner == player or f.owner == -1:
            continue
        best = None
        best_d = float("inf")
        for p in my_planets:
            if fleet_hits_planet(f, p):
                d = dist((f.x, f.y), (p.x, p.y))
                if d < best_d:
                    best_d = d
                    best = p
        if best is not None:
            if best.id not in incoming:
                incoming[best.id] = 0
            incoming[best.id] += f.ships
    return incoming


def compute_my_incoming(fleets, my_planet_ids, player):
    incoming = {pid: 0 for pid in my_planet_ids}
    for f in fleets:
        if f.owner == player and f.from_planet_id in incoming:
            incoming[f.from_planet_id] += f.ships
    return incoming


def choose_focus_enemy(planets, fleets, player):
    enemy_ships = {}
    for p in planets:
        if p.owner not in (-1, player):
            enemy_ships[p.owner] = enemy_ships.get(p.owner, 0) + int(p.ships)
    for f in fleets:
        if f.owner not in (-1, player):
            enemy_ships[f.owner] = enemy_ships.get(f.owner, 0) + int(f.ships)
    if not enemy_ships:
        return None
    return max(enemy_ships, key=enemy_ships.get)


def score_target(source, target, player, step, initial_by_id, angular_velocity, comet_ids, ships, comets_data, focus_enemy):
    sx, sy = source.x, source.y
    tx, ty = target.x, target.y
    d = dist((sx, sy), (tx, ty))
    if line_crosses_sun((sx, sy), (tx, ty)):
        return None

    speed = fleet_speed(max(1, ships))
    travel = max(1.0, d / speed)
    arrival_step = step + int(round(travel))
    fpos = planet_position_at(target, initial_by_id, angular_velocity, arrival_step, comet_ids)
    if line_crosses_sun((sx, sy), fpos):
        return None

    is_comet = target.id in comet_ids
    is_enemy = target.owner not in (-1, player)
    is_focus = is_enemy and target.owner == focus_enemy

    remaining_game = GAME_LENGTH - arrival_step
    if remaining_game <= 0:
        return -999999

    effective_remaining = remaining_game
    if is_comet:
        comet_rem = comet_remaining_turns(target.id, comets_data)
        effective_remaining = min(effective_remaining, comet_rem)
        if effective_remaining < 5:
            return -999999

    prod_value = target.production * effective_remaining

    capture_cost = int(target.ships) + 1
    if is_enemy:
        capture_cost += int(math.ceil(travel * target.production))

    net_value = prod_value - capture_cost

    enemy_bonus = 0.0
    if is_enemy:
        enemy_bonus = 50.0 + target.production * 8.0
        if is_focus:
            enemy_bonus += 20.0

    comet_bonus = 0.0
    if is_comet:
        if effective_remaining > 20:
            comet_bonus = 15.0
        elif effective_remaining > 10:
            comet_bonus = 5.0

    static_bonus = 3.0 if not is_orbiting(target) else 0.0

    dist_penalty = d * 0.3

    return net_value + enemy_bonus + comet_bonus + static_bonus - dist_penalty


def agent(obs):
    player = get(obs, "player", 0)
    planets = parse_planets(get(obs, "planets", []))
    fleets = [Fleet(*f) for f in get(obs, "fleets", [])]
    initial_planets = parse_planets(get(obs, "initial_planets", get(obs, "planets", [])))
    initial_by_id = {p.id: p for p in initial_planets}
    angular_velocity = float(get(obs, "angular_velocity", 0.035))
    comet_ids = set(get(obs, "comet_planet_ids", []))
    comets_data = get(obs, "comets", [])
    step = int(get(obs, "step", 0) or 0)

    my_planets = [p for p in planets if p.owner == player]
    if not my_planets:
        return []

    all_targets = [p for p in planets if p.owner != player and p.x >= 0 and p.y >= 0]
    if not all_targets:
        return []

    players = set(p.owner for p in planets if p.owner != -1) | set(f.owner for f in fleets if f.owner != -1)
    ship_counts = total_ships_by_player(planets, fleets, players)
    my_ships = ship_counts.get(player, 0)
    max_enemy_ships = max((v for k, v in ship_counts.items() if k != player), default=0)
    ahead = my_ships > max_enemy_ships * 1.15
    far_ahead = my_ships > max_enemy_ships * 1.8

    threat_map = compute_threat_map(fleets, my_planets, player)
    total_threat = sum(threat_map.values())
    my_incoming = compute_my_incoming(fleets, {p.id for p in my_planets}, player)
    focus_enemy = choose_focus_enemy(planets, fleets, player)

    moves = []
    claimed = set()

    for source in sorted(my_planets, key=lambda p: (p.ships, p.production), reverse=True):
        total_pressure = threat_map.get(source.id, 0)

        if step < 40:
            reserve = max(1, int(source.production * 0.8))
        elif step < 80:
            reserve = max(2, int(source.production * 1.2))
        elif step < 120:
            reserve = max(4, int(source.production * 2.0))
        elif far_ahead and step > 300:
            reserve = max(15, int(source.production * 6.0))
        elif ahead and step > 300:
            reserve = max(10, int(source.production * 4.0))
        else:
            reserve = max(5, int(source.production * 2.5))

        reserve += int(total_pressure * 0.95)

        if step > GAME_LENGTH - 30 and ahead:
            reserve = int(source.ships)

        available = int(source.ships) - reserve
        if my_incoming.get(source.id, 0) > 0:
            available -= min(available, my_incoming[source.id] // 4)
        if available <= 0:
            continue

        launches = 0
        max_launches = 2 if step < 100 else 1
        if far_ahead and step > 400:
            max_launches = 0

        while available > 0 and launches < max_launches:
            open_targets = [t for t in all_targets if t.id not in claimed]
            if not open_targets:
                break

            enemy_targets = [t for t in open_targets if t.owner not in (-1, player)]
            focus_targets = [t for t in enemy_targets if t.owner == focus_enemy] if focus_enemy else []
            neutral_targets = [t for t in open_targets if t.owner == -1]
            static_neutrals = [t for t in neutral_targets if not is_orbiting(t)]
            comet_targets = [t for t in open_targets if t.id in comet_ids]

            if step < 40:
                if static_neutrals:
                    pool = static_neutrals
                elif neutral_targets:
                    pool = neutral_targets
                else:
                    pool = open_targets
            elif step < 60:
                if neutral_targets:
                    pool = neutral_targets
                elif static_neutrals:
                    pool = static_neutrals
                else:
                    pool = open_targets
            elif step < 80:
                if enemy_targets:
                    pool = enemy_targets
                elif static_neutrals:
                    pool = static_neutrals
                else:
                    pool = open_targets
            elif step < 150:
                valuable_comets = [c for c in comet_targets if comet_remaining_turns(c.id, comets_data) > 15]
                if valuable_comets:
                    pool = valuable_comets
                elif focus_targets:
                    pool = focus_targets
                elif enemy_targets:
                    pool = enemy_targets
                elif static_neutrals:
                    pool = static_neutrals
                else:
                    pool = open_targets
            elif step < 350:
                if focus_targets:
                    pool = focus_targets
                elif enemy_targets:
                    pool = enemy_targets
                else:
                    pool = open_targets
            else:
                if far_ahead:
                    pool = []
                elif enemy_targets and not ahead:
                    pool = enemy_targets
                else:
                    pool = open_targets

            if not pool:
                break

            best = None
            best_score = -1e9
            best_ships = 0

            for target in pool:
                if target.id == source.id:
                    continue

                rough_d = dist((source.x, source.y), (target.x, target.y))

                if step < 60:
                    commit_ratio = 0.55
                elif step < 80:
                    commit_ratio = 0.50
                elif step < 200:
                    commit_ratio = 0.45
                elif far_ahead and step > 300:
                    commit_ratio = 0.20
                elif ahead and step > 350:
                    commit_ratio = 0.25
                else:
                    commit_ratio = 0.50

                if target.production >= 4:
                    commit_ratio = max(commit_ratio, 0.55)
                if target.owner not in (-1, player):
                    commit_ratio = max(commit_ratio, 0.60)
                if step > 400:
                    commit_ratio = max(commit_ratio, 0.65)

                is_comet = target.id in comet_ids
                if is_comet:
                    rem = comet_remaining_turns(target.id, comets_data)
                    if rem < 8:
                        commit_ratio = min(commit_ratio, 0.30)
                    else:
                        commit_ratio = max(commit_ratio, 0.50)

                planned = max(1, int(available * commit_ratio))
                if step < 70 and available >= 20 and rough_d >= 12:
                    planned = max(planned, 18)

                rough_travel = rough_d / fleet_speed(min(available, planned))
                need = capture_need(target, target.owner not in (-1, player), rough_travel)
                if need > available:
                    continue
                committed = min(available, max(need, planned))

                if step < 50 and target.owner == -1 and rough_d >= 18 and committed < 12:
                    continue

                sc = score_target(
                    source, target, player, step, initial_by_id, angular_velocity,
                    comet_ids, committed, comets_data, focus_enemy
                )
                if sc is None:
                    continue

                if step < 100 and target.owner == -1:
                    sc += 25.0

                speed_bonus = (fleet_speed(committed) - fleet_speed(need)) * 2.0
                sc += speed_bonus

                if sc > best_score:
                    best_score = sc
                    best = target
                    best_ships = committed

            if best is None:
                break

            aim = planet_position_at(
                best, initial_by_id, angular_velocity,
                step + int(round(dist((source.x, source.y), (best.x, best.y)) / fleet_speed(best_ships))),
                comet_ids,
            )
            angle = math.atan2(aim[1] - source.y, aim[0] - source.x)
            actual = max(1, min(best_ships, int(source.ships) - sum(m[2] for m in moves if m[0] == source.id)))
            if actual <= 0:
                break
            moves.append([source.id, angle, actual])
            claimed.add(best.id)
            available -= actual
            launches += 1

    return moves