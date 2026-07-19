# Android-specific python services.

include "config.pxi"

cdef extern void android_vibrate(double)
def vibrate(s):
    android_vibrate(s)

cdef extern void android_accelerometer_enable(int)
cdef extern void android_accelerometer_reading(float *)
accelerometer_enabled = False

def accelerometer_enable(p):
    global accelerometer_enabled
    android_accelerometer_enable(p)
    accelerometer_enabled = p

def accelerometer_reading():
    cdef float rv[3]
    android_accelerometer_reading(rv)
    return (rv[0], rv[1], rv[2])

cdef extern void android_wifi_scanner_enable()
cdef extern char * android_wifi_scan()

def wifi_scanner_enable():
    android_wifi_scanner_enable()

def wifi_scan():
    cdef char * reading
    reading = android_wifi_scan()
    reading_list = []
    for line in filter(lambda l: l, reading.split('\n')):
        [ssid, mac, level] = line.split('\t')
        reading_list.append((ssid.strip(), mac.upper().strip(), int(level)))
    return reading_list

cdef extern int android_get_dpi()
def get_dpi():
    return android_get_dpi()

cdef extern void android_show_keyboard(int)
cdef extern void android_hide_keyboard()

from jnius import autoclass, PythonJavaClass, java_method, cast
api_version = autoclass('android.os.Build$VERSION').SDK_INT
version_codes = autoclass('android.os.Build$VERSION_CODES')
python_act = autoclass(ACTIVITY_CLASS_NAME)
Rect = autoclass(u'android.graphics.Rect')
mActivity = python_act.mActivity
if mActivity:
    height = 0
    def get_keyboard_height():
        rctx = Rect()
        mActivity.getWindow().getDecorView().getWindowVisibleDisplayFrame(rctx)
        rctx.top = 0
        height = mActivity.getWindowManager().getDefaultDisplay().getHeight() - (rctx.bottom - rctx.top)
        return height
else:
    def get_keyboard_height():
        return 0

TYPE_CLASS_DATETIME = 4
TYPE_CLASS_NUMBER = 2
TYPE_NUMBER_VARIATION_PASSWORD = 16
TYPE_CLASS_TEXT = 1
TYPE_TEXT_FLAG_NO_SUGGESTIONS = 524288
TYPE_TEXT_VARIATION_EMAIL_ADDRESS = 32
TYPE_TEXT_VARIATION_PASSWORD = 128
TYPE_TEXT_VARIATION_POSTAL_ADDRESS = 112
TYPE_TEXT_VARIATION_URI = 16
TYPE_CLASS_PHONE = 3

IF BOOTSTRAP in ['sdl2', 'sdl3']:
    def remove_presplash():
        mActivity.removeLoadingScreen()

def show_keyboard(target, input_type):
    if input_type == 'text':
        _input_type = TYPE_CLASS_TEXT
    elif input_type == 'number':
        _input_type = TYPE_CLASS_NUMBER
    elif input_type == 'url':
        _input_type = TYPE_CLASS_TEXT | TYPE_TEXT_VARIATION_URI
    elif input_type == 'mail':
        _input_type = TYPE_CLASS_TEXT | TYPE_TEXT_VARIATION_EMAIL_ADDRESS
    elif input_type == 'datetime':
        _input_type = TYPE_CLASS_DATETIME
    elif input_type == 'tel':
        _input_type = TYPE_CLASS_PHONE
    elif input_type == 'address':
        _input_type = TYPE_TEXT_VARIATION_POSTAL_ADDRESS
    if hasattr(target, 'password') and target.password:
        if _input_type == TYPE_CLASS_TEXT:
            _input_type |= TYPE_TEXT_VARIATION_PASSWORD
        elif _input_type == TYPE_CLASS_NUMBER:
            _input_type |= TYPE_NUMBER_VARIATION_PASSWORD
    if hasattr(target, 'keyboard_suggestions') and not target.keyboard_suggestions:
        if _input_type == TYPE_CLASS_TEXT:
            _input_type = TYPE_CLASS_TEXT | TYPE_TEXT_FLAG_NO_SUGGESTIONS
    android_show_keyboard(_input_type)

def hide_keyboard():
    android_hide_keyboard()

cdef extern char* BUILD_MANUFACTURER
cdef extern char* BUILD_MODEL
cdef extern char* BUILD_PRODUCT
cdef extern char* BUILD_VERSION_RELEASE
cdef extern void android_get_buildinfo()

class BuildInfo:
    MANUFACTURER = None
    MODEL = None
    PRODUCT = None
    VERSION_RELEASE = None

def get_buildinfo():
    android_get_buildinfo()
    binfo = BuildInfo()
    binfo.MANUFACTURER = BUILD_MANUFACTURER
    binfo.MODEL = BUILD_MODEL
    binfo.PRODUCT = BUILD_PRODUCT
    binfo.VERSION_RELEASE = BUILD_VERSION_RELEASE
    return binfo

def open_url(url):
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    browserIntent = Intent()
    browserIntent.setAction(Intent.ACTION_VIEW)
    browserIntent.setData(Uri.parse(url))
    currentActivity = cast('android.app.Activity', mActivity)
    currentActivity.startActivity(browserIntent)
    return True

class AndroidBrowser(object):
    def open(self, url, new=0, autoraise=True):
        return open_url(url)
    def open_new(self, url):
        return open_url(url)
    def open_new_tab(self, url):
        return open_url(url)

import webbrowser
webbrowser.register('android', AndroidBrowser)

def start_service(title='Background Service', description='', arg='', as_foreground=True):
    if title is None:
        title = 'Background Service'
    if description is None:
        description = ''
    if arg is None:
        arg = ''
    mActivity = autoclass(ACTIVITY_CLASS_NAME).mActivity
    if as_foreground:
        mActivity.start_service(title, description, arg)
    else:
        mActivity.start_service_not_as_foreground(title, description, arg)

cdef extern void android_stop_service()
def stop_service():
    android_stop_service()

class AndroidService(object):
    def __init__(self, title='Python service', description='Kivy Python service started'):
        self.title = title
        self.description = description
    def start(self, arg=''):
        start_service(self.title, self.description, arg)
    def stop(self):
        stop_service()
