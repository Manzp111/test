from celery import shared_task
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.core.mail import EmailMessage,send_mail
from django.db import transaction
from django.conf import settings
from weasyprint import HTML

# Local imports
from .models import PurchaseRequest
from .document_processing import extract_text_from_any_pdf, parse_with_ai
from .ai_matching import are_items_same

import logging



logger = logging.getLogger(__name__) # Configure logger for this module

@shared_task
def process_proforma(request_id):
    """Process proforma with automatic format detection"""
    from .models import PurchaseRequest
    
    pr = PurchaseRequest.objects.get(id=request_id)
    
    try:
        raw_text = extract_text_from_any_pdf(pr.proforma)
        logger.info(f"Extracted {len(raw_text)} characters from request {request_id}")
        
        # Parse with AI
        structured_data = parse_with_ai(raw_text)
        
        # Save results
        pr.vendor_name = structured_data.get("vendor_name", "")[:255]
        pr.vendor_address = structured_data.get("vendor_address", "")
        pr.items_json = structured_data.get("items", [])
        pr.total_amount_extracted = structured_data.get("total_amount")
        pr.payment_terms = structured_data.get("payment_terms", "")
        pr.extraction_status = "SUCCESS"
        
        logger.info(f"Successfully processed proforma for request {request_id}")
        
    except Exception as e:
        error_msg = str(e)[:300]  # Truncate long errors
        logger.error(f"Extraction failed for {request_id}: {error_msg}")
        
        pr.extraction_status = "FAILED"
        pr.vendor_address = f"Processing error: {error_msg}"
    
    pr.save()





@shared_task
def generate_purchase_order(request_id):
    """
    Generate a PDF Purchase Order and email it to the request creator.
    """
    try:
        pr = PurchaseRequest.objects.get(id=request_id)

        if pr.status != "APPROVED":
            logger.warning(f"Skipping PO generation for non-approved request {request_id}")
            return
        items_with_totals = []
        for item in pr.items_json:
            item_copy = item.copy()
            item_copy["total_price"] = float(item["price"]) * int(item["quantity"])
            items_with_totals.append(item_copy)


        # Render Template → HTML string
        html_string = render_to_string("emails/po.html", {"purchase_request": pr,"items": items_with_totals,})

        #  Convert HTML → PDF bytes
        pdf_bytes = HTML(string=html_string).write_pdf()

        # Save PDF to model field
        filename = f"PO_{pr.id}.pdf"
        pr.purchase_order.save(filename, ContentFile(pdf_bytes), save=True)

        # Email the PDF to request creator
        if pr.created_by and pr.created_by.email:
            email = EmailMessage(
                subject=f"Purchase Order #{pr.id} Approved",
                body=(
                    f"Hello {pr.created_by.last_name + pr.created_by.first_name},\n\n"
                    f"Your purchase request titled '{pr.title}' has been fully approved.\n"
                    f"The Purchase Order is attached.\n\n"
                    f"Thank you.\n"
                ),
                to=[pr.created_by.email],
            )

            email.attach(filename, pdf_bytes, "application/pdf")
            email.send()

            logger.info(f" PO emailed to {pr.created_by.email}")

        logger.info(f" Purchase Order generated and emailed for request {request_id}")

    except Exception as e:
        logger.error(f" PO generation failed for request {request_id}: {e}")

        # Clean-up fallback: remove invalid PO file
        try:
            pr = PurchaseRequest.objects.get(id=request_id)
            pr.purchase_order = None
            pr.save()
        except:
            pass







