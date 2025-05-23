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
    damaged_items_report,
    # Import/Export views
    import_employees,
    export_employee_template,
    # Employee archiving
    toggle_employee_archive,
    uniform_stock_api,
    uniform_type_sizes_api,
    uniform_by_type_size_api,
    AssetBreakdownView,
    UniformWithSizesCreateView,
    UniformSizeListView,
    UniformSizeCreateView,
    UniformSizeUpdateView,
    CustomLogoutView,
    # Site Location views
    SiteLocationListView,
    SiteLocationCreateView,
    SiteLocationDetailView,
    SiteLocationUpdateView,
    toggle_site_location_status,
    # Equipment Item views
    EquipmentItemListView,
    EquipmentItemCreateView,
    EquipmentItemDetailView,
    EquipmentItemUpdateView,
    EquipmentItemAssignView,
    update_equipment_status,
    # Data generation API
    generate_sample_data_api,
)
from django.views.generic import TemplateView

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
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('locked-out/', TemplateView.as_view(template_name='inventory/lockout.html'), name='locked_out'),
    
    # User Management
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/add/', UserCreateView.as_view(), name='user_add'),
    path('users/<int:pk>/role/', user_edit_role, name='user_edit_role'),
    
    # Employee Routes
    path('employees/', EmployeeListView.as_view(), name='employee_list'),
    path('employees/<int:pk>/', EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/<int:pk>/pdf/', employee_pdf, name='employee_pdf'),
    path('employees/<int:pk>/archive/', toggle_employee_archive, name='toggle_employee_archive'),
    
    # Uniform Inventory Route
    path('uniforms/', UniformListView.as_view(), name='uniform_list'),
    
    # Transaction Routes
    path('transaction/new/', MultiItemTransactionCreateView.as_view(), name='transaction_create'),
    path('transaction-item/<int:pk>/return/', process_item_return, name='item_return'),
    path('damaged-items/', damaged_items_report, name='damaged_items_report'),
    
    # Import/Export Routes
    path('employees/import/', import_employees, name='import_employees'),
    path('employees/template/', export_employee_template, name='export_employee_template'),
    
    # API Routes
    path('api/uniform/<int:uniform_id>/stock/', uniform_stock_api, name='uniform_stock_api'),
    path('api/uniform-types/<int:type_id>/sizes/', uniform_type_sizes_api, name='uniform_type_sizes_api'),
    path('api/uniforms/by-type-size/', uniform_by_type_size_api, name='uniform_by_type_size_api'),
    
    path('asset-breakdown/', AssetBreakdownView.as_view(), name='asset_breakdown'),
    
    # Uniform with sizes URLs
    path('uniforms/add-with-sizes/', UniformWithSizesCreateView.as_view(), name='uniform_add_with_sizes'),
    path('uniform-sizes/', UniformSizeListView.as_view(), name='uniform_sizes'),
    path('uniform-sizes/add/', UniformSizeCreateView.as_view(), name='uniform_size_add'),
    path('uniform-sizes/<int:pk>/edit/', UniformSizeUpdateView.as_view(), name='uniform_size_edit'),
    
    # Site Locations URLs
    path('site-locations/', SiteLocationListView.as_view(), name='site_location_list'),
    path('site-locations/create/', SiteLocationCreateView.as_view(), name='site_location_create'),
    path('site-locations/<int:pk>/', SiteLocationDetailView.as_view(), name='site_location_detail'),
    path('site-locations/<int:pk>/update/', SiteLocationUpdateView.as_view(), name='site_location_update'),
    path('site-locations/<int:pk>/toggle-status/', toggle_site_location_status, name='toggle_site_location_status'),
    
    # Equipment Item URLs
    path('equipment/', EquipmentItemListView.as_view(), name='equipment_item_list'),
    path('equipment/create/', EquipmentItemCreateView.as_view(), name='equipment_item_create'),
    path('equipment/<int:pk>/', EquipmentItemDetailView.as_view(), name='equipment_item_detail'),
    path('equipment/<int:pk>/update/', EquipmentItemUpdateView.as_view(), name='equipment_item_update'),
    path('equipment/<int:pk>/assign/', EquipmentItemAssignView.as_view(), name='equipment_item_assign'),
    path('equipment/<int:pk>/status/', update_equipment_status, name='update_equipment_status'),
    
    # Sample Data Generation API
    path('api/generate-data/', generate_sample_data_api, name='generate_sample_data_api'),
]



