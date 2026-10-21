"""Download one month of NYC TLC yellow taxi trips."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import requests

from taxi_elt.config import Settings

log = logging.getLogger(__name__)


class MonthNotPublishedError(RuntimeError):
    """TLC publishes each month with a ~2 month delay; the file is not there yet."""


def file_name(month: date) -> str:
    return f"yellow_tripdata_{month:%Y-%m}.parquet"


def download_month(month: date, settings: Settings, *, overwrite: bool = False) -> Path:
    """Download the parquet file for `month` into DATA_DIR/landing and return its path.

    The download is written to a temp file and renamed, so a crashed run never
    leaves a half-written file that a retry would treat as complete.
    """
    target = settings.data_dir / "landing" / file_name(month)
    if target.exists() and not overwrite:
        log.info("Already downloaded: %s", target)
        return target

    url = f"{settings.tlc_base_url}/{file_name(month)}"
    log.info("Downloading %s", url)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")

    with requests.get(url, stream=True, timeout=60) as resp:
        # CloudFront answers 403 (not 404) for files that don't exist yet.
        if resp.status_code in (403, 404):
            raise MonthNotPublishedError(f"{url} returned {resp.status_code}")
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)

    tmp.replace(target)
    log.info("Saved %s (%.1f MB)", target, target.stat().st_size / 1e6)
    return target