@shared_task(bind=True, max_retries=2)
def validate_receipt(self, request_id):
    """
    Performs intelligent 3-way matching between:
    - Purchase Order (from proforma AI extraction)
    - Receipt (uploaded by staff)
    
    Implements Payhawk-style matching with:
    - AI semantic item comparison
    - Custom discrepancy thresholds (±5% price, ±10% quantity)
    - Vendor matching
    - Email alerts on discrepancies
    """
    try:
        pr = PurchaseRequest.objects.get(id=request_id)
        
        if not pr.receipt:
            logger.warning(f"No receipt uploaded for request {request_id}")
            return

        # 1. EXTRACT DATA FROM RECEIPT USING AI-DRIVEN OCR
        receipt_text = extract_text_from_any_pdf(pr.receipt)
        receipt_data = parse_with_ai(receipt_text)
        
        # 2. GET PO DATA (FROM PROFORMA AI EXTRACTION)
        po_items = pr.items_json 
        po_vendor = pr.vendor_name or ""
        po_total = pr.total_amount_extracted or pr.amount

        # 3. COMPARE VENDOR NAMES
        receipt_vendor = (receipt_data.get("vendor_name") or "").strip()
        vendor_match = False
        if po_vendor and receipt_vendor:
            vendor_match = are_items_same(po_vendor, receipt_vendor)

        # 4. COMPARE ITEMS WITH AI SEMANTIC MATCHING
        discrepancies = []
        all_item_issues = []
        receipt_items = receipt_data.get("items", [])
        matched_receipt_items = set()

        # Match PO items to receipt items
        for po_item in po_items:
            po_name = po_item.get("name", "").strip()
            po_price = float(po_item.get("price", 0))
            po_qty = int(po_item.get("quantity", 0))
            
            if not po_name:
                continue

            matched = False
            for rcpt_idx, rcpt_item in enumerate(receipt_items):
                if rcpt_idx in matched_receipt_items:
                    continue
                    
                rcpt_name = rcpt_item.get("name", "").strip()
                rcpt_price = float(rcpt_item.get("price", 0))
                rcpt_qty = int(rcpt_item.get("quantity", 0))
                
                if not rcpt_name:
                    continue

                #  AI SEMANTIC MATCHING
                if are_items_same(po_name, rcpt_name):
                    matched = True
                    matched_receipt_items.add(rcpt_idx)
                    
                    # Validate price tolerance (±5%)
                    price_ok = True
                    if po_price > 0:
                        price_diff_pct = abs(po_price - rcpt_price) / po_price * 100
                        if price_diff_pct > float(pr.amount_tolerance_percent):
                            price_ok = False
                            all_item_issues.append({
                                "type": "price",
                                "item": po_name,
                                "expected_price": po_price,
                                "received_price": rcpt_price,
                                "tolerance_pct": float(pr.amount_tolerance_percent),
                                "difference_pct": round(price_diff_pct, 2)
                            })
                    
                    # Validate quantity tolerance (±10%)
                    qty_ok = True
                    if po_qty > 0:
                        qty_diff_pct = abs(po_qty - rcpt_qty) / po_qty * 100
                        if qty_diff_pct > float(pr.quantity_tolerance_percent):
                            qty_ok = False
                            all_item_issues.append({
                                "type": "quantity",
                                "item": po_name,
                                "expected_quantity": po_qty,
                                "received_quantity": rcpt_qty,
                                "tolerance_pct": float(pr.quantity_tolerance_percent),
                                "difference_pct": round(qty_diff_pct, 2)
                            })
                    
                    if not (price_ok and qty_ok):
                        discrepancies.append("item_mismatch")
                    break

            if not matched:
                discrepancies.append("missing_item")
                all_item_issues.append({
                    "type": "missing_item",
                    "item": po_name,
                    "expected": f"{po_qty} units @ ${po_price}",
                    "message": "Item not found in receipt"
                })

        # Check for extra items in receipt
        for rcpt_idx, rcpt_item in enumerate(receipt_items):
            if rcpt_idx not in matched_receipt_items:
                rcpt_name = rcpt_item.get("name", "").strip()
                if rcpt_name:
                    discrepancies.append("extra_item")
                    all_item_issues.append({
                        "type": "extra_item",
                        "item": rcpt_name,
                        "message": "Item in receipt not found in purchase order"
                    })

        # 5. UPDATE MATCHING STATUS
        with transaction.atomic():
            pr = PurchaseRequest.objects.select_for_update().get(id=request_id)
            
            if discrepancies:
                pr.three_way_match_status = "DISCREPANCY"
                pr.discrepancy_details = {
                    "receipt_validation": all_item_issues,
                    "vendor_match": vendor_match,
                    "po_vendor": po_vendor,
                    "receipt_vendor": receipt_vendor,
                    "receipt_items_raw": receipt_items
                }
                pr.save()
                send_discrepancy_email_task.delay(request_id)
            else:
                pr.three_way_match_status = "MATCHED"
                pr.discrepancy_details = {"vendor_match": vendor_match}
                pr.save()

        logger.info(
            f" 3-way matching completed for request {request_id}. "
            f"Status: {pr.three_way_match_status}, Issues: {len(discrepancies)}"
        )

    except Exception as exc:
        error_msg = str(exc)[:500]
        logger.error(f"3-way matching failed for request {request_id}: {error_msg}")
        
        try:
            with transaction.atomic():
                pr = PurchaseRequest.objects.select_for_update().get(id=request_id)
                pr.three_way_match_status = "DISCREPANCY"
                pr.discrepancy_details = {"error": error_msg}
                pr.save()
        except Exception as save_exc:
            logger.error(f"Failed to update matching status: {save_exc}")

        raise self.retry(exc=exc, countdown=60)
    


