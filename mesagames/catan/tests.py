from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from rest_framework import status
from catan.models import *
import json
from django.contrib.auth.models import User


class BoardTestCase(APITestCase):
    expected = [
        {
            "position": {"level": 1, "index": 1},
            "token": 1,
            "terrain": "wool"
        },
        {
            "position": {"level": 1, "index": 2},
            "token": 2,
            "terrain": "ore"
        },
        {
            "position": {"level": 2, "index": 2},
            "token": 3,
            "terrain": "desert"
        }
    ]

    expected_board = [{"id": 1, "name": "ingenieria"}]

    def test_game_board_returns_correct_hexes(self):
        board = Board.objects.create(name="board")
        game = Game.objects.create(board=board)

        for hexagon in self.expected:
            Hexagon.objects.create(
                board=board,
                pos_level=hexagon["position"]["level"],
                pos_index=hexagon["position"]["index"],
                resource=(hexagon["terrain"] if hexagon["terrain"] != "desert" else None),
                token=hexagon["token"])

        response = self.client.get("/games/" + str(game.id) + "/board")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"hexes": self.expected})

        response = self.client.get("/games/-1/board")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        hexagon = Hexagon.objects.create(board=board, pos_level=2, pos_index=0, token=9)
        self.assertEqual(str(hexagon), "Hexagon (2, 0)")
        self.assertEqual(str(board), "board")

    def test_get_boards(self):
        board = Board.objects.create(name="ingenieria")
        user = User.objects.create()

        self.client.force_authenticate(user=user)
        response = self.client.get("/boards")

        self.assertEqual(response.data, self.expected_board)


class GameTest(APITestCase):
    expected_games = [{
        "id": 1,
        "name": "ingenieria",
        "in_turn": "diego"
    }]

    def test_victory_points(self):
        board = Board.objects.create(name="ingenieria")
        user = User.objects.create(username="diego")
        game = Game.objects.create(board=board, name="ingenieria")
        player_1 = Player.objects.create(game=game, user=user)
        player_2 = Player.objects.create(game=game, user=user)

        SettlementBuilding.objects.create(owner=player_1, game=game, pos_index=0, pos_level=0)

        SettlementBuilding.objects.create(owner=player_2, game=game, pos_index=0, pos_level=0)
        SettlementBuilding.objects.create(owner=player_2, game=game, pos_index=0, pos_level=0)

        self.assertEquals(game.calculate_points(player_1), 1)
        self.assertEquals(game.calculate_points(player_2), 2)

    def test_get_games(self):
        board = Board.objects.create(name="ingenieria")
        user = User.objects.create(username="diego")
        game = Game.objects.create(board=board, name="ingenieria")
        player = Player.objects.create(game=game, user=user)
        game.current_turn = player
        game.save()

        self.client.force_authenticate(user=user)
        response = self.client.get("/games/")

        self.assertEquals(response.data, self.expected_games)

    def test_distribute_resources(self):
        board = Board.objects.create(name="ingenieria")
        user = User.objects.create(username="diego")
        game = Game.objects.create(board=board, name="ingenieria")
        player = Player.objects.create(game=game, user=user)
        ResourcesCard.objects.create(game=game, resource='brick')
        ResourcesCard.objects.create(game=game, resource='wool')
        ResourcesCard.objects.create(game=game, resource='wool')
        Hexagon.objects.create(board=board, pos_level=2, pos_index=8, resource='brick', token=4)
        Hexagon.objects.create(board=board, pos_level=2, pos_index=2, resource='wool', token=5)
        SettlementBuilding.objects.create(owner=player, game=game, pos_level=2, pos_index=20)
        CityBuilding.objects.create(owner=player, game=game, pos_level=2, pos_index=5)

        game.distribute_resources(4)
        res = ResourcesCard.count_player_all(player)
        self.assertEqual(1, res)
        game.distribute_resources(5)
        res = ResourcesCard.count_player_all(player)
        self.assertEqual(3, res)


