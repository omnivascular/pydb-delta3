from django.urls import path, re_path, include
from django.contrib import admin
from . import views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('django.contrib.auth.urls')),
    path('users/', include('users.urls')),
    path("products/", views.all_products, name="all-products"),
    path("products/used", views.all_products_used, name="all-products-used"),
    path("products/expired-stocked", views.all_products_expired_still_stocked, name="all-products-expired-stocked"),
    path("products/report/added_last_30_days/", views.report_items_added_30days, name="report_items_added_30days"),
    path("products/report/used_last_30_days/", views.report_items_used_30days, name="report_items_used_30days"),
    path("vendors/", views.all_vendors, name="all-vendors"),
    path("inventory_update/", views.database_update_current_inventory, name="update-inventory"),
    path("procedures_update/", views.database_update_procedures, name="update-procedures"),
    path("purchaseorders_update/", views.database_update_purchaseorders, name="update-purchaseorders"),
    path("procedures/", views.all_procedures, name="all-procedures"),
    path("purchase_orders/", views.all_purchase_orders, name="all-purchase-orders"),
    # path('edit_product_notes/<int:product_id>/', views.edit_product_notes, name='edit_product_notes'),
    path(
        "vendors/<int:vendor_id>/",
        views.all_vendor_products,
        name="all-vendor-products",
    ),
    path(
        "product/<int:item_id>/",
        views.product_detail,
        name="product_detail",
    ),
    path(
        "procedure/<int:procedure_id>/",
        views.procedure_detail,
        name="procedure_detail",
    ),
    path(
        "purchase_order/<int:po_id>/",
        views.po_detail,
        name="po_detail",
    ),
    # re_path(r"^ajax_calls/search/$", views.autocompleteModel, name="autocomplete"),
    path("product_search/", views.product_search, name="product_search"),
    path("update_product/<int:product_id>/", views.update_product, name="update_product"),
    path("update_po/<int:po_id>/", views.update_po, name="update_po"),
    path('add_product/', views.add_product, name='add_product'),
    path('create_po/', views.create_po, name='create_po'),
    path('add_vendor/', views.add_vendor, name='add_vendor'),
    path('', views.home, name='home'),
    path('expiring_products/in-<int:month_number>-months/', views.expiry_check_products_by_month, name='expiry_check_products_by_month'),
    path('expiry_check_custom/', views.expiry_check_custom_dates, name='expiry_check_custom'),
    path('procedure/', views.procedure, name='procedure'),
]

admin.site.header = "Omni Vascular Inventory Management"
admin.site.site_title = "Browser Title"
admin.site.index_title = "Welcome to Omni IT!"