@shared_task(bind=True, max_retries=3)
def send_discrepancy_email_task(self, request_id):
    """
    Generates a beautifully formatted PDF discrepancy report and emails it.
    """
    try:
       

        pr = PurchaseRequest.objects.get(id=request_id)
        staff = pr.created_by
        
        if not staff or not staff.email:
            logger.warning(f"No email for staff on request {request_id}")
            return

        details = pr.discrepancy_details
        receipt_items = {item.get("name", "").lower(): item for item in details.get("receipt_items_raw", [])}
        po_items = {item.get("name", "").lower(): item for item in pr.items_json}

        vendor_match = details.get("vendor_match", True)

        all_items = set(po_items.keys()) | set(receipt_items.keys())
        matched_count = 0
        rows = []

        # Build rows for HTML table
        for item_name in sorted(all_items):
            po_item = po_items.get(item_name)
            rcpt_item = receipt_items.get(item_name)

            row = {
                "name": item_name.title(),
                "po_price": po_item["price"] if po_item else "-",
                "receipt_price": rcpt_item["price"] if rcpt_item else "-",
                "po_qty": po_item["quantity"] if po_item else "-",
                "receipt_qty": rcpt_item["quantity"] if rcpt_item else "-"
            }

            # Determine status
            if po_item and rcpt_item:
                price_ok = qty_ok = True

                if po_item["price"] > 0:
                    price_diff_pct = abs(po_item["price"] - rcpt_item["price"]) / po_item["price"] * 100
                    if price_diff_pct > float(pr.amount_tolerance_percent):
                        price_ok = False

                if po_item["quantity"] > 0:
                    qty_diff_pct = abs(po_item["quantity"] - rcpt_item["quantity"]) / po_item["quantity"] * 100
                    if qty_diff_pct > float(pr.quantity_tolerance_percent):
                        qty_ok = False

                if price_ok and qty_ok:
                    row["status"] = "MATCHED"
                    matched_count += 1
                else:
                    row["status"] = "MISMATCH"

            elif po_item:
                row["status"] = "MISSING_IN_RECEIPT"
            elif rcpt_item:
                row["status"] = "EXTRA_IN_RECEIPT"

            rows.append(row)

        issues_count = len(all_items) - matched_count

        # Build HTML using template
        context = {
            "pr": pr,
            "staff": staff,
            "details": details,
            "vendor_match": vendor_match,
            "items": rows,
            "matched_count": matched_count,
            "issues_count": issues_count,
            "total_items": len(all_items),
            "po_total": pr.total_amount_extracted or pr.amount,
            "receipt_total": details.get("receipt_total", "-"),
        }

        html_string = render_to_string("email/matching_report.html", context)
        pdf_bytes = HTML(string=html_string).write_pdf()

        # Send email with attached PDF
        email = EmailMessage(
            subject=f"3-Way Matching Report: {pr.title}",
            body=(
                f"Hi {staff.first_name},\n\n"
                f"Your detailed 3-way matching report is attached as a PDF.\n\n"
                f"Request ID: {pr.id}\n"
                f"PO Total: ${pr.total_amount_extracted or pr.amount}\n\n"
                f"Best regards,\nProcurement System"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[staff.email],
        )

        email.attach(f"3way_report_{pr.id}.pdf", pdf_bytes, "application/pdf")
        email.send()

        logger.info(f" PDF report sent to {staff.email} for request {request_id}")

    except Exception as exc:
        logger.error(f" PDF report task failed for request {request_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
