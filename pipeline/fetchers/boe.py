"""Bank of England data (free, no key).

* IADB (Interactive Statistical Database) CSV download: Bank Rate, gilt
  par/zero yields at 5/10/20y, BoE spot FX. The host returns 403 to
  non-browser clients, so requests pass browser headers.
* GLC nominal yield-curve spreadsheets: the only free source of a daily 2-year
  gilt yield. The current-month zip is small (~300 KB); the full archive
  (~40 MB) is only downloaded to bootstrap history when we have none yet.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime

import pandas as pd

from .http import browser_headers, get

IADB = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
GLC_LATEST = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip"
GLC_ARCHIVE = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/glcnominalddata.zip"
YIELD_CURVE_PAGE = "https://www.bankofengland.co.uk/statistics/yield-curves"


def series_url(code: str) -> str:
    """Human-readable IADB page for a series."""
    return (
        "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
        f"?Travel=NIxAZxSUx&FromSeries=1&ToSeries=50&DAT=ALL&CSVF=TT&html.x=66&html.y=26"
        f"&SeriesCodes={code}&UsingCodes=Y&Filter=N&title={code}&VPD=Y"
    )


# ── IADB ───────────────────────────────────────────────────────────────────

def parse_iadb_csv(text: str) -> dict[str, pd.Series]:
    """Parse an IADB CSV (CSVF=TN layout: DATE,<code>,<code>...; dates like '02 Jan 2024').

    Returns one float Series per code with NaNs dropped. Raises ValueError if the
    payload is not a CSV (IADB answers unknown codes with an HTML error page).
    """
    head = text.lstrip()[:200].lower()
    if head.startswith("<") or "date" not in head.split("\n", 1)[0]:
        raise ValueError("IADB did not return CSV (bad series code or blocked request)")
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() for c in df.columns]
    idx = pd.to_datetime(df["DATE"].astype(str).str.strip(), format="%d %b %Y", errors="coerce")
    out = {}
    for col in df.columns[1:]:
        s = pd.Series(pd.to_numeric(df[col], errors="coerce").values, index=idx).dropna()
        s = s[s.index.notna()].sort_index()
        s.name = col
        out[col] = s.astype(float)
    return out


def fetch_iadb(codes: list[str], start: str | date = "2000-01-01") -> dict[str, pd.Series]:
    start_d = pd.Timestamp(start)
    r = get(IADB, params={
        "csv.x": "yes", "Datefrom": start_d.strftime("%d/%b/%Y"), "Dateto": "now",
        "SeriesCodes": ",".join(codes), "CSVF": "TN", "UsingCodes": "Y", "VPD": "Y", "VFD": "N",
    }, headers=browser_headers(Accept="text/csv,*/*"), timeout=45)
    return parse_iadb_csv(r.text)


# ── GLC nominal spot curve (2-year gilt) ───────────────────────────────────

def parse_glc_sheet(rows, tenor_years: float) -> pd.Series:
    """Extract one tenor from a GLC '4. spot curve' sheet given as row tuples.

    Layout: a header row starting 'years:' lists maturities; data rows start with a
    datetime in column 0. Empty strings / None are missing values.
    """
    col = None
    data = {}
    for row in rows:
        if not row:
            continue
        first = row[0]
        if isinstance(first, str) and first.strip().lower().startswith("years"):
            for j, v in enumerate(row):
                if isinstance(v, (int, float)) and abs(float(v) - tenor_years) < 1e-6:
                    col = j
                    break
            continue
        if col is not None and isinstance(first, (datetime, date)):
            v = row[col] if col < len(row) else None
            if isinstance(v, (int, float)):
                data[pd.Timestamp(first)] = float(v)
    if col is None:
        raise ValueError(f"tenor {tenor_years}y not found in GLC sheet")
    s = pd.Series(data, dtype=float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _sheet_rows(xlsx_bytes: bytes, sheet: str = "4. spot curve"):
    import openpyxl  # lazy: only the UK section needs it
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    try:
        return list(wb[sheet].iter_rows(values_only=True))
    finally:
        wb.close()


def _glc_from_zip(content: bytes, tenor: float, name_filter) -> pd.Series:
    z = zipfile.ZipFile(io.BytesIO(content))
    parts = [parse_glc_sheet(_sheet_rows(z.read(n)), tenor)
             for n in z.namelist() if "Nominal" in n and n.endswith(".xlsx") and name_filter(n)]
    if not parts:
        raise ValueError("no nominal GLC workbook in zip")
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="last")]


def fetch_glc_spot(tenor: float, bootstrap: bool = False) -> pd.Series:
    """Daily nominal zero-coupon (spot) gilt yield for `tenor` years.

    Always reads the current-month file. With bootstrap=True, also reads the
    2016+ workbooks from the full archive to build ~10 years of history.
    """
    hdr = browser_headers()
    latest = _glc_from_zip(get(GLC_LATEST, headers=hdr, timeout=60).content, tenor, lambda n: True)
    if not bootstrap:
        return latest
    def recent(n: str) -> bool:  # noqa: E306 - '2016 to 2024', '2025 to present'
        try:
            return int(n.rsplit("_", 1)[-1][:4]) >= 2016
        except ValueError:
            return False
    hist = _glc_from_zip(get(GLC_ARCHIVE, headers=hdr, timeout=180).content, tenor, recent)
    s = pd.concat([hist, latest]).sort_index()
    return s[~s.index.duplicated(keep="last")]
