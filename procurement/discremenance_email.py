from .models import PurchaseRequest
import logging
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

import base64

logger = logging.getLogger(__name__)

def send_discrepancy_email_task(self, request_id):
    """
    Generates a beautifully formatted PDF discrepancy report and emails it using SendGrid.
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

        #
        # ▶▶ Send using SendGrid
        #
        message = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=staff.email,
            subject=f"3-Way Matching Report: {pr.title}",
            html_content=(
                f"Hi {staff.first_name},<br><br>"
                f"Your detailed 3-way matching report is attached as a PDF.<br><br>"
                f"<strong>Request ID:</strong> {pr.id}<br>"
                f"<strong>PO Total:</strong> ${pr.total_amount_extracted or pr.amount}<br><br>"
                f"Best regards,<br>"
                f"Procurement System"
            )
        )

        # Attach PDF
        encoded_pdf = base64.b64encode(pdf_bytes).decode()
        attachment = Attachment(
            FileContent(encoded_pdf),
            FileName(f"3way_report_{pr.id}.pdf"),
            FileType("application/pdf"),
            Disposition("attachment")
        )
        message.attachment = attachment

        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)

        logger.info(f" PDF report sent to {staff.email} for request {request_id}")

    except Exception as exc:
        logger.error(f" PDF report task failed for request {request_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
