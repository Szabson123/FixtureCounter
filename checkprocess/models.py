from django.db import models
import uuid


class Product(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
class SubProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='subproduct')
    name = models.CharField(max_length=255)
    child_limit = models.IntegerField(null=True, blank=True, default=20)
    
    def __str__(self) -> str:
        return self.name


class ProductProcess(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='processes')
    type = models.CharField(max_length=255)
    label = models.CharField(max_length=255)
    pos_x = models.FloatField(null=True, blank=True)
    pos_y = models.FloatField(null=True, blank=True)
    is_required = models.BooleanField(default=True)
    cond_path = models.BooleanField(null=True, blank=True) # -> checking condition path True: Pass Path False: Fail Path None: Dont check
    killing_app = models.BooleanField(default=False)
    respect_fifo_rules = models.BooleanField(default=True)
    search = models.BooleanField(default=False) # _ Forntend settings to show searching field

    def __str__(self):
        return f"{self.label} ({self.product.name})"

class ProductProcessFields(models.Model):
    product_process = models.OneToOneField(ProductProcess, on_delete=models.CASCADE, related_name='fields')
    product = models.BooleanField(default=False)
    mother_object = models.BooleanField(default=False)
    sub_product = models.BooleanField(default=False)
    is_mother = models.BooleanField(default=False)
    current_process = models.BooleanField(default=False)
    current_place = models.BooleanField(default=False)
    serial_number = models.BooleanField(default=False)
    full_sn = models.BooleanField(default=False)
    created_at = models.BooleanField(default=False)
    expire_date = models.BooleanField(default=False)
    production_date = models.BooleanField(default=False)
    exp_date_in_process = models.BooleanField(default=False)
    quranteen_time = models.BooleanField(default=False)
    max_in_process = models.BooleanField(default=False)
    ex_mother = models.BooleanField(default=False)
    sito_cycle_limit = models.BooleanField(default=False)
    sito_cycles_count = models.BooleanField(default=False)
    end = models.BooleanField(default=False)
    is_full = models.BooleanField(default=False)
    last_move = models.BooleanField(default=False)
    free_plain_text = models.BooleanField(default=False)
    sito_basic_unnamed_place = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.product_process.label} - {self.product_process.product.name}"


class ProductProcessDefault(models.Model):
    product_process = models.OneToOneField(ProductProcess, on_delete=models.CASCADE, related_name='defaults')
    how_much_days_exp_date = models.IntegerField(default=None, blank=True, null=True)
    how_much_hours_max_working = models.IntegerField(default=None, blank=True, null=True)
    quranteen_time = models.IntegerField(default=None, blank=True, null=True)
    respect_quranteen_time = models.BooleanField(default=False)
    expecting_child = models.BooleanField(default=False)
    validate_fish = models.BooleanField(default=False) # FrontEnd settings to know when check skanning fich
    show_the_couter = models.BooleanField(default=False) # FrontEnd settings to know when use endpoint
    use_list_endpoint = models.BooleanField(default=False) # From last process -> 3 in 3 out
    production_process_type = models.BooleanField(default=False) # place when we can set -> possible or continue production
    stencil_production_process_type = models.BooleanField(default=False) # stencil prod
    check_outside_database = models.CharField(max_length=255, default=None, null=True, blank=True) # place when we can connect to databaset to check for production out
    use_poke = models.BooleanField(default=False) # Place when we set poking to microservice we start production [In future add endpoint not hardcoded]
    working_only_if_obj_on_machine = models.BooleanField(default=False) # setting log to check if producing without reetoling
    quranteen_time_receive = models.IntegerField(default=None, blank=True, null=True)

    def __str__(self):
        return f'{self.product_process.label} -- {self.product_process.product.name}'
    

class ProductProcessCondition(models.Model):
    product_process = models.OneToOneField(ProductProcess, on_delete=models.CASCADE, related_name='conditions')
    pass_fail = models.BooleanField(default=True)
    

class ProductProcessStart(models.Model):
    product_process = models.OneToOneField(ProductProcess, on_delete=models.CASCADE, related_name='starts')
    how_much_days_exp_date = models.IntegerField(default=None, blank=True, null=True)
    quranteen_time = models.IntegerField(default=None, blank=True, null=True)
    respect_quranteen_time = models.BooleanField(default=False)
    expecting_child = models.BooleanField(default=False)
    add_multi = models.BooleanField(default=False)


class ProductProcessEnding(models.Model):
    product_process = models.OneToOneField(ProductProcess, on_delete=models.CASCADE, related_name='endings')


class PlaceGroupToAppKill(models.Model):
    name = models.CharField(max_length=255, unique=True)
    last_check = models.DateTimeField()
    checking = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.checking}"


class Place(models.Model):
    group = models.ForeignKey(PlaceGroupToAppKill, on_delete=models.CASCADE, related_name='place', null=True, blank=True)
    name = models.CharField(max_length=255)
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='assigned_place', null=True, blank=True, default=None)
    only_one_product_object = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('name', 'process')
    
    def __str__(self) -> str:
        return f"{self.name} -- {self.process.product.name}"


