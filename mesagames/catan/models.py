import random
from django.contrib.auth.models import User
from django.db import models

RESOURCE_TYPES = (
    ('brick', 'Brick'),
    ('lumber', 'Lumber'),
    ('wool', 'Wool'),
    ('grain', 'Grain'),
    ('ore', 'Ore'),
)

CARD_TYPES = (
    ('road_building', 'Road Building'),
    ('knight', 'Knight'),
)


def is_valid_resource(resource):
    for r, _ in RESOURCE_TYPES:
        if r == resource:
            return True
    return False


def is_valid_level(level):
    return level in range(0, 3)


def vertex_count(level):
    return 6 * (1 + level * 2)


def hexagon_count(level):
    if level == 0:
        return 1
    else:
        return level * 6


def is_valid_vert_index(level, index):
    return index in range(0, vertex_count(level))


def is_valid_hex_index(level, index):
    return index in range(hexagon_count(level))


def next_neighbors(vertex):
    count = vertex_count(vertex[0])
    result = [
        (vertex[0], (vertex[1] + 1) % count),
        (vertex[0], (vertex[1] - 1) % count)
    ]
    return result


def get_vertex(pos_level, pos_index):
    vertexs = []
    if pos_level == 0:
        vertexs = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)]
    elif pos_level == 1:
        if pos_index == 0:
            vertexs = [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2), (1, 3)]
        elif pos_index == 1:
            vertexs = [(0, 1), (0, 2), (1, 3), (1, 4), (1, 5), (1, 6)]
        elif pos_index == 2:
            vertexs = [(0, 2), (0, 3), (1, 6), (1, 7), (1, 8), (1, 9)]
        elif pos_index == 3:
            vertexs = [(0, 3), (0, 4), (1, 9), (1, 10), (1, 11), (1, 12)]
        elif pos_index == 4:
            vertexs = [(0, 4), (0, 5), (1, 12), (1, 13), (1, 14), (1, 15)]
        elif pos_index == 5:
            vertexs = [(0, 0), (0, 5), (1, 0), (1, 15), (1, 16), (1, 17)]
    elif pos_level == 2:
        if pos_index == 0:
            vertexs = [(1, 0), (1, 1), (2, 0), (2, 1), (1, 17), (2, 29)]
        elif pos_index == 1:
            vertexs = [(1, 1), (1, 2), (2, 1), (2, 2), (2, 3), (2, 4)]
        elif pos_index == 2:
            vertexs = [(1, 2), (1, 3), (1, 4), (2, 4), (2, 5), (2, 6)]
        elif pos_index == 3:
            vertexs = [(1, 4), (1, 5), (2, 6), (2, 7), (2, 8), (2, 9)]
        elif pos_index == 4:
            vertexs = [(1, 5), (1, 6), (1, 7), (2, 9), (2, 10), (2, 11)]
        elif pos_index == 5:
            vertexs = [(1, 7), (1, 8), (2, 11), (2, 12), (2, 13), (2, 14)]
        elif pos_index == 6:
            vertexs = [(1, 8), (1, 9), (1, 10), (2, 14), (2, 15), (2, 16)]
        elif pos_index == 7:
            vertexs = [(1, 10), (1, 11), (2, 16), (2, 17), (2, 18), (2, 19)]
        elif pos_index == 8:
            vertexs = [(1, 11), (1, 12), (1, 13), (2, 19), (2, 20), (2, 21)]
        elif pos_index == 9:
            vertexs = [(1, 13), (1, 14), (2, 21), (2, 22), (2, 23), (2, 24)]
        elif pos_index == 10:
            vertexs = [(1, 14), (1, 15), (1, 16), (2, 24), (2, 25), (2, 26)]
        elif pos_index == 11:
            vertexs = [(1, 16), (1, 17), (2, 26), (2, 27), (2, 28), (2, 29)]
    return vertexs


