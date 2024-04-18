from catan.models import *
from django.core.exceptions import ObjectDoesNotExist

ACTION_HANDLERS = dict()


def register_action_handler(action, handler):
    ACTION_HANDLERS[action] = handler


def check_structure(struct, conf):
    if isinstance(struct, dict) and isinstance(conf, dict):
        return all(k in conf and check_structure(struct[k], conf[k]) for k in struct)
    if isinstance(struct, list) and isinstance(conf, list):
        return all(check_structure(struct[0], c) for c in conf)
    elif isinstance(struct, type):
        return isinstance(conf, struct)
    else:
        return False


class BaseActionHandler:
    def is_payload_valid(self, payload):
        """Returns True only if the given payload is valid for this action."""
        return True

    def can_execute(self, player, game, payload):
        """Returns True only if the player may play this action on his turn."""
        return True

    def execute(self, player, game, payload):
        """Assuming can_execute and is_payload_valid, play this action."""


def get_available_settlement_positions(player):
    result = []
    for level in range(3):
        for index in range(vertex_count(level)):
            sett_pos = (level, index)
            can_construct_here = SettlementBuilding \
                .is_available_position(player, sett_pos)

            if can_construct_here:
                result.append(sett_pos)

    return result


def get_available_settlement_positions_pos(player):
    result = []
    for level in range(3):
        for index in range(vertex_count(level)):
            sett_pos = (level, index)
            can_construct_here = SettlementBuilding \
                .is_available_position(player, sett_pos)

            if can_construct_here:
                result.append({"level": sett_pos[0], "index": sett_pos[1]})

    return result


class BuildSettlementAction(BaseActionHandler):
    def is_payload_valid(self, payload):
        payload_format = {
            "level": int,
            "index": int
        }

        if not check_structure(payload_format, payload):
            return False

        valid_level = is_valid_level(payload["level"])
        valid_index = is_valid_vert_index(payload["level"], payload["index"])

        return valid_level and valid_index

    def can_execute(self, player, game, payload):
        enough_resources = SettlementBuilding.has_resources_to_build(player)
        free_slot = SettlementBuilding.objects.filter(owner=player).count() < 5
        available_position = SettlementBuilding.is_available_position(
            player, (payload["level"], payload["index"])
        )
        return enough_resources and free_slot and available_position

    def execute(self, player, game, payload):
        SettlementBuilding.take_resources(player)
        SettlementBuilding.objects.create(
            owner=player,
            game=game,
            pos_level=payload["level"],
            pos_index=payload["index"]
        )


class BuildRoadAction(BaseActionHandler):
    def is_payload_valid(self, payload):
        payload_format = [
            {"level": int, "index": int},
            {"level": int, "index": int}
        ]

        if not check_structure(payload_format, payload) or len(payload) != 2:
            return False

        fst_vertex = (payload[0]["level"], payload[0]["index"])
        snd_vertex = (payload[1]["level"], payload[1]["index"])

        valid_fst_level = is_valid_level(fst_vertex[0])
        valid_fst_index = is_valid_vert_index(fst_vertex[0], fst_vertex[1])
        valid_fst_vertex = valid_fst_level and valid_fst_index

        valid_snd_level = is_valid_level(snd_vertex[0])
        valid_snd_index = is_valid_vert_index(snd_vertex[0], snd_vertex[1])
        valid_snd_vertex = valid_snd_level and valid_snd_index

        return (
            valid_fst_vertex and valid_snd_vertex and
            snd_vertex in get_neighbors(fst_vertex)
        )

    def can_execute(self, player, game, payload):
        enough_resources = RoadBuilding.has_resources_to_build(player)
        free_slot = RoadBuilding.objects.filter(owner=player).count() < 15
        available_position = RoadBuilding.is_available_position(
            game, player,
            (
                (payload[0]["level"], payload[0]["index"]),
                (payload[1]["level"], payload[1]["index"])
            )
        )
        return enough_resources and free_slot and available_position

    def execute(self, player, game, payload):
        RoadBuilding.take_resources(player)
        RoadBuilding.objects.create(
            owner=player,
            game=game,
            fst_pos_level=payload[0]["level"],
            fst_pos_index=payload[0]["index"],
            snd_pos_level=payload[1]["level"],
            snd_pos_index=payload[1]["index"]
        )


class EndTurnAction(BaseActionHandler):
    def execute(self, player, game, payload):
        game.advance_turn()
        game.roll_dices()

        if game.dices_sum() == 7:
            game.robber_activate()
        else:
            game.distribute_resources(game.dices_sum())


