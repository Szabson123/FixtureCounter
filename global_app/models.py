from django.db import models


class MailingGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class UserToMail(models.Model):
    mail_group = models.ForeignKey(MailingGroup, on_delete=models.CASCADE)
    email = models.EmailField()

    def __str__(self):
        return f'{self.mail_group.name} - {self.email}'