def extern_neighbor(vertex):
    result = []

    level = vertex[0]
    index = vertex[1]

    if level == 0:
        result.append((1, index * 3))
    elif level == 1:
        if index % 3 == 0:
            result.append((0, index // 3))
        else:
            result.append((2, (index % 3)**2 + 5 * (index // 3)))
    else:
        if index % 5 == 1:
            result.append((1, 1 + 3 * (index // 5)))
        elif index % 5 == 4:
            result.append((1, 2 + 3 * (index // 5)))
    return result


def get_neighbors(vertex):
    return next_neighbors(vertex) + extern_neighbor(vertex)


def get_adjacent_players(game, hex_level, hex_index):
    result = []
    for v in get_vertex(hex_level, hex_index):
        city = CityBuilding.objects.filter(game=game, pos_level=v[0], pos_index=v[1])
        sett = SettlementBuilding.objects.filter(game=game, pos_level=v[0], pos_index=v[1])

        if city.count() == 1:
            owner = city[0].owner
            if owner not in result:
                result.append(owner)
        elif sett.count() == 1:
            owner = sett[0].owner
            if owner not in result:
                result.append(owner)
    return result


class Board(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class Hexagon(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE)
    pos_level = models.IntegerField()
    pos_index = models.IntegerField()
    resource = models.CharField(max_length=10, choices=RESOURCE_TYPES, blank=True, null=True)
    token = models.IntegerField()

    def __str__(self):
        return "Hexagon (" + str(self.pos_level) + ", " + str(self.pos_index) + ")"


class Game(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    robber_level = models.IntegerField(default=0)
    robber_index = models.IntegerField(default=0)
    current_dices_1 = models.IntegerField(default=0)
    current_dices_2 = models.IntegerField(default=0)
    current_turn = models.ForeignKey(
        "catan.Player",
        related_name="current_turn",
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    winner = models.ForeignKey(
        "catan.Player",
        related_name="winner",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    robber_moved = models.BooleanField(default=False)

    def calculate_points(self, player):
        setts = SettlementBuilding.objects.filter(game=self, owner=player).count()
        cities = CityBuilding.objects.filter(game=self, owner=player).count()
        return setts * 1 + cities * 2

    def get_winner_name_or_none(self):
        res = None
        if self.winner is not None:
            res = self.winner.user.username

        return res

    def try_set_to_winner(self, player):
        if self.calculate_points(player) >= 10:
            self.winner = player
            self.save()
            return True

        return False

    def reset_dices(self):
        self.current_dices_1 = 0
        self.current_dices_2 = 0
        self.save()

    def are_dices_rolled(self):
        return self.current_dices_1 != 0 and self.current_dices_2 != 0

    def roll_dices(self):
        self.current_dices_1 = random.randint(1, 6)
        self.current_dices_2 = random.randint(1, 6)
        self.save()

    def dices_sum(self):
        return self.current_dices_1 + self.current_dices_2

    def advance_turn(self):
        players = [p for p in Player.objects.filter(game=self.id)]
        if len(players) == 0:
            self.current_turn = None
        else:
            idx = players.index(self.current_turn)
            self.current_turn = players[(idx + 1) % len(players)]
        self.robber_moved = False
        self.save()

    def robber_activate(self):
        for player in Player.objects.filter(game=self):
            count = ResourcesCard.count_player_all(player)
            if count > 7:
                for _ in range(count // 2):
                    ResourcesCard.take_random(player)

    def move_robber(self, position):
        self.robber_level = position[0]
        self.robber_index = position[1]
        self.robber_moved = True
        self.save()

    def distribute_resources(self, dices):
        hexagons = Hexagon.objects.filter(board=self.board, token=dices)
        for hexagon in hexagons:
            if not (self.robber_level, self.robber_index) == (hexagon.pos_level, hexagon.pos_index):
                vertexs = get_vertex(hexagon.pos_level, hexagon.pos_index)
                for v in vertexs:
                    city = CityBuilding.objects.filter(
                                    game=self,
                                    pos_level=v[0],
                                    pos_index=v[1])
                    sett = SettlementBuilding.objects.filter(
                                    game=self,
                                    pos_level=v[0],
                                    pos_index=v[1])
                    if city.count() == 1:
                        ResourcesCard.give(city[0].owner, hexagon.resource, 2)
                    elif sett.count() == 1:
                        ResourcesCard.give(sett[0].owner, hexagon.resource, 1)

    def steal_resource(self, player, target):
        if target is None:
            possible_players = get_adjacent_players(self, self.robber_level, self.robber_index)
            if possible_players == []:
                return
            target = random.choice(possible_players)
        ResourcesCard.take_random(target, player)

    def __str__(self):
        return "Game (" + str(self.id) + ")"


class Room(models.Model):
    MAX_PLAYERS = ((3, 3), (4, 4))

    name = models.CharField(max_length=50)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='owner'
    )
    players = models.ManyToManyField(User, related_name='players')
    max_players = models.IntegerField(choices=MAX_PLAYERS, default=4)
    game_has_started = models.BooleanField(default=False)
    game_id = models.ForeignKey(
        Game,
        null=True,
        blank=True,
        on_delete=models.SET_NULL)
    board_id = models.ForeignKey(Board, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    colour = models.CharField(max_length=40)

    def __str__(self):
        return str(self.user) + " (in " + str(self.game) + ")"


class ResourcesCard(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    player = models.ForeignKey(
        Player,
        blank=True,
        null=True,  # if null, owned by bank
        on_delete=models.SET_NULL,
    )
    resource = models.CharField(max_length=10, choices=RESOURCE_TYPES)

    def is_owned_by_bank(self):
        return self.player is None

    @staticmethod
    def count_player(player, resource):
        """Returns the number of cards of such resource player has."""
        return ResourcesCard.objects \
                            .filter(game=player.game, player=player, resource=resource) \
                            .count()

    @staticmethod
    def count_player_all(player):
        """Returns the total number of resources the player has."""
        return ResourcesCard.objects \
                            .filter(game=player.game, player=player) \
                            .count()

    @staticmethod
    def count_bank(game, resource):
        """Returns the number of cards of such resource the bank has."""
        return ResourcesCard.objects \
                            .filter(game=game, player=None, resource=resource) \
                            .count()

    @staticmethod
    def take(player, resource, amount):
        """
        Transfer from player to bank amount cards of the given resource.
        Raises ValueError if the player does not have such amount.
        """
        if ResourcesCard.count_player(player, resource) < amount:
            raise ValueError("player does't own that amount of the resource")

        cards = ResourcesCard.objects.filter(player=player, resource=resource)[:amount]
        for card in cards:
            card.player = None
            card.save()

    @staticmethod
    def take_random(player, new_owner=None):
        """Take one random resource from player and give it to new_owner (if exists)."""
        if player is not new_owner:
            player_res = ResourcesCard.objects.filter(game=player.game, player=player)
            if player_res.count() > 0:
                card = random.choice(player_res)
                card.player = new_owner
                card.save()

    @staticmethod
    def give(player, resource, amount):
        """
        Transfer to player amount cards of the given resource.
        Raises ValueError if the bank does not have such amount.
        """
        if ResourcesCard.count_bank(player.game, resource) < amount:
            raise ValueError("bank does't own that amount of the resource")

        g = player.game
        cards = ResourcesCard.objects.filter(game=g, player=None, resource=resource)[:amount]

        for card in cards:
            card.player = player
            card.save()

    def __str__(self):
        return self.resource + " (" + str(self.player) + ")"


class DevelopmentCard(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    player = models.ForeignKey(
        Player,
        blank=True,
        null=True,  # if null, owned by bank
        on_delete=models.SET_NULL,
    )
    card = models.CharField(max_length=20, choices=CARD_TYPES)

    @staticmethod
    def count_player(player, card=None):
        """Returns the number of cards that player has."""
        if card is None:
            return DevelopmentCard.objects.filter(game=player.game, player=player).count()
        else:
            return DevelopmentCard.objects \
                                .filter(game=player.game, player=player, card=card) \
                                .count()

    @staticmethod
    def count_bank(game):
        """Returns the number of cards that the bank has."""
        return DevelopmentCard.objects.filter(game=game, player=None).count()

    @staticmethod
    def take(player, card_name, amount):
        """
        Transfer from player to bank amount cards of the given card.
        Raises ValueError if the player does not have such amount.
        """
        if DevelopmentCard.count_player(player, card_name) < amount:
            raise ValueError("player does't own that amount of the card")

        cards = DevelopmentCard.objects.filter(player=player, card=card_name)[:amount]
        for card in cards:
            card.player = None
            card.save()

    @staticmethod
    def give(player, amount):
        """
        Transfer development card to player.
        Raises ValueError if the bank does not have cards.
        """
        g = player.game
        if DevelopmentCard.count_bank(g) < amount:
            raise ValueError("bank does't have cards")

        Dcards = DevelopmentCard.objects.filter(game=g, player=None)[:amount]
        for card in Dcards:
            card.player = player
            card.save()

    def __str__(self):
        return self.card + " (" + str(self.player) + ")"


class SettlementBuilding(models.Model):
    owner = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    pos_level = models.IntegerField()
    pos_index = models.IntegerField()

    @staticmethod
    def has_resources_to_build(player):
        has_brick = ResourcesCard.count_player(player, 'brick') > 0
        has_lumber = ResourcesCard.count_player(player, 'lumber') > 0
        has_wool = ResourcesCard.count_player(player, 'wool') > 0
        has_grain = ResourcesCard.count_player(player, 'grain') > 0

        return has_brick and has_lumber and has_wool and has_grain

    @staticmethod
    def is_available_position(player, position):
        game_setts = [
            (s.pos_level, s.pos_index)
            for s in SettlementBuilding.objects.filter(game=player.game)
        ]
        has_neighbors = any(n in game_setts for n in get_neighbors(position))

        player_roads = [
            ((r.fst_pos_level, r.fst_pos_index), (r.snd_pos_level, r.snd_pos_index))
            for r in RoadBuilding.objects.filter(game=player.game, owner=player)
        ]
        from_road = any(position in road_pos for road_pos in player_roads)

        return position not in game_setts and not has_neighbors and from_road

    @staticmethod
    def take_resources(player):
        ResourcesCard.take(player, 'brick', 1)
        ResourcesCard.take(player, 'lumber', 1)
        ResourcesCard.take(player, 'wool', 1)
        ResourcesCard.take(player, 'grain', 1)

    def __str__(self):
        return "Settlement in " + str(self.game) + " at (" + \
            str(self.pos_level) + ", " + str(self.pos_index) + ")"


class CityBuilding(models.Model):
    owner = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    pos_level = models.IntegerField()
    pos_index = models.IntegerField()


class RoadBuilding(models.Model):
    owner = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    fst_pos_level = models.IntegerField()
    fst_pos_index = models.IntegerField()
    snd_pos_level = models.IntegerField()
    snd_pos_index = models.IntegerField()

    @staticmethod
    def has_resources_to_build(player):
        has_brick = ResourcesCard.count_player(player, 'brick') > 0
        has_lumber = ResourcesCard.count_player(player, 'lumber') > 0

        return has_brick and has_lumber

    @staticmethod
    def is_available_position(game, player, position):
        game_roads = [
            ((r.fst_pos_level, r.fst_pos_index), (r.snd_pos_level, r.snd_pos_index))
            for r in RoadBuilding.objects.filter(game=game)
        ]

        player_setts = [
            (s.pos_level, s.pos_index)
            for s in SettlementBuilding.objects.filter(game=game, owner=player)
        ]
        from_settlement = any(position[i] in player_setts for i in [0, 1])

        player_cities = [
            (c.pos_level, c.pos_index)
            for c in CityBuilding.objects.filter(game=game, owner=player)
        ]
        from_city = any(position[i] in player_cities for i in [0, 1])

        player_roads = [
            ((r.fst_pos_level, r.fst_pos_index), (r.snd_pos_level, r.snd_pos_index))
            for r in RoadBuilding.objects.filter(game=game, owner=player)
        ]
        from_road = any(
            position[i] in player_roads[j] for i in [0, 1] for j in range(len(player_roads))
        )

        return position not in game_roads and (from_settlement or from_city or from_road)

    @staticmethod
    def take_resources(player):
        ResourcesCard.take(player, 'brick', 1)
        ResourcesCard.take(player, 'lumber', 1)

    def __str__(self):
        return "Road in " + str(self.game) + " at ((" + \
            str(self.fst_pos_level) + ", " + str(self.fst_pos_index) + "), (" + \
            str(self.snd_pos_level) + ", " + str(self.snd_pos_index) + "))"
