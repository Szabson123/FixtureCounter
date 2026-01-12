import pytest
from django.urls import reverse
from checkprocess.models import LastProductOnPlace, ProductObject, ProductObjectProcessLog, ProductProcess, ConditionLog, OneToOneMap
from .factories import ProductObjectFactory
from unittest.mock import patch


@pytest.mark.django_db
def test_create_product_happy_path(api_client):
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
    assert response.status_code == 201
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

    payload = {
        "full_sn": "TEST-SN-123",
        "place_name": "Stanowisko 1",
        "who_entry": "Janusz"
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == 400
    assert "process startowy" in str(response.data)


@pytest.mark.django_db
def test_create_fails_when_we_dont_have_sub_product(api_client, product_factory, product_process_factory, sub_product_factory):
    product = product_factory()
    process = product_process_factory(product=product, start=True)

    url = f"/api/process/{product.id}/{process.id}/product-objects/"

    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D20251229@@",
        "place_name": "Stanowisko 1",
        "who_entry": "Janusz"
    }

    response = api_client.post(url, payload, format="json")
    assert response.status_code == 400
    assert "SubProduct" in str(response.data)
    assert "nie istnieje dla produktu" in str(response.data)


@pytest.mark.django_db
def test_create_fails_when_bad_place(api_client, product_factory, product_process_factory, sub_product_factory):
    product = product_factory()
    process = product_process_factory(product=product, start=True)
    sub_product = sub_product_factory(product=product)

    url = f"/api/process/{product.id}/{process.id}/product-objects/"

    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D20251229@@",
        "place_name": "Stanowisko 1",
        "who_entry": "Janusz"
    }

    response = api_client.post(url, payload, format="json")
    assert response.status_code == 400
    assert "Takie miejsce nie istnieje" in str(response.data)


@pytest.mark.django_db
def test_create_fails_when_obj_already_exists(api_client, product_factory, product_process_factory, sub_product_factory, place_process_factory, product_object_factory):
    product = product_factory()
    process = product_process_factory(product=product, start=True)
    place = place_process_factory(process=process)
    sub_product = sub_product_factory(product=product)
    product_object = product_object_factory(product=product, sub_product=sub_product)

    url = f"/api/process/{product.id}/{process.id}/product-objects/"
    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "place_name": place.name,
        "who_entry": "53241",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == 400
    assert "Taki obiekt już istnieje" in str(response.data)

@pytest.mark.django_db
def test_create_fails_when_bad_parser_type(api_client, product_factory, product_process_factory, sub_product_factory, place_process_factory):

    product = product_factory()
    process = product_process_factory(product=product, start=True)

    url = f"/api/process/{product.id}/{process.id}/product-objects/"

    payload = {
        "full_sn": "Bad Sn No Parser",
        "place_name": "Stanowisko 1",
        "who_entry": "Janusz"
    }

    response = api_client.post(url, payload, format="json")
    assert response.status_code == 400
    assert "Nieobsługiwany typ parsera:" in str(response.data)


@pytest.mark.django_db
def test_move_fails_product_object_unknown_movement_type(api_client, product_factory, product_process_factory, place_process_factory, product_object_factory, sub_product_factory):
    product = product_factory()
    process = product_process_factory(product=product, start=True)
    place = place_process_factory(process=process)
    sub_product = sub_product_factory(product=product)
    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process, current_place=place)
    movement_type = "unknown"
    
    payload = {
        "process_uuid": process.id,
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "place_name": place.name,
        "movement_type": movement_type,
        "who": "51123",
    }

    url = f"/api/process/product-object/move/{process.id}/"
    response = api_client.post(url, payload, format="json")
    assert response.status_code == 400, f"Otrzymano błąd walidacji: {response.data}"
    assert f'Typ ruchu "{movement_type}" nie jest obsługiwany' in str(response.data)


