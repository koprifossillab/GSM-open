"""층리 뺀 5만 지질도의 제목을 "(층리 등 제외)" 로 (사람, 2026-09-30, jikhanjung 005).

`seed_catalog` 는 이미 있는 레이어의 제목을 덮지 않는다 — 사람이 손질한 것을 지키려는
것이다. 그래서 씨앗에서 고친 제목은 새로 까는 DB 에만 들고, 배포한 DB 는 여기서 바꾼다.
씨앗이 준 옛 제목 그대로일 때만 바꾼다 — 누가 손으로 고쳐 두었으면 그대로 둔다.
"""
from django.db import migrations

NAME = "L_50K_Geology_Map_NoAttitude"
OLD = "5만 지질도 (층리·엽리 뺀 판)"
NEW = "5만 지질도 (층리 등 제외)"


def forward(apps, schema_editor):
    apps.get_model("viewer", "Layer").objects.filter(name=NAME, title=OLD).update(title=NEW)


def backward(apps, schema_editor):
    apps.get_model("viewer", "Layer").objects.filter(name=NAME, title=NEW).update(title=OLD)


class Migration(migrations.Migration):
    dependencies = [("viewer", "0015_region_arctic_ocean")]
    operations = [migrations.RunPython(forward, backward)]
