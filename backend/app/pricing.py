from dataclasses import dataclass
from decimal import Decimal

ONE_MILLION = Decimal(1_000_000)
COST_PRECISION = Decimal("0.00000001")


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    output_per_million: Decimal


# Prices in US dollars per million tokens.
PRICES: dict[str, ModelPrice] = {
    # Made-up prices so cost tracking can be tested without a real provider.
    "mock-1": ModelPrice(input_per_million=Decimal("1.00"), output_per_million=Decimal("2.00")),
    # Gemini 3.5 Flash-Lite paid list price as of November 2026. On the free tier the real
    # charge is zero, so this records what the same usage would cost at list price.
    "gemini-flash": ModelPrice(
        input_per_million=Decimal("0.30"), output_per_million=Decimal("2.50")
    ),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Estimated cost in US dollars, or None if the model has no known price."""
    price = PRICES.get(model)
    if price is None:
        return None

    cost = (
        Decimal(input_tokens) * price.input_per_million
        + Decimal(output_tokens) * price.output_per_million
    ) / ONE_MILLION
    return cost.quantize(COST_PRECISION)