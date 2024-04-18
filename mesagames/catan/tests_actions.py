from rest_framework.test import APITestCase
from rest_framework import status

from catan.actions import *


class ActionHandlerTest(APITestCase):
    def setUp(self):
        board = Board.objects.create()
        self.game = Game.objects.create(board=board)

        user1 = User.objects.create(username="user1")
        self.player1 = Player.objects.create(game=self.game, user=user1)

        user2 = User.objects.create(username="user2")
        self.player2 = Player.objects.create(game=self.game, user=user2)

    def post_action(self, player, action, payload={}):
        self.client.force_authenticate(user=player.user)
        response = self.client.post(
            "/games/" + str(player.game.id) + "/player/actions",
            {"type": action, "payload": payload},
            format="json"
        )

        self.game = Game.objects.get(id=self.game.id)  # reload in case the post mutated game
        return response.status_code

    def test_check_structure(self):
        self.assertFalse(check_structure(["foo"], ["bar"]), "invalid structure")

    def test_player_not_in_game(self):
        user = User.objects.create(username="new_user")

        self.client.force_authenticate(user=user)
        response = self.client.post("/games/" + str(self.game.id) + "/player/actions")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, "player not in game")

    def test_invalid_action_and_payload(self):
        self.game.current_turn = self.player1
        self.game.save()

        code = self.post_action(self.player1, "bank_trade")
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST, "no payload given")

        payload = {"give": "wool", "receive": "grain"}
        code = self.post_action(self.player1, "asd", payload)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST, "action 'asd' dont exist")

    def test_end_turn_advances_turn(self):
        code = self.post_action(self.player1, "end_turn")
        self.assertEqual(code, status.HTTP_401_UNAUTHORIZED, "be 401 when not in turn")

        self.game.current_turn = self.player1
        self.game.save()
        code = self.post_action(self.player1, "end_turn")
        self.assertEqual(code, status.HTTP_200_OK, "return 200 when p1 in turn")
        self.assertEqual(self.game.current_turn, self.player2, "advance the turn to p2")

        code = self.post_action(self.player2, "end_turn")
        self.assertEqual(code, status.HTTP_200_OK, "return 200 when p2 in turn")
        self.assertEqual(self.game.current_turn, self.player1, "advance the turn again to p1")


class BankTradeActionTest(APITestCase):
    def setUp(self):
        self.subject = BankTradeAction()

        board = Board.objects.create()
        self.game = Game.objects.create(board=board)

        user = User.objects.create()
        self.player = Player.objects.create(game=self.game, user=user)

        ResourcesCard.objects.create(game=self.game, player=None, resource="ore")

    def test_payload_valid(self):
        self.assertTrue(self.subject.is_payload_valid({
            "give": "wool",
            "receive": "ore"
        }), "payload fine")
        self.assertFalse(self.subject.is_payload_valid({
            "give": "ore",
            "receive": "ore"
        }), "payload without sense")
        self.assertFalse(self.subject.is_payload_valid({
            "give": "wool"
        }), "payload incomplete")
        self.assertFalse(self.subject.is_payload_valid({
            "give": "brick",
            "receive": "not_a_resource"
        }), "invalid resource")
        self.assertFalse(self.subject.is_payload_valid({
            "give": "not_a_resource",
            "receive": 5
        }), "invalid resource and invalid format")

    def test_execute_passes(self):
        for _ in range(4):
            ResourcesCard.objects.create(game=self.game, player=self.player, resource="wool")

        payload = {
            "give": "wool",
            "receive": "ore"
        }
        self.assertTrue(
            self.subject.can_execute(self.player, self.game, payload),
            "can execute"
        )
        self.subject.execute(self.player, self.game, payload)
        self.assertEqual(ResourcesCard.count_bank(self.game, "wool"), 4, "bank count")
        self.assertEqual(ResourcesCard.count_player(self.player, "ore"), 1, "player count")

    def test_execute_fail(self):
        for _ in range(3):  # 3, not 4.
            ResourcesCard.objects.create(game=self.game, player=self.player, resource="wool")

        payload = {
            "give": "wool",
            "receive": "ore"
        }
        self.assertFalse(self.subject.can_execute(self.player, self.game, payload))


