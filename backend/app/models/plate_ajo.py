"""Plate Ajo tables: prepaid plates at a locked price, and each prepaid plate served.

Customa never holds money: the customer transfers to the vendor's own account and the vendor
confirms it on the dashboard. These tables only keep the count. Migration:
scripts/migrations/2026-10-11_plate_ajo.sql.
"""

from datetime import datetime

from msflib.models import ModelBase
from sqlmodel import Field


class PlateBundle(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    item: str  # menu item name at the time of purchase
    unit_price: int  # naira per plate, read from the menu on the server and locked at purchase
    plates_total: int  # 5 or 10
    plates_used: int = 0
    # pending (customer says they sent the transfer) -> active (vendor confirmed) | rejected;
    # active -> finished when plates_used reaches plates_total.
    status: str = Field(default="pending", index=True)
    payer_name: str | None = None  # name on the transfer, to help the vendor match it
    confirmed_at: datetime | None = None


class PlateUse(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    bundle_id: int = Field(foreign_key="platebundle.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    plate_number: int  # 1..plates_total within the bundle
