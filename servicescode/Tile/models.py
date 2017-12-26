# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from MixedWebMapServices.settings import DATABASES

class TileCache(models.Model):
    tile_info = models.CharField(max_length=256)
    image = models.BinaryField()
    create_time = models.DateTimeField()

    class Meta:
        db_table = DATABASES['default']['TABLE']
