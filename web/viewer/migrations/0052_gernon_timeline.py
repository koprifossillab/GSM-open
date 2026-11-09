"""동남극 고지형의 연대마다 레이어를 하나로 묶었다 — 옛 행을 지운다 (wetherilli 439).

`seed_catalog` 는 씨앗에 없는 행을 지우지 않는다 — 넣고 손볼 뿐이다. 열 연대의 래스터(`gernontopo:<연대>`)와
등고선(`antpapers:gernon_<연대>ma`)은 씨앗에서 빠지고 연대 막대를 따르는 레이어 하나씩(`gernontopo:paleotopo`·
`antpapers:gernon_contours`)이 대신한다. 빈 레이어군 "동남극 고지형 등고선 (Gernon 2026)" 도 지운다 — 등고선은
래스터와 같은 레이어군으로 옮겼다. 되돌리기는 하지 않는다(옛 씨앗으로 `seed_catalog` 를 부르면 다시 생긴다).
"""
from django.db import migrations

AGES = (100, 90, 80, 70, 60, 50, 44, 40, 36, 34)
OLD = [f"gernontopo:{a}" for a in AGES] + [f"antpapers:gernon_{a}ma" for a in AGES]
OLD_GROUP = "동남극 고지형 등고선 (Gernon 2026)"


def forward(apps, schema_editor):
    Layer = apps.get_model("viewer", "Layer")
    LayerGroup = apps.get_model("viewer", "LayerGroup")
    Layer.objects.filter(name__in=OLD).delete()
    LayerGroup.objects.filter(name=OLD_GROUP, region="antarctica", layers__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("viewer", "0051_offline_pack_request")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