class ProductObject(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_objects')
    mother_object = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_object')
    sub_product = models.ForeignKey(SubProduct, on_delete=models.SET_NULL, related_name='product_objects', null=True, blank=True)
    
    is_mother = models.BooleanField(default=False)

    last_move = models.DateTimeField(null=True, blank=True)
    current_process = models.ForeignKey(ProductProcess, on_delete=models.SET_NULL, null=True, blank=True)
    current_place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True)
    sito_basic_unnamed_place = models.CharField(max_length=255, null=True, blank=True) # Place in cabin with no Model PLace to help production easier find stencil
    free_plain_text = models.CharField(max_length=255, null=True, blank=True)# Stencil to searching in cabin
    
    serial_number = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    full_sn = models.CharField(max_length=255, unique=True, db_index=True, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expire_date = models.DateField(null=True, blank=True, default=None)
    production_date = models.DateField(null=True, blank=True, default=None)
    exp_date_in_process = models.DateField(null=True, blank=True, default=None)
    quranteen_time = models.DateTimeField(null=True, blank=True, default=None)
    max_in_process = models.DateTimeField(null=True, blank=True, default=None)

    ex_mother = models.CharField(max_length=255, null=True, blank=True)

    sito_cycle_limit = models.PositiveIntegerField(default=300000)
    sito_cycles_count = models.PositiveIntegerField(default=0)
    
    end = models.BooleanField(default=False)
    is_full = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["current_place", "end"], name="idx_place_end"),
        ]

    def __str__(self):
        return f"{self.serial_number} ({self.product.name})"


class ProductObjectProcess(models.Model):
    product_object = models.ForeignKey(ProductObject, on_delete=models.CASCADE, related_name='assigned_processes')
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='assigned_processes')

    class Meta:
        unique_together = ('product_object', 'process')

    def __str__(self):
        return f"{self.product_object.serial_number} - {self.process.name}"


class ProductObjectProcessLog(models.Model):
    product_object = models.ForeignKey(ProductObject, on_delete=models.CASCADE, related_name='logs')
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, null=True, blank=True)
    entry_time = models.DateTimeField(auto_now_add=True)
    who_entry = models.CharField(max_length=255, null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    who_exit = models.CharField(max_length=255, null=True, blank=True)
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True, related_name="process_logs")
    movement_type = models.CharField(max_length=255, null=True, blank=True)

    name_of_productig_product = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Log for @ {self.entry_time:%Y-%m-%d %H:%M}"


class AppToKill(models.Model):
    line_name = models.OneToOneField(Place, on_delete=models.CASCADE)
    killing_flag = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.line_name.name} -- {self.line_name.process.product.name} (Group: {self.line_name.group.name}) {self.killing_flag}"
    

class Edge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='outgoing_edges')
    target = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, related_name='incoming_edges')
    source_handle = models.CharField(max_length=255, null=True, blank=True)
    target_handle = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=50, default='default')
    label = models.CharField(max_length=255, blank=True, null=True)
    animated = models.BooleanField(default=False)

    
    def __str__(self) -> str:
        return f"{self.source.label} -> {self.target.label} ({self.source.product.name})"
    

class EdgeOptionsSets(models.Model):
    edge = models.OneToOneField(Edge, on_delete=models.CASCADE, related_name='edgeoptions')
    set_not_full = models.BooleanField(default=True)
    check_same_out_same_in = models.BooleanField(default=False)
    

class OneToOneMap(models.Model):
    s_input = models.CharField(max_length=255)
    s_output = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.s_input} - {self.s_output}"
    

class LastProductOnPlace(models.Model):
    product_process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    p_type = models.ForeignKey(SubProduct, on_delete=models.CASCADE, blank=True, null=True)
    name_of_productig_product = models.CharField(max_length=255, null=True, blank=True)
    
    
class ConditionLog(models.Model):
    process = models.ForeignKey(ProductProcess, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(ProductObject, on_delete=models.CASCADE, null=True, blank=True)
    time_date = models.DateTimeField(auto_now_add=True)
    result = models.BooleanField(default=False)
    who = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        ordering = ['-time_date']
        
    
NODE_TYPE_MAP = {
    'normal': ProductProcessDefault,
    'add_receive': ProductProcessStart,
    'end': ProductProcessEnding,
    'condition': ProductProcessCondition,
}

# //////////////////////////////////////////////////////////////////////////////////


class DataBasesSpiMap(models.Model):
    data_base_name = models.CharField(max_length=255)
    ip = models.CharField(max_length=255)
    line_name = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True)
    identyficator = models.CharField(max_length=255, null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.data_base_name} -- {self.line_name.name}({self.line_name.process.product.name})"
    

class DataBasesASMMap(models.Model):
    data_base_name = models.CharField(max_length=255)
    ip = models.CharField(max_length=255)
    line_name = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True)
    identyficator = models.CharField(max_length=255, null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.data_base_name} -- {self.line_name.name}({self.line_name.process.product.name})"


class LogFromSpi(models.Model):
    fixed_id = models.IntegerField()
    pcb_name = models.CharField(max_length=255)
    time_date = models.DateTimeField(auto_now_add=True)
    machine_name = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True)
    result = models.CharField(max_length=255)


class MessageToApp(models.Model):
    line = models.ForeignKey(Place, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, default=None)
    message = models.CharField(max_length=255)
    send = models.BooleanField(default=False)
    when_trigger = models.DateTimeField()


class LogFromMistake(models.Model):
    process = models.ForeignKey(ProductProcess, on_delete=models.SET_NULL, null=True, blank=True)
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Pola tekstowe (zawsze dostępne z requestu)
    process_uuid_raw = models.CharField(max_length=255, null=True, blank=True) # ID przesłane w żądaniu
    place_name_raw = models.CharField(max_length=255, null=True, blank=True)   # Nazwa miejsca z żądania
    
    product_sn = models.CharField(max_length=255)
    who = models.CharField(max_length=255, null=True)
    
    error_message = models.TextField()
    error_code = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    movement_type = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Error {self.error_code} for {self.product_sn}"