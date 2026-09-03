from __future__ import annotations

"""Best-effort passthrough to GitHub's official user-level billing usage API.

Uses the GitHub CLI (``gh``) already authenticated on this machine so this
application never reads, stores, or commits any GitHub credential itself -
``gh`` handles its own token via the OS keyring. If ``gh`` is missing,
unauthenticated, lacking the required token scope, or the account/plan has no
billing data exposed, every function here returns ``{"ok": False, "reason":
...}`` and the caller (ai_usage_service) falls back to the existing manual
AiUsageCreditEntry path.

No web pages are ever scraped - only the documented REST endpoint
``GET /users/{username}/settings/billing/ai_credit/usage``.
"""

import json
import shutil
import subprocess
from datetime import datetime, timezone

GH_BINARY = shutil.which("gh")
_TIMEOUT_SECONDS = 15


def _run_gh_api(path: str) -> dict:
    if not GH_BINARY:
        return {"ok": False, "reason": "GitHub CLI (gh) is not installed / not on PATH."}

    try:
        proc = subprocess.run(
            [GH_BINARY, "api", path],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": f"Failed to run gh CLI: {exc}"}

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if "scope" in stderr.lower():
            return {
                "ok": False,
                "reason": (
                    "GitHub CLI token is missing the required 'user' scope. "
                    "Run: gh auth refresh -h github.com -s user"
                ),
            }
        if "404" in stderr or "Not Found" in stderr:
            return {
                "ok": False,
                "reason": "GitHub billing usage API returned 404 (not available for this account/plan).",
            }
        return {"ok": False, "reason": stderr or "gh api call failed."}

    try:
        return {"ok": True, "data": json.loads(proc.stdout)}
    except (json.JSONDecodeError, ValueError):
        return {"ok": False, "reason": "gh api returned non-JSON output."}


def get_authenticated_username() -> dict:
    result = _run_gh_api("user")
    if not result["ok"]:
        return result

    login = result["data"].get("login")
    if not login:
        return {"ok": False, "reason": "Could not determine the authenticated GitHub username."}
    return {"ok": True, "username": login}


def fetch_month_ai_credit_usage(username: str, year: int, month: int) -> dict:
    """Sum ``grossQuantity`` (AI credits consumed, pre-discount) for one month."""
    result = _run_gh_api(f"/users/{username}/settings/billing/ai_credit/usage?year={year}&month={month}")
    if not result["ok"]:
        return result

    items = result["data"].get("usageItems", [])
    total = sum(float(item.get("grossQuantity") or 0) for item in items)

    model_breakdown: dict[str, float] = {}
    for item in items:
        model = item.get("model") or "unknown"
        model_breakdown[model] = model_breakdown.get(model, 0.0) + float(item.get("grossQuantity") or 0)

    return {"ok": True, "credits_used": total, "usage_items": items, "model_breakdown": model_breakdown}


def fetch_month_to_date_credits_used() -> dict:
    """Cumulative month-to-date AI credits used for the authenticated GitHub user.

    ``credits_used`` matches the semantics of the existing manual
    ``AiUsageCreditEntry.credits_used`` field (a running total-to-date), so it
    can be stored through the same table without changing its schema.
    """
    username_result = get_authenticated_username()
    if not username_result["ok"]:
        return username_result

    today = datetime.now(timezone.utc).date()
    usage_result = fetch_month_ai_credit_usage(username_result["username"], today.year, today.month)
    if not usage_result["ok"]:
        return usage_result

    return {
        "ok": True,
        "username": username_result["username"],
        "credits_used": usage_result["credits_used"],
        "model_breakdown": usage_result["model_breakdown"],
    }
