# requests/models.py

from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL



class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_created"
    )

    class Meta:
        abstract = True




class ApprovalLevel(BaseModel):
    level = models.PositiveIntegerField()
    name = models.CharField(max_length=100)
    approvers = models.ManyToManyField(
        User,
        related_name="approval_levels",
        help_text="Users allowed to approve at this level"
    )

    class Meta:
        ordering = ["level"]
        unique_together = ("level", "name")

    def __str__(self):
        return f"Level {self.level} - {self.name}"




class PurchaseRequest(BaseModel):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    MATCHING_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("MATCHED", "Matched"),
        ("DISCREPANCY", "Discrepancy"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    current_level = models.PositiveIntegerField(default=1)

    

    # Files
    proforma = models.FileField(upload_to="proformas/", null=True, blank=True)
    purchase_order = models.FileField(upload_to="purchase_orders/", null=True, blank=True)
    invoice = models.FileField(upload_to="invoices/", null=True, blank=True)
    receipt = models.FileField(upload_to="receipts/", null=True, blank=True)

    # AI-extracted data (proforma)
    vendor_name = models.CharField(max_length=255, blank=True)
    vendor_address = models.TextField(blank=True)
    items_json = models.JSONField(default=list, blank=True)
    total_amount_extracted = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    extraction_status = models.CharField(
        max_length=10,
        choices=[("PENDING", "Pending"), ("SUCCESS", "Success"), ("FAILED", "Failed")],
        default="PENDING"
    )

    # AI-extracted data (invoice)
    invoice_vendor_name = models.CharField(max_length=255, blank=True)
    invoice_items_json = models.JSONField(default=list, blank=True)
    invoice_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    invoice_extraction_status = models.CharField(
        max_length=10,
        choices=[("PENDING", "Pending"), ("SUCCESS", "Success"), ("FAILED", "Failed")],
        default="PENDING"
    )

    # 3-way matching
    three_way_match_status = models.CharField(
        max_length=15,
        choices=MATCHING_STATUS_CHOICES,
        default="PENDING"
    )
    discrepancy_details = models.JSONField(default=dict, blank=True)

    # Tolerance thresholds
    amount_tolerance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    quantity_tolerance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"


# class to track approval actions
class ApprovalAction(BaseModel):
    ACTION_CHOICES = [
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected")
    ]

    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="actions")
    level = models.PositiveIntegerField()
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    comment = models.TextField(null=True, blank=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="approval_actions")
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["acted_at"]
        unique_together = ("request", "level", "actor")

    def __str__(self):
        return f"{self.actor} {self.action} at level {self.level}"
