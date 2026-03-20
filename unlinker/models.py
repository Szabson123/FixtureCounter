from django.db import models


class UserUnlinkerProfile(models.Model):
    user_card = models.CharField(max_length=10)

    def __str__(self):
        return self.user_card


class ProcessUnlinking(models.Model):
    class Statuses(models.TextChoices):
        IN_PROGRESS = 'IP', 'In Progress'
        SUCCESS = 'SC', 'Success'
        ERROR = 'ER', 'Error'
        UNKNOWN = 'UN', 'Unknown'

    user = models.ForeignKey(UserUnlinkerProfile, on_delete=models.CASCADE, related_name='processunlinkings')
    status = models.CharField(max_length=2, choices=Statuses, default=Statuses.UNKNOWN)


class ProcessUnlinkingData(models.Model):
    class Options(models.TextChoices):
        DELETING = 'DL', 'Deleting'
        SETTING_101 = '101', 'Setting 101'

    process_unlinking = models.ForeignKey(ProcessUnlinking, on_delete=models.CASCADE, related_name='processdata')
    code = models.CharField(max_length=25) # np. 30417504
    phases = models.JSONField(null=True, blank=True) # Json z kodami np. 62006508 : True, 62006643 : False, 82003195 : True, 82003196 : False żeby dało się sięgnac do histori pi przywrócić procesy
    process_type = models.CharField(max_length=1024, choices=Options, null=True, blank=True)
    error_code = models.CharField(null=True, blank=True, max_length=255)

