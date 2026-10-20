"""Generate the Tableau workbook tableau/bank_dashboard.twb from the extracts in tableau/data/.

The workbook only displays the precomputed, validated values written by
notebooks/08_tableau_extracts.ipynb. It computes no metric itself: aggregation is off on every
sheet, so each row of an extract is one mark. The .twb file holds the layout and the paths to the
CSV files, not the data, so it can be committed. Run from the project root:

    python -I tableau/build_workbook.py

then open tableau/bank_dashboard.twb in Tableau Desktop (tested with 2026.2). The layout follows
tableau/dashboard_spec.md.
"""
import csv
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "bank_dashboard.twb"

COLORS = {"BBCA": "#2a78d6", "BBRI": "#eb6834", "BMRI": "#1baf7a", "IHSG": "#52514e"}
INK, MUTED = "#0b0b0b", "#52514e"
PCT = 'n#,##0.00"%";-#,##0.00"%"'
NUM2 = "n#,##0.00;-#,##0.00"
NUM1 = "n#,##0.0;-#,##0.0"
PTS = 'n#,##0.0" pts";-#,##0.0" pts"'

# file, then (column, datatype, caption, number format) in the CSV's column order
SOURCES = {
    "kpi": ("kpi.csv", [
        ("ticker", "string", "Instrument", None), ("price_return_pct", "real", "Price return 2021-26", PCT),
        ("total_return_pct", "real", "Total return incl. dividends", PCT), ("sharpe", "real", "Sharpe ratio", NUM2),
        ("sharpe_diff_vs_ihsg", "real", "Sharpe minus IHSG", NUM2), ("sharpe_diff_p", "real", "p-value", NUM2),
        ("beta", "real", "Beta", NUM2), ("r2", "real", "R-squared", NUM2)]),
    "daily": ("daily_series.csv", [
        ("trade_date", "date", "Date", None), ("ticker", "string", "Instrument", None), ("regime", "string", "Regime", None),
        ("growth_index", "real", "Growth of 100", NUM1), ("drawdown_pct", "real", "Drawdown", PCT),
        ("rolling_sharpe_252", "real", "Rolling 252-day Sharpe ratio", NUM2)]),
    "metrics": ("period_metrics.csv", [
        ("period", "string", "Period", None), ("period_order", "integer", "Period order", None),
        ("ticker", "string", "Instrument", None), ("basis", "string", "Return basis", None),
        ("n_days", "integer", "Return days", None), ("cum_return_pct", "real", "Cumulative return", PCT),
        ("ann_return_pct", "real", "Annualized return", PCT), ("ann_vol_pct", "real", "Annualized volatility", PCT),
        ("sharpe", "real", "Sharpe ratio", NUM2), ("sharpe_ci_low", "real", "Sharpe 95% low", NUM2),
        ("sharpe_ci_high", "real", "Sharpe 95% high", NUM2), ("mdd_pct", "real", "Maximum drawdown", PCT)]),
    "sdiff": ("sharpe_difference.csv", [
        ("period", "string", "Period", None), ("period_order", "integer", "Period order", None),
        ("ticker", "string", "Instrument", None), ("sharpe_bank", "real", "Sharpe ratio (bank)", NUM2),
        ("sharpe_ihsg", "real", "Sharpe ratio (IHSG)", NUM2), ("delta", "real", "Sharpe minus IHSG", NUM2),
        ("ci_low", "real", "95% interval low", NUM2), ("ci_high", "real", "95% interval high", NUM2),
        ("p_value", "real", "p-value", NUM2), ("p_holm", "real", "Holm-adjusted p", NUM2),
        ("significant_5pct", "string", "Significant at 5%", None), ("label", "string", "Label", None)]),
    "capm": ("capm.csv", [
        ("period", "string", "Period", None), ("period_order", "integer", "Period order", None),
        ("ticker", "string", "Instrument", None), ("n", "integer", "Return days", None), ("beta", "real", "Beta", NUM2),
        ("beta_ci_low", "real", "Beta 95% low", NUM2), ("beta_ci_high", "real", "Beta 95% high", NUM2),
        ("p_beta_eq_1", "real", "p (beta = 1)", NUM2), ("p_beta_eq_1_holm", "real", "Holm-adjusted p (beta = 1)", NUM2),
        ("p_beta_eq_1_newey_west", "real", "Newey-West p (beta = 1)", NUM2), ("r2", "real", "R-squared", NUM2),
        ("r2_ci_low", "real", "R-squared 95% low", NUM2), ("r2_ci_high", "real", "R-squared 95% high", NUM2),
        ("alpha_ann_pct", "real", "Annualized intercept", PCT), ("alpha_p", "real", "p (intercept)", NUM2)]),
    "implied": ("market_implied.csv", [
        ("period", "string", "Period", None), ("period_order", "integer", "Period order", None),
        ("ticker", "string", "Instrument", None), ("beta", "real", "Beta", NUM2),
        ("ihsg_return_pct", "real", "IHSG return", PCT), ("actual_pct", "real", "Actual return", PCT),
        ("market_implied_pct", "real", "Market-implied return", PCT),
        ("gap_pct_points", "real", "Not accounted for by market exposure", PTS)]),
    "regimes": ("regimes.csv", [
        ("regime", "string", "Regime", None), ("regime_order", "integer", "Regime order", None),
        ("label", "string", "Label", None), ("start_date", "string", "Start", None), ("end_date", "string", "End", None),
        ("return_days", "integer", "Return days", None)]),
}
DIMENSION_INTEGERS = {"period_order", "regime_order"}
CALCS = {  # row-level widths of the intervals, used as Gantt bar sizes
    "sdiff": [("ci_width", "Interval width", "[ci_high] - [ci_low]")],
    "capm": [("beta_ci_width", "Beta interval width", "[beta_ci_high] - [beta_ci_low]"),
             ("r2_ci_width", "R-squared interval width", "[r2_ci_high] - [r2_ci_low]")],
}
PARAMETERS = [("Zero", "real", "0.0"), ("One", "real", "1.0"), ("Hundred", "real", "100.0"),
              ("R2 start", "datetime", "#2022-08-23 00:00:00#"), ("R3 start", "datetime", "#2024-09-18 00:00:00#"),
              ("Stub start", "datetime", "#2026-05-20 00:00:00#")]


