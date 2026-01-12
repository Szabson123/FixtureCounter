import factory
from factory.django import DjangoModelFactory
from checkprocess.models import Product, ProductProcess, Place, SubProduct, ProductProcessStart, ProductProcessDefault, ProductObject, Edge, ProductProcessCondition, ProductProcessEnding


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product
    
    name = "Testowy Produkt"


class SubProductFactory(DjangoModelFactory):
    class Meta:
        model = SubProduct

    product = factory.SubFactory(ProductFactory)
    name = "Alpha"
    child_limit = 20


class ProductProcessFactory(DjangoModelFactory):
    class Meta:
        model = ProductProcess
        skip_postgeneration_save = True

    product = factory.SubFactory(ProductFactory)
    label = factory.Faker("word")
    pos_x = factory.Faker("pyfloat", positive=True, max_value=1000)
    pos_y = factory.Faker("pyfloat", positive=True, max_value=1000)

    is_required = True
    killing_app = False
    respect_fifo_rules = True
    search = False

    class Params:
        start = factory.Trait(
            type="start",
            start_config = factory.RelatedFactory(
                'tests.test_process.factories.ProductProcessStartFactory',
                factory_related_name="product_process"
            )
        )
        normal = factory.Trait(
            type="normal",
            normal_config = factory.RelatedFactory(
                'tests.test_process.factories.ProductProcessDefaultFactory',
                factory_related_name="product_process"
            )
        )
        end = factory.Trait(
            type="end",
        )

        condition = factory.Trait(
            type='condition',
            normal_config = factory.RelatedFactory(
                'tests.test_process.factories.ProductProcessConditionFactory',
                factory_related_name="product_process"
            )
        )

        trash = factory.Trait(
            type='trash',
            normal_config = factory.RelatedFactory(
                'tests.test_process.factories.ProductProcessEndingFactory',
                factory_related_name="product_process"
            )
        )


class ProductProcessConditionFactory(DjangoModelFactory):
    class Meta:
        model = ProductProcessCondition


class ProductProcessEndingFactory(DjangoModelFactory):
    class Meta:
        model = ProductProcessEnding


class ProductProcessStartFactory(DjangoModelFactory):
    class Meta:
        model = ProductProcessStart

    how_much_days_exp_date = 5
    quranteen_time = 5
    respect_quranteen_time = False
    expecting_child = False
    add_multi = False
    quranteen_time_receive = 5


class ProductProcessDefaultFactory(DjangoModelFactory):
    class Meta:
        model = ProductProcessDefault

    how_much_days_exp_date = 5
    quranteen_time = 5
    how_much_hours_max_working = 5
    respect_quranteen_time = False
    expecting_child = False
    validate_fish = False
    show_the_couter = False
    use_list_endpoint = False
    quranteen_time_receive = 5
    production_process_type = True
    stencil_production_process_type = False
    check_outside_database = False
    use_poke = False
    working_only_if_obj_on_machine = False


class PlaceProcessFactory(DjangoModelFactory):
    class Meta:
        model = Place
        
    group = None
    name = factory.Faker('word')
    process = factory.SubFactory(ProductProcessFactory)
    only_one_product_object = False


class ProductObjectFactory(DjangoModelFactory):
    class Meta:
        model = ProductObject
    
    product = factory.SubFactory(ProductFactory)
    full_sn = "[)>@06@1P262298@1T52916365@3SM5291636522322@Q12KGM000@6D20250702@14D21251229@@"
    sub_product = factory.SubFactory(ProductFactory)


class EdgeFactory(DjangoModelFactory):
    class Meta:
        model = Edge
    source = factory.SubFactory(ProductProcessFactory)
    target = factory.SubFactory(ProductProcessFactory)
        