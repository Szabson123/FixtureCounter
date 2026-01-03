import pytest
from rest_framework.test import APIClient
from pytest_factoryboy import register
from .factories import ProductFactory, ProductProcessFactory, PlaceProcessFactory, SubProductFactory

register(ProductFactory)
register(ProductProcessFactory)
register(PlaceProcessFactory)
register(SubProductFactory)


@pytest.fixture
def api_client():
    return APIClient()