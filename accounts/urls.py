from django.urls import path

from . import views as view

urlpatterns = [
    path('login/', view.login_view, name='login'),
    path('logout/', view.logout_view, name='logout'),
    path('profile/', view.profile_view, name='profile'),

    path('users/', view.user_home, name='user_home'),
    path('users/create/', view.user_form, name='user_create'),
    path('users/<int:pk>/edit/', view.user_form, name='user_edit'),
    path('users/<int:pk>/password/', view.user_password, name='user_password'),
    path('users/<int:pk>/toggle/', view.user_toggle, name='user_toggle'),

    path('groups/', view.group_home, name='group_home'),
    path('groups/create/', view.group_form, name='group_create'),
    path('groups/<int:pk>/edit/', view.group_form, name='group_edit'),
    path('groups/<int:pk>/delete/', view.group_delete, name='group_delete'),
]
