import os
# from bs4 import BeautifulSoup
from PIL import Image, ExifTags
from pymap3d import ecef2enu, geodetic2ecef
import numpy as np
import pyexiv2 


def dms_to_decimal(d, m, s):
    return d + (m / 60.0) + (s / 3600.0)


def get_gps_coords(im):
    """
    Gets latitude and longitude values from image EXIF data.
    :param im:
    :return:
    """
    exif = im.getexif()
    exif_data = dict()
    for tag, value in exif.items():
        decoded_tag = ExifTags.TAGS.get(tag, tag)
        exif_data[decoded_tag] = value
    gps_info = exif_data['GPSInfo']
    lat_dms = map(lambda x: x[0] / float(x[1]), gps_info[2])
    lat = dms_to_decimal(*lat_dms)
    if gps_info[1] == 'S':
        lat *= -1
    lng_dms = map(lambda x: x[0] / float(x[1]), gps_info[4])
    lng = dms_to_decimal(*lng_dms)
    if gps_info[3] == 'W':
        lng *= -1
    return lat, lng

def convert_dms_to_deg(dms):
    dms_split = dms.split(" ")
    d = convert_string_to_float(dms_split[0])
    m = convert_string_to_float(dms_split[1]) / 60
    s = convert_string_to_float(dms_split[2]) / 3600
    deg = d + m + s
    return deg

def convert_string_to_float(string):
    str_split = string.split('/')
    return int(str_split[0]) / int(str_split[1])    # unit: mm

def get_data(path):
    lat0 = None
    lon0 = None
    h0 = 0
    for root, dirs, files in os.walk(path):
        for filename in sorted(filter(lambda x: os.path.splitext(x)[1].lower() == '.jpg', files)):
            filepath = os.path.join(root, filename)
            with pyexiv2.Image(filepath) as img:
                exif = img.read_exif()
                xmp = img.read_xmp()
                longitude = convert_dms_to_deg(exif["Exif.GPSInfo.GPSLongitude"])
                latitude = convert_dms_to_deg(exif["Exif.GPSInfo.GPSLatitude"])

                if exif["Exif.Image.Make"] == "DJI":
                    altitude = float(xmp['Xmp.drone-dji.RelativeAltitude'])
                    roll = float(xmp['Xmp.drone-dji.GimbalRollDegree'])
                    pitch = float(xmp['Xmp.drone-dji.GimbalPitchDegree'])
                    yaw = float(xmp['Xmp.drone-dji.GimbalYawDegree'])
                elif exif["Exif.Image.Make"] == "samsung":
                    altitude = convert_string_to_float(exif['Exif.GPSInfo.GPSAltitude'])
                    roll = float(xmp['Xmp.DLS.Roll']) * 180 / np.pi
                    pitch = float(xmp['Xmp.DLS.Pitch']) * 180 / np.pi
                    yaw = float(xmp['Xmp.DLS.Yaw']) * 180 / np.pi
                else:
                    altitude = 0
                    roll = 0
                    pitch = 0
                    yaw = 0
                
                if lat0 is None:
                    lat0 = latitude
                    lon0 = longitude
                x, y, z = geodetic2ecef(latitude, longitude, altitude)
                x, y, z = ecef2enu(x, y, z, lat0, lon0, h0)
                # yield filename, '{:f}'.format(x), '{:f}'.format(y), '{:f}'.format(z), yaw, pitch+90.0, roll
                yield filename, '{:f}'.format(x), '{:f}'.format(y), '{:f}'.format(z), 0.0, pitch+90.0, roll


            # with Image.open(filepath) as im:
            #     for segment, content in im.applist:
            #         marker, body = content.split(b'\x00', 1)
            #         # if segment == 'APP1' and marker == 'http://ns.adobe.com/xap/1.0/':
            #         if segment == 'APP1' :
            #             soup = BeautifulSoup(body, features='html.parser')
            #             description = soup.find('x:xmpmeta').find('rdf:rdf').find('rdf:description')
            #             pitch = float(description['drone-dji:gimbalpitchdegree']) + 90
            #             yaw = float(description['drone-dji:gimbalyawdegree'])
            #             roll = float(description['drone-dji:gimbalrolldegree'])
            #             alt = float(description['drone-dji:relativealtitude'])
            #             lat, lon = get_gps_coords(im)
            #             if lat0 is None:
            #                 lat0 = lat
            #                 lon0 = lon
            #             x, y, z = geodetic2ecef(lat, lon, alt)
            #             x, y, z = ecef2enu(x, y, z, lat0, lon0, h0)
            #             yield filename, '{:f}'.format(x), '{:f}'.format(y), '{:f}'.format(z), yaw, pitch, roll


def main():
    data = [d for d in get_data('datasets/images')]
    data = sorted(data, key=lambda x: x[0])
    x = np.array(map(lambda d: d[1], data))
    y = np.array(map(lambda d: d[2], data))
    with open('datasets/imageData.txt', 'w+') as f:
        for datum in data:
            f.write(','.join([str(d) for d in datum]) + '\n')


if __name__ == '__main__':
    main()