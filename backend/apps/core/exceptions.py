from rest_framework import status
from rest_framework.exceptions import APIException


class BusinessRuleError(APIException):
    """A valid request that breaks a business rule (returns HTTP 400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Business rule violated."
    default_code = "business_rule"


class InsufficientStock(BusinessRuleError):
    default_detail = "Insufficient stock."
    default_code = "insufficient_stock"
