from data_sources.loader import load_companies
from data_sources.mocks import MockProviderClient


def test_load_companies_returns_thirty_rows():
    companies = load_companies()
    assert len(companies) == 30


def test_load_companies_first_row_matches_csv():
    companies = load_companies()
    assert companies[0] == {
        "company_name": "Cedar Ridge Plumbing LLC",
        "mailing_address": "4821 Maple Ave, Lincoln, NE 68504",
    }


def test_query_all_returns_full_record_for_known_company():
    client = MockProviderClient()
    result = client.query_all("Cedar Ridge Plumbing LLC")

    assert result["registry"]["name"] == "Daniel Ortega"
    assert result["registry"]["role"] == "Owner"
    assert result["listing"]["phone"] == "+1-402-555-0148"
    assert result["enrichment"]["email"] == "d.ortega@cedarridgeplumbing.com"


def test_query_all_returns_partial_record_for_single_source_company():
    client = MockProviderClient()
    result = client.query_all("Northgate HVAC Services")

    assert result["registry"]["name"] == "Thomas Reed"
    assert result["listing"] is None
    assert result["enrichment"] is None


def test_query_all_returns_all_none_for_unknown_company():
    client = MockProviderClient()
    result = client.query_all("Redwood Cabinetry")

    assert result == {"registry": None, "listing": None, "enrichment": None}
