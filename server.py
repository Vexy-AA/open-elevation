import configparser
import json
import os
import numpy as np
import math
from bottle import route, run, request, response, hook
from gdal_interfaces import GDALTileInterface


class InternalException(ValueError):
    """
    Utility exception class to handle errors internally and return error codes to the client
    """
    pass

print('Reading config file ...')
parser = configparser.ConfigParser()
parser.read('config.ini')

HOST = parser.get('server', 'host')
PORT = parser.getint('server', 'port')
NUM_WORKERS = parser.getint('server', 'workers')
DATA_FOLDER = parser.get('server', 'data-folder')
OPEN_INTERFACES_SIZE = parser.getint('server', 'open-interfaces-size')
URL_ENDPOINT = parser.get('server', 'endpoint')
ALWAYS_REBUILD_SUMMARY = parser.getboolean('server', 'always-rebuild-summary')
CERTS_FOLDER = parser.get('server', 'certs-folder')
CERT_FILE = '%s/cert.crt' % CERTS_FOLDER
KEY_FILE = '%s/cert.key' % CERTS_FOLDER

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)
"""
Initialize a global interface. This can grow quite large, because it has a cache.
"""
interface = GDALTileInterface(DATA_FOLDER, '%s/summary.json' % DATA_FOLDER, OPEN_INTERFACES_SIZE)

if interface.has_summary_json() and not ALWAYS_REBUILD_SUMMARY:
    print('Re-using existing summary JSON')
    interface.read_summary_json()
else:
    print('Creating summary JSON ...')
    interface.create_summary_json()

def get_elevation(locations):
    """
    Get the elevation at point (lat,lng) using the currently opened interface
    :param lat:
    :param lng:
    :return:
    """
    result = []
    for (lat, lng) in locations:
        try:
            elevation = interface.lookup(lat, lng)
            result.append(elevation)
        except:
            result.append(99)

    return result


@hook('after_request')
def enable_cors():
    """
    Enable CORS support.
    :return:
    """
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'PUT, GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'


def lat_lng_from_location(location_with_comma):
    """
    Parse the latitude and longitude of a location in the format "xx.xxx,yy.yyy" (which we accept as a query string)
    :param location_with_comma:
    :return:
    """
    try:
        lat, lng = [float(i) for i in location_with_comma.split(',')]
        return lat, lng
    except:
        raise InternalException(json.dumps({'error': 'Bad parameter format "%s".' % location_with_comma}))


def query_to_locations():
    """
    Grab a list of locations from the query and turn them into [(lat,lng),(lat,lng),...]
    :return:
    """
    locations = request.query.points
    floats = []
    result = []
    if not locations:
        raise InternalException(json.dumps({'error': '"Locations" is required.'}))
    try:
        floats = np.array([float(i) for i in locations.split(',')])
    except:
        raise InternalException(json.dumps({'error': 'Bad parameter format "%s".' % location_with_comma}))
    if (floats.size % 2):
        raise InternalException(json.dumps({'error': 'uneven coord number'}))
    result = np.reshape(floats, (-1,2))
    return result


""" def body_to_locations():

    try:
        locations = request.json.get('locations', None)
    except Exception:
        raise InternalException(json.dumps({'error': 'Invalid JSON.'}))

    if not locations:
        raise InternalException(json.dumps({'error': '"Locations" is required in the body.'}))

    latlng = []
    for l in locations:
        try:
            latlng += [ (l['latitude'],l['longitude']) ]
        except KeyError:
            raise InternalException(json.dumps({'error': '"%s" is not in a valid format.' % l}))

    return latlng """


    
def do_lookup(get_locations_func):
    """
    Generic method which gets the locations in [(lat,lng),(lat,lng),...] format by calling get_locations_func
    and returns an answer ready to go to the client.
    :return:
    """
    try:
        locations = get_locations_func()
        data = get_elevation(locations)
        return {'status':'success','data':data}
        
        """ data = get_elevation(locations)
        return {'status':'success','data':dict()} """
    except InternalException as e:
        response.status = 400
        response.content_type = 'application/json'
        return e.args[0]