class BuildSettlementActionTest(APITestCase):
    def setUp(self):
        self.subject = BuildSettlementAction()

        board = Board.objects.create()
        self.game = Game.objects.create(board=board)

        user = User.objects.create()
        self.player = Player.objects.create(game=self.game, user=user)

    def test_payload_valid(self):
        self.assertFalse(self.subject.is_payload_valid(
            {"level": 0}
        ), "payload incomplete")
        self.assertFalse(self.subject.is_payload_valid(
            {"foo": "some", "bar": (1, True)}
        ), "invalid format")
        self.assertFalse(self.subject.is_payload_valid(
            {"level": 3, "index": 0}
        ), "invalid level")
        self.assertFalse(self.subject.is_payload_valid(
            {"level": 1, "index": 18}
        ), "invalid index for level")
        self.assertTrue(self.subject.is_payload_valid(
            {"level": 2, "index": 1}
        ), "payload fine")

    def test_execute_passes(self):
        resources = ["brick", "lumber", "wool", "grain"]
        for res in resources:
            ResourcesCard.objects.create(game=self.game, player=self.player, resource=res)

        RoadBuilding.objects.create(
            owner=self.player,
            game=self.game,
            fst_pos_level=1,
            fst_pos_index=3,
            snd_pos_level=1,
            snd_pos_index=2
        )

        payload = {"level": 1, "index": 3}
        self.assertTrue(self.subject.can_execute(self.player, self.game, payload), "can execute")
        self.subject.execute(self.player, self.game, payload)

        for res in resources:
            self.assertEqual(ResourcesCard.count_player(self.player, res), 0, "gave " + res)
        self.assertIn(
            (payload["level"], payload["index"]),
            [(s.pos_level, s.pos_index) for s in SettlementBuilding.objects.filter(game=self.game)],
            "settlement created"
        )
        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload),
            "cannot execute"
        )

    def test_execute_fail(self):
        resources = ["brick", "lumber", "wool"]
        for res in resources:
            ResourcesCard.objects.create(game=self.game, player=self.player, resource=res)

        payload = {"level": 2, "index": 11}
        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload),
            "not enough resources"
        )

        ResourcesCard.objects.create(game=self.game, player=self.player, resource="grain")
        sett = SettlementBuilding.objects \
            .create(game=self.game, owner=self.player, pos_level=2, pos_index=11)

        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload),
            "occupied position"
        )
        self.assertEqual(str(sett), "Settlement in Game (1) at (2, 11)", "string match")

        payload = {"level": 1, "index": 7}
        self.assertFalse(self.subject.can_execute(self.player, self.game, payload), "has neighbor")


