from django.db import migrations

GROUP_NAME = "Goldens-super-admin"
PERMISSION_CODENAMES = ["can_update_create_goldens", "can_delete_golden_dictionaries"]


def create_group(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    # uprawnienia powstaja dopiero w post_migrate, a grupa potrzebuje ich teraz
    app_config = apps.get_app_config("goldensample")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    group.permissions.add(
        *Permission.objects.filter(
            content_type__app_label="goldensample", codename__in=PERMISSION_CODENAMES
        )
    )


def remove_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("goldensample", "0032_golden_dictionaries_delete_perm"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(create_group, remove_group),
    ]
