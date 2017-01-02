from __future__ import unicode_literals

import inspect
import os
import shutil
import tempfile
from importlib import import_module

import numpy

from django.conf import settings
from django.core.files import File
from django.core.urlresolvers import reverse
from django.test import Client, TransactionTestCase
from raster.models import Legend, LegendEntry, LegendEntryOrder, LegendSemantics, RasterLayer


class RasterTestCase(TransactionTestCase):

    def setUp(self):
        # Instantiate Django file instance for rasterlayer generation
        self.pwd = os.path.dirname(os.path.abspath(
            inspect.getfile(inspect.currentframe())
        ))

        # Create legend semantics
        sem1 = LegendSemantics.objects.create(name='Earth')
        sem2 = LegendSemantics.objects.create(name='Wind')
        sem3 = LegendSemantics.objects.create(name='Water')
        sem4 = LegendSemantics.objects.create(name='Fire')

        # Create legend entries (semantics with colors and expressions)
        ent1 = LegendEntry.objects.create(semantics=sem1, expression='4', color='#123456')
        ent2 = LegendEntry.objects.create(semantics=sem1, expression='10', color='#123456')
        ent3 = LegendEntry.objects.create(semantics=sem2, expression='2', color='#654321')
        ent4 = LegendEntry.objects.create(semantics=sem3, expression='4', color='#654321')
        ent5 = LegendEntry.objects.create(semantics=sem4, expression='4', color='#654321')
        ent6 = LegendEntry.objects.create(semantics=sem4, expression='5', color='#123456')
        ent7 = LegendEntry.objects.create(semantics=sem4, expression='(x >= 2) & (x < 5)', color='#123456')

        # Create legends
        leg = Legend.objects.create(title='MyLegend')
        LegendEntryOrder.objects.create(legend=leg, legendentry=ent1, code='1')

        self.legend = Legend.objects.create(title='Algebra Legend')
        LegendEntryOrder.objects.create(legend=self.legend, legendentry=ent2, code='1')
        LegendEntryOrder.objects.create(legend=self.legend, legendentry=ent3, code='2')

        leg2 = Legend.objects.create(title='Other')
        LegendEntryOrder.objects.create(legend=leg2, legendentry=ent4, code='1')

        leg3 = Legend.objects.create(title='Dual')
        LegendEntryOrder.objects.create(legend=leg3, legendentry=ent5, code='1')
        LegendEntryOrder.objects.create(legend=leg3, legendentry=ent6, code='2')

        leg_expression = Legend.objects.create(title='Legend with Expression')
        LegendEntryOrder.objects.create(legend=leg_expression, legendentry=ent7, code='1')
        self.legend_with_expression = leg_expression

        # Create user sssion
        # https://docs.djangoproject.com/en/1.9/topics/http/sessions/#using-sessions-out-of-views

        engine = import_module(settings.SESSION_ENGINE)
        store = engine.SessionStore()
        store.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = store.session_key

        # Create test raster layer
        rasterfile = File(
            open(os.path.join(self.pwd, 'raster.tif.zip'), 'rb'),
            name='raster.tif.zip'
        )
        settings.MEDIA_ROOT = tempfile.mkdtemp()
        self.media_root = settings.MEDIA_ROOT
        self.rasterlayer = RasterLayer.objects.create(
            name='Raster data',
            description='Small raster for testing',
            datatype='ca',
            rasterfile=rasterfile,
            legend=leg,
        )
        # Create another layer with no tiles
        self.empty_rasterlayer = RasterLayer.objects.create(
            name='Raster data',
            description='Small raster for testing',
            datatype='ca',
            rasterfile=rasterfile,
        )
        self.empty_rasterlayer.rastertile_set.all().delete()

        # Setup query urls for tests
        self.tile = self.rasterlayer.rastertile_set.get(tilez=11, tilex=552, tiley=858)
        self.tile_url = reverse('tms', kwargs={
            'z': self.tile.tilez, 'y': self.tile.tiley, 'x': self.tile.tilex,
            'layer': self.rasterlayer.id, 'format': '.png'
        })
        self.algebra_tile_url = reverse('algebra', kwargs={
            'z': self.tile.tilez, 'y': self.tile.tiley,
            'x': self.tile.tilex, 'format': '.png'
        })

        # Precompute expected totals from value count
        expected = {}
        for tile in self.rasterlayer.rastertile_set.filter(tilez=11):
            val, counts = numpy.unique(tile.rast.rast.bands[0].data(), return_counts=True)
            for pair in zip(val, counts):
                if pair[0] in expected:
                    expected[pair[0]] += pair[1]
                else:
                    expected[pair[0]] = pair[1]

        # Drop nodata value (aggregation uses masked arrays)
        expected.pop(255)

        self.expected_totals = expected
        self.continuous_expected_histogram = {
            '(0.0, 0.90000000000000002)': 21741,
            '(0.90000000000000002, 1.8)': 695,
            '(1.8, 2.7000000000000002)': 56,
            '(2.7000000000000002, 3.6000000000000001)': 4131,
            '(3.6000000000000001, 4.5)': 31490,
            '(7.2000000000000002, 8.0999999999999996)': 1350,
            '(8.0999999999999996, 9.0)': 2977
        }

        # Instantiate test client
        self.client = Client()

    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT)

    def assertIsExpectedTile(self, png, tile):
        with open(os.path.join('tests/expected_tiles/', '%s.png' % tile), 'rb') as f:
            self.assertEqual(bytes(png), f.read())
