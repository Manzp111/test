# requests/admin.py
from django.contrib import admin
from .models import PurchaseRequest, ApprovalAction

class ApprovalActionInline(admin.TabularInline):
    model = ApprovalAction
    extra = 0
    readonly_fields = ('level', 'action', 'actor', 'comment', 'acted_at')
    can_delete = False
    ordering = ('acted_at',)

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'status', 'three_way_match_status', 'current_level', 
        'created_by', 'purchase_order','invoice', 'receipt',
    )
    list_filter = ('status', 'three_way_match_status', 'current_level', 'created_at')
    search_fields = ('title', 'vendor_name', 'vendor_address', 'created_by__username')
    readonly_fields = (
        'total_amount_extracted', 'extraction_status', 
        'invoice_total', 'invoice_extraction_status',
        'three_way_match_status', 'discrepancy_details',
        'created_at', 'updated_at'
    )
  
    ordering = ('-created_at',)

@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ('id', 'request', 'level', 'action', 'actor', 'acted_at')
    list_filter = ('action', 'level', 'acted_at')
    search_fields = ('request__title', 'actor__username', 'comment')
    readonly_fields = ('request', 'level', 'action', 'actor', 'comment', 'acted_at')
