"""Rules and municipal waste sorting guidelines router."""

from fastapi import APIRouter

from backend.app.core.exceptions import EntityNotFoundError
from backend.app.schemas import RuleResponse
from backend.app.services.municipal_rules import (
    DEFAULT_CITY,
    get_city,
    list_cities,
    normalize_city,
)

router = APIRouter()


@router.get("/rules", response_model=dict)
def get_all_rules():
    """Retrieve supported municipalities for disposal rules."""
    return {"supported_cities": list_cities(), "default_city": DEFAULT_CITY}


@router.get("/rules/{city}", response_model=RuleResponse)
def get_city_rules(city: str):
    """Retrieve waste sorting rules for a specific municipality."""
    city_data = get_city(city)
    if city_data is None:
        raise EntityNotFoundError(
            f"City '{city}' not found. Supported cities: {list_cities()}",
        )

    return RuleResponse(
        city=normalize_city(city),
        rules=city_data["rules"],
        source_url=city_data["source_url"],
    )
