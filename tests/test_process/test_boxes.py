import pytest

from checkprocess.models import ProductObject
from checkprocess.services.movement_service import MoveHandler, TrashHandler, ReceiveHandler


def _box_with_children(product_object_factory, product, process, place, n):
    box = product_object_factory(
        product=product, sub_product=None, full_sn="BOX-1", is_mother=True,
        current_process=process, current_place=place,
    )
    kids = [
        product_object_factory(
            product=product, sub_product=None, full_sn=f"KID-{i}", mother_object=box,
            current_process=process, current_place=place,
        )
        for i in range(n)
    ]
    return box, kids


@pytest.mark.django_db
def test_box_closes_when_last_child_moved_after_other_trashed(
    product_factory, product_process_factory, place_process_factory, product_object_factory
):
    product = product_factory()
    process = product_process_factory(product=product, normal=True)
    place = place_process_factory(process=process)
    box, (kid_a, kid_b) = _box_with_children(product_object_factory, product, process, place, 2)

    TrashHandler(kid_a, place, process, "1", movement_type="trash").execute()
    box.refresh_from_db()
    kid_a.refresh_from_db()
    assert kid_a.mother_object is None and kid_a.ex_mother == "BOX-1"
    assert box.end is False  # kid_b wciąż w kartonie

    MoveHandler(kid_b, place, process, "1", movement_type="move").execute()
    box.refresh_from_db()
    assert box.end is True
    assert box.current_place is None and box.current_process is None


@pytest.mark.django_db
def test_box_closes_when_last_child_trashed(
    product_factory, product_process_factory, place_process_factory, product_object_factory
):
    product = product_factory()
    process = product_process_factory(product=product, normal=True)
    place = place_process_factory(process=process)
    box, (kid,) = _box_with_children(product_object_factory, product, process, place, 1)

    TrashHandler(kid, place, process, "1", movement_type="trash").execute()
    box.refresh_from_db()
    assert box.end is True


@pytest.mark.django_db
def test_moving_box_keeps_children_inside(
    product_factory, product_process_factory, place_process_factory, product_object_factory
):
    product = product_factory()
    process = product_process_factory(product=product, normal=True)
    place = place_process_factory(process=process)
    box, kids = _box_with_children(product_object_factory, product, process, place, 2)

    MoveHandler(box, place, process, "1", movement_type="move").execute()
    box.refresh_from_db()
    assert box.end is False
    assert ProductObject.objects.filter(mother_object=box).count() == 2

    ReceiveHandler(box, place, process, "1", movement_type="receive").execute()
    assert ProductObject.objects.filter(mother_object=box).count() == 2
