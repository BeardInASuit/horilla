"""
URL configuration for asset-related views.
"""
from django.urls import path
from django import views
from asset.forms import AssetCategoryForm, AssetForm
from asset.models import Asset, AssetCategory
from base.views import object_duplicate
from . import views


urlpatterns = [
    path("asset-creation/<int:id>/", views.asset_creation, name="asset-creation"),
    path("asset-list/<int:cat_id>", views.asset_list, name="asset-list"),
    path("asset-update/<int:asset_id>/", views.asset_update, name="asset-update"),
    path(
        "duplicate-asset/<int:obj_id>/",
        object_duplicate,
        name="duplicate-asset",
        kwargs={
            "model": Asset,
            "form": AssetForm,
            "form_name": "asset_creation_form",
            "template": "asset/asset_creation.html",
        },
    ),
    path("asset-delete/<int:asset_id>/", views.asset_delete, name="asset-delete"),
    path(
        "asset-information/<int:asset_id>/",
        views.asset_information,
        name="asset-information",
    ),
    path("asset-category-view/", views.asset_category_view, name="asset-category-view"),
    path(
        "asset-category-view-search-filter",
        views.asset_category_view_search_filter,
        name="asset-category-view-search-filter",
    ),
    path(
        "asset-category-duplicate/<int:obj_id>/",
        object_duplicate,
        name="asset-category-duplicate",
        kwargs={
            "model": AssetCategory,
            "form": AssetCategoryForm,
            "form_name": "asset_category_form",
            "template": "category/asset_category_creation.html",
        },
    ),
    path(
        "asset-category-creation",
        views.asset_category_creation,
        name="asset-category-creation",
    ),
    path(
        "asset-category-update/<int:cat_id>",
        views.asset_category_update,
        name="asset-category-update",
    ),
    path(
        "asset-category-delete/<int:cat_id>",
        views.delete_asset_category,
        name="asset-category-delete",
    ),
    path(
        "asset-request-creation",
        views.asset_request_creation,
        name="asset-request-creation",
    ),
    path(
        "asset-request-allocation-view",
        views.asset_request_alloaction_view,
        name="asset-request-allocation-view",
    ),
    path(
        "asset-request-individual-view/<int:id>",
        views.asset_request_individual_view,
        name="asset-request-individual-view",
    ),
    path(
        "asset-allocation-individual-view/<int:id>",
        views.asset_allocation_individual_view,
        name="asset-allocation-individual-view",
    ),
    path(
        "asset-request-allocation-view-search-filter",
        views.asset_request_alloaction_view_search_filter,
        name="asset-request-allocation-view-search-filter",
    ),
    path(
        "asset-request-approve/<int:req_id>/",
        views.asset_request_approve,
        name="asset-request-approve",
    ),
    path(
        "asset-request-reject/<int:req_id>/",
        views.asset_request_reject,
        name="asset-request-reject",
    ),
    path(
        "asset-allocate-creation",
        views.asset_allocate_creation,
        name="asset-allocate-creation",
    ),
    path(
        "asset-allocate-return/<int:asset_id>/",
        views.asset_allocate_return,
        name="asset-allocate-return",
    ),
    path("asset-excel", views.asset_excel, name="asset-excel"),
    path("asset-import", views.asset_import, name="asset-import"),
    path("asset-export-excel", views.asset_export_excel, name="asset-export-excel"),
    path(
        "asset-batch-number-creation",
        views.asset_batch_number_creation,
        name="asset-batch-number-creation",
    ),
    path("asset-batch-view", views.asset_batch_view, name="asset-batch-view"),
    path(
        "asset-batch-number-search",
        views.asset_batch_number_search,
        name="asset-batch-number-search",
    ),
    path(
        "asset-batch-update/<int:batch_id>",
        views.asset_batch_update,
        name="asset-batch-update",
    ),
    path(
        "asset-batch-number-delete/<int:batch_id>",
        views.asset_batch_number_delete,
        name="asset-batch-number-delete",
    ),
    path("asset-count-update", views.asset_count_update, name="asset-count-update"),
    path("add-asset-report/", views.add_asset_report, name="add-asset-report"),
    path(
        "add-asset-report/<int:asset_id>",
        views.add_asset_report,
        name="add-asset-report",
    ),
    path("dashboard/", views.asset_dashboard, name="asset-dashboard"),
    path(
        "asset-available-chart/",
        views.asset_available_chart,
        name="asset-available-chart",
    ),
    path(
        "asset-category-chart/", views.asset_category_chart, name="asset-category-chart"
    ),
]
