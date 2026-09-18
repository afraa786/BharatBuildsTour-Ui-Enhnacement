from uuid import UUID

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.catalog.service import search_products
from app.modules.inventory.schemas import InventoryCheckIn
from app.modules.inventory.service import check_stock


class SearchProductsInput(BaseModel):
    query: str = Field(description="The product name, SKU, or alias to search for")


class CheckInventoryInput(BaseModel):
    product_id: str = Field(description="The UUID of the product")
    requested_qty: float = Field(description="The quantity requested")
    requested_unit: str | None = Field(
        default=None, description="The unit requested (e.g. 'box', 'piece')"
    )


def build_commerce_tools(db: Session, business_id: UUID) -> list[StructuredTool]:
    """
    Builds tools for the commerce agent, strictly scoped to the business_id.
    """

    def _search_products(query: str) -> list[dict]:
        """Search for products in the catalog."""
        products = search_products(db, business_id, query)
        return [
            {
                "id": str(p.product_id),
                "name": p.name,
                "sku": p.sku,
                "sellable_unit": p.sellable_unit,
                "price_paise": p.base_unit_price_paise,
                "gst_rate_bps": p.gst_rate_bps,
            }
            for p in products
        ]

    def _check_inventory(
        product_id: str, requested_qty: float, requested_unit: str | None = None
    ) -> dict:
        """Check real-time stock availability for a product."""
        try:
            pid = UUID(product_id)
        except ValueError:
            return {"error": "Invalid product_id format"}

        try:
            result = check_stock(
                db,
                business_id,
                InventoryCheckIn(
                    business_id=business_id,
                    run_id="agent-check",
                    product_id=pid,
                    requested_qty=str(requested_qty),
                    requested_unit=requested_unit,
                ),
            )
            return {
                "status": result.status.value,
                "available_qty": str(result.available_qty),
                "stock_unit": result.stock_unit,
                "substitutes": [
                    {"id": str(s.product_id), "name": s.name, "reason": s.reason}
                    for s in result.substitutes
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    return [
        StructuredTool.from_function(
            func=_search_products,
            name="search_products",
            description="Search for products in the catalog. Returns ID, name, sku, and price.",
            args_schema=SearchProductsInput,
        ),
        StructuredTool.from_function(
            func=_check_inventory,
            name="check_inventory",
            description="Check real-time stock availability for a specific product ID.",
            args_schema=CheckInventoryInput,
        ),
    ]
