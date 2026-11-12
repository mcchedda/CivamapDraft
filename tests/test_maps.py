from src.maps import directions_url, map_embed_url, map_search_url, place_query


def test_statewide_has_no_destination():
    assert place_query({"Resource Name": "SNAP", "Primary Service Area": "Statewide"}) is None
    assert directions_url({"Resource Name": "SNAP", "Primary Service Area": "All Maine"}) is None


def test_local_map_links_encode_places():
    row = {"Resource Name": "Community Food Center", "Primary Service Area": "Waterville"}
    assert place_query(row) == "Community Food Center, Waterville, Maine"
    assert "output=embed" in map_embed_url(row)
    assert "Community+Food+Center" in map_search_url(row)
    assert "destination=" in directions_url(row)
    assert "origin=" not in directions_url(row)