class BuildRoadActionTest(APITestCase):
    def setUp(self):
        self.subject = BuildRoadAction()

        board = Board.objects.create()
        self.game = Game.objects.create(board=board)

        user = User.objects.create()
        self.player = Player.objects.create(game=self.game, user=user)

        self.resources = ["brick", "lumber"]
        for res in self.resources:
            ResourcesCard.objects.create(game=self.game, player=self.player, resource=res)

    def test_payload_valid(self):
        self.assertFalse(self.subject.is_payload_valid(
            [{"level": 2, "index": 0}]
        ), "payload incomplete")
        self.assertFalse(self.subject.is_payload_valid(
            {"foo": 1, "bar": 2}
        ), "invalid format")
        self.assertFalse(self.subject.is_payload_valid(
            [{"level": 5, "index": 0}, {"level": 1, "index": 15}]
        ), "invalid level")
        self.assertFalse(self.subject.is_payload_valid(
            [{"level": 1, "index": 15}, {"level": 2, "index": 156}]
        ), "invalid index for level")
        self.assertTrue(self.subject.is_payload_valid(
            [{"level": 2, "index": 9}, {"level": 1, "index": 5}]
        ), "payload fine")

    def test_execute_passes(self):
        SettlementBuilding.objects.create(
            owner=self.player,
            game=self.game,
            pos_level=1,
            pos_index=3
        )

        payload = [{"level": 1, "index": 3}, {"level": 1, "index": 4}]
        self.assertTrue(self.subject.can_execute(self.player, self.game, payload), "can execute")
        self.subject.execute(self.player, self.game, payload)

        for res in self.resources:
            self.assertEqual(ResourcesCard.count_player(self.player, res), 0, "gave " + res)
        self.assertIn(
            (
                (payload[0]["level"], payload[0]["index"]),
                (payload[1]["level"], payload[1]["index"])
            ),
            [
                ((r.fst_pos_level, r.fst_pos_index), (r.snd_pos_level, r.snd_pos_index))
                for r in RoadBuilding.objects.filter(game=self.game, owner=self.player)
            ],
            "road created"
        )
        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload),
            "cannot execute"
        )

    def test_execute_fail(self):
        payload = [{"level": 2, "index": 11}, {"level": 2, "index": 10}]
        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload),
            "no own buildings nearby"
        )

        RoadBuilding.objects.create(
            owner=self.player,
            game=self.game,
            fst_pos_level=1,
            fst_pos_index=7,
            snd_pos_level=2,
            snd_pos_index=11
        )

        r = ResourcesCard.objects.get(resource="brick")
        r.player = None
        r.save()
        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload),
            "not enough resources"
        )

        r.player = self.player
        r.save()
        road = RoadBuilding.objects.create(
            owner=self.player,
            game=self.game,
            fst_pos_level=payload[0]["level"],
            fst_pos_index=payload[0]["index"],
            snd_pos_level=payload[1]["level"],
            snd_pos_index=payload[1]["index"]
        )

        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload),
            "occupied position"
        )
        self.assertEqual(str(road), "Road in Game (1) at ((2, 11), (2, 10))", "string match")


class BuyCardActionTest(APITestCase):
    def setUp(self):
        self.subject = BuyCardAction()

        board = Board.objects.create()
        self.game = Game.objects.create(board=board)

        user = User.objects.create(username="user")
        self.player = Player.objects.create(game=self.game, user=user)

    def test_payload_valid(self):
        self.assertTrue(self.subject.is_payload_valid({}), "payload true")

    def test_execute_passes(self):
        resources = ["ore", "grain", "wool"]
        for res in resources:
            ResourcesCard.objects.create(game=self.game, player=self.player, resource=res)

        DevelopmentCard.objects.create(
                                    game=self.game,
                                    player=None,
                                    card=random.choice(CARD_TYPES))

        payload = {}
        self.assertTrue(
            self.subject.can_execute(self.player, self.game, payload),
            "can execute"
        )
        self.subject.execute(self.player, self.game, payload)
        self.assertEqual(DevelopmentCard.count_player(self.player), 1, "player count")

    def test_execute_fail(self):
        ResourcesCard.objects.create(game=self.game, player=None, resource="ore")
        ResourcesCard.objects.create(game=self.game, player=self.player, resource="brick")

        DevelopmentCard.objects.create(game=self.game, player=None, card='monopoly')

        payload = {"level": 2, "index": 11}
        self.assertFalse(self.subject.can_execute(self.player, self.game, payload))


