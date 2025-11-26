from rest_framework import serializers
from Users.user_serializer import UserSerializer
from .models import PurchaseRequest

class PurchaseRequestSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    proforma_url = serializers.SerializerMethodField()
    purchase_order_url = serializers.SerializerMethodField()
    receipt_url = serializers.SerializerMethodField()
    invoice_url = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequest
        fields = [
            'id', 'title', 'description', 'amount', 'status',
            'created_by', 'current_level',
            'proforma', 'proforma_url',
            'purchase_order', 'purchase_order_url',
            'invoice', 'invoice_url',
            'receipt', 'receipt_url',
            'vendor_name', 'items_json', 'extraction_status',
            'three_way_match_status', 'discrepancy_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'created_by', 'current_level',
            'vendor_name', 'items_json', 'extraction_status',
            'purchase_order', 'invoice',
            'three_way_match_status', 'discrepancy_details',
            'created_at', 'updated_at'
        ]

    def get_proforma_url(self, obj):
        request = self.context.get('request')
        if obj.proforma:
            return request.build_absolute_uri(obj.proforma.url)
        return None

    def get_purchase_order_url(self, obj):
        request = self.context.get('request')
        if obj.purchase_order:
            return request.build_absolute_uri(obj.purchase_order.url)
        return None

    def get_receipt_url(self, obj):
        request = self.context.get('request')
        if obj.receipt:
            return request.build_absolute_uri(obj.receipt.url)
        return None

    def get_invoice_url(self, obj):
        request = self.context.get('request')
        if obj.invoice:
            return request.build_absolute_uri(obj.invoice.url)
        return None

    def validate_proforma(self, value):
        if not value:
            raise serializers.ValidationError("Proforma file is required.")
        ext = value.name.split('.')[-1].lower()
        if ext not in ['pdf']:
            raise serializers.ValidationError("Only PDF, JPG, or PNG allowed.")
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File must be under 5MB.")
        return value

class ReceiptUploadSerializer(serializers.Serializer):
    receipt = serializers.FileField()

    def validate_receipt(self, value):
        ext = value.name.split('.')[-1].lower()
        if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
            raise serializers.ValidationError("Only PDF, JPG, or PNG allowed.")
        return value

class ApprovalActionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)

class InvoiceUploadSerializer(serializers.Serializer):
    invoice = serializers.FileField()