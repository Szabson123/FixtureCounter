import pytest
from django.urls import reverse
from checkprocess.models import ProductObject, ProductObjectProcessLog

@pytest.mark.django_db
def test_create_product_endpoint(api_client):
    url = '/api/process/products/' 
    payload = {
        'name': 'Nowy Super Produkt',
    }

    response = api_client.post(url, payload)

    assert response.status_code == 201
    assert response.data['name'] == 'Nowy Super Produkt'


@pytest.mark.django_db
def test_create_product_object_happy_path(api_client, product_factory, product_process_factory, place_process_factory, sub_product_factory):
    product = product_factory()
    process = product_process_factory(product=product, start=True)
    place = place_process_factory(process=process)
    sub_product = sub_product_factory(product=product)

    url = f"/api/process/{product.id}/{process.id}/product-objects/"
    payload = {
        "place_name": place.name,
        "who_entry": "53241",
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D20251229@@",
    }

    response = api_client.post(url, payload, format="json")
    assert response.status_code == 201, f"Otrzymano błąd walidacji: {response.data}"
    obj = ProductObject.objects.get()
    assert obj.product == product
    assert obj.current_process == process
    assert obj.current_place == place

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "create"
    assert log.who_entry == "53241"


@pytest.mark.django_db
def test_create_fails_when_process_is_not_start(api_client, product_factory, product_process_factory):
    product = product_factory()
    process = product_process_factory(product=product, normal=True)

    url = f"/api/process/{product.id}/{process.id}/product-objects/"

    valid_payload = {
        "full_sn": "TEST-SN-123",
        "place_name": "Stanowisko 1",
        "who_entry": "Janusz"
    }

    response = api_client.post(url, valid_payload, format="json")

    assert response.status_code == 400
    assert "process startowy" in str(response.data)


@pytest.mark.django_db
def test_create_fails_when_we_d(api_client):
    pass