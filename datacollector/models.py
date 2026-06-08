from django.db import models


class CollectorsServers(models.Model):
    ip = models.CharField(max_length=255)
    user = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    basic_path = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.ip


class CollectorComputer(models.Model):
    server = models.ForeignKey(CollectorsServers, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    version_of_collectors = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} - {self.version_of_collectors}"


class CollectorComputerSettings(models.Model):
    collector_computer = models.ForeignKey(CollectorComputer, on_delete=models.CASCADE)
    watching_path = models.CharField(max_length=255)
    folder_in_server_name = models.CharField(max_length=255)
    slow_mode = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.watching_path} - {self.folder_in_server_name}"


class CollectorRuleSettings(models.Model):
    collector_computer_settings = models.ForeignKey(CollectorComputerSettings, on_delete=models.CASCADE)
    path = models.CharField(max_length=255)
    rule = models.CharField(max_length=255)
    folder_name = models.CharField(null=True, blank=True, max_length=255)
    copy_file_force = models.BooleanField(default=False) # Set as true if you want to copy file in diffrent director if False cut instead copy

    def __str__(self):
        return f"{self.collector_computer_settings.collector_computer.name} - {self.path} - {self.folder_name}"