from pathlib import Path

from trading_monitoring.alerts import alert_names, load_alert_rules
from trading_monitoring.dashboard import dashboard_titles, load_dashboard

ROOT = Path(__file__).resolve().parents[4]


def test_prometheus_alert_rules_are_parseable_and_include_kill_switch():
    rules = load_alert_rules(ROOT / "infra" / "prometheus" / "rules" / "trading_bot_alerts.yml")
    names = alert_names(rules)

    assert "KillSwitchActive" in names
    assert "OrderBookSequenceUnhealthy" in names
    assert "EmergencyFlattenActive" in names


def test_grafana_dashboards_are_valid_and_have_panels():
    directory = ROOT / "infra" / "grafana" / "dashboards"
    titles = dashboard_titles(directory)

    assert "Trading Bot - Market Data Health" in titles
    assert "Trading Bot - Strategy Health" in titles
    assert "Trading Bot - Execution & Risk" in titles
    for path in directory.glob("*.json"):
        dashboard = load_dashboard(path)
        assert len(dashboard["panels"]) >= 8