class BankTradeAction(BaseActionHandler):
    def is_payload_valid(self, payload):
        payload_format = {
            "give": str,
            "receive": str
        }

        if not check_structure(payload_format, payload):
            return False

        if not is_valid_resource(payload["give"]) or not is_valid_resource(payload["receive"]):
            return False

        if payload["give"] == payload["receive"]:
            return False

        return True

    def can_execute(self, player, game, payload):
        enough_gives = ResourcesCard.count_player(player, payload["give"]) >= 4
        enough_receives = ResourcesCard.count_bank(game, payload["receive"]) >= 1
        return enough_gives and enough_receives

    def execute(self, player, game, payload):
        ResourcesCard.take(player, payload["give"], 4)
        ResourcesCard.give(player, payload["receive"], 1)
        return True


class BuyCardAction(BaseActionHandler):
    def is_payload_valid(self, payload):
        return True

    def can_execute(self, player, game, payload):
        has_ore = ResourcesCard.count_player(player, 'ore') >= 1
        has_wool = ResourcesCard.count_player(player, 'wool') >= 1
        has_grain = ResourcesCard.count_player(player, 'grain') >= 1
        return has_ore and has_wool and has_grain

    def execute(self, player, game, playload):
        ResourcesCard.take(player, 'ore', 1)
        ResourcesCard.take(player, 'wool', 1)
        ResourcesCard.take(player, 'grain', 1)
        DevelopmentCard.give(player, 1)
        return True


def parse_road_position_pair(payload):
    """
    Parses the given payload into a (ROAD_POSITION, ROAD_POSITION) tuple,
    raising a ValueError if any ROAD_POSITION parameter is out of bounds.
    """
    fst_vertex = (payload[0]["level"], payload[0]["index"])
    snd_vertex = (payload[1]["level"], payload[1]["index"])

    valid_fst_level = is_valid_level(fst_vertex[0])
    valid_fst_index = is_valid_vert_index(fst_vertex[0], fst_vertex[1])
    if not valid_fst_level or not valid_fst_index:
        raise ValueError("first road position is out of bounds")

    valid_snd_level = is_valid_level(snd_vertex[0])
    valid_snd_index = is_valid_vert_index(snd_vertex[0], snd_vertex[1])
    if not valid_snd_level or not valid_snd_index:
        raise ValueError("second road position is out of bounds")

    return (fst_vertex, snd_vertex)


def get_available_road_positions(player):
    result = []
    for level in range(3):
        for index in range(vertex_count(level)):
            v = (level, index)
            for n in get_neighbors(v):
                road_pos = (v, n)
                if road_pos in result or (n, v) in result:
                    continue

                can_construct_here = RoadBuilding.is_available_position(
                    player.game, player, road_pos)
                if can_construct_here:
                    result.append(road_pos)

    return result


def get_available_road_positions_pos(player):
    result = []
    for ps in get_available_road_positions(player):
        r2 = []
        for p in ps:
            r2.append({"level": p[0], "index": p[1]})

        result.append(r2)

    return result


class PlayBuildRoadCardAction(BaseActionHandler):
    def is_payload_valid(self, payload):
        payload_format = [
            [
                {"level": int, "index": int},
                {"level": int, "index": int}
            ]
        ]

        if not check_structure(payload_format, payload) or len(payload) != 2:
            return False

        if len(payload[0]) != 2 or len(payload[1]) != 2:
            return False

        try:
            parse_road_position_pair(payload[0])
            parse_road_position_pair(payload[1])
        except ValueError:
            return False

        return True

    def cmp_roads(self, r1, r2):
        if (r1[0] == r2[0] and r1[1] == r2[1]):
            return True

        if (r1[0] == r2[1] and r1[1] == r2[0]):  # orden invertido
            return True

        return False

    def is_road_in_roads(self, road, roadlist):
        for r in roadlist:
            if self.cmp_roads(r, road):
                return True

        return False

    def can_execute(self, player, game, payload):
        road_pos_0 = parse_road_position_pair(payload[0])
        road_pos_1 = parse_road_position_pair(payload[1])
        available = get_available_road_positions(player)
        has_the_card = DevelopmentCard.count_player(player, 'road_building') >= 1
        road_1_valid = self.is_road_in_roads(road_pos_0, available)
        road_2_valid = self.is_road_in_roads(road_pos_1, available)

        if self.cmp_roads(road_pos_0, road_pos_1):
            return False

        return road_1_valid and road_2_valid and has_the_card

    def execute(self, player, game, payload):
        DevelopmentCard.take(player, 'road_building', 1)

        road_pos_0 = parse_road_position_pair(payload[0])
        road_pos_1 = parse_road_position_pair(payload[1])

        for vertex1, vertex2 in [road_pos_0, road_pos_1]:
            RoadBuilding.objects.create(
                owner=player,
                game=game,
                fst_pos_level=vertex1[0],
                fst_pos_index=vertex1[1],
                snd_pos_level=vertex2[0],
                snd_pos_index=vertex2[1],
            )


