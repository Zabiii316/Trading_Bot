from trading_market_data.backoff import ExponentialBackoff


def test_backoff_caps_and_resets():
    backoff = ExponentialBackoff(initial_delay_s=1, max_delay_s=4, jitter_s=0)
    assert backoff.next_delay() == 1
    assert backoff.next_delay() == 2
    assert backoff.next_delay() == 4
    assert backoff.next_delay() == 4
    backoff.reset()
    assert backoff.next_delay() == 1
