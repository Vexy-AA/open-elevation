import math
import os
from osgeo import gdal, osr
from lazy import lazy
from os import listdir
from os.path import isfile, join, getsize
import json
from rtree import index

# Originally based on https://stackoverflow.com/questions/13439357/extract-point-from-raster-in-gdal
class GDALInterface(object):
    SEA_LEVEL = 0
    def __init__(self, tif_path):
        super(GDALInterface, self).__init__()
        self.tif_path = tif_path
        self.loadMetadata()

    def get_corner_coords(self):
        ulx, xres, xskew, uly, yskew, yres = self.geo_transform
        lrx = ulx + (self.src.RasterXSize * xres)
        lry = uly + (self.src.RasterYSize * yres)
        return {
            'TOP_LEFT': (ulx, uly),
            'TOP_RIGHT': (lrx, uly),
            'BOTTOM_LEFT': (ulx, lry),
            'BOTTOM_RIGHT': (lrx, lry),
        }

    def loadMetadata(self):
        # open the raster and its spatial reference
        self.src = gdal.Open(self.tif_path)

        if self.src is None:
            raise Exception('Could not load GDAL file "%s"' % self.tif_path)
        spatial_reference_raster = osr.SpatialReference(self.src.GetProjection())

        # get the WGS84 spatial reference
        spatial_reference = osr.SpatialReference()
        spatial_reference.ImportFromEPSG(4326)  # WGS84

        # coordinate transformation
        self.coordinate_transform = osr.CoordinateTransformation(spatial_reference, spatial_reference_raster)
        gt = self.geo_transform = self.src.GetGeoTransform()
        self.nodata = self.src.GetRasterBand(1).GetNoDataValue()
        self.res = abs(gt[1])
        dev = (gt[1] * gt[5] - gt[2] * gt[4])
        self.geo_transform_inv = (gt[0], gt[5] / dev, -gt[2] / dev,
                                  gt[3], -gt[4] / dev, gt[1] / dev)



    @lazy
    def points_array(self):
        b = self.src.GetRasterBand(1)
        return b.ReadAsArray()

    def print_statistics(self):
        print(self.src.GetRasterBand(1).GetStatistics(True, True))


    def lookup(self, lat, lon):
        """Height at lat/lon, or None when the point is outside this file or on a no-data pixel."""
        try:

            # get coordinate of the raster
            xgeo, ygeo, zgeo = self.coordinate_transform.TransformPoint(lon, lat, 0)

            # convert it to pixel/line on band
            u = xgeo - self.geo_transform_inv[0]
            v = ygeo - self.geo_transform_inv[3]
            # floor, not int(): int() rounds -0.5 up to 0. Points outside the file are refused
            # instead of letting a negative index wrap around to the other side of the array.
            xpix = math.floor(self.geo_transform_inv[1] * u + self.geo_transform_inv[2] * v)
            ylin = math.floor(self.geo_transform_inv[4] * u + self.geo_transform_inv[5] * v)
            if not (0 <= xpix < self.src.RasterXSize and 0 <= ylin < self.src.RasterYSize):
                return None

            # look the value up
            v = self.points_array[ylin, xpix]
            if v != v or v == -32768 or (self.nodata is not None and v == self.nodata):
                return None
            return v
        except Exception as e:
            print(e)
            return None

    def close(self):
        self.src = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

class GDALTileInterface(object):
    def __init__(self, tiles_folder, summary_file, open_interfaces_size=5):
        super(GDALTileInterface, self).__init__()
        self.tiles_folder = tiles_folder
        self.summary_file = summary_file
        self.index = index.Index()
        self.cached_open_interfaces = []
        self.cached_open_interfaces_dict = {}
        self.open_interfaces_size = open_interfaces_size

    def _open_gdal_interface(self, path):
        if path in self.cached_open_interfaces_dict:
            interface = self.cached_open_interfaces_dict[path]
            self.cached_open_interfaces.remove(path)
            self.cached_open_interfaces += [path]

            return interface
        else:

            interface = GDALInterface(path)
            self.cached_open_interfaces += [path]
            self.cached_open_interfaces_dict[path] = interface

            if len(self.cached_open_interfaces) > self.open_interfaces_size:
                last_interface_path = self.cached_open_interfaces.pop(0)
                last_interface = self.cached_open_interfaces_dict[last_interface_path]
                last_interface.close()

                self.cached_open_interfaces_dict[last_interface_path] = None
                del self.cached_open_interfaces_dict[last_interface_path]

            return interface

    def _all_files(self):
        return [f for f in listdir(self.tiles_folder) if isfile(join(self.tiles_folder, f)) and f.endswith(u'.tif')]

    def has_summary_json(self):
        return os.path.exists(self.summary_file)

    def create_summary_json(self):
        all_coords = []
        for file in self._all_files():
            full_path = join(self.tiles_folder,file)
            print('Processing %s ... (%s MB)' % (full_path, getsize(full_path) / 2**20))
            i = self._open_gdal_interface(full_path)
            coords = i.get_corner_coords()

            lmin, lmax = coords['BOTTOM_RIGHT'][1], coords['TOP_RIGHT'][1]
            lngmin, lngmax = coords['TOP_LEFT'][0], coords['TOP_RIGHT'][0]
            all_coords += [
                {
                    'file': full_path,
                    'res': i.res,
                    'coords': ( lmin,  # latitude min
                                lmax,  # latitude max
                                lngmin,  # longitude min
                                lngmax,  # longitude max

                                )
                }
            ]
            print('\tDone! LAT (%s,%s) | LNG (%s,%s)' % (lmin, lmax, lngmin, lngmax))

        with open(self.summary_file, 'w') as f:
            json.dump(all_coords, f)

        self.all_coords = all_coords

        self._build_index()

    def read_summary_json(self):
        with open(self.summary_file) as f:
            self.all_coords = json.load(f)

        self._build_index()

    def lookup(self, lat, lng):
        """Height from the pieces that contain the point.

        Several pieces can contain a point (overlapping pieces, or a point on a shared
        edge): they are tried finest resolution first, then by file name, and the first
        one with data there answers. That makes overlaps deterministic and lets a piece
        with a no-data hole fall through to the next one. A point inside no piece, or on
        no-data in all of them, is sea level (0) - before, the nearest piece answered
        with whatever pixel a wrapped-around index pointed at.
        """
        hits = list(self.index.intersection((lat, lng, lat, lng), objects=True))
        if not hits:
            return GDALInterface.SEA_LEVEL
        hits.sort(key=lambda h: (h.object.get('res') or 0, h.object['file']))
        for h in hits:
            value = self._open_gdal_interface(h.object['file']).lookup(lat, lng)
            if value is not None:
                return int(value)
        return GDALInterface.SEA_LEVEL

    def _build_index(self):
        print('Building spatial index ...')
        index_id = 1
        for e in self.all_coords:
            e['index_id'] = index_id
            left, bottom, right, top = (e['coords'][0], e['coords'][2], e['coords'][1], e['coords'][3])
            self.index.insert( index_id, (left, bottom, right, top), obj=e)
