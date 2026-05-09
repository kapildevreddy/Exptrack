import re


def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_returns_200_when_logged_in(logged_in_client):
    response = logged_in_client.get("/profile")
    assert response.status_code == 200


def test_profile_shows_user_name(logged_in_client):
    response = logged_in_client.get("/profile")
    assert b"Demo User" in response.data


def test_profile_shows_user_email(logged_in_client):
    response = logged_in_client.get("/profile")
    assert b"demo@spendly.com" in response.data


def test_profile_shows_stats(logged_in_client):
    response = logged_in_client.get("/profile")
    assert b"356" in response.data
    assert b"8"   in response.data


def test_profile_shows_transaction_rows(logged_in_client):
    response = logged_in_client.get("/profile")
    assert b"Groceries"         in response.data
    assert b"Electricity bill"  in response.data
    assert b"Movie tickets"     in response.data


def test_profile_shows_category_badges(logged_in_client):
    response = logged_in_client.get("/profile")
    html = response.data.decode()
    assert "badge-food"     in html
    assert "badge-bills"    in html
    assert "badge-shopping" in html


def test_profile_shows_category_bars(logged_in_client):
    response = logged_in_client.get("/profile")
    html = response.data.decode()
    assert "cat-bar-food"     in html
    assert "cat-bar-bills"    in html
    assert "cat-bar-shopping" in html


def test_navbar_shows_username_when_logged_in(logged_in_client):
    response = logged_in_client.get("/profile")
    assert b"Demo User" in response.data


def test_no_inline_hex_in_profile(logged_in_client):
    response = logged_in_client.get("/profile")
    html = response.data.decode()
    hex_pattern = re.compile(r'(?<!["\w&])#[0-9a-fA-F]{3,6}(?![0-9a-fA-F])')
    assert not hex_pattern.search(html), "Hex color found in rendered profile HTML"
