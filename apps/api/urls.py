from django.urls import path
from apps.api import views

urlpatterns = [
    # Main fact-checking endpoints
    path('fact-check/', views.fact_check_create, name='fact_check_create'),
    path('fact-check/<uuid:session_id>/status/', views.fact_check_status, name='fact_check_status'),
    path('fact-check/<uuid:session_id>/results/', views.fact_check_results, name='fact_check_results'),
    path('fact-check/<uuid:session_id>/steps/', views.fact_check_steps, name='fact_check_steps'),
    path('fact-check/<uuid:session_id>/delete/', views.fact_check_delete, name='fact_check_delete'),
    
    # List and utility endpoints
    path('fact-check/list/', views.fact_check_list, name='fact_check_list'),
    path('health/', views.health_check, name='health_check'),
]