class GameStatusTestCase(APITestCase):
    def make_player_obj(self, game, username, colour, resources, cards):
        user = User.objects.create_user(username)
        player = Player.objects.create(user=user, game=game, colour=colour)
        for _ in range(resources):
            ResourcesCard.objects.create(game=game, player=player, resource="ore")
        for _ in range(cards):
            DevelopmentCard.objects.create(game=game, player=player, card="knight")
        return player

    def make_player_json(self, username, colour, resources, cards):
        return {
            "username": username,
            "colour": colour,
            "settlements": [],
            "cities": [],
            "roads": [],
            "resources_cards": resources,
            "development_cards": cards,
            "last_gained": [],
            "victory_points": 0
        }

    def expected(self):
        return {
            "players": [
                self.make_player_json("pepe", "red", 1, 0),
                self.make_player_json("juan", "blue", 0, 1),
            ],
            "robber": {"level": 0, "index": 0},
            "current_turn": {
                "user": "pepe",
                "dice": [0, 0]
            },
            "winner": None
        }

    def compare_player_list(self, given, expected):
        self.maxDiff = None
        self.assertEqual(len(given), len(expected), "length mismatch")
        for i in range(0, len(given)):
            self.assertEqual(given[i], expected[i], "mismatch at element " + str(i))

    def test_game_status_returns_correct_response(self):
        board = Board.objects.create(name="board")
        game = Game.objects.create(id=103, board=board)
        pepe = self.make_player_obj(game, "pepe", "red", 1, 0)
        juan = self.make_player_obj(game, "juan", "blue", 0, 1)
        game.current_turn = pepe
        game.save()

        response = self.client.get("/games/-1/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get("/games/" + str(game.id) + "/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected = self.expected()
        given = response.data
        self.compare_player_list(given["players"], expected["players"])
        self.assertEqual(given, expected, "full match failed")
        self.assertEqual(str(game), "Game (103)")


class RoomTestCase(APITestCase):
    expected_get = [
        {
            "id": 1,
            "name": "foo",
            "owner": "pepe",
            "players": ["pepe"],
            "max_players": 4,
            "game_has_started": False,
            "game_id": None,
        },
        {
            "id": 2,
            "name": "bar",
            "owner": "josé",
            "players": ["josé", "marianela", "hector"],
            "max_players": 4,
            "game_has_started": False,
            "game_id": None,
        }
    ]
    expected_get_post = {
            "id": 1,
            "name": "123",
            "owner": "diego",
            "players": ["diego"],
            "max_players": 4,
            "game_has_started": False,
            "game_id": None,
        }
    expected_start_game = {
        "current_turn": {
            "dice": [
                3,
                1
            ],
            "user": "diego"
        },
        "players": [
            {
                "cities": [],
                "colour": "red",
                "development_cards": 0,
                "last_gained": [],
                "resources_cards": 0,
                "roads": [({'index': 2, 'level': 1}, {'index': 3, 'level': 1}),
                          ({'index': 9, 'level': 1}, {'index': 10, 'level': 1})],
                "settlements": [{'index': 2, 'level': 1},
                                {'index': 9, 'level': 1}],
                "username": "diego",
                "victory_points": 2,
            },
            {
                "cities": [],
                "colour": "green",
                "development_cards": 0,
                "last_gained": [],
                "resources_cards": 0,
                "roads": [({'index': 5, 'level': 1}, {'index': 6, 'level': 1}),
                          ({'index': 15, 'level': 1}, {'index': 16, 'level': 1})],
                "settlements": [{'index': 5, 'level': 1},
                                {'index': 15, 'level': 1}],
                "username": "laura",
                "victory_points": 2,
            },
            {
                "cities": [],
                "colour": "yellow",
                "development_cards": 0,
                "last_gained": [],
                "resources_cards": 0,
                "roads": [({'index': 7, 'level': 1}, {'index': 8, 'level': 1}),
                          ({'index': 11, 'level': 1}, {'index': 12, 'level': 1})],
                "settlements": [{'index': 7, 'level': 1},
                                {'index': 11, 'level': 1}],
                "username": "chun",
                "victory_points": 2,
            }
        ],
        "robber": {
            "index": 0,
            "level": 0
        },
        "winner": None,
    }

    def setUp(self):
        self.board = Board.objects.create(name="asd")

    def test_list_rooms(self):
        for room in self.expected_get:
            new_room = Room.objects.create(
                name=room["name"],
                owner=User.objects.create(username=room["owner"]),
                max_players=room["max_players"],
                game_has_started=False,
                board_id=self.board
            )
            for user in room["players"]:
                (new_user, _) = User.objects.get_or_create(username=user)
                new_room.players.add(new_user)

        self.client.force_authenticate(user=new_user)
        response = self.client.get("/rooms/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content.decode("utf-8")), self.expected_get)

    def test_join_room(self):
        user1 = User.objects.create(username="Hermenegildo")
        room = Room.objects.create(
                        name="New room",
                        owner=user1,
                        game_has_started=False,
                        board_id=self.board)
        room.players.add(user1)

        user2 = User.objects.create_user(username="Teodomira")
        self.client.force_authenticate(user=user2)
        response = self.client.put("/rooms/" + str(room.id) + "/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, None)
        self.assertEqual(room.players.get(id=2), user2)
        self.assertEqual(str(room), "New room")

    def test_create_room(self):
        user1 = User.objects.create(username="diego")

        self.client.force_authenticate(user=user1)
        response = self.client.post("/rooms/", {"name": "123", "board_id": 1}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_get_post)

    def test_delete_room(self):
        user = User.objects.create(username="diego")
        self.client.force_authenticate(user=user)

        response = self.client.post("/rooms/", {"name": "123", "board_id": 1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Room.objects.all().count(), 1)
        self.assertEqual(response.data['id'], 1)

        response = self.client.delete("/rooms/1/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Room.objects.all().count(), 0)

    def test_get_room(self):
        user1 = User.objects.create(username="diego")
        room = Room.objects.create(
                        name="123",
                        owner=user1,
                        board_id=self.board)
        room.players.add(user1)

        self.client.force_authenticate(user=user1)
        response = self.client.get("/rooms/" + str(room.id) + "/")

        self.assertEqual(room.players.get(id=1), user1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_get_post)

    def test_start_game(self):
        user1 = User.objects.create(username="diego")
        user2 = User.objects.create(username="laura")
        user3 = User.objects.create(username="chun")
        room12 = Room.objects.create(
                        name="ingenieria",
                        owner=user1,
                        board_id=self.board)
        room12.players.add(user1)
        room12.players.add(user2)
        room12.players.add(user3)

        self.client.force_authenticate(user=user1)
        response = self.client.patch("/rooms/" + str(room12.id) + "/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, None)

        response_get = self.client.get("/rooms/" + str(room12.id) + "/")
        game_id = response_get.data["game_id"]
        game = Game.objects.get(pk=game_id)
        self.expected_start_game["current_turn"]["dice"][0] = game.current_dices_1
        self.expected_start_game["current_turn"]["dice"][1] = game.current_dices_2

        response_game = self.client.get("/games/" + str(game_id) + "/")
        self.maxDiff = None
        self.assertEqual(response_game.data, self.expected_start_game)


class ResourceAndCardsTest(APITestCase):
    expected = {
        "cards": ["monopoly"],
        "resources": ["brick"]
    }

    def setUp(self):
        self.board = Board.objects.create(name="board")
        self.game = Game.objects.create(board=self.board)
        self.user = User.objects.create(username="pepe")

    def test_game_resources_and_cards(self):
        player = Player.objects.create(user=self.user, game=self.game)
        res = ResourcesCard.objects.create(game=self.game, player=player, resource="brick")
        card = DevelopmentCard.objects.create(game=self.game, player=player, card="monopoly")

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/games/" + str(self.game.id) + "/player")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected)
        self.assertEqual(str(res), "brick (pepe (in Game (1)))")
        self.assertEqual(str(card), "monopoly (pepe (in Game (1)))")


class GameTestCase(APITestCase):
    def test_roll_dices(self):
        game = Game.objects.create(
            board=Board.objects.create(name="board"),
            current_dices_1=1,
            current_dices_2=2)
        game.reset_dices()
        self.assertFalse(game.are_dices_rolled(), "dices should not be rolled when resetted")
        game.roll_dices()
        self.assertTrue(game.are_dices_rolled(), "dices should be rolled")
        self.assertIn(game.dices_sum(), range(2, 12+1), "dices sum should be between 2 and 12")

    def test_advance_turn(self):
        game = Game.objects.create(board=Board.objects.create(name="board"))
        game.advance_turn()
        p1 = Player.objects.create(game=game, user=User.objects.create_user("p1"))
        p2 = Player.objects.create(game=game, user=User.objects.create_user("p2"))
        game.current_turn = p1
        game.save()
        game.advance_turn()
        self.assertEqual(game.current_turn, p2, "when advancing 1 turn, p2 should have the turn")
        game.advance_turn()
        self.assertEqual(game.current_turn, p1, "when advancing 2 turns, p1 should have the turn")

    def test_robber_activate(self):
        board = Board.objects.create()
        game = Game.objects.create(board=board)

        user1 = User.objects.create(username="user1")
        player1 = Player.objects.create(game=game, user=user1)
        cards1 = ["brick", "brick", "grain"]
        for res in cards1:
            ResourcesCard.objects.create(game=game, player=player1, resource=res)

        user2 = User.objects.create(username="user2")
        player2 = Player.objects.create(game=game, user=user2)
        cards2 = ["brick", "grain", "grain", "wool", "ore", "ore", "lumber"]
        for res in cards2:
            ResourcesCard.objects.create(game=game, player=player2, resource=res)

        user3 = User.objects.create(username="user3")
        player3 = Player.objects.create(game=game, user=user3)
        cards3 = ["brick", "brick", "grain", "wool", "wool", "ore", "lumber", "lumber", "lumber"]
        for res in cards3:
            ResourcesCard.objects.create(game=game, player=player3, resource=res)

        game.robber_activate()
        self.assertEqual(
            ResourcesCard.count_player_all(player1), len(cards1),
            "1 not affected by the robber"
        )
        self.assertEqual(
            ResourcesCard.count_player_all(player2), len(cards2),
            "2 not affected by the robber"
        )
        self.assertEqual(
            ResourcesCard.count_player_all(player3), len(cards3) // 2 + len(cards3) % 2,
            "3 has been affected by the robber"
        )


class ResourcesCardTest(APITestCase):
    def setUp(self):
        self.game = Game.objects.create(board=Board.objects.create(name="board"))
        self.player = Player.objects.create(user=User.objects.create_user("user"), game=self.game)

    def spawn_resources(self, game, resource, amount, player=None):
        for _ in range(amount):
            ResourcesCard.objects.create(game=game, player=player, resource=resource)

    def test_owned_by_bank(self):
        res = ResourcesCard.objects.create(game=self.game)
        self.assertTrue(res.is_owned_by_bank())

    def test_count_all(self):
        game = self.game
        player = self.player
        self.spawn_resources(game, "wool", 4)
        self.spawn_resources(game, "ore", 3)
        self.assertEqual(ResourcesCard.count_bank(game, "wool"), 4, "bank has incorrect wool")
        self.assertEqual(ResourcesCard.count_bank(game, "ore"), 3, "bank has incorrect ore")

        self.spawn_resources(game, "wool", 1, player)
        self.spawn_resources(game, "ore", 2, player)
        self.assertEqual(ResourcesCard.count_player(player, "wool"), 1, "player has incorrect wool")
        self.assertEqual(ResourcesCard.count_player(player, "ore"), 2, "player has incorrect ore")

    def test_take(self):
        game = self.game
        player = self.player

        with self.assertRaises(ValueError):
            ResourcesCard.take(player, 'wool', 1)
        self.spawn_resources(game, "wool", 4)
        self.spawn_resources(game, "wool", 1, player)

        ResourcesCard.take(player, "wool", 1)
        self.assertEqual(ResourcesCard.count_bank(game, "wool"), 5, "bank has incorrect wool")
        self.assertEqual(ResourcesCard.count_player(player, "wool"), 0, "player has incorrect wool")

    def test_give(self):
        game = self.game
        player = self.player

        with self.assertRaises(ValueError):
            ResourcesCard.give(player, 'ore', 1)
        self.spawn_resources(game, "wool", 4)
        self.spawn_resources(game, "wool", 1, player)

        ResourcesCard.give(player, "wool", 4)
        self.assertEqual(ResourcesCard.count_bank(game, "wool"), 0, "bank has incorrect wool")
        self.assertEqual(ResourcesCard.count_player(player, "wool"), 5, "player has incorrect wool")


class UserTestCase(APITestCase):
    register_data = {
        "user": "user1",
        "pass": "12345678"
    }

    def test_register_new_user(self):
        self.assertTrue(
            User.objects.filter(username=self.register_data["user"]).count() == 0
        )
        response = self.client.post("/users/", data=self.register_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, None)
        self.assertTrue(
            User.objects.filter(username=self.register_data["user"]).count() == 1
        )

    def test_registered_user(self):
        User.objects.create(username=self.register_data["user"])
        self.assertTrue(
            User.objects.filter(username=self.register_data["user"]).count() == 1
        )
        response = self.client.post("/users/", data=self.register_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            User.objects.filter(username=self.register_data["user"]).count() == 1
        )
