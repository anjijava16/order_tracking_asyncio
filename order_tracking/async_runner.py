"""Async orchestration for the order-tracking agents.

This mirrors the "many at once" pattern: each specialist agent is wrapped in a
coroutine (`run_agent_task`) and the whole batch is fired concurrently with
`asyncio.gather`. Wall-clock time is roughly the slowest agent, not the sum.

A streaming variant (`run_all_streaming`) uses `asyncio.as_completed` to surface
each result the moment its agent finishes.

Run it:

    uv run python -m order_tracking.async_runner ORD-1001
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

# Support both module execution (`python -m order_tracking.async_runner`) and
# direct script execution (`python order_tracking/async_runner.py`).
try:
    from .agent import ORDER_AGENTS, support_agent
except ImportError:  # pragma: no cover - path execution fallback
    from order_tracking.agent import ORDER_AGENTS, support_agent

APP_NAME = "order_tracking_demo"


@dataclass
class AgentResult:
    """The final text response produced by a single agent run."""

    agent: str
    response: str | None


# ---------------------------------------------------------------------------
# Run a single agent as an isolated async task
# ---------------------------------------------------------------------------
async def run_agent_task(
    agent: Agent,
    session_service: InMemorySessionService,
    user_id: str,
    session_id: str,
    prompt: str,
) -> AgentResult:
    """Run one agent to completion and return its final response.

    A distinct ``session_id`` per task prevents session-state collisions when
    agents run concurrently.
    """
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    final_response: str | None = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    return AgentResult(agent=agent.name, response=final_response)


def _prompt_for(agent_name: str, order_id: str) -> str:
    """Build an agent-specific prompt for an order id."""
    prompts = {
        "order_status_agent": f"What is the status of order {order_id}?",
        "shipping_agent": f"Where is order {order_id} and when will it arrive?",
        "inventory_agent": (
            f"Check stock for the items in order {order_id}. "
            "If you don't know the SKUs, check SKU-APL-01, SKU-KBD-07 and "
            "SKU-MON-22."
        ),
        "payment_agent": f"What is the payment status of order {order_id}?",
        "support_agent": (
            f"Write a friendly status update for the customer about order "
            f"{order_id}."
        ),
    }
    return prompts.get(agent_name, f"Help with order {order_id}.")


# ---------------------------------------------------------------------------
# Many at once — wait for all (asyncio.gather)
# ---------------------------------------------------------------------------
async def run_all(order_id: str) -> list[AgentResult]:
    """Run every specialist agent concurrently and return all results.

    ``return_exceptions=True`` ensures one agent failing does not abort the
    whole batch.
    """
    session_service = InMemorySessionService()

    tasks = [
        run_agent_task(
            agent=agent,
            session_service=session_service,
            user_id=f"user_{i}",
            session_id=f"session_{i}",
            prompt=_prompt_for(agent.name, order_id),
        )
        for i, agent in enumerate(ORDER_AGENTS)
    ]

    start = time.time()
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start

    results: list[AgentResult] = []
    for agent, item in zip(ORDER_AGENTS, raw):
        if isinstance(item, Exception):
            results.append(AgentResult(agent=agent.name, response=f"ERROR: {item}"))
        else:
            results.append(item)

    print(f"\n--- Completed {len(results)} agents in {elapsed:.2f}s ---\n")
    for r in results:
        print(f"[{r.agent}]\n{r.response}\n")
    return results


# ---------------------------------------------------------------------------
# Real-time — surface results as each agent finishes (asyncio.as_completed)
# ---------------------------------------------------------------------------
async def run_all_streaming(order_id: str) -> None:
    """Run all agents concurrently and print each result as it completes."""
    session_service = InMemorySessionService()

    tasks = [
        run_agent_task(
            agent=agent,
            session_service=session_service,
            user_id=f"user_{i}",
            session_id=f"stream_{i}",
            prompt=_prompt_for(agent.name, order_id),
        )
        for i, agent in enumerate(ORDER_AGENTS)
    ]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        preview = (result.response or "")[:80]
        print(f"[{result.agent}] done -> {preview}...")


# ---------------------------------------------------------------------------
# Fan-out then summarize — specialists in parallel, support agent last
# ---------------------------------------------------------------------------
async def run_and_summarize(order_id: str) -> str | None:
    """Run the four data specialists in parallel, then have support summarize.

    Demonstrates combining concurrent fan-out with a dependent final step.
    """
    session_service = InMemorySessionService()
    specialists = [a for a in ORDER_AGENTS if a is not support_agent]

    tasks = [
        run_agent_task(
            agent=agent,
            session_service=session_service,
            user_id=f"user_{i}",
            session_id=f"sum_{i}",
            prompt=_prompt_for(agent.name, order_id),
        )
        for i, agent in enumerate(specialists)
    ]
    findings = await asyncio.gather(*tasks, return_exceptions=True)

    bullets = []
    for agent, item in zip(specialists, findings):
        text = f"ERROR: {item}" if isinstance(item, Exception) else item.response
        bullets.append(f"- {agent.name}: {text}")
    combined = "\n".join(bullets)

    summary = await run_agent_task(
        agent=support_agent,
        session_service=session_service,
        user_id="user_summary",
        session_id="session_summary",
        prompt=(
            f"Here are the specialist findings for order {order_id}:\n{combined}\n\n"
            "Write a single friendly customer update."
        ),
    )
    print("\n--- Customer summary ---\n")
    print(summary.response)
    return summary.response


async def _main() -> None:
    order_id = sys.argv[1] if len(sys.argv) > 1 else "ORD-1001"
    print(f"Tracking order {order_id} across {len(ORDER_AGENTS)} agents...\n")
    await run_all(order_id)


if __name__ == "__main__":
    asyncio.run(_main())