class PlayBuildRoadCardActionTest(APITestCase):
    def setUp(self):
        self.subject = PlayBuildRoadCardAction()

        board = Board.objects.create()
        self.game = Game.objects.create(board=board)

        user = User.objects.create(username="user")
        self.player = Player.objects.create(game=self.game, user=user)

        SettlementBuilding.objects.create(
            owner=self.player,
            game=self.game,
            pos_level=0,
            pos_index=5
        )

    def vertex_json(self, vertex):
        return {
            "level": vertex[0],
            "index": vertex[1],
        }

    def road_pos(self, vertex1, vertex2):
        return [
            {
                "level": vertex1[0],
                "index": vertex1[1],
            },
            {
                "level": vertex2[0],
                "index": vertex2[1],
            }
        ]

    def test_payload_valid(self):
        road1 = self.road_pos((0, 3), (1, 2))
        road2 = self.road_pos((1, 0), (2, 2))
        self.assertTrue(self.subject.is_payload_valid([road1, road2]), "two road positions")
        self.assertFalse(self.subject.is_payload_valid([[]]), "only one road position")

    def test_get_available_road_positions(self):
        expected = [((0, 0), (0, 5)), ((0, 4), (0, 5)), ((0, 5), (1, 15))]
        result = get_available_road_positions(self.player)
        self.assertEqual(result, expected)

    def test_execute(self):
        road1 = self.road_pos((0, 5), (0, 0))
        road2 = self.road_pos((0, 5), (0, 4))
        road1_bad = self.road_pos((1, 3), (1, 2))
        road2_bad = self.road_pos((2, 10), (2, 11))

        DevelopmentCard.objects.create(player=self.player, game=self.game, card='road_building')

        payload = [road1, road2]
        self.assertTrue(
            self.subject.can_execute(self.player, self.game, payload),
            "good payload says its false"
        )

        payload_bad = [road1_bad, road2_bad]
        self.assertFalse(
            self.subject.can_execute(self.player, self.game, payload_bad),
            "bad payload says its true"
        )

        self.subject.execute(self.player, self.game, payload)
        roads = RoadBuilding.objects.filter(owner=self.player, game=self.game)
        self.assertEquals(2, roads.count(), "bad road count")
        self.assertEquals(
            0,
            DevelopmentCard.objects.filter(player=self.player).count(),
            "bad developmentcard count"
        )


class MoveRobberActionTest(APITestCase):
    def setUp(self):
        self.subject = MoveRobberAction()

        board = Board.objects.create(name="new_board")
        self.game = Game.objects.create(board=board)

        user1 = User.objects.create(username="user1")
        self.player1 = Player.objects.create(game=self.game, user=user1)
        user2 = User.objects.create(username="user2")
        self.player2 = Player.objects.create(game=self.game, user=user2)

        self.game.current_turn = self.player1
        self.game.current_dices_1 = 3
        self.game.current_dices_2 = 4
        self.game.save()

    def test_payload_valid(self):
        self.assertFalse(self.subject.is_payload_valid(
            "i'm not a dict"
        ), "given payload is not a dictionary")
        self.assertFalse(self.subject.is_payload_valid(
            {"position": 12, "player": "Jhon"}
        ), "invalid type of position")
        self.assertFalse(self.subject.is_payload_valid(
            {"position": {"level": 2}, "player": "some"}
        ), "incomplete position")
        self.assertFalse(self.subject.is_payload_valid(
            {"position": {"level": 1, "index": 6}, "player": ""}
        ), "invalid index")
        self.assertFalse(self.subject.is_payload_valid(
            {"position": {"level": 1, "index": 3}}
        ), "missing field 'player'")
        self.assertTrue(self.subject.is_payload_valid(
            {"position": {"level": 0, "index": 0}, "player": "Will"}
        ), "payload is valid")

    def test_execute_passes(self):
        ResourcesCard.objects.create(
            game=self.game,
            player=self.player2,
            resource="brick"
        )
        SettlementBuilding.objects.create(
            game=self.game,
            owner=self.player2,
            pos_level=0,
            pos_index=0
        )

        payload = {
            "position": {"level": 1, "index": 0},
            "player": self.player2.user.username
        }

        self.assertTrue(self.subject.can_execute(self.player1, self.game, payload))
        self.subject.execute(self.player1, self.game, payload)

        self.assertEqual(
            self.game.robber_level, payload["position"]["level"],
            "new robber level is ok"
        )
        self.assertEqual(
            self.game.robber_index, payload["position"]["index"],
            "new robber index is ok"
        )
        self.assertTrue(self.game.robber_moved, "the robber has been moved this turn")
        self.assertTrue(
            ResourcesCard.objects.filter(game=self.game, player=self.player2).count() == 0,
            "player2 has no resources now"
        )
        self.assertTrue(
            ResourcesCard.objects.filter(game=self.game, player=self.player1).count() == 1,
            "player1 has one resource now"
        )

    def test_execute_fail(self):
        payload = {
            "position": {"level": 2, "index": 2},
            "player": "not_exist"
        }

        self.assertFalse(
            self.subject.can_execute(self.player1, self.game, payload),
            "invalid target player"
        )
        payload["player"] = ""

        self.game.robber_level = 2
        self.game.robber_index = 2
        self.game.save()

        self.assertFalse(
            self.subject.can_execute(self.player1, self.game, payload),
            "new position is the actual robber position"
        )
        self.game.robber_index = 8

        self.game.current_dices_1 = 1
        self.game.current_dices_2 = 2
        self.game.save()

        self.assertFalse(
            self.subject.can_execute(self.player1, self.game, payload),
            "the sum of dices is not 7"
        )
        self.game.current_dices_1 = 5

        self.game.robber_moved = True
        self.game.save()

        self.assertFalse(
            self.subject.can_execute(self.player1, self.game, payload),
            "the robber has been moved this turn"
        )
        self.game.robber_moved = False
        self.game.save()

        self.assertTrue(self.subject.can_execute(self.player1, self.game, payload))