def a(value):
    """Escape a value for a single-quoted XML attribute."""
    return "'" + escape(str(value), {"'": "&apos;", '"': "&quot;"}) + "'"


def ds_name(key):
    return f"federated.{key}"


def kind_of(key, col):
    dtype = next((d for c, d, _, _ in SOURCES[key][1] if c == col), "real")
    if dtype == "string" or col in DIMENSION_INTEGERS:
        return "dim"
    if dtype == "date":
        return "date"
    return "meas"


def inst(col, kind):
    return {"dim": f"[none:{col}:nk]", "date": f"[tdy:{col}:qk]", "meas": f"[none:{col}:qk]"}[kind]


def ref(key, col, kind=None):
    return f"[{ds_name(key)}].{inst(col, kind or kind_of(key, col))}"


# --- data sources ------------------------------------------------------------------

def check_headers():
    for key, (file, cols) in SOURCES.items():
        with open(DATA / file, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        expected = [c for c, *_ in cols]
        if header != expected:
            raise SystemExit(f"{file}: columns {header} do not match the expected {expected}. Rerun notebook 08.")


def column_meta(key, col, dtype, caption, fmt):
    kind = kind_of(key, col)
    role = "measure" if kind == "meas" else "dimension"
    typ = {"dim": "nominal", "date": "ordinal", "meas": "quantitative"}[kind]
    if col in DIMENSION_INTEGERS:
        typ = "ordinal"
    fmt_attr = f" default-format={a(fmt)}" if fmt else ""
    return f"<column caption={a(caption)} datatype='{dtype}'{fmt_attr} name='[{col}]' role='{role}' type='{typ}' />"


def datasource(key):
    file, cols = SOURCES[key]
    rel_cols = "\n".join(f"            <column datatype='{d}' name={a(c)} ordinal='{i}' />" for i, (c, d, _, _) in enumerate(cols))
    meta = "\n".join("      " + column_meta(key, *c) for c in cols)
    calcs = "\n".join(
        f"      <column caption={a(cap)} datatype='real' default-format={a(NUM2)} name='[{name}]' role='measure' type='quantitative'>"
        f"<calculation class='tableau' formula={a(formula)} /></column>" for name, cap, formula in CALCS.get(key, []))
    palette = ""
    if any(c == "ticker" for c, *_ in cols):
        maps = "".join(f"<map to='{color}'><bucket>&quot;{t}&quot;</bucket></map>" for t, color in COLORS.items())
        palette = (f"      <style><style-rule element='mark'><encoding attr='color' field='[none:ticker:nk]' type='palette'>"
                   f"{maps}</encoding></style-rule></style>")
    table = "[" + file.replace(".", "#") + "]"
    return f"""    <datasource caption={a(file[:-4])} inline='true' name='{ds_name(key)}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption={a(file[:-4])} name='textscan.{key}'>
            <connection class='textscan' directory={a(DATA.as_posix())} filename={a(file)} password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection='textscan.{key}' name={a(file)} table={a(table)} type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>
{rel_cols}
          </columns>
        </relation>
      </connection>
      <aliases enabled='yes' />
{meta}
{calcs}
      <layout dim-ordering='alphabetic' dim-percentage='0.5' measure-ordering='alphabetic' measure-percentage='0.4' show-structure='false' />
{palette}
    </datasource>"""


def parameters():
    cols = []
    for name, dtype, value in PARAMETERS:
        cols.append(f"      <column caption={a(name)} datatype='{dtype}' name={a('[' + name + ']')} param-domain-type='any' "
                    f"role='measure' type='quantitative' value={a(value)}><calculation class='tableau' formula={a(value)} /></column>")
    return ("    <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>\n      <aliases enabled='yes' />\n"
            + "\n".join(cols) + "\n    </datasource>")


# --- worksheets ----------------------------------------------------------------------

def dependencies(key, cols, calc_names=(), agg=False):
    out = []
    file_cols = {c: (d, cap, fmt) for c, d, cap, fmt in SOURCES[key][1]}
    calcs = {n: (cap, f) for n, cap, f in CALCS.get(key, [])}
    for col in sorted(set(cols) | set(calc_names)):
        if col in calcs:
            cap, formula = calcs[col]
            out.append(f"            <column caption={a(cap)} datatype='real' name='[{col}]' role='measure' type='quantitative'>"
                       f"<calculation class='tableau' formula={a(formula)} /></column>")
            kind = "meas"
        else:
            d, cap, fmt = file_cols[col]
            out.append("            " + column_meta(key, col, d, cap, fmt))
            kind = kind_of(key, col)
        derivation = "Day-Trunc" if kind == "date" else ("Sum" if agg and kind == "meas" else "None")
        typ = {"dim": "nominal", "date": "quantitative", "meas": "quantitative"}[kind]
        name = f"[sum:{col}:qk]" if agg and kind == "meas" else inst(col, kind)
        out.append(f"            <column-instance column='[{col}]' derivation='{derivation}' name='{name}' pivot='key' type='{typ}' />")
    return "\n".join(out)


def tooltip(parts):
    runs = []
    for p in parts:
        if isinstance(p, tuple):
            runs.append(f"<run fontname='Tableau Bold'><![CDATA[<{p[0]}>]]></run>")
        else:
            runs.append(f"<run fontcolor='{MUTED}'>{escape(p)}</run>")
    return "<customized-tooltip><formatted-text>" + "".join(runs) + "</formatted-text></customized-tooltip>"


def refline(axis_ref, param, rid, label=None):
    lab = f" label={a(label)} label-type='custom'" if label else " label-type='none'"
    return (f"<reference-line axis-column={a(axis_ref)} enable-instant-analytics='false' formula='average' id='{rid}'{lab} "
            f"scope='per-table' value-column={a('[Parameters].[' + param + ']')} z-order='1' />")


def pane(mark, encodings="", tip="", reflines="", pid=None, axis=None, labels=False, mark_style=""):
    # Tableau's schema fixes the order inside a pane: encodings, reference lines, tooltip, style
    pid_attr = f" id='{pid}'" if pid is not None else ""
    axis_attr = f" x-axis-name={a(axis)}" if axis else ""
    fmt = ("<format attr='mark-labels-show' value='true' />" if labels else "") + mark_style
    style = f"<style><style-rule element='mark'>{fmt}</style-rule></style>" if fmt else ""
    return (f"<pane{pid_attr} selection-relaxation-option='selection-relaxation-allow'{axis_attr}><view><breakdown value='auto' /></view>"
            f"<mark class='{mark}' /><encodings>{encodings}</encodings>{reflines}{tip}{style}</pane>")


def title_xml(title, caption=None):
    runs = f"<run fontcolor='{INK}' fontname='Tableau Semibold' fontsize='11'>{escape(title)}</run>"
    if caption:
        runs += f"<run fontcolor='{MUTED}' fontsize='9'>&#10;{escape(caption)}</run>"
    return f"<layout-options><title><formatted-text>{runs}</formatted-text></title></layout-options>"


def worksheet(name, key, cols, rows, columns, panes_xml, title, caption=None, calcs=(), filters="", style="", agg=False, slices=""):
    return f"""    <worksheet name={a(name)}>
      {title_xml(title, caption)}
      <table>
        <view>
          <datasources>
            <datasource caption={a(SOURCES[key][0][:-4])} name='{ds_name(key)}' />
            <datasource name='Parameters' />
          </datasources>
          <datasource-dependencies datasource='{ds_name(key)}'>
{dependencies(key, cols, calcs, agg)}
          </datasource-dependencies>
          {filters}
          {slices}
          <aggregation value='{"true" if agg else "false"}' />
        </view>
        <style>{sheet_palette(key)}{style}</style>
        <panes>{panes_xml}</panes>
        <rows>{escape(rows)}</rows>
        <cols>{escape(columns)}</cols>
      </table>
    </worksheet>"""


def sheet_palette(key):
    if not any(c == "ticker" for c, *_ in SOURCES[key][1]):
        return ""
    maps = "".join(f"<map to='{color}'><bucket>&quot;{t}&quot;</bucket></map>" for t, color in COLORS.items())
    return (f"<style-rule element='mark'><encoding attr='color' field={a(ref(key, 'ticker'))} type='palette'>{maps}</encoding>"
            "</style-rule>")


def tip_field(key, col):
    return (ref(key, col), col)


def hide_header(key):
    # the instrument is identified by colour and the legend; its row header only overlaps at this size
    return (f"<style-rule element='header'><format attr='display' class='0' field={a(ref(key, 'ticker'))} scope='rows' "
            "value='false' /></style-rule>")


def interval_sheet(name, key, low, high, point, width_calc, ref_param, title, caption, tip):
    """Dot (point estimate) and bar (95% interval) on a synchronized dual axis, one row per period and bank."""
    color = f"<color column={a(ref(key, 'ticker'))} />"
    gantt = pane("GanttBar", color + f"<size column={a(ref(key, width_calc, 'meas'))} />", tip=tooltip(tip),
                 reflines=refline(ref(key, low), ref_param, "refline0"), pid=1, axis=ref(key, low),
                 mark_style="<format attr='mark-transparency' value='110' /><format attr='size' value='0.35' />")
    dot = pane("Circle", color, tip=tooltip(tip), pid=2, axis=ref(key, point), mark_style="<format attr='size' value='1.4' />")
    style = (hide_header(key) + f"<style-rule element='axis'><encoding attr='space' class='0' field={a(ref(key, point))} field-type='quantitative' "
             f"fold='true' scope='cols' synchronized='true' type='space' />"
             f"<format attr='display' class='0' field={a(ref(key, point))} scope='cols' value='false' /></style-rule>")
    tip_cols = [p[1] for p in tip if isinstance(p, tuple)]
    return worksheet(name, key, ["period", "ticker", low, high, point] + tip_cols,
                     f"({ref(key, 'period')} / {ref(key, 'ticker')})", f"({ref(key, low)} + {ref(key, point)})",
                     pane("Automatic") + gantt + dot, title, caption, calcs=[width_calc], style=style)


def build_worksheets():
    sheets = {}
    # S1 headline tiles: one row per instrument, one column per measure (Measure Names / Measure Values)
    kpi_measures = ["price_return_pct", "total_return_pct", "sharpe", "sharpe_diff_vs_ihsg", "sharpe_diff_p", "beta", "r2"]
    members = "".join(f"<groupfilter function='member' level='[:Measure Names]' member={a(chr(34) + '[' + ds_name('kpi') + '].[sum:' + m + ':qk]' + chr(34))} />"
                      for m in kpi_measures)
    kpi_filter = (f"<filter class='categorical' column='[{ds_name('kpi')}].[:Measure Names]'>"
                  f"<groupfilter function='union' user:op='manual'>{members}</groupfilter></filter>")
    sheets["S1 Headline tiles"] = worksheet(
        "S1 Headline tiles", "kpi", ["ticker"] + kpi_measures, ref("kpi", "ticker"), f"[{ds_name('kpi')}].[:Measure Names]",
        pane("Text", f"<text column='[{ds_name('kpi')}].[Multiple Values]' />"),
        "Full period, 4 Jan 2021 - 30 Sep 2026 (Sharpe minus IHSG: Ledoit-Wolf paired test)", None,
        filters=kpi_filter, agg=True,
        slices=f"<slices><column>[{ds_name('kpi')}].[:Measure Names]</column></slices>")

    # S2, S6, S7 daily lines with regime reference lines
    def line_sheet(name, measure, title, caption, ref_param=None):
        date = ref("daily", "trade_date")
        # regime boundaries are not drawn: Tableau rejects date-parameter reference lines here; the
        # tooltip names the regime and S10 lists the dates
        lines = ""
        if ref_param:
            lines += refline(ref("daily", measure), ref_param, "refline9")
        tip = [tip_field("daily", "ticker"), ", ", tip_field("daily", "trade_date"), ": ", tip_field("daily", measure),
               " (", tip_field("daily", "regime"), ")"]
        p = pane("Line", f"<color column={a(ref('daily', 'ticker'))} />", tip=tooltip(tip), reflines=lines)
        return worksheet(name, "daily", ["trade_date", "ticker", "regime", measure], ref("daily", measure), date, p, title, caption)

    sheets["S2 Growth of 100"] = line_sheet("S2 Growth of 100", "growth_index",
                                            "Growth of 100 invested on 30 December 2020 (price return)",
                                            "Regime dates are listed in the Regimes table on the Detail dashboard", "Hundred")
    sheets["S6 Drawdown"] = line_sheet("S6 Drawdown", "drawdown_pct", "Drawdown from the running peak (price return)",
                                       "Lowest point for all four: 8 June 2026")
    sheets["S7 Rolling Sharpe"] = line_sheet("S7 Rolling Sharpe", "rolling_sharpe_252",
                                             "Rolling 252-day Sharpe ratio (annualized, excess over the policy rate)",
                                             "First value on 7 January 2022; a window can straddle two regimes", "Zero")

    # S3, S5, S8 interval charts
    sheets["S3 Sharpe minus IHSG"] = interval_sheet(
        "S3 Sharpe minus IHSG", "sdiff", "ci_low", "ci_high", "delta", "ci_width", "Zero",
        "Sharpe ratio of each bank minus the IHSG's (95% interval)",
        "Intervals that cross 0: no significant difference. None of the 12 does.",
        [tip_field("sdiff", "ticker"), ", ", tip_field("sdiff", "period"), ": difference ", tip_field("sdiff", "delta"),
         " (95% interval ", tip_field("sdiff", "ci_low"), " to ", tip_field("sdiff", "ci_high"), "), p = ",
         tip_field("sdiff", "p_value"), ", Holm-adjusted p = ", tip_field("sdiff", "p_holm")])
    sheets["S5 Beta"] = interval_sheet(
        "S5 Beta", "capm", "beta_ci_low", "beta_ci_high", "beta", "beta_ci_width", "One",
        "Beta against the IHSG (95% HC3 interval)", "Line at 1: moves one-for-one with the IHSG",
        [tip_field("capm", "ticker"), ", ", tip_field("capm", "period"), ": beta ", tip_field("capm", "beta"),
         " (", tip_field("capm", "beta_ci_low"), " to ", tip_field("capm", "beta_ci_high"), "); test of beta = 1: p = ",
         tip_field("capm", "p_beta_eq_1"), ", Holm-adjusted ", tip_field("capm", "p_beta_eq_1_holm")])
    sheets["S8 R-squared"] = interval_sheet(
        "S8 R-squared", "capm", "r2_ci_low", "r2_ci_high", "r2", "r2_ci_width", "Zero",
        "R-squared against the IHSG (95% bootstrap interval)",
        "R-squared moves with market volatility as well as with the relationship; read it with beta",
        [tip_field("capm", "ticker"), ", ", tip_field("capm", "period"), ": R-squared ", tip_field("capm", "r2"),
         " (", tip_field("capm", "r2_ci_low"), " to ", tip_field("capm", "r2_ci_high"), ")"])

    # S4 gap bars
    gap = ref("implied", "gap_pct_points")
    tip = [tip_field("implied", "ticker"), ", ", tip_field("implied", "period"), ": actual ", tip_field("implied", "actual_pct"),
           ", market-implied ", tip_field("implied", "market_implied_pct"), ", gap ", tip_field("implied", "gap_pct_points"),
           "; beta ", tip_field("implied", "beta")]
    p = pane("Bar", f"<color column={a(ref('implied', 'ticker'))} /><text column={a(gap)} />",
             tip=tooltip(tip), reflines=refline(gap, "Zero", "refline0"), labels=True)
    sheets["S4 Market-implied gap"] = worksheet(
        "S4 Market-implied gap", "implied", ["period", "ticker", "gap_pct_points", "actual_pct", "market_implied_pct", "beta"],
        f"({ref('implied', 'period')} / {ref('implied', 'ticker')})", gap, p,
        "Return not accounted for by market exposure (percentage points)",
        "Actual price return minus beta x IHSG plus the risk-free rate. R3: about -23 to -29 points; R2: +15 to +66 points.",
        style=hide_header("implied"))

    # S9 price against total return, banks only
    bank_members = "".join(f"<groupfilter function='member' level='[none:ticker:nk]' member='&quot;{t}&quot;' />"
                           for t in ("BBCA", "BBRI", "BMRI"))
    bank_filter = (f"<filter class='categorical' column={a(ref('metrics', 'ticker'))}>"
                   f"<groupfilter function='union' user:op='manual'>{bank_members}</groupfilter></filter>")
    cum = ref("metrics", "cum_return_pct")
    tip = [tip_field("metrics", "ticker"), ", ", tip_field("metrics", "period"), ", ", tip_field("metrics", "basis"), ": ",
           tip_field("metrics", "cum_return_pct")]
    p = pane("Bar", f"<color column={a(ref('metrics', 'ticker'))} />", tip=tooltip(tip), reflines=refline(cum, "Zero", "refline0"))
    sheets["S9 Price vs total return"] = worksheet(
        "S9 Price vs total return", "metrics", ["period", "ticker", "basis", "cum_return_pct"], cum,
        f"({ref('metrics', 'period')} / {ref('metrics', 'ticker')} / {ref('metrics', 'basis')})", p,
        "Cumulative return: price return against total return (banks only)",
        "The IHSG has no dividend data, so it is not shown on the total-return basis", filters=bank_filter)

    # S10 regimes table
    sheets["S10 Regimes"] = worksheet(
        "S10 Regimes", "regimes", ["regime", "label", "start_date", "end_date", "return_days"],
        f"({ref('regimes', 'regime')} / {ref('regimes', 'label')} / [{ds_name('regimes')}].[none:start_date:nk] / "
        f"[{ds_name('regimes')}].[none:end_date:nk])", "",
        pane("Text", f"<text column={a(ref('regimes', 'return_days', 'meas'))} />"),
        "Regimes (fixed in advance by policy-rate phase)", "Return days in each regime")
    return sheets


# --- dashboards ----------------------------------------------------------------------

_zone_id = [100]


def zid():
    _zone_id[0] += 1
    return _zone_id[0]


def sheet_zone(name, x, y, w, h):
    return f"<zone h='{h}' id='{zid()}' name={a(name)} w='{w}' x='{x}' y='{y}' />"


def text_zone(runs, x, y, w, h):
    body = "".join(f"<run fontcolor='{c}' fontname={a(font)} fontsize='{size}'>{escape(t)}</run>" for t, c, font, size in runs)
    return f"<zone h='{h}' id='{zid()}' type-v2='text' w='{w}' x='{x}' y='{y}'><formatted-text>{body}</formatted-text></zone>"


def legend_zone(sheet, field, x, y, w, h):
    return (f"<zone h='{h}' id='{zid()}' name={a(sheet)} pane-specification-id='0' param={a(field)} type-v2='color' "
            f"w='{w}' x='{x}' y='{y}' />")


HEADER = [
    ("Indonesia's Big Three banks against the IHSG, 2021-2026\n", INK, "Tableau Semibold", 16),
    ("No bank's risk-adjusted return is statistically distinguishable from the IHSG's. The banks diverged most in the "
     "2024-26 easing regime, losing about 43% against 19% for the index.\n", INK, "Tableau Book", 11),
    ("BBCA, BBRI, BMRI against the IHSG  |  daily price returns, 4 January 2021 - 30 September 2026  |  excess returns over the "
     "Bank Indonesia policy rate  |  annualized with 252 trading days  |  Source: Yahoo Finance (yfinance), Bank Indonesia; "
     "own calculations", MUTED, "Tableau Book", 9),
]
FOOTER = [("Historical and in-sample; not a forecast or investment advice. Price returns exclude dividends (the IHSG data has none); "
           "all returns in rupiah, no currency adjustment. The banks are part of the IHSG, so beta and R-squared are partly mechanical. "
           "Regimes: R1 to 22 Aug 2022, R2 to 17 Sep 2024, R3 to 19 May 2026, Stub to 30 Sep 2026. "
           "Full method and limitations: report/report_draft.md.", MUTED, "Tableau Book", 8)]


DASHBOARD_SHEETS = {
    "Overview": ["S1 Headline tiles", "S2 Growth of 100", "S3 Sharpe minus IHSG", "S4 Market-implied gap", "S5 Beta"],
    "Detail": ["S6 Drawdown", "S7 Rolling Sharpe", "S8 R-squared", "S9 Price vs total return", "S10 Regimes"],
}


def dashboard(name, zones):
    return f"""    <dashboard name={a(name)}>
      <style />
      <size maxheight='800' maxwidth='1200' minheight='800' minwidth='1200' sizing-mode='fixed' />
      <zones>
        <zone h='100000' id='{zid()}' type-v2='layout-basic' w='100000' x='0' y='0'>
          {''.join(zones)}
        </zone>
      </zones>
    </dashboard>"""


def build_dashboards():
    overview = dashboard("Overview", [
        text_zone(HEADER, 500, 500, 87000, 12500),
        legend_zone("S2 Growth of 100", ref("daily", "ticker"), 88000, 1000, 11500, 12000),
        sheet_zone("S1 Headline tiles", 500, 13500, 99000, 17000),
        sheet_zone("S2 Growth of 100", 500, 31000, 57000, 31000),
        sheet_zone("S3 Sharpe minus IHSG", 58000, 31000, 41500, 31000),
        sheet_zone("S4 Market-implied gap", 500, 62500, 57000, 31000),
        sheet_zone("S5 Beta", 58000, 62500, 41500, 31000),
        text_zone(FOOTER, 500, 94000, 99000, 5500),
    ])
    detail = dashboard("Detail", [
        text_zone(HEADER[:1] + HEADER[2:], 500, 500, 87000, 8000),
        legend_zone("S6 Drawdown", ref("daily", "ticker"), 88000, 500, 11500, 9000),
        sheet_zone("S6 Drawdown", 500, 9500, 49500, 33000),
        sheet_zone("S7 Rolling Sharpe", 50000, 9500, 49500, 33000),
        sheet_zone("S8 R-squared", 500, 43000, 49500, 33000),
        sheet_zone("S9 Price vs total return", 50000, 43000, 49500, 33000),
        sheet_zone("S10 Regimes", 500, 76500, 99000, 17000),
        text_zone(FOOTER, 500, 94000, 99000, 5500),
    ])
    return overview, detail


def actions():
    out = []
    for i, d in enumerate(("Overview", "Detail"), start=1):
        out.append(f"""    <action caption={a('Highlight instrument (' + d + ')')} name='[Action{i}_HIGHLIGHT_{d.upper()}]'>
      <activation auto-clear='true' type='on-hover' />
      <source dashboard={a(d)} type='sheet' />
      <command command='tsc:brush'>
        <param name='special-fields' value='all' />
        <param name='target' value={a(d)} />
      </command>
    </action>""")
    return "  <actions>\n" + "\n".join(out) + "\n  </actions>"


def windows(sheet_names):
    cards = ("<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>"
             "<edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip>"
             "<strip size='2147483647'><card type='title' /></strip></edge></cards>")
    out = [f"    <window class='worksheet' name={a(n)}>{cards}</window>" for n in sheet_names]
    # dashboard windows need a viewpoint per sheet on the dashboard, then active and device-preview, in that order
    def tail(sheets_on_dashboard):
        views = "".join(f"<viewpoint name={a(n)}><zoom type='entire-view' /></viewpoint>" for n in sheets_on_dashboard)
        return (f"<viewpoints>{views}</viewpoints><active id='-1' />"
                "<device-preview><device is-portrait='true' name='iPhone 6' type='Phone' /></device-preview>")
    out.append(f"    <window class='dashboard' name='Detail'>{tail(DASHBOARD_SHEETS['Detail'])}</window>")
    out.append(f"    <window class='dashboard' maximized='true' name='Overview'>{tail(DASHBOARD_SHEETS['Overview'])}</window>")
    return "  <windows source-height='30'>\n" + "\n".join(out) + "\n  </windows>"


def main():
    check_headers()
    sheets = build_worksheets()
    overview, detail = build_dashboards()
    xml = f"""<?xml version='1.0' encoding='utf-8' ?>
<!-- Generated by tableau/build_workbook.py. Edit the script, not this file, then rerun it. -->
<workbook source-build='2026.2.0 (20262.26.0912.1023)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <datasources>
{parameters()}
{chr(10).join(datasource(k) for k in SOURCES)}
  </datasources>
{actions()}
  <worksheets>
{chr(10).join(sheets.values())}
  </worksheets>
  <dashboards>
{overview}
{detail}
  </dashboards>
{windows(list(sheets))}
</workbook>
"""
    OUT.write_text(xml, encoding="utf-8")
    print(f"wrote {OUT} ({len(xml):,} characters, {len(sheets)} worksheets, 2 dashboards)")


if __name__ == "__main__":
    main()
