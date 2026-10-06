# 상류 호출 가운데 명령(대조·미리 데우기·받기)이 낸 수 (wetherilli 363). db 기본값을 둔다 — 옛 판으로 되돌려도 행을 넣을 수 있게 (wetherilli 299)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0046_upstream_timing_db_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="upstreamday",
            name="batch",
            field=models.PositiveIntegerField(db_default=0, default=0, verbose_name="명령이 낸 것"),
        ),
    ]
