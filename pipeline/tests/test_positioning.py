import pandas as pd

from pipeline.fetchers import cftc


def _rows(nets, start="2023-01-03", report="tff"):
    cfg = cftc.REPORTS[report]
    dates = pd.date_range(start, periods=len(nets), freq="7D")
    return [{
        cftc.DATE: f"{d:%Y-%m-%d}T00:00:00.000",
        cfg["long"]: str(1000 + max(n, 0)),
        cfg["short"]: str(1000 + max(-n, 0)),
        "open_interest_all": "10000",
    } for d, n in zip(dates, nets)]


def test_parse_rows_computes_net_and_dedupes():
    rows = _rows([100, -50])
    rows.append(dict(rows[-1]))  # duplicate date
    df = cftc.parse_rows(rows, "tff")
    assert list(df["net"]) == [100, -50]


def test_parse_rows_disaggregated_fields_and_bad_rows():
    rows = _rows([10, 20], report="disaggregated") + [{cftc.DATE: "2024-01-01", "oops": 1}]
    df = cftc.parse_rows(rows, "disaggregated")
    assert len(df) == 2 and df["net"].iloc[-1] == 20


def test_summarize_percentile_and_change():
    nets = list(range(-100, 101, 10))  # rising: latest is the 3y max
    s = cftc.summarize(cftc.parse_rows(_rows(nets), "tff"))
    assert s["net"] == 100 and s["net_prev"] == 90 and s["change_wow"] == 10
    assert s["percentile_3y"] == 100 and s["cot_index_3y"] == 100
    assert s["net_pct_oi"] == 1.0
    assert s["history"][-1] == [s["report_date"], 100]


def test_summarize_window_excludes_old_data():
    # 5 years of weekly data: an old extreme beyond 3y must not affect the range
    nets = [10_000] + [0] * 259 + [5]
    s = cftc.summarize(cftc.parse_rows(_rows(nets, start="2021-01-05"), "tff"))
    assert s["max_3y"] == 5
    assert s["weeks"] <= 158
