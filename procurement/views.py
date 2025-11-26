
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from django.db import transaction
from .models import PurchaseRequest, ApprovalAction
from rest_framework.permissions import IsAuthenticated
from django.db import models
from .serializers import (
    PurchaseRequestSerializer,
    ReceiptUploadSerializer,
    ApprovalActionSerializer,
    InvoiceUploadSerializer
)
from .permissions import IsStaff, IsApprover
from Users.utils import api_response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .tasks import process_proforma,validate_receipt



class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'  # Allow clients to set page size
    max_page_size = 100



@extend_schema(tags=['Purchase Requests'])
class PurchaseRequestViewSet(ModelViewSet):
    serializer_class = PurchaseRequestSerializer
    permission_classes=[IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)  # Enable file uploads

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
    'status': ['exact', 'iexact'],
    'current_level': ['exact'],
    'created_by': ['exact'],
    'created_at': ['exact'],
}

    search_fields = ['title', 'description', 'vendor_name']
    ordering_fields = ['created_at', 'amount', 'current_level', 'status']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination
    
    def get_permissions(self):
        """
        Require authentication for all actions. Use custom permissions
        for specific actions like create, approve, reject, etc.
        """
        # Ensure user is logged in for all actions
        permissions = [IsAuthenticated()]

        # Add custom permissions based on action
        if self.action == 'create':
            permissions.append(IsStaff())
        elif self.action in ['approve', 'reject']:
            permissions.append(IsApprover())
        elif self.action == 'submit_receipt':
            permissions.append(IsStaff())
        elif self.action in ['update', 'partial_update']:
            permissions.append(IsStaff())

        return permissions
    


    def get_queryset(self):
        user = self.request.user
        queryset = PurchaseRequest.objects.select_related('created_by').prefetch_related('actions')

        # Role-based filtering
        if user.role == 'staff':
            queryset = queryset.filter(created_by=user)
        elif user.role == 'manager':
            queryset = queryset.filter(current_level=1)
        elif user.role == 'general_manager':
            queryset = queryset.filter(current_level=2)
        elif user.role == 'finance':
            queryset = queryset.filter(status='APPROVED')

        # Status filter
        status_param = self.request.query_params.get('status')
        if status_param and status_param.lower() != 'all':
            queryset = queryset.filter(status__iexact=status_param)

        # Approved/reviewed filter
        approved_by_me = self.request.query_params.get('approved_by_me')
        if approved_by_me in ['0', '1'] and user.role in ['manager', 'general_manager']:
            queryset = queryset.annotate(
                has_reviewed=models.Exists(
                    ApprovalAction.objects.filter(
                        request=models.OuterRef('pk'),
                        actor=user,
                        level=models.OuterRef('current_level'),
                        action__in=['APPROVED', 'REJECTED']
                    )
                )
            )
            if approved_by_me == '1':
                queryset = queryset.filter(has_reviewed=True)
            else:
                queryset = queryset.filter(has_reviewed=False)

        return queryset.distinct()




    #documentation for create
    @extend_schema(
        summary="Create a new purchase request ",
        description="""
        Staff can submit a purchase request with a proforma invoice (PDF/image).
        The system automatically extracts vendor, items, prices, and terms using AI.
        
        **File Requirements**:
        - Format: PDF, JPG, JPEG, PNG
        - Max size: 5MB
        """,
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string', 'example': 'Marketing Conference Registration'},
                    'description': {'type': 'string', 'example': 'Annual tech event in Kigali'},
                    'amount': {'type': 'number', 'format': 'float', 'example': 350.00},
                    'proforma': {'type': 'string', 'format': 'binary', 'description': 'Proforma invoice'}
                },
                'required': ['title', 'description', 'amount', 'proforma']
            }
        },

    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            first_field = next(iter(serializer.errors))
            first_msg = serializer.errors[first_field]
            return api_response(
                success=False,
                message=first_msg[0] if isinstance(first_msg, list) else str(first_msg),
                data=None,
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        purchase_request = serializer.save(created_by=request.user)

        # Trigger AI processing
        try:
            process_proforma.delay(purchase_request.id)
        except Exception as e:
            print(f"AI processing error: {e}")

        return api_response(
            success=True,
            message="Purchase request created. Proforma processing started.",
            data=serializer.data,
            status_code=status.HTTP_201_CREATED
        )
    
    # documentation for list
    @extend_schema(
        summary="List purchase requests",
        description="""
        Returns requests filtered by user role:
        - **Staff**: only their own requests
        - **Approvers**: only PENDING requests
        - **Finance**: only APPROVED requests
        
        Supports filtering by status (`?status=pending`).
        """,
        parameters=[
             OpenApiParameter(
                 name='status',
                 description='Filter by request status (pending, approved, rejected)',
                 required=False,
                 type=str,
             ),
             OpenApiParameter(
                 name='my_approved',
                 description='If set to `1` (for Approvers), returns **ALL** requests the user has ever approved, regardless of their current status or level.',
                 required=False,
                 type=str,
                 examples=[OpenApiExample('Approved History', value='1')]
             )
        ],


       )
    def list(self, request, * args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return api_response(
            success=True,
            message="Requests retrieved successfully",
            data=response.data,
            status_code=status.HTTP_200_OK
        )


    # documentation for retrieve
    @extend_schema(
        summary="Retrieve a purchase request",
        description="""
        Get full details of a purchase request, including:
        - AI-extracted vendor and items
        - Approval history
        - File URLs (proforma, PO, receipt, invoice)
        """,
   
     )
    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return api_response(
            success=True,
            message="Request retrieved successfully",
            data=response.data,
            status_code=status.HTTP_200_OK
        )


   # documentation for update
    @extend_schema(
        summary="Update a pending purchase request",
        description="Staff can update their own PENDING requests (title, description, amount).",
        request=PurchaseRequestSerializer,

    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.created_by != request.user or instance.status != 'PENDING':
            return api_response(
                success=False,
                message="You can only update your own pending requests.",
                data=None,
                status_code=status.HTTP_403_FORBIDDEN
            )
        response = super().update(request, *args, **kwargs)
        return api_response(
            success=True,
            message="Request updated successfully.",
            data=response.data,
            status_code=status.HTTP_200_OK
        )
    
    # documentation for approve added here
    @extend_schema(
    tags=['Purchase Requests'],
    summary="Approve a purchase request",
    description="""
    Approvers can approve a PENDING request at their assigned level.

    - **Level 1** → Managers approve first
    - **Level 2** → General Managers give final approval
    - Final approval automatically triggers PDF Purchase Order generation
    - Concurrency protection using `select_for_update()` row locks
    """,
    request=ApprovalActionSerializer,

      )
        
    @action(detail=True, methods=["patch"])
    def approve(self, request, pk=None):
         # we used transaction to ensure concurrency safety and if not all operations are successful then rollback
        with transaction.atomic(): 
          
            purchase_request = get_object_or_404(
                PurchaseRequest.objects.select_for_update(),
                id=pk
            )

          
            if purchase_request.status != "PENDING":
                return api_response(
                    success=False,
                    message="Request is already processed.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            current_level = purchase_request.current_level
            user_role = request.user.role

           
            required_role = "manager" if current_level == 1 else "general_manager"

            if user_role != required_role:
                return api_response(
                    success=False,
                    message=f"Only {required_role.replace('_', ' ')}s can approve at level {current_level}.",
                    status_code=status.HTTP_403_FORBIDDEN
                )

          
            serializer = ApprovalActionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            existing = ApprovalAction.objects.filter(
            request=purchase_request,
            level=current_level,
            actor=request.user
                 ).exists()

            if existing:
                return api_response(
                    success=False,
                    message="You have already approved this request at this level.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )


            
            ApprovalAction.objects.create(
                request=purchase_request,
                level=current_level,
                action="APPROVED",
                actor=request.user,
                comment=serializer.validated_data.get("comment", "")
            )

           
            if current_level == 2:
                # FINAL APPROVAL
                purchase_request.status = "APPROVED"
                purchase_request.save()

                
                from .tasks import generate_purchase_order
                generate_purchase_order.delay(purchase_request.id)

            else:
                # LEVEL 1 → LEVEL 2
                purchase_request.current_level = 2
                purchase_request.save()

        
        return api_response(
            success=True,
            message="Request approved successfully.",
            data=self.get_serializer(purchase_request).data,
            status_code=status.HTTP_200_OK
        )
    

    # documentation for reject added here
    @extend_schema(
        summary="Reject a purchase request",
        description="Approvers can reject a PENDING request at any level. Rejection is final and stops the workflow.",
        request=ApprovalActionSerializer,
        
    )
    @action(detail=True, methods=["patch"])
    def reject(self, request, pk=None):

        serializer = ApprovalActionSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                success=False,
                message="Invalid input",
                data=None,
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )



        with transaction.atomic():
            # LOCK FOR CONCURRENCY SAFETY
            purchase_request = get_object_or_404(
                PurchaseRequest.objects.select_for_update(),
                id=pk
            )
            current_level = purchase_request.current_level
            existing = ApprovalAction.objects.filter(
            request=purchase_request,
            level=current_level,
            actor=request.user
            ).exists()

            if existing:
                return api_response(
                    success=False,
                    message="You have already acted on this request at this level.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

           
            if purchase_request.status != 'PENDING':
                return api_response(
                    success=False,
                    message="Request is already processed.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

           
            ApprovalAction.objects.create(
                request=purchase_request,
                level=purchase_request.current_level,
                action='REJECTED',
                actor=request.user,
                comment=serializer.validated_data.get('comment', '')
            )

           
            purchase_request.status = 'REJECTED'
            purchase_request.save()

        response_data = self.get_serializer(purchase_request).data

        return api_response(
            success=True,
            message="Request rejected successfully.",
            data=response_data,
            status_code=status.HTTP_200_OK
        )


    # documentation for submit_receipt added here
    @extend_schema(
        summary="Submit a receipt for an approved request",
        description="Staff can upload a receipt after a request is APPROVED. Triggers 3-way matching validation.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'receipt': {'type': 'string', 'format': 'binary', 'description': 'Receipt file (PDF/image)'}
                },
                'required': ['receipt']
            }
        },
        
    )
    @action(detail=True, methods=["post"])
    def submit_receipt(self, request, pk=None):
        purchase_request = self.get_object()

        if purchase_request.created_by != request.user:
            return api_response(
                success=False,
                message="You can only submit receipts for your own requests.",
                data=None,
                status_code=status.HTTP_403_FORBIDDEN
            )

        if purchase_request.status != 'APPROVED':
            return api_response(
                success=False,
                message="Receipt can only be submitted for approved requests.",
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReceiptUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                success=False,
                message="Invalid receipt file.",
                data=None,
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        purchase_request.receipt = serializer.validated_data['receipt']
        purchase_request.save()

        # Optional: trigger receipt validation
        try:
            validate_receipt.delay(purchase_request.id)
        except Exception as e:
            print(f"Receipt validation error: {e}")

        return api_response(
            success=True,
            message="Receipt submitted successfully.",
            data={"receipt_url": request.build_absolute_uri(purchase_request.receipt.url)},
            status_code=status.HTTP_200_OK
        )
    
    # documentation for finance_submit_invoice added here
    @extend_schema(
        summary="Finance: Upload an invoice file",
        description=(
            "Finance team uploads the invoice for a purchase request. "
            "Allows only the invoice file and triggers AI invoice extraction."
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'invoice': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Invoice file (PDF/image)'
                    }
                },
                'required': ['invoice']
            }
        },

    )
    @action(detail=True, methods=["post"], url_path="finance-submit-invoice")
    def finance_submit_invoice(self, request, pk=None):
        purchase_request = self.get_object()

        # Only Finance team should access this
        if not request.user.role == "finance":
            return api_response(
                success=False,
                message="Only finance team can upload invoices.",
                status_code=status.HTTP_403_FORBIDDEN
            )

        serializer = InvoiceUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                success=False,
                message="Invalid invoice file.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        purchase_request.invoice = serializer.validated_data["invoice"]
        purchase_request.save()

        return api_response(
            success=True,
            message="Invoice uploaded successfully.",
            data={"invoice_url": request.build_absolute_uri(purchase_request.invoice.url)},
            status_code=status.HTTP_200_OK
        )

    