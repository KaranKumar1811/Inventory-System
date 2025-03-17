from django.urls import path

from django.contrib.auth import views as auth_views
from .views import (
    EmployeeListView,
    EmployeeDetailView,
    UniformListView,
    MultiItemTransactionCreateView,
    employee_pdf,
    process_item_return,
    LoadingPageView,
    DashboardView,
    SearchView,
    # User management views
    UserListView,
    UserCreateView,
    user_edit_role,
    # Uncomment or add these once the views are implemented
    # EmployeeCreateView,
    # EmployeeUpdateView,
    # EmployeeDeleteView,
    # UniformDeleteView,
    damaged_items_report,
    # Import/Export views
    import_employees,
    import_uniforms,
    export_employee_template,
    export_uniform_template,
)

app_name = 'inventory'

urlpatterns = [
    # Loading Page as root for initial experience
    path('', LoadingPageView.as_view(), name='loading_page'),
    
    # Dashboard with its own URL
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # Search functionality
    path('search/', SearchView.as_view(), name='search'),
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # User Management
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/add/', UserCreateView.as_view(), name='user_add'),
    path('users/<int:pk>/role/', user_edit_role, name='user_edit_role'),
    
    # Employee Routes
    path('employees/', EmployeeListView.as_view(), name='employee_list'),
    path('employees/<int:pk>/', EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/<int:pk>/pdf/', employee_pdf, name='employee_pdf'),
    
    # Uncomment these when you implement the views
    # path('employees/add/', EmployeeCreateView.as_view(), name='employee_add'),
    # path('employees/<int:pk>/edit/', EmployeeUpdateView.as_view(), name='employee_edit'),
    # path('employees/<int:pk>/delete/', EmployeeDeleteView.as_view(), name='employee_delete'),
    
    # Uniform Inventory Route
    path('uniforms/', UniformListView.as_view(), name='uniform_list'),
    
    # Uncomment this when you implement the view
    # path('uniforms/<int:pk>/delete/', UniformDeleteView.as_view(), name='uniform_delete'),
    
    # Transaction Routes
    path('transaction/new/', MultiItemTransactionCreateView.as_view(), name='transaction_create'),
    path('transaction-item/<int:pk>/return/', process_item_return, name='item_return'),
    path('damaged-items/', damaged_items_report, name='damaged_items_report'),
    
    # Import/Export Routes
    path('employees/import/', import_employees, name='import_employees'),
    path('employees/template/', export_employee_template, name='export_employee_template'),
    path('uniforms/import/', import_uniforms, name='import_uniforms'),
    path('uniforms/template/', export_uniform_template, name='export_uniform_template'),
]



