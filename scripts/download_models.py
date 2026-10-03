import os
import sys
import urllib.request
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
MODEL_GROUPS = {'DNN face detector': [('face_deploy.prototxt', 'https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt', 1000), ('face_res10_300x300_ssd.caffemodel', 'https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel', 5000000)], 'Age-estimation model': [('age_deploy.prototxt', 'https://raw.githubusercontent.com/spmallick/learnopencv/master/AgeGender/age_deploy.prototxt', 1000), ('age_net.caffemodel', 'https://raw.githubusercontent.com/eveningglow/age-and-gender-classification/master/model/age_net.caffemodel', 10000000)]}

def download(filename, url, min_size):
    dest = os.path.join(MODEL_DIR, filename)
    if os.path.exists(dest) and os.path.getsize(dest) >= min_size:
        print(f'  [skip] {filename} already present ({os.path.getsize(dest):,} bytes)')
        return True
    print(f'  [fetch] {filename} <- {url}')
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as e:
        print(f'  [FAIL] Could not download {filename}: {e}')
        return False
    size = os.path.getsize(dest)
    if size < min_size:
        print(f'  [FAIL] {filename} downloaded but looks too small ({size} bytes) — the source may have moved. Removing partial file.')
        os.remove(dest)
        return False
    print(f'  [ok] {filename} saved ({size:,} bytes)')
    return True

def verify_group(name):
    import cv2
    try:
        if name == 'DNN face detector':
            proto = os.path.join(MODEL_DIR, 'face_deploy.prototxt')
            weights = os.path.join(MODEL_DIR, 'face_res10_300x300_ssd.caffemodel')
            cv2.dnn.readNetFromCaffe(proto, weights)
        elif name == 'Age-estimation model':
            proto = os.path.join(MODEL_DIR, 'age_deploy.prototxt')
            weights = os.path.join(MODEL_DIR, 'age_net.caffemodel')
            cv2.dnn.readNetFromCaffe(proto, weights)
        print(f'  [ok] {name} loads successfully in OpenCV DNN.')
        return True
    except Exception as e:
        print(f"  [FAIL] {name} files downloaded but OpenCV couldn't load them: {e}")
        return False
if __name__ == '__main__':
    os.makedirs(MODEL_DIR, exist_ok=True)
    results = {}
    for group_name, files in MODEL_GROUPS.items():
        print(f'{group_name}:')
        ok = all((download(fn, url, sz) for fn, url, sz in files))
        if ok:
            ok = verify_group(group_name)
        results[group_name] = ok
        print()
    for group_name, ok in results.items():
        status = 'ready' if ok else 'NOT available (will use the built-in fallback)'
        print(f'  {group_name}: {status}')
    if not all(results.values()):
        print("\nOne or more optional models didn't download — that's fine, the app still works using its built-in fallback for those. Re-run this script anytime to retry.")
        sys.exit(1)
    else:
        print('\nAll optional models ready.')
