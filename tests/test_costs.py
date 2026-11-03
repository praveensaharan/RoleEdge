from roleedge.costs import PRICES_PER_1M, dollars
from roleedge.llm import Usage


def test_cached_tokens_are_billed_at_the_cached_rate():
    price = PRICES_PER_1M["azure gpt-5-mini (measured)"]  # 0.25 / 0.025 / 2.00 per 1M
    usage = Usage(input=1_000_000, cached=400_000, output=100_000)
    assert round(dollars(usage, price), 4) == round(0.6 * 0.25 + 0.4 * 0.025 + 0.1 * 2.00, 4)


def test_usage_adds_up():
    assert Usage(1, 2, 3, 4) + Usage(10, 20, 30, 40) == Usage(11, 22, 33, 44)
