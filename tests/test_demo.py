"""Demo mode: deterministic, one-click, repeatable."""

from kthma.demo import run_demo


def test_demo_is_deterministic_and_repeatable():
    assert run_demo() == run_demo()


def test_demo_shows_all_four_scenarios_and_recovers_money():
    out = run_demo()
    assert "A - Payment failure" in out
    assert "B - Checkout abandonment" in out
    assert "C - Subscription failure" in out
    assert "D - Do nothing" in out
    assert "[VERIFY]" in out
    recovered_line = next(ln for ln in out.splitlines() if ln.startswith("Revenue recovered"))
    assert int(recovered_line.split("Rs")[1]) > 0


def test_demo_scenario_d_refuses_to_retry():
    out = run_demo()
    scenario_d = out.split("D - Do nothing")[1].split("\n\n")[0]
    assert "action=do_nothing" in scenario_d


def test_demo_banner_present():
    assert "DEMO MERCHANT · SYNTHETIC DATA" in run_demo()