@pytest.mark.django_db
def test_move_product_object_happy_path(api_client, product_factory, product_process_factory, place_process_factory, product_object_factory, sub_product_factory):
    product = product_factory()
    process = product_process_factory(product=product, start=True)
    place = place_process_factory(process=process)
    sub_product = sub_product_factory(product=product)
    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process, current_place=place)

    obj = ProductObject.objects.get()
    assert obj.current_place == place
    
    payload = {
        "process_uuid": process.id,
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "place_name": place.name,
        "movement_type": "move",
        "who": "51123",
    }

    url = f"/api/process/product-object/move/{process.id}/"
    response = api_client.post(url, payload, format="json")
    assert response.status_code == 200, f"Otrzymano błąd walidacji: {response.data}"
    assert "Ruch został wykonany pomyślnie." in str(response.data)

    obj.refresh_from_db()
    assert obj.current_place == None
    assert obj.current_process == ProductProcess.objects.get(id=process.id)

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "move"
    assert log.who_entry == "51123"


@pytest.mark.django_db
def test_receive_product_object_happy_path(api_client, product_factory, product_process_factory, place_process_factory, product_object_factory, sub_product_factory, edge_factory):
    product = product_factory()

    process_source = product_process_factory(product=product, start=True)
    process_target = product_process_factory(product=product, start=True)

    place = place_process_factory(process=process_target)
    sub_product = sub_product_factory(product=product)

    edge = edge_factory(source=process_source, target=process_target)
    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process_source)


    obj = ProductObject.objects.get()
    assert obj.current_place == None
    
    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "place_name": place.name,
        "movement_type": "receive",
        "who": "51123",
    }

    url = f"/api/process/product-object/move/{process_target.id}/"
    response = api_client.post(url, payload, format="json")
    assert response.status_code == 200, f"Otrzymano błąd walidacji: {response.data}"
    assert "Ruch został wykonany pomyślnie." in str(response.data)

    obj.refresh_from_db()
    assert obj.current_place == place
    assert obj.current_process == ProductProcess.objects.get(id=process_target.id)

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "receive"
    assert log.who_entry == "51123"


@pytest.mark.django_db
def test_check_product_object_happy_path(api_client, product_factory, product_process_factory, sub_product_factory, edge_factory, product_object_factory):
    product = product_factory()

    process_source = product_process_factory(product=product, start=True)
    process_target = product_process_factory(product=product, condition=True)

    sub_product = sub_product_factory(product=product)

    edge = edge_factory(source=process_source, target=process_target)
    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process_source)

    obj = ProductObject.objects.get()
    assert obj.current_place == None

    url = url = f"/api/process/product-object/move/{process_target.id}/"
    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "movement_type": "check",
        "who": "51123",
        "result": True
    }

    response = api_client.post(url, payload, format="json")
    assert response.status_code == 200, f"Otrzymano błąd walidacji: {response.data}"
    assert "Ruch został wykonany pomyślnie." in str(response.data)

    obj.refresh_from_db()
    assert obj.current_process == ProductProcess.objects.get(id=process_target.id)

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "check"
    assert log.who_entry == "51123"

    log_check = ConditionLog.objects.get()

    assert log_check.who == "51123"
    assert log_check.result == True
    assert log_check.product == obj


@pytest.mark.django_db
def test_trash_product_object_happy_path(api_client, product_factory, product_process_factory, sub_product_factory, edge_factory, product_object_factory, place_process_factory):
    product = product_factory()

    process_source = product_process_factory(product=product, start=True)
    process_target = product_process_factory(product=product, trash=True)

    place = place_process_factory(process=process_target)
    sub_product = sub_product_factory(product=product)

    edge = edge_factory(source=process_source, target=process_target)
    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process_source)


    url = url = f"/api/process/trash-obj/{process_target.id}/"
    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "movement_type": "trash",
        "who": "51123",
        "place_name": place.name
    }

    response = api_client.post(url, payload, format="json")
    assert response.status_code == 200, f"Otrzymano błąd walidacji: {response.data}"
    assert "Ruch został wykonany pomyślnie." in str(response.data)

    obj = ProductObject.objects.get()
    assert obj.current_process == ProductProcess.objects.get(id=process_target.id)
    assert obj.current_place == place
    assert obj.end == True

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "trash"
    assert log.who_entry == "51123"