def get_available_robber_positions(player):
    result = []
    current = (player.game.robber_level, player.game.robber_index)

    for level in range(3):
        for index in range(hexagon_count(level)):
            h = (level, index)

            if h != current:
                result.append({"level": level, "index": index})

    return result


class MoveRobberAction(BaseActionHandler):
    def is_payload_valid(self, payload):
        payload_format = {
            "position": {
                "level": int,
                "index": int
            },
            "player": str
        }

        if not check_structure(payload_format, payload):
            return False
        new_pos = (payload["position"]["level"], payload["position"]["index"])
        valid_level = is_valid_level(new_pos[0])
        valid_index = is_valid_hex_index(new_pos[0], new_pos[1])

        return valid_level and valid_index

    def can_execute(self, player, game, payload):
        new_pos = (payload["position"]["level"], payload["position"]["index"])
        target_player = None

        valid_player = True
        if len(payload["player"]) != 0:
            try:
                target_user = User.objects.get(username=payload["player"])
                target_player = Player.objects.get(game=game, user=target_user)
                itself = player == target_player
                possible_players = get_adjacent_players(game, new_pos[0], new_pos[1])

                valid_player = not itself and target_player in possible_players
            except ObjectDoesNotExist:
                valid_player = False
        correct_dices_sum = game.dices_sum() == 7
        other_pos = new_pos != (game.robber_level, game.robber_index)
        moved = game.robber_moved

        return valid_player and correct_dices_sum and other_pos and not moved

    def execute(self, player, game, payload):
        new_pos = (payload["position"]["level"], payload["position"]["index"])
        game.move_robber(new_pos)

        target_player = None
        if len(payload["player"]) != 0:
            target_user = User.objects.get(username=payload["player"])
            target_player = Player.objects.get(game=game, user=target_user)
        game.steal_resource(player, target_player)


class PlayKnightAction(BaseActionHandler):
    def is_payload_valid(self, payload):
        payload_format = {
            "position": {
                "level": int,
                "index": int
            },
            "player": str
        }

        if not check_structure(payload_format, payload):
            return False
        new_pos = (payload["position"]["level"], payload["position"]["index"])
        valid_level = is_valid_level(new_pos[0])
        valid_index = is_valid_hex_index(new_pos[0], new_pos[1])

        return valid_level and valid_index

    def can_execute(self, player, game, payload):
        new_pos = (payload["position"]["level"], payload["position"]["index"])
        target_player = None

        valid_player = True
        if len(payload["player"]) != 0:
            try:
                target_user = User.objects.get(username=payload["player"])
                target_player = Player.objects.get(game=game, user=target_user)
                itself = player == target_player
                possible_players = get_adjacent_players(game, new_pos[0], new_pos[1])

                valid_player = not itself and target_player in possible_players
            except ObjectDoesNotExist:
                valid_player = False
        has_knight_card = DevelopmentCard.count_player(player, "knight") > 0
        other_pos = new_pos != (game.robber_level, game.robber_index)
        moved = game.robber_moved

        return valid_player and has_knight_card and other_pos and not moved

    def execute(self, player, game, payload):
        DevelopmentCard.take(player, 'knight', 1)

        new_pos = (payload["position"]["level"], payload["position"]["index"])
        game.move_robber(new_pos)

        target_player = None
        if len(payload["player"]) != 0:
            target_user = User.objects.get(username=payload["player"])
            target_player = Player.objects.get(game=game, user=target_user)
        game.steal_resource(player, target_player)


register_action_handler("build_settlement", BuildSettlementAction())
register_action_handler("build_road", BuildRoadAction())
register_action_handler("end_turn", EndTurnAction())
register_action_handler("bank_trade", BankTradeAction())
register_action_handler("buy_card", BuyCardAction())
register_action_handler("play_road_building_card", PlayBuildRoadCardAction())
register_action_handler("move_robber", MoveRobberAction())
register_action_handler("play_knight_card", PlayKnightAction())
