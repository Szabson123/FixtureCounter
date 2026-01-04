import pytest
from rest_framework.test import APIClient
from pytest_factoryboy import register
from .factories import ProductFactory, ProductProcessFactory, PlaceProcessFactory, SubProductFactory, ProductObjectFactory, EdgeFactory

register(ProductFactory)
register(ProductProcessFactory)
register(PlaceProcessFactory)
register(SubProductFactory)
register(ProductObjectFactory)
register(EdgeFactory)


@pytest.fixture
def api_client():
    return APIClient()