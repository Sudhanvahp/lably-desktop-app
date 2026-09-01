"""The app's public identity, in one place so a rename touches one file."""

APP_NAME = "Lably"
APP_TAGLINE = "Blood Report Manager"
NAV_TAGLINE = "Pathology Reports"

# Folder under %APPDATA% where reports live. Deliberately unchanged by the
# rename: renaming it would orphan every report already on disk.
DATA_FOLDER = "BloodReportApp"

APP_VERSION = "v1.1"   # billing, the standalone bill, strict Indian phones
