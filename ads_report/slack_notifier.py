"""
Formats and sends the daily ads report to a Slack channel via Incoming Webhook.
"""

import os
import json
import requests
from typing import Optional


def _currency(value: Optional[float], symbol: str = "R$") -> str:
    if value is None:
        return "—"
    return f"{symbol} {value:,.2f}"


def _num(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}"


def _build_platform_block(report: dict) -> list:
    platform = report["platform"]
    emoji = {"Meta Ads": ":facebook:", "Google Ads": ":google:", "LinkedIn Ads": ":linkedin:"}.get(platform, ":bar_chart:")
    currency = "R$"

    header = {
        "type": "header",
        "text": {"type": "plain_text", "text": f"{emoji}  {platform} — {report['date']}"},
    }

    summary = (
        f"*Conta:* `{report['account_id']}`\n"
        f"*Campanhas ativas:* {_num(report['active_campaigns_count'])}\n"
        f"*Total investido:* {_currency(report['total_spend'], currency)}\n"
        f"*Impressões:* {_num(report['total_impressions'])}"
        + (f"   *Alcance:* {_num(report['total_reach'])}" if report.get('total_reach') else "")
        + (f"   *Frequência:* {report['total_frequency']}" if report.get('total_frequency') else "") + "\n"
        f"*Cliques:* {_num(report['total_clicks'])}"
        + (f"   *Visualiz. pág. destino:* {_num(report['total_landing_page_views'])}" if report.get('total_landing_page_views') else "") + "\n"
        f"*Leads:* {_num(report['total_leads'])}   *CPL:* {_currency(report['total_cpl'], currency)}"
    )

    blocks = [
        header,
        {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
    ]

    # Per-campaign table (top 10 by spend)
    campaigns = sorted(report.get("campaigns", []), key=lambda c: c["spend"], reverse=True)[:10]
    if campaigns:
        rows = []
        for c in campaigns:
            freq = f"  Freq {c['frequency']}" if c.get("frequency") else ""
            rows.append(
                f"• *{c['name']}*\n"
                f"  Invest: {_currency(c['spend'], currency)}  |  Leads: {_num(c['leads'])}  |  CPL: {_currency(c['cpl'], currency)}{freq}"
            )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Campanhas (top por investimento):*\n" + "\n".join(rows)},
        })

    blocks.append({"type": "divider"})
    return blocks


def send_report(reports: list[dict], webhook_url: Optional[str] = None) -> None:
    """Post all platform reports to Slack."""
    url = webhook_url or os.environ["SLACK_WEBHOOK_URL"]

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":mega:  *Report Diário de Mídia Paga*"},
        },
        {"type": "divider"},
    ]

    for report in reports:
        blocks.extend(_build_platform_block(report))

    payload = {"blocks": blocks}
    resp = requests.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=15)
    resp.raise_for_status()
    print("Slack notificado com sucesso.")
