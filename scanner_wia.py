"""
WIA Scanner module - يشتغل مع معظم السكانرات على ويندوز
حتى لو مش عندهم TWAIN driver
"""

def get_wia_scanners():
    """إرجع قائمة السكانرات عبر WIA"""
    try:
        import win32com.client
        wia = win32com.client.Dispatch("WIA.DeviceManager")
        scanners = []
        for device in wia.DeviceInfos:
            if device.Type == 1:  # ScannerDeviceType = 1
                scanners.append({
                    "name": device.Properties("Name").Value,
                    "id": device.DeviceID
                })
        return scanners
    except Exception as e:
        print(f"[WIA] Error: {e}")
        return []


def scan_wia(device_id, dpi=300):
    """سكان صورة عبر WIA وارجعها كـ numpy array"""
    import win32com.client
    import numpy as np
    import cv2
    import tempfile, os

    wia = win32com.client.Dispatch("WIA.DeviceManager")
    
    # Find device
    device = None
    for dev_info in wia.DeviceInfos:
        if dev_info.DeviceID == device_id:
            device = dev_info.Connect()
            break
    
    if device is None:
        raise Exception("السكانر مش موجود!")

    # Get scanner item (first item)
    scanner_item = device.Items[1]

    # Set DPI
    try:
        scanner_item.Properties("Horizontal Resolution").Value = dpi
        scanner_item.Properties("Vertical Resolution").Value = dpi
        scanner_item.Properties("Current Intent").Value = 4  # Grayscale
    except:
        pass  # بعض السكانرات مش بتدعم تغيير الإعدادات

    # Scan
    image = scanner_item.Transfer("{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}")  # BMP format
    
    # Save to temp file then read with OpenCV
    tmp = tempfile.mktemp(suffix=".bmp")
    image.SaveFile(tmp)
    
    img = cv2.imread(tmp)
    os.remove(tmp)
    return img
