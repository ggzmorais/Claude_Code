"""
Meta Ads (Facebook/Instagram) — daily report fetcher.
Uses the Marketing API v21.0.
"""

import os
import requests
from datetime import date, timedelta
from typing import Optional


BASE_URL = "https://graph.facebook.com/v21.0"


def _get(path: str, params: dict) -> dict:
    params["access_token"] = os.environ["META_ACCESS_TOKEN"]
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_report(
    ad_account_id: str,
    date_start: Optional[str] = None,
    date_stop: Optional[str] = None,
) -> dict:
    """Return aggregated KPIs + per-campaign breakdown for one Meta ad account."""
    yesterday = date.today() - timedelta(days=1)
    date_start = date_start or str(yesterday)
    date_stop = date_stop or str(yesterday)

    # --- Active campaigns ---
    campaigns_resp = _get(
        f"/act_{ad_account_id}/campaigns",
        {
            "fields": "id,name,status",
            "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE"]}]',
            "limit": 200,
        },
    )
    active_campaigns = campaigns_resp.get("data", [])

    # --- Insights at account level ---
    account_insights = _get(
        f"/act_{ad_account_id}/insights",
        {
            "fields": "spend,impressions,reach,frequency,clicks,actions,landing_page_views",
            "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
            "level": "account",
        },
    )

    # --- Insights per campaign ---
    campaign_insights = _get(
        f"/act_{ad_account_id}/insights",
        {
            "fields": "campaign_name,campaign_id,spend,impressions,reach,frequency,clicks,actions,landing_page_views",
            "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
            "level": "campaign",
            "limit": 200,
        },
    )

    account_data = (account_insights.get("data") or [{}])[0]
    total_spend = float(account_data.get("spend", 0))

    def _extract_action(actions: list, action_type: str) -> int:
        for a in actions or []:
            if a.get("action_type") == action_type:
                return int(a.get("value", 0))
        return 0

    def _parse_campaign(row: dict) -> dict:
        actions = row.get("actions", [])
        leads = _extract_action(actions, "lead") or _extract_action(actions, "onsite_conversion.lead_grouped")
        spend = float(row.get("spend", 0))
        cpl = round(spend / leads, 2) if leads else None
        return {
            "id": row.get("campaign_id"),
            "name": row.get("campaign_name"),
            "spend": spend,
            "impressions": int(row.get("impressions", 0)),
            "reach": int(row.get("reach", 0)),
            "frequency": round(float(row.get("frequency", 0)), 2),
            "clicks": int(row.get("clicks", 0)),
            "landing_page_views": int(row.get("landing_page_views") or 0),
            "leads": leads,
            "cpl": cpl,
        }

    campaigns_data = [_parse_campaign(r) for r in campaign_insights.get("data", [])]

    # Account-level aggregates
    actions = account_data.get("actions", [])
    total_leads = _extract_action(actions, "lead") or _extract_action(actions, "onsite_conversion.lead_grouped")
    total_cpl = round(total_spend / total_leads, 2) if total_leads else None

    return {
        "platform": "Meta Ads",
        "account_id": ad_account_id,
        "date": date_start,
        "active_campaigns_count": len(active_campaigns),
        "total_spend": total_spend,
        "total_impressions": int(account_data.get("impressions", 0)),
        "total_reach": int(account_data.get("reach", 0)),
        "total_frequency": round(float(account_data.get("frequency", 0)), 2),
        "total_clicks": int(account_data.get("clicks", 0)),
        "total_landing_page_views": int(account_data.get("landing_page_views") or 0),
        "total_leads": total_leads,
        "total_cpl": total_cpl,
        "campaigns": campaigns_data,
    }
