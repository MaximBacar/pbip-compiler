import json

THIN_VERSION = "1.28".encode("utf-16-le")

THIN_CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="json" ContentType="" />'
    b'<Override PartName="/Version" ContentType="" />'
    b'<Override PartName="/DiagramLayout" ContentType="" />'
    b'<Override PartName="/Report/Layout" ContentType="" />'
    b'<Override PartName="/Settings" ContentType="application/json" />'
    b'<Override PartName="/Metadata" ContentType="application/json" />'
    b'</Types>'
)

THIN_DIAGRAM = json.dumps({
    "version": "1.1.0",
    "diagrams": [{"ordinal": 0, "scrollPosition": {"x": 0, "y": 0},
                  "nodes": [], "name": "All tables", "zoomValue": 100,
                  "pinKeyFieldsToTop": False, "showExtraHeaderInfo": False,
                  "hideKeyFieldsWhenCollapsed": False, "tablesLocked": False}],
    "selectedDiagram": "All tables",
    "defaultDiagram": "All tables",
}, separators=(",", ":")).encode("utf-16-le")

# Settings must include QueriesSettings.Version — without it PBI June 2026
# raises MashupValidationError.
THIN_SETTINGS = json.dumps({
    "Version": 4,
    "ReportSettings": {},
    "QueriesSettings": {
        "TypeDetectionEnabled": True,
        "RelationshipImportEnabled": False,
        "Version": "2.126.29.0",
    },
}, separators=(",", ":")).encode("utf-16-le")

THIN_METADATA = json.dumps({
    "Version": 5,
    "AutoCreatedRelationships": [],
    "CreatedFrom": "Cloud",
    "CreatedFromRelease": "2024.03",
}, separators=(",", ":")).encode("utf-16-le")


# ── Live-connection (connect-to-published-semantic-model) constants ──────────
# A live report embeds the PBIR definition/ folder verbatim under Report/ and
# carries a Connections part instead of a DataModel. Values mirror a real
# Desktop-saved live .pbix (June 2026). SecurityBindings is a machine-specific
# DPAPI blob; it is omitted (and left out of Content_Types) — Desktop opens fine
# without it and regenerates it on save.
LIVE_VERSION = "1.32".encode("utf-16-le")

# UTF-8 with BOM, matching what Desktop writes for the live package.
LIVE_CONTENT_TYPES = (
    b'\xef\xbb\xbf'
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="json" ContentType="" />'
    b'<Override PartName="/Version" ContentType="" />'
    b'<Override PartName="/Settings" ContentType="application/json" />'
    b'<Override PartName="/Metadata" ContentType="application/json" />'
    b'<Override PartName="/Connections" ContentType="" />'
    b'</Types>'
)

LIVE_SETTINGS = json.dumps({
    "Version": 4,
    "ReportSettings": {},
    "QueriesSettings": {
        "TypeDetectionEnabled": True,
        "RelationshipImportEnabled": True,
        "Version": "2.155.385.0",
    },
}, separators=(",", ":")).encode("utf-16-le")

LIVE_METADATA = json.dumps({
    "Version": 5,
    "AutoCreatedRelationships": [],
    "CreatedFrom": "Cloud",
    "CreatedFromRelease": "2026.06",
}, separators=(",", ":")).encode("utf-16-le")
