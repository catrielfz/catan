from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView, status
from rest_framework import permissions

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.http import Http404

from catan.serializers import RoomSerializer, GameSerializer, BoardSerializer
from catan.actions import ACTION_HANDLERS, get_available_road_positions
from catan.actions import get_available_settlement_positions_pos, get_available_road_positions_pos
from catan.actions import get_available_settlement_positions, get_available_robber_positions
from catan.models import *


def vertex_position_json(level, index):
    return {"level": level, "index": index}


def player_for_game_or_404(user, game_id):
    try:
        game = Game.objects.get(pk=game_id)
        return Player.objects.get(game=game_id, user=user.id), game
    except ObjectDoesNotExist:
        raise Http404


class BoardList(APIView):
    def get(self, request):
        boards = Board.objects.all()
        result = BoardSerializer(boards, many=True)
        return Response(result.data)


class HexList(APIView):
    def get(self, request, id, format=None):
        try:
            game = Game.objects.get(pk=id)
        except Game.DoesNotExist:
            raise Http404

        result = []
        for h in Hexagon.objects.filter(board=game.board):
            terrain = h.resource
            if terrain is None:
                terrain = "desert"

            result.append({
                "position": vertex_position_json(h.pos_level, h.pos_index),
                "terrain": terrain,
                "token": h.token
            })

        return Response({"hexes": result})


class PlayerAction(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, id):
        player, game = player_for_game_or_404(request.user, id)
        if game.current_turn != player:
            return Response({"details": "not in your turn"}, status=401)

        try:
            action = request.data["type"]
            payload = request.data["payload"]
            handler = ACTION_HANDLERS[action]
        except KeyError:
            return Response({"details": "invalid action or no payload given"}, status=400)

        if not handler.is_payload_valid(payload):
            return Response({"details": "invalid payload"}, status=400)

        if not handler.can_execute(player, game, payload):
            return Response({"details": "action cannot be executed"}, status=400)

        handler.execute(player, game, payload)
        game.try_set_to_winner(player)
        return Response()

    def get(self, request, id):
        player = get_object_or_404(Player, user=request.user, game=id)

        available_actions = list()

        if player.game.current_turn == player:
            end_turn_locked = player.game.dices_sum() == 7 and not player.game.robber_moved
            robber = list()
            for h in get_available_robber_positions(player):
                players = list()
                for p in get_adjacent_players(player.game, h["level"], h["index"]):
                    if p != player:
                        players.append(p.user.username)
                robber.append({"position": h, "players": players})
            if end_turn_locked:
                if robber != []:
                    available_actions.append({"type": "move_robber", "payload": robber})
            else:
                available_actions.append({"type": "end_turn", "payload": None})

                sett = get_available_settlement_positions_pos(player)
                if sett != []:
                    if SettlementBuilding.has_resources_to_build(player):
                        available_actions.append({"type": "build_settlement", "payload": sett})

                if robber != []:
                    if DevelopmentCard.count_player(player, "knight") > 0:
                        available_actions.append({"type": "play_knight_card", "payload": robber})

                road = get_available_road_positions_pos(player)
                if road != []:
                    if RoadBuilding.has_resources_to_build(player):
                        available_actions.append({"type": "build_road", "payload": road})
                    if DevelopmentCard.count_player(player, "road_building") > 0:
                        available_actions.append(
                            {
                                "type": "play_road_building_card",
                                "payload": road
                            }
                        )

                # bank_trade
                for r, _ in RESOURCE_TYPES:
                    if ResourcesCard.count_player(player, r) >= 4:
                        available_actions.append({"type": "bank_trade", "payload": None})
                        break

                # buy card
                has_ore = ResourcesCard.count_player(player, 'ore') >= 1
                has_wool = ResourcesCard.count_player(player, 'wool') >= 1
                has_grain = ResourcesCard.count_player(player, 'grain') >= 1
                if has_grain and has_ore and has_wool:
                    available_actions.append({"type": "buy_card", "payload": None})

        return Response(available_actions)


class GameStatus(APIView):
    def player_to_json(self, game, p):
        return {
            "username": p.user.username,
            "colour": p.colour,
            "settlements": [
                {"level": s.pos_level, "index": s.pos_index}
                for s in SettlementBuilding.objects.filter(owner=p)
            ],
            "cities": [],
            "roads": [(
                {"level": r.fst_pos_level, "index": r.fst_pos_index},
                {"level": r.snd_pos_level, "index": r.snd_pos_index})
                for r in RoadBuilding.objects.filter(owner=p)
            ],
            "development_cards": DevelopmentCard.objects.filter(player=p).count(),
            "resources_cards": ResourcesCard.objects.filter(player=p).count(),
            "last_gained": [],
            "victory_points": game.calculate_points(p)
        }

    def get(self, request, id, format=None):
        try:
            game = Game.objects.get(pk=id)
        except Game.DoesNotExist:
            raise Http404

        players = [self.player_to_json(game, p) for p in Player.objects.filter(game=id)]
        result = {
            "players": players,
            "robber": vertex_position_json(game.robber_level, game.robber_index),
            "current_turn": {
                "user": game.current_turn.user.username,
                "dice": [game.current_dices_1, game.current_dices_2],
            },
            "winner": game.get_winner_name_or_none()
        }
        return Response(result)