@pytest.mark.django_db
def test_trash_test_product_object_happy_path(api_client, product_factory, product_process_factory, sub_product_factory, edge_factory, product_object_factory, place_process_factory):
    product = product_factory()

    process_source = product_process_factory(product=product, start=True)
    process_target = product_process_factory(product=product, trash=True)

    place = place_process_factory(process=process_target)
    sub_product = sub_product_factory(product=product)

    edge = edge_factory(source=process_source, target=process_target)
    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process_source)

    url = url = f"/api/process/product-object/move/{process_target.id}/"

    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "movement_type": "trash",
        "who": "51123",
        "place_name": place.name
    }

    response = api_client.post(url, payload, format="json")
    assert response.status_code == 200, f"Otrzymano błąd walidacji: {response.data}"
    assert "Ruch został wykonany pomyślnie." in str(response.data)

    obj = ProductObject.objects.get()
    assert obj.current_process == ProductProcess.objects.get(id=process_target.id)
    assert obj.current_place == place
    assert obj.end == True

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "trash"
    assert log.who_entry == "51123"


@patch('checkprocess.views.get_printer_info_from_card')
@pytest.mark.django_db
def test_start_new_production_happy_path(mock_get_printer_info, api_client, product_factory, product_process_factory, place_process_factory, sub_product_factory, edge_factory, product_object_factory):
    zm = OneToOneMap.objects.create(s_input="LF(OM-338-PT)", s_output="Alpha")

    product = product_factory()

    process_source = product_process_factory(product=product, start=True)
    process_target = product_process_factory(product=product, normal=True)

    place = place_process_factory(process=process_target)
    sub_product = sub_product_factory(product=product)

    edge = edge_factory(source=process_source, target=process_target)
    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process_source)

    fake_mapped_names = ['Alpha', 'ZmapowanaNazwa2']
    fake_printer_name = 'Printer_15007535'
    
    mock_get_printer_info.return_value = (fake_mapped_names, fake_printer_name)

    url = f"/api/process/start-new-prod/{process_target.id}/"

    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "place_name": place.name,
        "movement_type": "receive",
        "who": "51123",
        "production_card": "test"
    }
    
    # 4. Asercje
    response = api_client.post(url, payload, format="json")
    assert response.status_code == 200, f"Otrzymano błąd walidacji: {response.data}"

    obj = ProductObject.objects.get()
    assert obj.current_process == ProductProcess.objects.get(id=process_target.id)
    assert obj.current_place == place
    assert obj.end == False

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "receive"
    assert log.who_entry == "51123"

    last_prod = LastProductOnPlace.objects.get()
    assert last_prod.product_process == ProductProcess.objects.get(id=process_target.id)
    assert last_prod.place == place
    assert last_prod.name_of_productig_product ==  fake_printer_name


@pytest.mark.django_db
def test_continue_production_happy_path(api_client, edge_factory, product_factory, product_process_factory, place_process_factory, sub_product_factory, product_object_factory):
    product = product_factory()

    process_source = product_process_factory(product=product, start=True)
    process_target = product_process_factory(product=product, normal=True)

    place = place_process_factory(process=process_target)
    sub_product = sub_product_factory(product=product)

    edge = edge_factory(source=process_source, target=process_target)

    product_object = product_object_factory(product=product, sub_product=sub_product, current_process=process_source)

    LastProductOnPlace.objects.create(
        product_process = process_target,
        place = place,
        p_type = sub_product
    )

    payload = {
        "full_sn": "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@",
        "place_name": place.name,
        "movement_type": "receive",
        "who": "51123",
    }

    url = f"/api/process/continue-prod/{process_target.id}/"

    response = api_client.post(url, payload)
    assert response.status_code == 200, f"Otrzymano błąd walidacji: {response.data}"

    obj = ProductObject.objects.get()
    assert obj.current_process == ProductProcess.objects.get(id=process_target.id)
    assert obj.current_place == place
    assert obj.end == False

    log = ProductObjectProcessLog.objects.get()
    assert log.movement_type == "receive"
    assert log.who_entry == "51123"
