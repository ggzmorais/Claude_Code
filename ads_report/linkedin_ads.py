"""
LinkedIn Ads — daily report fetcher.
Uses LinkedIn Marketing API v2 with OAuth2 access token.
"""

import os
import requests
from datetime import date, timedelta
from typing import Optional


BASE_URL = "https://api.linkedin.com/v2"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['LINKEDIN_ACCESS_TOKEN']}",
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_report(
    ad_account_id: str,
    date_start: Optional[str] = None,
    date_stop: Optional[str] = None,
) -> dict:
    """Return aggregated KPIs + per-campaign breakdown for one LinkedIn ad account."""
    yesterday = date.today() - timedelta(days=1)
    ds = date_start or str(yesterday)
    de = date_stop or str(yesterday)

    start = date.fromisoformat(ds)
    end = date.fromisoformat(de)

    # Active campaigns
    campaigns_resp = _get(
        "/adCampaignsV2",
        {
            "q": "search",
            "search.account.values[0]": f"urn:li:sponsoredAccount:{ad_account_id}",
            "search.status.values[0]": "ACTIVE",
            "fields": "id,name,status",
            "count": 200,
        },
    )
    active_campaigns = campaigns_resp.get("elements", [])

    # Analytics — account level
    account_analytics = _get(
        "/adAnalyticsV2",
        {
            "q": "analytics",
            "pivot": "ACCOUNT",
            "dateRange.start.year": start.year,
            "dateRange.start.month": start.month,
            "dateRange.start.day": start.day,
            "dateRange.end.year": end.year,
            "dateRange.end.month": end.month,
            "dateRange.end.day": end.day,
            "timeGranularity": "ALL",
            "accounts[0]": f"urn:li:sponsoredAccount:{ad_account_id}",
            "fields": "costInLocalCurrency,impressions,clicks,landingPageClicks,leadGenerationMailContactInfoShares,oneClickLeads,externalWebsiteConversions",
        },
    )

    # Analytics — campaign level
    campaign_analytics = _get(
        "/adAnalyticsV2",
        {
            "q": "analytics",
            "pivot": "CAMPAIGN",
            "dateRange.start.year": start.year,
            "dateRange.start.month": start.month,
            "dateRange.start.day": start.day,
            "dateRange.end.year": end.year,
            "dateRange.end.month": end.month,
            "dateRange.end.day": end.day,
            "timeGranularity": "ALL",
            "accounts[0]": f"urn:li:sponsoredAccount:{ad_account_id}",
            "fields": "pivotValues,costInLocalCurrency,impressions,clicks,landingPageClicks,leadGenerationMailContactInfoShares,oneClickLeads,externalWebsiteConversions",
        },
    )

    # Campaign id → name map
    campaign_names = {str(c["id"]): c.get("name", str(c["id"])) for c in active_campaigns}

    def _parse_row(row: dict, campaign_id: str = None) -> dict:
        spend = float(row.get("costInLocalCurrency", 0))
        leads = int(row.get("oneClickLeads", 0)) + int(row.get("leadGenerationMailContactInfoShares", 0))
        cpl = round(spend / leads, 2) if leads else None
        return {
            "id": campaign_id,
            "name": campaign_names.get(campaign_id, campaign_id),
            "spend": round(spend, 2),
            "impressions": int(row.get("impressions", 0)),
            "clicks": int(row.get("clicks", 0)),
            "landing_page_views": int(row.get("landingPageClicks", 0)),
            "leads": leads,
            "cpl": cpl,
            "frequency": None,
        }

    campaigns_data = []
    for row in campaign_analytics.get("elements", []):
        pivot_vals = row.get("pivotValues", [])
        cid = pivot_vals[0].split(":")[-1] if pivot_vals else None
        campaigns_data.append(_parse_row(row, cid))

    acct_row = (account_analytics.get("elements") or [{}])[0]
    total_spend = float(acct_row.get("costInLocalCurrency", 0))
    total_leads = int(acct_row.get("oneClickLeads", 0)) + int(acct_row.get("leadGenerationMailContactInfoShares", 0))
    total_cpl = round(total_spend / total_leads, 2) if total_leads else None

    return {
        "platform": "LinkedIn Ads",
        "account_id": ad_account_id,
        "date": ds,
        "active_campaigns_count": len(active_campaigns),
        "total_spend": round(total_spend, 2),
        "total_impressions": int(acct_row.get("impressions", 0)),
        "total_clicks": int(acct_row.get("clicks", 0)),
        "total_landing_page_views": int(acct_row.get("landingPageClicks", 0)),
        "total_leads": total_leads,
        "total_cpl": total_cpl,
        "total_frequency": None,
        "total_reach": None,
        "campaigns": campaigns_data,
    }
