"""
Google Ads — daily report fetcher.
Uses google-ads-python SDK with OAuth2 / service-account credentials.
"""

import os
from datetime import date, timedelta
from typing import Optional


def _get_client():
    from google.ads.googleads.client import GoogleAdsClient  # type: ignore

    # Credentials are read from GOOGLE_ADS_YAML_PATH or env vars set in workflow.
    yaml_path = os.environ.get("GOOGLE_ADS_YAML_PATH", "google-ads.yaml")
    return GoogleAdsClient.load_from_storage(yaml_path)


def fetch_report(
    customer_id: str,
    date_start: Optional[str] = None,
    date_stop: Optional[str] = None,
) -> dict:
    """Return aggregated KPIs + per-campaign breakdown for one Google Ads account."""
    yesterday = date.today() - timedelta(days=1)
    date_start = date_start or str(yesterday)
    date_stop = date_stop or str(yesterday)

    client = _get_client()
    service = client.get_service("GoogleAdsService")
    cid = customer_id.replace("-", "")

    # Active campaigns
    campaigns_query = f"""
        SELECT campaign.id, campaign.name, campaign.status
        FROM campaign
        WHERE campaign.status = 'ENABLED'
              AND segments.date BETWEEN '{date_start}' AND '{date_stop}'
    """
    active = list(service.search(customer_id=cid, query=campaigns_query))

    # Insights per campaign
    insights_query = f"""
        SELECT
            campaign.id,
            campaign.name,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.average_cpc,
            metrics.conversions,
            metrics.cost_per_conversion,
            metrics.view_through_conversions
        FROM campaign
        WHERE campaign.status = 'ENABLED'
              AND segments.date BETWEEN '{date_start}' AND '{date_stop}'
    """
    rows = list(service.search(customer_id=cid, query=insights_query))

    def _parse(row) -> dict:
        m = row.metrics
        spend = m.cost_micros / 1_000_000
        leads = m.conversions
        cpl = round(spend / leads, 2) if leads else None
        return {
            "id": str(row.campaign.id),
            "name": row.campaign.name,
            "spend": round(spend, 2),
            "impressions": m.impressions,
            "clicks": m.clicks,
            "landing_page_views": m.view_through_conversions,
            "leads": round(leads, 0),
            "cpl": cpl,
            "frequency": None,  # not available at campaign level in Google Ads
        }

    campaigns_data = [_parse(r) for r in rows]
    total_spend = sum(c["spend"] for c in campaigns_data)
    total_leads = sum(c["leads"] for c in campaigns_data)
    total_cpl = round(total_spend / total_leads, 2) if total_leads else None

    return {
        "platform": "Google Ads",
        "account_id": customer_id,
        "date": date_start,
        "active_campaigns_count": len(active),
        "total_spend": total_spend,
        "total_impressions": sum(c["impressions"] for c in campaigns_data),
        "total_clicks": sum(c["clicks"] for c in campaigns_data),
        "total_landing_page_views": sum(c["landing_page_views"] for c in campaigns_data),
        "total_leads": total_leads,
        "total_cpl": total_cpl,
        "total_frequency": None,
        "total_reach": None,
        "campaigns": campaigns_data,
    }
