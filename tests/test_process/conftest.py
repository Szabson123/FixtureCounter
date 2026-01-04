import pytest
from rest_framework.test import APIClient
from pytest_factoryboy import register
from .factories import ProductFactory, ProductProcessFactory, PlaceProcessFactory, SubProductFactory, ProductObjectFactory

register(ProductFactory)
register(ProductProcessFactory)
register(PlaceProcessFactory)
register(SubProductFactory)
register(ProductObjectFactory)


@pytest.fixture
def api_client():
    return APIClient()