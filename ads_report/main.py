"""
Entry point — fetches reports from all configured ad platforms and sends to Slack.

Environment variables required (set as GitHub Actions secrets):
  Meta Ads:
    META_ACCESS_TOKEN         — long-lived user/system-user token
    META_AD_ACCOUNT_IDS       — comma-separated account IDs (sem "act_"), e.g. 1234567,7654321

  Google Ads:
    GOOGLE_ADS_YAML_PATH      — path to google-ads.yaml (or set individual env vars accepted by the SDK)
    GOOGLE_ADS_CUSTOMER_IDS   — comma-separated customer IDs, e.g. 123-456-7890,098-765-4321

  LinkedIn Ads:
    LINKEDIN_ACCESS_TOKEN     — OAuth2 access token
    LINKEDIN_AD_ACCOUNT_IDS   — comma-separated account IDs, e.g. 510123456,510654321

  Slack:
    SLACK_WEBHOOK_URL         — Incoming Webhook URL

Optional:
  REPORT_DATE_START / REPORT_DATE_END  — override date range (YYYY-MM-DD). Defaults to yesterday.
"""

import os
import sys
import traceback
from typing import Optional

import meta_ads
import google_ads as gadwords
import linkedin_ads
import slack_notifier


def _ids(env_var: str) -> list[str]:
    val = os.environ.get(env_var, "").strip()
    return [v.strip() for v in val.split(",") if v.strip()] if val else []


def main():
    date_start: Optional[str] = os.environ.get("REPORT_DATE_START") or None
    date_stop: Optional[str] = os.environ.get("REPORT_DATE_END") or None

    reports = []
    errors = []

    # --- Meta Ads ---
    for acct in _ids("META_AD_ACCOUNT_IDS"):
        try:
            print(f"[Meta Ads] Buscando conta {acct}...")
            reports.append(meta_ads.fetch_report(acct, date_start, date_stop))
        except Exception as e:
            errors.append(f"Meta Ads ({acct}): {e}")
            traceback.print_exc()

    # --- Google Ads ---
    for cid in _ids("GOOGLE_ADS_CUSTOMER_IDS"):
        try:
            print(f"[Google Ads] Buscando conta {cid}...")
            reports.append(gadwords.fetch_report(cid, date_start, date_stop))
        except Exception as e:
            errors.append(f"Google Ads ({cid}): {e}")
            traceback.print_exc()

    # --- LinkedIn Ads ---
    for acct in _ids("LINKEDIN_AD_ACCOUNT_IDS"):
        try:
            print(f"[LinkedIn Ads] Buscando conta {acct}...")
            reports.append(linkedin_ads.fetch_report(acct, date_start, date_stop))
        except Exception as e:
            errors.append(f"LinkedIn Ads ({acct}): {e}")
            traceback.print_exc()

    if not reports:
        print("Nenhum report coletado. Verifique as variáveis de ambiente.", file=sys.stderr)
        sys.exit(1)

    slack_notifier.send_report(reports)

    if errors:
        print("\nErros encontrados durante a coleta:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
