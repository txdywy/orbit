import math

import main


def obs(planets, player=0, fleets=None, step=0):
    return {
        "player": player,
        "planets": planets,
        "fleets": fleets or [],
        "initial_planets": [p[:] for p in planets],
        "angular_velocity": 0.03,
        "comets": [],
        "comet_planet_ids": [],
        "step": step,
    }


def reset_agent_state():
    main._prev_step = -1


def test_segment_hits_sun_detects_blocked_route():
    assert main.segment_hits_sun(20, 50, 80, 50)
    assert not main.segment_hits_sun(20, 20, 30, 25)


def test_agent_returns_empty_without_owned_planets():
    reset_agent_state()
    observation = obs(
        [
            [0, -1, 20.0, 20.0, 2.0, 10, 4],
            [1, 1, 80.0, 80.0, 2.0, 10, 4],
        ]
    )

    assert main.agent(observation) == []


def test_agent_actions_are_well_formed_and_legal():
    reset_agent_state()
    observation = obs(
        [
            [0, 0, 20.0, 20.0, 2.0, 120, 4],
            [1, -1, 20.0, 90.0, 2.6, 8, 3],
            [2, -1, 90.0, 20.0, 2.6, 12, 5],
            [3, 1, 80.0, 80.0, 2.0, 50, 4],
        ],
        step=25,
    )

    moves = main.agent(observation)

    assert isinstance(moves, list)
    owned = {0: 120}
    spent = {}
    for move in moves:
        assert isinstance(move, list)
        assert len(move) == 3
        source_id, angle, ships = move
        assert source_id in owned
        assert isinstance(angle, float)
        assert -math.tau <= angle <= math.tau
        assert isinstance(ships, int)
        assert ships > 0
        spent[source_id] = spent.get(source_id, 0) + ships
        assert spent[source_id] <= owned[source_id]


def test_agent_cross_game_reset_does_not_suppress_new_game_actions():
    reset_agent_state()
    first_game = obs(
        [
            [0, 0, 20.0, 20.0, 2.0, 80, 4],
            [1, -1, 20.0, 90.0, 2.6, 8, 3],
        ],
        step=120,
    )
    second_game = obs(
        [
            [0, 0, 20.0, 20.0, 2.0, 80, 4],
            [1, -1, 20.0, 90.0, 2.6, 8, 3],
        ],
        step=0,
    )

    first_moves = main.agent(first_game)
    second_moves = main.agent(second_game)

    assert isinstance(first_moves, list)
    assert isinstance(second_moves, list)
