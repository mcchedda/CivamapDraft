"""Google Maps links for physical directory resources.

The workbook does not include verified street addresses or coordinates. These links
are searches, not guaranteed geocoded locations.
"""

from urllib.parse import quote, urlencode

GENERIC_AREAS = {
    "all maine", "statewide", "maine", "nationwide", "national",
    "online", "remote", "virtual", "all of maine", "throughout maine",
}


def place_query(resource: dict) -> str | None:
    name = str(resource.get("Resource Name", "")).strip()
    area = str(resource.get("Primary Service Area", "")).strip()
    if not name or not area or area.lower() in GENERIC_AREAS:
        return None
    # The workbook has no address field: search by provider and service area.
    return f"{name}, {area}, Maine"


def map_embed_url(resource: dict) -> str | None:
    query = place_query(resource)
    if not query:
        return None
    return "https://www.google.com/maps?q=" + quote(query, safe="") + "&output=embed"


def map_search_url(resource: dict) -> str | None:
    query = place_query(resource)
    if not query:
        return None
    return "https://www.google.com/maps/search/?" + urlencode({"api": "1", "query": query})


def directions_url(resource: dict) -> str | None:
    query = place_query(resource)
    if not query:
        return None
    # Omit origin: Maps asks the visitor to provide/allow their current location.
    return "https://www.google.com/maps/dir/?" + urlencode({
        "api": "1", "destination": query, "travelmode": "driving"
    })
