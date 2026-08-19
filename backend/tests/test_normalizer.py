"""Tests for entity normalization / canonicalization functions."""

from __future__ import annotations

from app.services.resolution.normalizer import (
    canonicalize_address,
    canonicalize_email,
    canonicalize_name,
    canonicalize_phone,
)


class TestCanonicalizeName:
    def test_acme_inc(self) -> None:
        assert canonicalize_name("Acme Inc.") == "acme"

    def test_acme_inc_caps(self) -> None:
        assert canonicalize_name("ACME INC") == "acme"

    def test_acme_incorporated(self) -> None:
        assert canonicalize_name("Acme Incorporated") == "acme"

    def test_acme_corp(self) -> None:
        assert canonicalize_name("ACME Corporation") == "acme"

    def test_acme_llc(self) -> None:
        assert canonicalize_name("Acme LLC") == "acme"

    def test_acme_ltd(self) -> None:
        assert canonicalize_name("Acme Ltd.") == "acme"

    def test_the_acme(self) -> None:
        assert canonicalize_name("The ACME Company") == "acme"

    def test_globex_solutions(self) -> None:
        assert canonicalize_name("Globex Solutions Inc.") == "globex"

    def test_whitespace(self) -> None:
        assert canonicalize_name("  Acme  Inc.  ") == "acme"

    def test_punctuation(self) -> None:
        # "Co." is removed by the suffix regex, leaving just "acme"
        assert canonicalize_name("Acme & Co.") == "acme"

    def test_unicode(self) -> None:
        # ™ normalizes to "tm" via NFKD, then punctuation is stripped
        assert canonicalize_name("Acme™ Inc.") == "acmetm"

    def test_empty(self) -> None:
        assert canonicalize_name("") == ""


class TestCanonicalizeEmail:
    def test_simple(self) -> None:
        assert canonicalize_email("test@example.com") == "test@example.com"

    def test_uppercase(self) -> None:
        assert canonicalize_email("TEST@EXAMPLE.COM") == "test@example.com"

    def test_gmail_dots(self) -> None:
        assert canonicalize_email("j.smith@gmail.com") == "jsmith@gmail.com"

    def test_gmail_dots_multiple(self) -> None:
        assert canonicalize_email("j.a.smith@gmail.com") == "jasmith@gmail.com"

    def test_non_gmail_dots_preserved(self) -> None:
        assert canonicalize_email("j.smith@company.com") == "j.smith@company.com"

    def test_whitespace(self) -> None:
        assert canonicalize_email("  test@example.com  ") == "test@example.com"


class TestCanonicalizePhone:
    def test_us_format(self) -> None:
        # +1-555-0101 → 10 digits (15550101), no leading-1 strip needed
        assert canonicalize_phone("+1-555-0101") == "15550101"

    def test_plain_digits(self) -> None:
        assert canonicalize_phone("5550101") == "5550101"

    def test_with_country_code(self) -> None:
        # 1-555-0101 → 8 digits (15550101), not 11 so no strip
        assert canonicalize_phone("1-555-0101") == "15550101"

    def test_parentheses(self) -> None:
        assert canonicalize_phone("(555) 010-1234") == "5550101234"

    def test_empty(self) -> None:
        assert canonicalize_phone("") == ""


class TestCanonicalizeAddress:
    def test_street_abbreviation(self) -> None:
        result = canonicalize_address("123 Main St")
        assert "street" in result
        assert "main" in result

    def test_boulevard(self) -> None:
        result = canonicalize_address("456 Oak Blvd")
        assert "boulevard" in result

    def test_lowercase(self) -> None:
        result = canonicalize_address("123 MAIN ST")
        assert result == "123 main street"

    def test_empty(self) -> None:
        assert canonicalize_address("") == ""
