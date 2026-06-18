"""Tools for the order tracking agents.

These are plain Python functions (ADK `FunctionTool`s). In a real system they
would query an OMS, a warehouse API, a carrier API and a payment gateway. Here
they return deterministic mock data keyed by ``order_id`` so the agents — and
their evaluations — are reproducible.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Mock data store (stands in for OMS / WMS / carrier / payment systems)
# ---------------------------------------------------------------------------
_ORDERS: dict[str, dict] = {
    "ORD-1001": {
        "status": "shipped",
        "placed_at": "2026-06-05",
        "items": [{"sku": "SKU-APL-01", "name": "Wireless Earbuds", "qty": 1}],
        "carrier": "UPS",
        "tracking_number": "1Z999AA10123456784",
        "eta": "2026-06-11",
        "warehouse": "WH-WEST",
        "payment": {"state": "captured", "amount": 129.99, "currency": "USD"},
    },
    "ORD-1002": {
        "status": "processing",
        "placed_at": "2026-06-09",
        "items": [{"sku": "SKU-KBD-07", "name": "Mechanical Keyboard", "qty": 2}],
        "carrier": None,
        "tracking_number": None,
        "eta": "2026-06-14",
        "warehouse": "WH-EAST",
        "payment": {"state": "authorized", "amount": 259.98, "currency": "USD"},
    },
    "ORD-1003": {
        "status": "delivered",
        "placed_at": "2026-05-28",
        "items": [{"sku": "SKU-MON-22", "name": "27-inch Monitor", "qty": 1}],
        "carrier": "FedEx",
        "tracking_number": "7790 1234 5678",
        "eta": "2026-06-02",
        "warehouse": "WH-WEST",
        "payment": {"state": "captured", "amount": 319.00, "currency": "USD"},
    },
}

_INVENTORY: dict[str, dict] = {
    "SKU-APL-01": {"name": "Wireless Earbuds", "on_hand": 142, "reorder_point": 50},
    "SKU-KBD-07": {"name": "Mechanical Keyboard", "on_hand": 8, "reorder_point": 20},
    "SKU-MON-22": {"name": "27-inch Monitor", "on_hand": 0, "reorder_point": 10},
}


def get_order_status(order_id: str) -> dict:
    """Return the high-level fulfilment status for an order.

    Args:
        order_id: The order identifier, e.g. ``"ORD-1001"``.

    Returns:
        A dict with ``status``, ``placed_at`` and ``items`` keys, or an error.
    """
    order = _ORDERS.get(order_id.strip().upper())
    if not order:
        return {"status": "error", "message": f"Order {order_id} not found."}
    return {
        "status": "success",
        "order_id": order_id.strip().upper(),
        "order_status": order["status"],
        "placed_at": order["placed_at"],
        "items": order["items"],
    }


def get_shipping_details(order_id: str) -> dict:
    """Return carrier, tracking number and ETA for an order.

    Args:
        order_id: The order identifier, e.g. ``"ORD-1001"``.

    Returns:
        A dict with shipment details, or an error if the order is unknown.
    """
    order = _ORDERS.get(order_id.strip().upper())
    if not order:
        return {"status": "error", "message": f"Order {order_id} not found."}
    return {
        "status": "success",
        "carrier": order["carrier"],
        "tracking_number": order["tracking_number"],
        "eta": order["eta"],
        "shipped": order["status"] in ("shipped", "delivered"),
    }


def check_inventory(sku: str) -> dict:
    """Return stock levels for a SKU and whether a reorder is needed.

    Args:
        sku: The stock keeping unit, e.g. ``"SKU-KBD-07"``.

    Returns:
        A dict with on-hand quantity and a reorder flag, or an error.
    """
    item = _INVENTORY.get(sku.strip().upper())
    if not item:
        return {"status": "error", "message": f"SKU {sku} not found."}
    return {
        "status": "success",
        "sku": sku.strip().upper(),
        "name": item["name"],
        "on_hand": item["on_hand"],
        "reorder_needed": item["on_hand"] <= item["reorder_point"],
    }


def get_payment_status(order_id: str) -> dict:
    """Return the payment/billing state for an order.

    Args:
        order_id: The order identifier, e.g. ``"ORD-1001"``.

    Returns:
        A dict with payment state, amount and currency, or an error.
    """
    order = _ORDERS.get(order_id.strip().upper())
    if not order:
        return {"status": "error", "message": f"Order {order_id} not found."}
    payment = order["payment"]
    return {
        "status": "success",
        "payment_state": payment["state"],
        "amount": payment["amount"],
        "currency": payment["currency"],
    }
