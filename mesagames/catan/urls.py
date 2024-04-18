from django.urls import path
from catan import views

urlpatterns = [
    path('games/', views.GamesList.as_view()),
    path('games/<int:id>/board/', views.HexList.as_view()),
    path('rooms/', views.RoomListAndCreate.as_view()),
    path('rooms/<int:id>/', views.RoomsId.as_view()),
    path('games/<int:id>/player/', views.ResourcesCardsList.as_view()),
    path('games/<int:id>/', views.GameStatus.as_view()),
    path('games/<int:id>/player/actions/', views.PlayerAction.as_view()),
    path('users/', views.UserRegister.as_view()),
    path('users/login/', views.UserLogin.as_view()),
    path('boards/', views.BoardList.as_view()),

    path('games', views.GamesList.as_view()),
    path('games/<int:id>/board', views.HexList.as_view()),
    path('rooms', views.RoomListAndCreate.as_view()),
    path('rooms/<int:id>', views.RoomsId.as_view()),
    path('games/<int:id>/player', views.ResourcesCardsList.as_view()),
    path('games/<int:id>', views.GameStatus.as_view()),
    path('games/<int:id>/player/actions', views.PlayerAction.as_view()),
    path('users', views.UserRegister.as_view()),
    path('users/login', views.UserLogin.as_view()),
    path('boards', views.BoardList.as_view()),
]