class PlayKnightCardActionTest(APITestCase):
    def setUp(self):
        self.subject = PlayKnightAction()

        board = Board.objects.create(name="new_board")
        self.game = Game.objects.create(board=board)

        user1 = User.objects.create(username="user1")
        self.player1 = Player.objects.create(game=self.game, user=user1)

        user2 = User.objects.create(username="user2")
        self.player2 = Player.objects.create(game=self.game, user=user2)

    def test_execute_passes(self):
        ResourcesCard.objects.create(
            game=self.game,
            player=self.player2,
            resource="brick"
        )
        SettlementBuilding.objects.create(
            game=self.game,
            owner=self.player2,
            pos_level=0,
            pos_index=0
        )
        DevelopmentCard.objects.create(
            game=self.game,
            player=self.player1,
            card="knight"
        )

        payload = {
            "position": {"level": 1, "index": 0},
            "player": self.player2.user.username
        }

        self.assertTrue(self.subject.can_execute(self.player1, self.game, payload))
        self.subject.execute(self.player1, self.game, payload)

        self.assertEqual(
            self.game.robber_level, payload["position"]["level"],
            "new robber level is ok"
        )
        self.assertEqual(
            self.game.robber_index, payload["position"]["index"],
            "new robber index is ok"
        )
        self.assertTrue(self.game.robber_moved, "the robber has been moved this turn")
        self.assertTrue(
            ResourcesCard.objects.filter(game=self.game, player=self.player2).count() == 0,
            "player2 has no resources now"
        )
        self.assertTrue(
            ResourcesCard.objects.filter(game=self.game, player=self.player1).count() == 1,
            "player1 has one resource now"
        )

    def test_execute_fails(self):
        # test only if the resource check fails, since all the robber move logic is already
        # tested in the move robber action test.

        ResourcesCard.objects.create(
            game=self.game,
            player=self.player2,
            resource="brick"
        )
        SettlementBuilding.objects.create(
            game=self.game,
            owner=self.player2,
            pos_level=0,
            pos_index=0
        )

        payload = {
            "position": {"level": 1, "index": 0},
            "player": self.player2.user.username
        }

        self.assertFalse(self.subject.can_execute(self.player1, self.game, payload))
