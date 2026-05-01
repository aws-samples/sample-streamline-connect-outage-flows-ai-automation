"""Unit tests for phone number validation."""

import sys
from pathlib import Path

# Add lambda directory to Python path
lambda_dir = Path(__file__).parent.parent
sys.path.insert(0, str(lambda_dir))

import pytest
from auth.phone_validator import (
    parse_allowlist,
    validate_phone_number,
    create_phone_validation_response
)


class TestParseAllowlist:
    """Tests for parse_allowlist function."""
    
    def test_parse_single_phone(self):
        """Test parsing single phone number."""
        result = parse_allowlist("+12345678901")
        assert result == ["+12345678901"]
    
    def test_parse_multiple_phones(self):
        """Test parsing multiple phone numbers."""
        result = parse_allowlist("+12345678901,+19876543210,+15555555555")
        assert len(result) == 3
        assert "+12345678901" in result
        assert "+19876543210" in result
        assert "+15555555555" in result
    
    def test_parse_with_whitespace(self):
        """Test parsing with whitespace around phone numbers."""
        result = parse_allowlist(" +12345678901 , +19876543210 , +15555555555 ")
        assert len(result) == 3
        assert "+12345678901" in result
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = parse_allowlist("")
        assert result == []
    
    def test_parse_with_empty_entries(self):
        """Test parsing with empty entries."""
        result = parse_allowlist("+12345678901,,+19876543210")
        assert len(result) == 2
        assert "+12345678901" in result
        assert "+19876543210" in result


class TestValidatePhoneNumber:
    """Tests for validate_phone_number function."""
    
    def test_valid_phone_in_allowlist(self):
        """Test validation with phone number in allowlist."""
        allowlist = ["+12345678901", "+19876543210"]
        result = validate_phone_number("+12345678901", allowlist)
        assert result is True
    
    def test_invalid_phone_not_in_allowlist(self):
        """Test validation with phone number not in allowlist."""
        allowlist = ["+12345678901", "+19876543210"]
        result = validate_phone_number("+15555555555", allowlist)
        assert result is False
    
    def test_empty_caller_number(self):
        """Test validation with empty caller number."""
        allowlist = ["+12345678901"]
        result = validate_phone_number("", allowlist)
        assert result is False
    
    def test_empty_allowlist(self):
        """Test validation with empty allowlist."""
        result = validate_phone_number("+12345678901", [])
        assert result is False
    
    def test_phone_normalization(self):
        """Test phone number normalization (spaces and dashes)."""
        allowlist = ["+1-234-567-8901"]
        result = validate_phone_number("+12345678901", allowlist)
        assert result is True
    
    def test_phone_with_spaces(self):
        """Test phone number with spaces."""
        allowlist = ["+1 234 567 8901"]
        result = validate_phone_number("+12345678901", allowlist)
        assert result is True


class TestCreatePhoneValidationResponse:
    """Tests for create_phone_validation_response function."""
    
    def test_authenticated_response(self):
        """Test response for authenticated phone."""
        response = create_phone_validation_response(
            authenticated=True,
            phone_number="+12345678901"
        )
        assert response["authenticated"] is True
        assert response["phoneNumber"] == "+12345678901"
        assert "timestamp" in response
        assert response["timestamp"].endswith("Z")
    
    def test_unauthenticated_response(self):
        """Test response for unauthenticated phone."""
        response = create_phone_validation_response(
            authenticated=False,
            phone_number="+15555555555"
        )
        assert response["authenticated"] is False
        assert response["phoneNumber"] == "+15555555555"
        assert "timestamp" in response


class TestPhoneValidationEdgeCases:
    """Edge case tests for phone validation."""
    
    def test_case_sensitivity(self):
        """Test that phone validation is case-insensitive (though E.164 has no letters)."""
        allowlist = ["+12345678901"]
        result = validate_phone_number("+12345678901", allowlist)
        assert result is True
    
    def test_exact_match_required(self):
        """Test that exact match is required (no partial matches)."""
        allowlist = ["+12345678901"]
        result = validate_phone_number("+1234567890", allowlist)
        assert result is False
    
    def test_multiple_phones_in_allowlist(self):
        """Test validation with multiple phones in allowlist."""
        allowlist = ["+12345678901", "+19876543210", "+15555555555"]
        assert validate_phone_number("+12345678901", allowlist) is True
        assert validate_phone_number("+19876543210", allowlist) is True
        assert validate_phone_number("+15555555555", allowlist) is True
        assert validate_phone_number("+11111111111", allowlist) is False
