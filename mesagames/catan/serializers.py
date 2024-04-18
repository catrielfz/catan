from rest_framework import serializers
from catan.models import Room, Game, Board
from django.contrib.auth.models import User


class RoomSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField()
    players = serializers.StringRelatedField(many=True)

    class Meta:
        model = Room
        fields = ['id', 'name', 'owner', 'players', 'max_players', 'game_has_started', 'game_id']
        read_only = fields


class GameSerializer(serializers.ModelSerializer):
    in_turn = serializers.CharField(source='current_turn.user')

    class Meta:
        model = Game
        fields = ['id', 'name', 'in_turn']
        read_only = fields


class BoardSerializer(serializers.ModelSerializer):

    class Meta:
        model = Board
        fields = ['id', 'name']
        read_only = fields
