'''
map tile service
'''
import io
import StringIO
import urllib2
import json
import re
import random
import datetime

from MixedWebMapServices.settings import AMAP, DEFALT_TILE_SIZE
from PIL import Image, ImageDraw
from django.http import HttpResponse
from Tile.models import TileCache


def debug_map_tile(request):
    '''
    map tile for debug
    '''
    request_type = request.GET.get('REQUEST')

    if request_type == "GetCapabilities":
        return get_debug_capability(request.META['HTTP_HOST'])
    elif request_type == "GetMap":
        width = request.GET.get('WIDTH')
        height = request.GET.get('HEIGHT')

        if width and height and width.isdigit() and height.isdigit():
            width = int(width)
            height = int(height)
        else:
            width = DEFALT_TILE_SIZE
            height = DEFALT_TILE_SIZE

        layer = request.GET.get('LAYERS')
        if layer is None:
            layer = "Debug"

        srs = request.GET.get('srs')
        if srs is None:
            srs = "EPSG:4326"

        if layer == "Debug":
            return get_debug_map(width, height, request.GET.get('BBOX').split(','))
        elif layer == "Amap":
            return get_amap_map(width, height, request.GET.get('BBOX').split(','))
        elif layer == "Amap_Convert":
            return get_amap_map(
                width, height, request.GET.get('BBOX').split(','), coordinate_convert=True)
        else:
            return get_debug_map(width, height, request.GET.get('BBOX').split(','))


def get_debug_capability(http_host):
    capabilities = open(
        r'servicescode\MixedWebMapServices\capabilities\debug.xml').read()
    response = HttpResponse(
        capabilities % (http_host, http_host, http_host), content_type="text/xml")
    return response


def get_debug_map(width, height, locations):

    tile_image = Image.new(
        "RGB", (width, height),
        (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

    draw_object = ImageDraw.Draw(tile_image)

    debug_info = ("width:%d\nheight:%d\n"
                  "left_bottom_lon:%s\nleft_bottom_lat:%s\n"
                  "right_top_lon:%s\nright_top_lat:%s")
    text = debug_info % (
        width, height, locations[0], locations[1], locations[2], locations[3])

    draw_object.text([10, 10], text)

    img_byte_arr = io.BytesIO()
    tile_image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    response = HttpResponse(img_byte_arr, content_type="image/png")
    return response


def get_amap_map(width, height, locations, coordinate_convert=False):

    cache_search = TileCache.objects.filter(
        tile_info=get_tile_info(coordinate_convert, width, height, locations))

    need_refresh = False
    if len(cache_search) == 0:
        print "no cache"
    else:
        if (datetime.date.today() - cache_search[0].create_time).days < 30:
            response = HttpResponse(cache_search[0].image, content_type="image/png")
            return response
        else:
            need_refresh = True

    if coordinate_convert:
        request = urllib2.Request(AMAP['COORDINATE_CONVERT_API'] % (
            locations[0], locations[1], locations[2], locations[3], AMAP['AMAP_KEY']))
        coordinate_data = urllib2.urlopen(request).read()

        locations = re.split("[,;]", json.loads(coordinate_data)['locations'])

    target_width = width + 300 if width + \
        300 <= AMAP['AMAP_TILE_MAX_SIZE'] else AMAP['AMAP_TILE_MAX_SIZE']
    target_height = height + 300 if height + \
        300 <= AMAP['AMAP_TILE_MAX_SIZE'] else AMAP['AMAP_TILE_MAX_SIZE']

    url = AMAP['AMAP_TILE_API'] % (
        target_width, target_height, 1, locations[0], locations[1],
        locations[2], locations[1], locations[2], locations[3],
        locations[0], locations[3], locations[0], locations[1], AMAP['AMAP_KEY'])

    img = get_image_by_url(url).convert("RGBA")

    picked = False
    for i in range(0, target_width):
        if not picked:
            if img.getpixel((i, target_height / 2)) == (0, 0, 0, 255):
                picked = True
                temp = i
                continue
        else:
            if img.getpixel((i, target_height / 2)) != (0, 0, 0, 255):
                left_width_cut = (temp + i) / 2
                break

    picked = False
    for i in range(target_width - 1, -1, -1):
        if not picked:
            if img.getpixel((i, target_height / 2)) == (0, 0, 0, 255):
                picked = True
                temp = i
                continue
        else:
            if img.getpixel((i, target_height / 2)) != (0, 0, 0, 255):
                right_width_cut = (temp + i) / 2
                break

    picked = False
    for j in range(0, target_height):
        if not picked:
            if img.getpixel((target_width / 2, j)) == (0, 0, 0, 255):
                picked = True
                temp = j
                continue
        else:
            if img.getpixel((target_width / 2, j)) != (0, 0, 0, 255):
                left_height_cut = (temp + j) / 2.0
                break

    picked = False
    for j in range(target_height - 1, -1, -1):
        if not picked:
            if img.getpixel((target_width / 2, j)) == (0, 0, 0, 255):
                picked = True
                temp = j
                continue
        else:
            if img.getpixel((target_width / 2, j)) != (0, 0, 0, 255):
                right_height_cut = (temp + j) / 2.0
                break

    url = AMAP['AMAP_TILE_API'] % (
        target_width, target_height, 0, locations[0], locations[1],
        locations[2], locations[1], locations[2], locations[3],
        locations[0], locations[3], locations[0], locations[1], AMAP['AMAP_KEY'])

    img = get_image_by_url(url)

    box = (left_width_cut, left_height_cut, right_width_cut, right_height_cut)
    new_img = img.crop(box)

    out = new_img.resize((width, height), Image.ANTIALIAS)

    img_byte_arr = io.BytesIO()
    out.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    if need_refresh:
        tile = TileCache.objects.get(
            tile_info=get_tile_info(coordinate_convert, width, height, locations))
        tile.image = img_byte_arr
        tile.create_time = datetime.date.today()
        tile.save()
    else:
        database_image = TileCache(
            tile_info=get_tile_info(coordinate_convert, width, height, locations),
            image=img_byte_arr,
            create_time=datetime.date.today())
        database_image.save()

    response = HttpResponse(img_byte_arr, content_type="image/png")
    return response


def test_database(request):
    response = HttpResponse(json.dumps(
        {'state': True}), content_type="application/json")
    return response


def get_image_by_url(url):
    request = urllib2.Request(url)
    img_data = urllib2.urlopen(request).read()
    img_buffer = StringIO.StringIO(img_data)
    return Image.open(img_buffer)


def get_tile_info(coordinate_convert, width, height, locations):
    if coordinate_convert:
        tile_info_type = '01'
    else:
        tile_info_type = '02'
    return '%s;%s,%s;%s,%s;%s,%s' % (
        tile_info_type, width, height,
        round(float(locations[0]), 8), round(float(locations[1]), 8),
        round(float(locations[2]), 8), round(float(locations[3]), 8))


# from pyproj import Proj, transform

# inProj = Proj(init='epsg:3857')
# outProj = Proj(init='epsg:4326')
# x1,y1 = -11705274.6374,4826473.6922
# x2,y2 = transform(inProj,outProj,x1,y1)
# print x2,y2
