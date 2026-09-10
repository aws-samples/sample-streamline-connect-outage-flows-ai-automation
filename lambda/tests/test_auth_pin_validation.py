"""Unit tests for PIN validation."""

import sys
from pathlib import Path

# Add lambda directory to Python path
lambda_dir = Path(__file__).parent.parent
sys.path.insert(0, str(lambda_dir))

import pytest
from unittest.mock import Mock, patch, MagicMock
from auth.pin_validator import validate_pin


class TestValidatePin:
    """Tests for validate_pin function."""
    
    @patch('auth.pin_validator.retrieve_pin_from_secrets_manager')
    def test_valid_pin(self, mock_retrieve):
        """Test validation with correct PIN."""
        mock_retrieve.return_value = "123456"
        result = validate_pin("123456", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin")
        assert result is True
    
    @patch('auth.pin_validator.retrieve_pin_from_secrets_manager')
    def test_invalid_pin(self, mock_retrieve):
        """Test validation with incorrect PIN."""
        mock_retrieve.return_value = "123456"
        result = validate_pin("654321", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin")
        assert result is False
    
    @patch('auth.pin_validator.retrieve_pin_from_secrets_manager')
    def test_empty_pin(self, mock_retrieve):
        """Test validation with empty PIN."""
        mock_retrieve.return_value = "123456"
        result = validate_pin("", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin")
        assert result is False
    
    @patch('auth.pin_validator.retrieve_pin_from_secrets_manager')
    def test_secrets_manager_error(self, mock_retrieve):
        """Test validation when Secrets Manager fails."""
        mock_retrieve.side_effect = Exception("Secrets Manager unavailable")
        result = validate_pin("123456", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin")
        # Should fail closed (deny access on error)
        assert result is False
    
    @patch('auth.pin_validator.retrieve_pin_from_secrets_manager')
    def test_pin_exact_match(self, mock_retrieve):
        """Test that PIN requires exact match."""
        mock_retrieve.return_value = "123456"
        assert validate_pin("123456", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin") is True
        assert validate_pin("12345", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin") is False
        assert validate_pin("1234567", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin") is False


class TestPinValidationEdgeCases:
    """Edge case tests for PIN validation."""
    
    @patch('auth.pin_validator.retrieve_pin_from_secrets_manager')
    def test_pin_with_leading_zeros(self, mock_retrieve):
        """Test PIN with leading zeros."""
        mock_retrieve.return_value = "000123"
        result = validate_pin("000123", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin")
        assert result is True
    
    @patch('auth.pin_validator.retrieve_pin_from_secrets_manager')
    def test_pin_all_same_digit(self, mock_retrieve):
        """Test PIN with all same digits."""
        mock_retrieve.return_value = "111111"
        result = validate_pin("111111", "arn:aws:secretsmanager:us-east-1:123456789012:secret:pin")
        assert result is True
