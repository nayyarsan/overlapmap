from pathlib import Path

# Repository root
ROOT = Path(__file__).parent.parent

# Data directories
RAW_DIR        = ROOT / "data" / "raw"
STATIC_DIR     = ROOT / "data" / "static"
BOUNDARIES_DIR = STATIC_DIR / "boundaries"
EPA_SLD_DIR    = STATIC_DIR / "epa_sld"
DOCS_DATA_DIR  = ROOT / "docs" / "data"
METADATA_PATH  = ROOT / "data" / "metadata.json"

# Output
TOPOJSON_OUT = DOCS_DATA_DIR / "scored_tracts.topojson"
GEOJSON_OUT  = RAW_DIR / "scored_tracts.geojson"  # for Kaggle

# LA County
LA_COUNTY_FIPS = "037"
CA_STATE_FIPS  = "06"
LA_FIPS_FULL   = CA_STATE_FIPS + LA_COUNTY_FIPS  # "06037"

# Bounding box for LA County (for coordinate validation)
LA_BBOX = {
    "min_lat": 33.70,
    "max_lat": 34.85,
    "min_lon": -118.95,
    "max_lon": -117.64,
}

# Census ACS
CENSUS_ACS_BASE = "https://api.census.gov/data/2022/acs/acs5"
CENSUS_RENT_VAR = "B25031_004E"       # median gross rent, 2-bedroom
CENSUS_AGE_VAR  = "B25035_001E"       # median year structure built

# LAPD NIBRS (Socrata API — no key required for read-only public datasets)
LAPD_NIBRS_OFFENSES_URL = (
    "https://data.lacity.org/resource/d5tf-ez2w.json"
)
LAPD_NIBRS_VICTIMS_URL = (
    "https://data.lacity.org/resource/gqf2-vm2j.json"
)

# LASD (ArcGIS Feature Service — public, no key required)
LASD_CFS_URL = (
    "https://egis-lacounty.hub.arcgis.com/datasets/"
    "lacounty::lasd-calls-for-service/api"
)

# CAL FIRE FHSZ — ArcGIS FeatureServer endpoints (original fire.ca.gov zip URLs return 403)
# LACoFD-hosted LA County layers (public, no auth); field: HAZ_CLASS
CALFIRE_SRA_URL = (
    "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/"
    "LACoFD_Fire_Hazard_Severity_Zones_SRA/FeatureServer/0"
)
CALFIRE_LRA_URL = (
    "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/"
    "LACoFD_Fire_Hazard_Severity_Zones_LRA/FeatureServer/0"
)

# CalEnviroScreen 4.0 (Zenodo mirror of OEHHA data)
CALENVIRO_URL = (
    "https://zenodo.org/api/records/14563093/files/"
    "calenviroscreen40resultsdatadictionaryf2021.zip/content"
)

# CDE CAASPP bulk download (seed URL — actual annual file resolved manually)
CDE_CAASPP_URL = "https://caaspp-elpac.ets.org/caaspp/ResearchFileList"
# CDE CAASPP 2024-25 All Students research file (8 MB)
CAASPP_CSV_URL = "https://caaspp-elpac.ets.org/caaspp/researchfiles/sb_ca2025_1_csv_v1.zip"
# CDE School Directory download (tab-delimited; ict=Y = active schools only)
CDE_SCHOOL_DIR_URL = "https://www.cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt&ict=Y"

# Census TIGER/Line CA state tracts (2023 vintage — filter to 06037 on load)
TIGER_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2023/TRACT/"
    "tl_2023_06_tract.zip"
)

# Census TIGER/Line CA places (cities + CDPs) for place-name labeling
TIGER_PLACES_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2023/PLACE/"
    "tl_2023_06_place.zip"
)
PLACES_DIR = STATIC_DIR / "boundaries"  # store alongside tracts

# EPA Smart Location Database v3 (updated URL — old /OA/EPA_SmartLocationDatabase_V3_Jan_2021_Final.zip returns 404)
EPA_SLD_URL = (
    "https://edg.epa.gov/EPADataCommons/public/OA/SLD/"
    "SmartLocationDatabaseV3.zip"
)

# Kaggle dataset slug
KAGGLE_DATASET = "la-county-neighborhood-scores"

# Cache freshness threshold (days) for monthly-refreshable fetchers
CACHE_MAX_AGE_DAYS = 30
