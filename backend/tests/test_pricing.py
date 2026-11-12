from decimal import Decimal

from app.pricing import estimate_cost


def test_one_million_input_tokens_costs_the_input_price() -> None:
    assert estimate_cost("mock-1", 1_000_000, 0) == Decimal("1.00")


def test_small_request_cost_is_calculated_exactly() -> None:
    # (2 x $1 + 5 x $2) per million tokens = $0.000012
    assert estimate_cost("mock-1", 2, 5) == Decimal("0.000012")


def test_unknown_model_has_no_cost() -> None:
    assert estimate_cost("not-a-model", 100, 100) is None


def test_gemini_flash_uses_its_list_price() -> None:
        assert estimate_cost("gemini-flash", 1_000_000, 1_000_000) == Decimal("2.80")