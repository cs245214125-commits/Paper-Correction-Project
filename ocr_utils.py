import easyocr
import cv2

reader = easyocr.Reader(['en'])

def extract_text(image_path):
    img = cv2.imread(image_path)
    results = reader.readtext(img)

    text = ""
    for r in results:
        text += r[1] + " "
    return text.strip()
