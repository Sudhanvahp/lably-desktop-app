"""The app's public identity, in one place so a rename touches one file."""

APP_NAME = "Lably"
APP_TAGLINE = "Blood Report Manager"
NAV_TAGLINE = "Pathology Reports"

# Folder under %APPDATA% where reports live. Deliberately unchanged by the
# rename: renaming it would orphan every report already on disk.
DATA_FOLDER = "BloodReportApp"

APP_VERSION = "v1.1"   # billing, the standalone bill, strict Indian phones

# Who made it, shown in the footer under every page. Separate from APP_NAME:
# the product can be renamed or white-labelled without touching the vendor.
VENDOR = "ACHUTHTECH"
ORIGIN = "Made in India"

# Dropped from the footer once the app is out of beta - set it to "" then.
RELEASE_STAGE = "Beta"


def footer_meta() -> str:
    """The one line under the vendor name: version, origin and release stage,
    skipping any part that is not set rather than printing a stray separator."""
    parts = [APP_VERSION, ORIGIN, RELEASE_STAGE]
    return "  |  ".join(part for part in parts if part)
