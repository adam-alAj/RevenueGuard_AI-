"""Tenant-scoped repository base class (ADR-003).

Every data-access class MUST inherit from TenantScopedRepository. The base
class ensures that:
1. All SELECT queries automatically filter by organization_id.
2. All INSERT operations automatically set organization_id.
3. organization_id is NEVER accepted from client input — it comes from the
   authenticated user's JWT session.

This is the single point of enforcement for multi-tenant isolation at the
repository layer. A coding agent cannot accidentally write an unscoped query
without bypassing this base class.
"""

from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class TenantScopedRepository(Generic[ModelType]):
    """Base repository that enforces tenant (organization) scoping on all queries.

    Every downstream repository (CustomerRepository, ContractRepository, etc.)
    inherits from this class and receives organization_id from the authenticated
    user context — never from a request parameter.
    """

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    def _scope_query(self, query: Select) -> Select:
        """Apply organization_id filter to a query."""
        # Get the model's table to check if it has organization_id
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(query.column_descriptions[0]["entity"])
        if hasattr(mapper.class_, "organization_id"):
            return query.where(mapper.class_.organization_id == self.organization_id)
        return query

    async def get_by_id(self, model: type[ModelType], entity_id: uuid.UUID) -> ModelType | None:
        """Get a single entity by ID, scoped to the current organization."""
        query = select(model).where(model.id == entity_id)
        query = self._scope_query(query)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        model: type[ModelType],
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Get all entities of a type, scoped to the current organization."""
        query = select(model).offset(offset).limit(limit)
        query = self._scope_query(query)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, instance: ModelType) -> ModelType:
        """Persist a new entity with organization_id set."""
        # Ensure organization_id is set
        if hasattr(instance, "organization_id"):
            instance.organization_id = self.organization_id
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, model: type[ModelType], entity_id: uuid.UUID) -> bool:
        """Delete an entity by ID, scoped to the current organization."""
        entity = await self.get_by_id(model, entity_id)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True