def getCarpetPoints(sw,ne):
    neExpected = []
    neExpected.append(0)
    neExpected.append(0)
    columns = []
    
    currentRow = sw[0]
    i = 0
    stopI = 0
    while not(math.isclose(currentRow,ne[0], abs_tol=0.00000001) and i >0):
        if (i != 0):
            currentRow = currentRow + 1/3600
            if (currentRow > ne[0]) or (math.isclose(currentRow,ne[0], abs_tol=0.00000001)):
                neExpected[0] = currentRow
                currentRow = ne[0]
                stopI = 1
        else:
            i = i+1
        rows = []
        currentCol = sw[1]
        #rows.append([currentRow,currentCol])
        j = 0
        stopJ = 0
        while(currentCol < ne[1]):
            if (j != 0):
                currentCol = currentCol + 1/3600
                if (currentCol > ne[1]):
                    neExpected[1] = currentCol
                    currentCol = ne[1]
                    stopJ = 1
            else:
                j = j +1
            if (currentCol < ne[1]):
                rows.append([currentRow,currentCol])
            if (stopJ > 0):
                break
            
        rows.append([currentRow,ne[1]])
        columns.append(rows)
        if (stopI > 0):
            break
        if (math.isclose(currentRow,ne[0], abs_tol=0.00000001)):
            break
    """ i = 1
    print('\n','\n','results:','\n',columns)
    for row in columns:
        if (len(columns) > 1):
            depth = get_elevation(row)
            print(row, depth, i,'\n')
            i = i+1
        else:
            depth = get_elevation(row)
            for y in row:
                print(y,depth[i-1],i)
                i = i+1 """
    return columns, neExpected

def getDepthsFromPoints(coordinates):
    depths = []

    for row in coordinates:
            depth = get_elevation(row)
            depths.append(depth)
    return depths

def do_lookup_carpet(get_locations_func):
    """
    Generic method which gets the locations in [(lat,lng),(lat,lng),...] format by calling get_locations_func
    and returns an answer ready to go to the client.
    :return:
    """
        
    try:
        locations = get_locations_func()
        """  print(locations[0][0])
        print(locations[0][1])
        print(locations[1][0])
        print(locations[1][1]) """
        swPoint = []
        nePoint = []
        neExpected = []
        if (locations[0][0] < locations[1][0]):
            swPoint.append(locations[0][0])
            nePoint.append(locations[1][0])
        else:
            swPoint.append(locations[1][0])
            nePoint.append(locations[0][0])
        if (locations[0][1] < locations[1][1]):
            swPoint.append(locations[0][1])
            nePoint.append(locations[1][1])
        else:
            swPoint.append(locations[1][1])
            nePoint.append(locations[0][1])
        coordinates, neExpected = getCarpetPoints(swPoint,nePoint)

        depths = getDepthsFromPoints(coordinates)

        #print('\n','results:\n','coordinates\n',coordinates)
        #print('depths\n',depths)
        #print('elements row count = ',len(depths),', columns count = ',len(depths[0]))
        depthArray = []
        for y in depths:
            for x in y:
                depthArray.append(x)
        minDepth = min(depthArray)
        maxDepth = max(depthArray)
        avgDepth = 0 if len(depthArray) == 0 else sum(depthArray)/len(depthArray)
        #print(depthArray)

        return {'status':'success','data':{'bounds':{'sw':swPoint,'ne':neExpected},'stats':{'max':maxDepth,'min':minDepth,'avg':avgDepth},'carpet':depths}}
        
        """ data = get_elevation(locations)
        return {'status':'success','data':dict()} """
    except InternalException as e:
        response.status = 400
        response.content_type = 'application/json'
        return e.args[0]
# For CORS
@route(URL_ENDPOINT, method=['OPTIONS'])
def cors_handler():
    return {}

@route(URL_ENDPOINT, method=['GET'])
def get_lookup():
    """
    GET method. Uses query_to_locations.
    :return:
    """
    return do_lookup(query_to_locations)

@route(URL_ENDPOINT+'carpet')
def get_lookup():
    """
    GET method. Uses query_to_locations.
    :return:
    """
    answer = do_lookup_carpet(query_to_locations)
    return answer

""" @route(URL_ENDPOINT, method=['POST'])
def post_lookup():
    return do_lookup(body_to_locations) """

if os.path.isfile(CERT_FILE) and os.path.isfile(KEY_FILE):
    print('Using HTTPS')
    run(host=HOST, port=PORT, server='gunicorn', workers=NUM_WORKERS, certfile=CERT_FILE, keyfile=KEY_FILE)
else:
    print('Using HTTP')
    run(host=HOST, port=PORT, server='gunicorn', workers=NUM_WORKERS)