class GamesList(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        games = Game.objects.all()
        result = GameSerializer(games, many=True)
        return Response(result.data)


class RoomListAndCreate(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        rooms = Room.objects.all()
        result = RoomSerializer(rooms, many=True)
        return Response(result.data)

    def post(self, request):
        try:
            name_r = request.data["name"]
            board_id = request.data["board_id"]
        except KeyError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        owner = request.user
        room = Room.objects.create(name=name_r,
                                   owner=owner,
                                   board_id=get_object_or_404(Board, id=board_id))
        room.players.add(owner)
        room.save()
        return Response(RoomSerializer(room).data)


class RoomsId(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, id):
        room = get_object_or_404(Room, id=id)
        return Response(RoomSerializer(room).data)

    def put(self, request, id):
        room = get_object_or_404(Room, id=id)
        if room.players.all().count() >= 4:
            return Response("hasta 4 permitidos", status=status.HTTP_400_BAD_REQUEST)
        if room.game_has_started:
            return Response("juego ya iniciado", status=status.HTTP_400_BAD_REQUEST)
        room.players.add(request.user)
        room.save()
        return Response()

    def delete(self, request, id):
        room = get_object_or_404(Room, id=id)
        if not room.owner == request.user:
            return Response("No es el duenio del lobby", status=status.HTTP_401_UNAUTHORIZED)
        room.delete()
        return Response(status=status.HTTP_200_OK)

    def patch(self, request, id):
        room = get_object_or_404(Room, id=id)
        if not room.owner == request.user:
            return Response("sin permisos", status=status.HTTP_401_UNAUTHORIZED)
        if room.game_has_started:
            return Response("juego ya iniciado", status=status.HTTP_400_BAD_REQUEST)
        if not 3 <= room.players.count() and room.players.count() <= 4:
            return Response("faltan jugadores", status=status.HTTP_400_BAD_REQUEST)

        game = Game.objects.create(board=room.board_id, name=room.name)
        colours = ['red', 'green', 'yellow', 'blue']
        count = 0
        settlements = [
            [(1, 2), (1, 9)],
            [(1, 5), (1, 15)],
            [(1, 7), (1, 11)],
            [(1, 13), (1, 17)]
        ]
        for u in room.players.all():
            p = Player.objects.create(user=u, game=game, colour=colours[count])
            ss = settlements[count]
            for s in ss:
                SettlementBuilding.objects.create(
                    game=game,
                    owner=p,
                    pos_level=s[0],
                    pos_index=s[1]
                )
                route_dst = get_neighbors(s)[0]
                RoadBuilding.objects.create(
                    game=game,
                    owner=p,
                    fst_pos_level=s[0],
                    fst_pos_index=s[1],
                    snd_pos_level=route_dst[0],
                    snd_pos_index=route_dst[1]
                )

            count = count+1

        # crear recursos
        cards = ['road_building', 'year_of_plenty', 'monopoly', 'victory_point', 'knight']
        for _ in range(25):
            DevelopmentCard.objects.create(
                        game=game,
                        player=None,
                        card=random.choice(cards)
            )
        for res, _ in RESOURCE_TYPES:
            for _ in range(19):
                ResourcesCard.objects.create(
                            game=game,
                            player=None,
                            resource=res
                )

        # movimiento inicial de la partida
        game.current_turn = Player.objects.get(game=game, user=request.user)
        game.roll_dices()
        game.distribute_resources(game.dices_sum())
        game.save()

        # iniciar room
        room.game_has_started = True
        room.game_id = game
        room.save()
        return Response()


class ResourcesCardsList(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, id, format=None):
        p, _ = player_for_game_or_404(request.user, id)
        resources = [
            r.resource for r in
            ResourcesCard.objects.filter(player=p.id)
        ]
        cards = [
            c.card for c in
            DevelopmentCard.objects.filter(player=p.id)
        ]
        return Response({"resources": resources, "cards": cards})


class UserRegister(APIView):

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        try:
            user_field = request.data["user"]
            pass_field = request.data["pass"]
        except KeyError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if not (3 <= len(user_field) <= 30):
            return Response("user entre 3 y 30 caracteres", status=status.HTTP_400_BAD_REQUEST)

        if len(pass_field) < 8:
            return Response("pass minimo 8 caracteres", status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=user_field).count() >= 1:
            return Response("username ya registrado", status=status.HTTP_400_BAD_REQUEST)

        User.objects.create_user(username=user_field, password=pass_field)
        return Response(status=status.HTTP_201_CREATED)


class UserLogin(APIView):
    def post(self, request):
        try:
            user_field = request.data["user"]
            pass_field = request.data["pass"]
        except KeyError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, username=user_field)
        if not user.check_password(pass_field):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            t = Token.objects.get(user=user)
        except Token.DoesNotExist:
            t = Token.objects.create(user=user)

        return Response({"token": t.key})
