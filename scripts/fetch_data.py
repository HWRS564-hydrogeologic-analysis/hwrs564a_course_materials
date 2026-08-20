#!/usr/bin/env python3
"""Build the course datasets in `data/`, reproducibly.

The datasets students work with are committed to the repo so no lab depends on
someone else's uptime (playbook §1.3). But committed CSVs with no provenance
rot into magic numbers nobody dares change, so this script is what produced
them, and re-running it reproduces them.

    python scripts/fetch_data.py            # build everything
    python scripts/fetch_data.py --list     # show what would be built

Everything here comes from USGS NWIS except the permeameter workbook, which is
synthetic — see `build_permeameter_xlsx` for why.

Network access required. Run it when you deliberately want to refresh the data,
not as part of a build.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / "cache"

# Tucson basin, roughly Sahuarita up to Marana. west, south, east, north.
TUCSON_BBOX = "-111.20,32.00,-110.75,32.45"

# Sabino Creek near Tucson — a flashy, strongly monsoonal ephemeral-to-perennial
# creek. Good for Weeks 6-7 precisely because it is *not* well behaved.
SABINO_GAGE = "09484000"

FEET_TO_M = 0.3048


def _unwrap(result):
    """dataretrieval has returned both a DataFrame and a (df, metadata) tuple
    across versions. Accept either."""
    return result[0] if isinstance(result, tuple) else result


# --------------------------------------------------------------------------
def build_well_inventory() -> pd.DataFrame:
    """Every NWIS groundwater site in the Tucson basin, tidied.

    Used in Week 5 (read a csv, select rows and columns) and Week 8 (map it).
    Left deliberately imperfect: real missing depths and aquifer codes are the
    point of the Week 6 missing-data material.
    """
    import dataretrieval.nwis as nwis

    raw = _unwrap(
        nwis.get_info(bBox=TUCSON_BBOX, siteType="GW", hasDataTypeCd="gw")
    )

    df = pd.DataFrame(
        {
            "site_no": raw["site_no"].astype(str),
            "station_name": raw["station_nm"].str.strip(),
            "latitude": pd.to_numeric(raw["dec_lat_va"], errors="coerce"),
            "longitude": pd.to_numeric(raw["dec_long_va"], errors="coerce"),
            "land_surface_elev_ft": pd.to_numeric(raw["alt_va"], errors="coerce"),
            "well_depth_ft": pd.to_numeric(raw["well_depth_va"], errors="coerce"),
            "hole_depth_ft": pd.to_numeric(raw["hole_depth_va"], errors="coerce"),
            "aquifer_code": raw["aqfr_cd"].replace("", pd.NA),
            "county_code": raw["county_cd"],
        }
    )

    # NWIS returns a site more than once when it has several data types on
    # file. One row per well, or every later join fans out.
    df = df.dropna(subset=["latitude", "longitude"]).drop_duplicates("site_no")
    df["land_surface_elev_m"] = (df["land_surface_elev_ft"] * FEET_TO_M).round(2)
    df["well_depth_m"] = (df["well_depth_ft"] * FEET_TO_M).round(2)
    return df.sort_values("site_no").reset_index(drop=True)


def build_water_levels(inventory: pd.DataFrame, n_wells: int = 80) -> pd.DataFrame:
    """Water-level measurements for the best-monitored wells in the inventory.

    Long format — one row per (well, date) — because that is the shape real
    monitoring data arrives in, and reshaping it is a Week 5 skill.

    Parameter 72019 is depth to water below land surface, in feet. Note this
    goes through `dataretrieval.waterdata`, not `dataretrieval.nwis`: as of
    1.2.0 `nwis.get_gwlevels` is gone and `nwis.get_record` is deprecated. The
    Week 6 lab should teach the `waterdata` API, not the one in older tutorials.
    """
    import dataretrieval.waterdata as wd

    raw, _ = wd.get_field_measurements(
        bbox=[float(x) for x in TUCSON_BBOX.split(",")],
        parameter_code="72019",
        properties=["monitoring_location_id", "time", "value", "approval_status"],
        skip_geometry=True,
        limit=200_000,
    )
    if not len(raw):
        raise SystemExit("no water levels came back — is NWIS reachable?")

    wl = pd.DataFrame(
        {
            # ids come back as "USGS-320000110555701"; the inventory uses the
            # bare site number, and they have to join.
            "site_no": raw["monitoring_location_id"].str.removeprefix("USGS-"),
            "date": pd.to_datetime(raw["time"], errors="coerce", utc=True).dt.tz_localize(None),
            "depth_to_water_ft": pd.to_numeric(raw["value"], errors="coerce"),
            "approval_status": raw["approval_status"],
        }
    ).dropna(subset=["date", "depth_to_water_ft"])

    # Keep the wells with the longest records; a lab dataset nobody can see a
    # trend in teaches nothing.
    keep = (
        wl.groupby("site_no").size().sort_values(ascending=False).head(n_wells).index
    )
    wl = wl[wl["site_no"].isin(keep)].copy()
    wl["depth_to_water_m"] = (wl["depth_to_water_ft"] * FEET_TO_M).round(2)

    elev = inventory.set_index("site_no")["land_surface_elev_ft"]
    wl["water_level_elev_ft"] = (
        wl["site_no"].map(elev) - wl["depth_to_water_ft"]
    ).round(2)

    return wl.sort_values(["site_no", "date"]).reset_index(drop=True)


def build_week07_paired_wells(levels: pd.DataFrame) -> pd.DataFrame:
    """Instructor-checked paired summaries for the Week 7 inference lab.

    Tucson Water began shifting its potable supply away from reliance on the
    Central Well Field around 2000-01.  The lab asks a deliberately bounded
    question: among monitored Tucson-area wells with coverage in both windows,
    did typical depth to water differ between 1996-2000 and 2002-2006?

    The observational unit is a well, not an individual tape reading.  We use
    one median per well and period, retain wells observed in at least three
    distinct years in each period, and leave 2001 out as a transition year.
    This makes the pairing and the selection rule explicit while keeping data
    wrangling out of an inference-focused lab.
    """
    levels = levels.copy()
    levels["year"] = pd.to_datetime(levels["date"]).dt.year

    rows: list[dict[str, object]] = []
    for site_no, group in levels.groupby("site_no"):
        pre = group[group["year"].between(1996, 2000)]
        post = group[group["year"].between(2002, 2006)]
        pre_years = int(pre["year"].nunique())
        post_years = int(post["year"].nunique())
        if pre_years < 3 or post_years < 3:
            continue

        pre_median = float(pre["depth_to_water_ft"].median())
        post_median = float(post["depth_to_water_ft"].median())
        rows.append(
            {
                "site_no": site_no,
                "pre_years": pre_years,
                "post_years": post_years,
                "pre_measurements": len(pre),
                "post_measurements": len(post),
                "pre_median_depth_ft": pre_median,
                "post_median_depth_ft": post_median,
                # Positive means the water table was deeper after the shift.
                "change_depth_ft": post_median - pre_median,
            }
        )

    out = pd.DataFrame(rows).sort_values("site_no").reset_index(drop=True)
    numeric = out.select_dtypes(include="number").columns
    out[numeric] = out[numeric].round(3)
    return out


def build_sabino_daily() -> pd.DataFrame:
    """Twenty years of daily mean discharge at Sabino Creek.

    This is the offline fallback required by playbook §1.3 rule 4: the Week 6
    lab tries the live API first and falls back to this file, so a class of
    twelve hitting NWIS at once can't take the session down.
    """
    import dataretrieval.nwis as nwis

    raw = _unwrap(
        nwis.get_record(
            sites=SABINO_GAGE, service="dv", start="2005-01-01", end="2024-12-31"
        )
    )
    df = raw.reset_index()
    df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(df["datetime"]).dt.tz_localize(None),
            "discharge_cfs": pd.to_numeric(df["00060_Mean"], errors="coerce"),
            "qualifier": df["00060_Mean_cd"],
        }
    )
    df["discharge_cms"] = (df["discharge_cfs"] * 0.0283168).round(4)
    return df


def build_grid_top(inventory: pd.DataFrame, nrow: int = 40, ncol: int = 60) -> pd.DataFrame:
    """Land-surface elevation on the Week 11-14 model grid, in metres.

    A **fitted second-order trend surface**, not a DEM. Interpolating the well
    elevations directly gives a grid with 8 m of relief between adjacent 250 m
    cells — an artifact of inconsistent survey accuracy, not topography, and
    steep enough to make a MODFLOW top array that produces dry cells
    immediately. The polynomial captures basin *form* (rising south-east toward
    the Santa Ritas and Catalinas) and leaves the mountain-front wells in the
    residual, where they belong.

    RMSE against the 1,693 well elevations is about 36 m, over a 760 m spread.
    That is the right accuracy for a teaching grid and the wrong accuracy for
    anything else; say so if you ever reuse it.
    """
    w = inventory.dropna(subset=["land_surface_elev_ft"])
    x, y = w["longitude"].to_numpy(), w["latitude"].to_numpy()
    z = w["land_surface_elev_ft"].to_numpy() * FEET_TO_M

    def design(a, b):
        return np.column_stack([np.ones_like(a), a, b, a * a, a * b, b * b])

    coef, *_ = np.linalg.lstsq(design(x, y), z, rcond=None)
    rmse = float(np.std(z - design(x, y) @ coef))

    west, south, east, north = (float(v) for v in TUCSON_BBOX.split(","))
    lon = np.linspace(west, east, ncol)
    lat = np.linspace(north, south, nrow)      # row 0 is the north edge
    LON, LAT = np.meshgrid(lon, lat)
    top = (design(LON.ravel(), LAT.ravel()) @ coef).reshape(LON.shape)

    print(f"  trend-surface RMSE {rmse:.1f} m; grid spans "
          f"{top.min():.0f}-{top.max():.0f} m")

    # Written as a plain grid of numbers: 40 rows, 60 columns, no header, so a
    # lab can do `np.loadtxt(..., delimiter=",")` and get a (40, 60) array.
    return pd.DataFrame(np.round(top, 2))


def build_permeameter_xlsx(path: Path) -> None:
    """A constant-head permeameter worksheet, for the one `pd.read_excel` demo.

    Synthetic, and deliberately so. The 2025 workbook (`Week 4 Lab Data.xlsx`)
    holds partially-filled measurements attributed to named students from that
    cohort, which should not be carried forward. The physics here is real:
    Darcy's law rearranged, K = QL / (A dh), with plausible scatter for three
    materials.
    """
    rng = np.random.default_rng(5641)          # fixed seed: same file every run

    materials = {                              # name: (true K m/d, sample count)
        "coarse sand": (28.0, 5),
        "fine sand": (4.2, 5),
        "silty sand": (0.65, 5),
    }
    length_cm, diameter_cm, head_diff_cm = 12.0, 5.4, 18.0
    area_cm2 = np.pi * (diameter_cm / 2) ** 2

    rows = []
    run = 1
    for material, (k_true, n) in materials.items():
        for _ in range(n):
            k = k_true * rng.lognormal(0.0, 0.18)               # real spread
            k_cm_per_s = k * 100 / 86400
            q_cm3_per_s = k_cm_per_s * area_cm2 * head_diff_cm / length_cm
            rows.append(
                {
                    "run": run,
                    "material": material,
                    "sample_length_cm": length_cm,
                    "sample_diameter_cm": diameter_cm,
                    "head_difference_cm": head_diff_cm,
                    "duration_s": 60.0,
                    "volume_collected_cm3": round(q_cm3_per_s * 60.0, 2),
                }
            )
            run += 1

    df = pd.DataFrame(rows)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Constant Head", index=False)
        pd.DataFrame(
            {
                "note": [
                    "Constant-head permeameter, HWRS 564a teaching dataset.",
                    "Compute Q = volume_collected_cm3 / duration_s.",
                    "Then K = Q * L / (A * dh), with A from the sample diameter.",
                    "Report K in m/d and compare across the three materials.",
                ]
            }
        ).to_excel(writer, sheet_name="Readme", index=False)


# --------------------------------------------------------------------------
TARGETS = {
    "data/tucson_basin_wells.csv": "NWIS well inventory, Tucson basin",
    "data/tucson_water_levels.csv": "NWIS water-level measurements, best-monitored wells",
    "data/week07_tucson_paired_wells.csv": "paired well summaries for Week 7 inference",
    "data/cache/nwis_09484000_dv.csv": "Sabino Creek daily discharge (Week 6 offline fallback)",
    "data/week04_permeameter.xlsx": "Constant-head permeameter runs (the one read_excel demo)",
    "data/tucson_grid_top.csv": "Land-surface elevation on the 40x60 model grid (Weeks 11-14)",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show targets and exit")
    args = ap.parse_args()

    if args.list:
        for name, desc in TARGETS.items():
            print(f"  {name:42s} {desc}")
        return 0

    DATA.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)

    print("Well inventory...")
    inventory = build_well_inventory()
    inventory.to_csv(DATA / "tucson_basin_wells.csv", index=False)
    print(f"  {len(inventory):,} wells -> data/tucson_basin_wells.csv")

    print("Water levels...")
    levels = build_water_levels(inventory)
    levels.to_csv(DATA / "tucson_water_levels.csv", index=False)
    print(
        f"  {len(levels):,} measurements across "
        f"{levels['site_no'].nunique()} wells -> data/tucson_water_levels.csv"
    )

    print("Week 7 paired well summaries...")
    paired = build_week07_paired_wells(levels)
    paired.to_csv(DATA / "week07_tucson_paired_wells.csv", index=False)
    print(
        f"  {len(paired)} paired wells -> data/week07_tucson_paired_wells.csv"
    )

    print("Sabino Creek daily discharge...")
    sabino = build_sabino_daily()
    sabino.to_csv(CACHE / f"nwis_{SABINO_GAGE}_dv.csv", index=False)
    print(f"  {len(sabino):,} days -> data/cache/nwis_{SABINO_GAGE}_dv.csv")

    print("Model grid top...")
    grid = build_grid_top(inventory)
    grid.to_csv(DATA / "tucson_grid_top.csv", index=False, header=False)
    print(f"  {grid.shape[0]}x{grid.shape[1]} grid -> data/tucson_grid_top.csv")

    print("Permeameter workbook...")
    build_permeameter_xlsx(DATA / "week04_permeameter.xlsx")
    print("  -> data/week04_permeameter.xlsx")

    return 0


if __name__ == "__main__":
    sys.exit(main())
