from rest_framework.response import Response

def api_response(success: bool, message: str, data=None, errors=None, status_code=200, page: int = 1, limit: int = None, total_items: int = None):
    """
    Standard API response formatter with pagination-like meta.

    Args:
        success (bool): True if request succeeded.
        message (str): Human-readable message.
        data (list | dict | None): Response payload.
        errors (dict | list | None): Error details.
        status_code (int): HTTP status code.
        page (int, optional): Current page number (default 1).
        limit (int, optional): Number of items in current page.
        total_items (int, optional): Total number of items.

    Returns:
        Response: DRF Response object with consistent structure.
    """
    # if data is None:
    #     limit = 0
    #     total_items = 0
    # else:
    #     # if data is a list, count items; if dict, default to 1
    #     limit = limit or (len(data) if isinstance(data, list) else 1)
    #     total_items = total_items or (len(data) if isinstance(data, list) else 1)

    # total_pages = 1 if limit == 0 else (total_items + limit - 1) // limit  # ceil division

    # meta = {
    #     "page": page,
    #     "limit": limit,
    #     "total_pages": total_pages,
    #     "total_items": total_items,
    #     "next": None,
    #     "previous": None
    # }

    return Response(
        {
            "success": success,
            "message": message,
            "data": data,
            "errors": errors,
            # "meta": meta
        },
        status=status_code
    )
