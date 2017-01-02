from django.contrib.gis.gdal import GDALRaster
from django.db.models import FileField
from django.db.models.fields.files import FieldFile


class RasterFile(FieldFile):
    """
    A FieldFile with a raster attribute.
    """

    _rast = None

    @property
    def rast(self):
        if not self._rast:
            self._rast = GDALRaster(self.file)
        return self._rast

    @rast.setter
    def rast(self, value):
        if value.driver.name == 'MEM':
            raise ValueError('Raster must be file based.')
        self._rast = value

    @property
    def bands(self):
        return self.rast.bands

    @property
    def width(self):
        return self.rast.width

    @property
    def height(self):
        return self.rast.height

    @property
    def srs(self):
        return self.rast.srs

    @property
    def srid(self):
        return self.rast.srid

    @property
    def origin(self):
        return self.rast.origin

    @property
    def skew(self):
        return self.rast.skew

    @property
    def scale(self):
        return self.rast.scale

    @property
    def extent(self):
        return self.rast.extent

    @property
    def warp(self):
        return self.rast.warp


class RasterFileField(FileField):
    """
    A file based raster field.
    """
    attr_class = RasterFile
