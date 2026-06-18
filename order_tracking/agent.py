"""Five specialist agents for an order-tracking workflow.

Each agent is independent — no shared state, no dependency on another agent's
output — which makes them ideal to run concurrently with ``asyncio.gather``
(see ``async_runner.py``). A ``root_agent`` is also exposed so the project works
with ``adk web .`` for interactive testing.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
import os
model_name = os.getenv("SHIPPING_MODEL", "gpt-4o")

from .tools import (
    check_inventory,
    get_order_status,
    get_payment_status,
    get_shipping_details,
)

MODEL = "gemini-3-flash-preview"

# ---------------------------------------------------------------------------
# 1. Order status agent
# ---------------------------------------------------------------------------
order_status_agent = Agent(
    name="order_status_agent",
    #model=MODEL,
    model=LiteLlm(model=model_name),
    description="Reports the high-level fulfilment status of an order.",
    instruction=(
        "You are an order status specialist. Use the get_order_status tool to "
        "look up the order and report its current status, when it was placed, "
        "and the items it contains. Be concise and factual."
    ),
    tools=[get_order_status],
)

# ---------------------------------------------------------------------------
# 2. Shipping agent
# ---------------------------------------------------------------------------
shipping_agent = Agent(
    name="shipping_agent",
    model=LiteLlm(model=model_name),
    description="Tracks carrier, tracking number and delivery ETA.",
    instruction=(
        "You are a shipping and logistics specialist. Use the "
        "get_shipping_details tool to report the carrier, tracking number and "
        "estimated delivery date. If the order has not shipped yet, say so "
        "clearly."
    ),
    tools=[get_shipping_details],
)

# ---------------------------------------------------------------------------
# 3. Inventory agent
# ---------------------------------------------------------------------------
inventory_agent = Agent(
    name="inventory_agent",
    model=LiteLlm(model=model_name),
    description="Checks stock levels and reorder needs for ordered items.",
    instruction=(
        "You are an inventory specialist. Given a SKU, use the check_inventory "
        "tool to report on-hand quantity and whether the item needs reordering. "
        "Flag any out-of-stock items explicitly."
    ),
    tools=[check_inventory],
)

# ---------------------------------------------------------------------------
# 4. Payment agent
# ---------------------------------------------------------------------------
payment_agent = Agent(
    name="payment_agent",
    model=LiteLlm(model=model_name),
    description="Verifies the payment / billing state of an order.",
    instruction=(
        "You are a payments specialist. Use the get_payment_status tool to "
        "report whether the payment is authorized, captured or failed, along "
        "with the amount and currency. Do not expose card details."
    ),
    tools=[get_payment_status],
)

# ---------------------------------------------------------------------------
# 5. Customer support agent (coordinator / summarizer)
# ---------------------------------------------------------------------------
support_agent = Agent(
    name="support_agent",
    model=LiteLlm(model=model_name),
    description="Composes a friendly customer-facing summary of an order.",
    instruction=(
        "You are a customer support agent. You may be given findings from the "
        "order status, shipping, inventory and payment specialists. Combine "
        "them into a single clear, friendly update for the customer. Lead with "
        "the most important information (where is my order, when will it "
        "arrive) and keep it under five sentences."
    ),
    tools=[
        get_order_status,
        get_shipping_details,
        get_payment_status,
    ],
)

# Convenience collection used by the async runner.
ORDER_AGENTS = [
    order_status_agent,
    shipping_agent,
    inventory_agent,
    payment_agent,
    support_agent,
]

# Root agent for `adk web .` — delegates to the specialists.
root_agent = Agent(
    name="order_tracking_coordinator",
    model=LiteLlm(model=model_name),
    description="Coordinates the order-tracking specialist agents.",
    instruction=(
        "You are the order-tracking coordinator. Route requests to the right "
        "specialist: order_status_agent for status, shipping_agent for "
        "delivery, inventory_agent for stock, payment_agent for billing, and "
        "support_agent to write the final customer summary."
    ),
    sub_agents=ORDER_AGENTS,
)
