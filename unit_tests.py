"""
Tests for the 3 transforms that matter most if they're wrong:
clean_phone (graded directly), clean_category (breaks every query if wrong),
extract_domain (drives entity resolution's domain-match pass).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from clean import clean_phone, clean_category
from entity_resolution import extract_domain


# clean_phone

@pytest.mark.parametrize("raw, expected", [
    ("8325162691", "8325162691"),          # already clean
    ("+14832838234", "4832838234"),        # +1 country code
    ("18325162691", "8325162691"),         # leading 1, no plus
    ("08325162691", "8325162691"),         # leading 0
    ("817-603-9312", "8176039312"),        # dashes
    ("(795) 830-2201", "7958302201"),      # US style brackets
    ("884.705.5203", "8847055203"),        # dots
    ("8325162691 ext. 1", "8325162691"),   # extension
    ("8325162691 EXT 10", "8325162691"),   # extension, uppercase
    ("1-807-557-9878 ext. 10", "8075579878"),  # country code + extension together
    ("+1 (537) 625-5317", "5376255317"),
])
def test_clean_phone_valid_formats(raw, expected):
    result, flag = clean_phone(raw)
    assert result == expected
    assert flag == "ok"


@pytest.mark.parametrize("raw", [None, "", "nan"])
def test_clean_phone_null_input(raw):
    result, flag = clean_phone(raw)
    assert result is None
    assert flag == "null"


@pytest.mark.parametrize("raw", [
    "12345",              
    "123456789012345",    
])
def test_clean_phone_cant_reach_10_digits(raw):
    result, flag = clean_phone(raw)
    assert result is None
    assert flag == "invalid"


# clean_category

@pytest.mark.parametrize("label", ["ERP", "HR", "Medical", "MSP Platform", "LMS", "Legal"])
def test_clean_category_canonical_passes_through(label):
    assert clean_category(label) == label


@pytest.mark.parametrize("raw, expected", [
    ("legal", "Legal"),       
    ("LEGAL", "Legal"),
    ("Lgl", "Legal"),
    ("LEGAL ", "Legal"),
    ("  ERP  ", "ERP"),
])
def test_clean_category_known_variants(raw, expected):
    assert clean_category(raw) == expected


def test_clean_category_unmapped_value_flagged_not_dropped():
    assert clean_category("SomethingRandom") == "Unknown"


def test_clean_category_none_stays_none():
    assert clean_category(None) is None


def test_clean_category_empty_string_is_none():
    # "" is treated as missing data (is_null_string), not an unrecognized
    # category - "Unknown" is reserved for values that are present but unmapped
    assert clean_category("") is None


# extract_domain

@pytest.mark.parametrize("url, domain", [
    ("https://www.cedarfinhub.io", "cedarfinhub.io"),
    ("http://www.cedarfinhub.io", "cedarfinhub.io"),
    ("https://cedarfinhub.io", "cedarfinhub.io"),
    ("cedarfinhub.io", "cedarfinhub.io"),
    ("https://www.cedarfinhub.io/about/team", "cedarfinhub.io"),  # path stripped
    ("https://cedarfinhub.io:8080", "cedarfinhub.io"),            # port stripped
    ("https://WWW.CedarFinHub.IO", "cedarfinhub.io"),             # lowercased
    ("www.summitforgetech.net", "summitforgetech.net"),
])
def test_extract_domain_formats(url, domain):
    assert extract_domain(url) == domain


@pytest.mark.parametrize("value", [None, ""])
def test_extract_domain_null_input(value):
    # fake-null strings like "nan" are clean_website's job upstream, not this function's, by the time extract_domain sees a value it's already real
    assert extract_domain(value) is None
