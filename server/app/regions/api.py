"""`GET /v1/regions`: the regions the app can plan in (public, no sign-in)."""

from fastapi import APIRouter, Request

from app.regions.service import load_regions

router = APIRouter(prefix="/v1/regions", tags=["regions"])


@router.get("")
async def list_regions(request: Request):
    async with request.app.state.db.transaction() as conn:
        regions = await load_regions(conn)
    return {"regions": [region.to_json() for region in regions]}
