from pathlib import Path
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()
import pytesseract
import exifread
import tempfile
import os 
import json

def enrich_image(path:Path)->dict :
    path = Path(path)
    meta = {}

    # OCR : for extracting text in images
    try :
        img = Image.open(path)
        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        # pytesseract struggles with HEIC-sourced images; save to temp PNG
        if path.suffix.lower() in {".heic", ".heif"}:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img.save(tmp.name, "PNG")
                ocr_text = pytesseract.image_to_string(tmp.name).strip()
                os.unlink(tmp.name)
        else:
            ocr_text = pytesseract.image_to_string(img).strip()

        if ocr_text :
            meta["ocr_text"] = ocr_text[:2000]
    except Exception as e :
        print(f"[enricher] OCR failed {path.name} with error  : {e}")

    # EXIF :  extract timestamp and gps -->  for metadata of the image
    try :
        with open(path,"rb") as f : 
            tags  = exifread.process_file(f , stop_tag = "GPS GPSLatitude")
        if  "EXIF DateTimeOriginal" in tags : 
            meta["exif_timestamp"] = str(tags['EXIF DateTimeOriginal'])

        lat = tags.get("GPS GPSLatitude")
        lon = tags.get("GPS GPSLongitude")

        if lat and lon : 
            meta["exif_gps"] = f"{lat} {lon}"
    except Exception as e : 
        print(f"[enricher] EXIF failed {path.name} with error :{e}")

    return meta


# using the enrich_audio part !! --> now or after

# testing funtion :
# path = '/Users/varunnihar/Downloads/IMG_1110.HEIC'
# res = enrich_image(path)
# print(json.dumps(res, indent=2))


