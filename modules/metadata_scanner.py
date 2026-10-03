from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

class MetadataScanner:

    def scan(self, image_path):
        try:
            img = Image.open(image_path)
            exif_data = img._getexif()
        except Exception:
            exif_data = None
        if not exif_data:
            return {'has_exif': False, 'has_gps': False, 'findings': []}
        has_gps = False
        details = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == 'GPSInfo':
                has_gps = True
                gps_data = {}
                try:
                    for k, v in value.items():
                        gps_data[GPSTAGS.get(k, k)] = v
                except AttributeError:
                    pass
                details['GPSInfo'] = gps_data
            else:
                details[tag] = str(value)[:120]
        findings = []
        if has_gps:
            findings.append({'type': 'gps_location', 'message': 'This image contains embedded GPS coordinates revealing where it was taken.'})
        return {'has_exif': True, 'has_gps': has_gps, 'findings': findings, 'raw': details}

    def strip_metadata(self, image_path, output_path):
        img = Image.open(image_path)
        data = list(img.getdata())
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(data)
        clean_img.save(output_path)
        return output_path
