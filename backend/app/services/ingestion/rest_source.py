"""Stub REST-pull DataSource.

Proves the integration abstraction without building a real third-party
connector. In a future phase, this would connect to QuickBooks, Stripe,
Xero, etc. For now, it returns a mock response.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import DataSource, Integration


async def create_rest_data_source(
    db: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    provider: str,
    entity_type: str,
) -> DataSource:
    """Create a REST data source for a given provider and entity type."""
    # Create the integration if it doesn't exist
    integration = Integration(
        organization_id=org_id,
        name=f"{provider} Integration",
        provider=provider,
        config={"type": "rest", "base_url": f"https://api.{provider}.example.com"},
    )
    db.add(integration)
    await db.flush()

    data_source = DataSource(
        organization_id=org_id,
        integration_id=integration.id,
        name=name,
        entity_type=entity_type,
        source_type="rest",
        config={
            "method": "GET",
            "endpoint": f"/v1/{entity_type}",
            "pagination": "cursor",
        },
    )
    db.add(data_source)
    await db.flush()
    return data_source


async def pull_from_rest_source(
    db: AsyncSession,
    data_source_id: uuid.UUID,
    org_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Pull data from a REST data source (stub — returns empty list).

    In production, this would:
    1. Read the data source config (base_url, endpoint, auth)
    2. Make the API call
    3. Parse the response
    4. Return normalized rows
    """
    # Stub: in a real implementation, this would make an HTTP request
    return []
