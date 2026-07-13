"""
plate_validator.py - Validate biển số xe Việt Nam
"""
import re
from typing import Dict, Tuple

# Bảng chữ cái hợp lệ cho seri
VALID_LETTERS = set("ABCDEFGHIKLMNPRSTUVXYZ")

# Mã tỉnh Việt Nam hiện tại (11-99), trừ một số mã chưa sử dụng
INVALID_PROVINCES = {
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "13", "23", "28", "31", "39", "44", "45", "46", "50", "55", "57",
    "58", "59", "64", "66", "69", "71", "73", "78", "80", "82", "84",
    "87", "88", "91", "94", "96", "97", "98", "99"
}

PROVINCE_MAP = {
    "11": "Cao Bằng", "12": "Lạng Sơn", "14": "Quảng Ninh", "15": "Hải Phòng",
    "16": "Hải Phòng", "17": "Thái Bình", "18": "Nam Định", "19": "Phú Thọ",
    "20": "Thái Nguyên", "21": "Yên Bái", "22": "Tuyên Quang", "24": "Lào Cai",
    "25": "Lai Châu", "26": "Sơn La", "27": "Điện Biên", "29": "Hà Nội",
    "30": "Hà Nội", "32": "Hà Nội", "33": "Hà Nội", "34": "Hải Dương",
    "35": "Ninh Bình", "36": "Thanh Hóa", "37": "Nghệ An", "38": "Hà Tĩnh",
    "40": "Hà Nội", "43": "Đà Nẵng", "47": "Đắk Lắk", "48": "Đắk Nông",
    "49": "Lâm Đồng", "51": "TP.HCM", "52": "TP.HCM", "53": "TP.HCM",
    "54": "TP.HCM", "56": "TP.HCM", "60": "Đồng Nai", "61": "Bình Dương",
    "62": "Long An", "63": "Tiền Giang", "65": "Cần Thơ", "67": "An Giang",
    "68": "Kiên Giang", "70": "Tây Ninh", "72": "Bà Rịa - Vũng Tàu",
    "74": "Quảng Trị", "75": "Thừa Thiên Huế", "76": "Quảng Ngãi",
    "77": "Bình Định", "79": "Khánh Hòa", "81": "Gia Lai", "83": "Sóc Trăng",
    "85": "Ninh Thuận", "86": "Bình Thuận", "89": "Hưng Yên", "90": "Hà Nam",
    "92": "Quảng Nam", "93": "Bình Phước", "95": "Hậu Giang"
}

# OCR common confusion mapping
OCR_CORRECTIONS = {
    'O': '0', 'Q': '0', 'D': '0',
    'I': '1', 'T': '1',
    'Z': '2',
    'S': '5',
    'B': '8',
    'G': '6'
}

# Map để khôi phục chữ cái nếu nhầm lẫn ở vị trí Seri
SERI_CORRECTIONS = {
    '0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B', '6': 'G'
}

def normalize_plate_text(text: str) -> str:
    """Chuẩn hóa chuỗi OCR và sửa lỗi nhận diện cơ bản"""
    if not text:
        return ""
    
    # Bỏ khoảng trắng, dấu gạch ngang, ký tự đặc biệt, chuyển in hoa
    text = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    if len(text) < 7:
        return text

    # Sửa lỗi phổ biến ở 2 ký tự đầu (Mã tỉnh, phải là số)
    prov = list(text[:2])
    for i in range(2):
        if prov[i] in OCR_CORRECTIONS:
            prov[i] = OCR_CORRECTIONS[prov[i]]
    
    # Ký tự thứ 3 thường là chữ (Seri)
    char3 = text[2]
    if char3 in SERI_CORRECTIONS:
        char3 = SERI_CORRECTIONS[char3]
        
    # Từ ký tự thứ 4 hoặc 5 trở đi phải là số
    # Xác định độ dài seri (1 hoặc 2 chữ cái)
    seri_len = 1
    if len(text) > 3 and text[3].isalpha():
        seri_len = 2
    
    tail = list(text[2 + seri_len:])
    for i in range(len(tail)):
        if tail[i] in OCR_CORRECTIONS:
            tail[i] = OCR_CORRECTIONS[tail[i]]
            
    return "".join(prov) + char3 + text[3:2+seri_len] + "".join(tail)


def validate_vietnamese_plate(plate_text: str) -> Tuple[bool, str]:
    """
    Kiểm tra biển số có hợp lệ chuẩn VN không.
    Returns: (is_valid, province_name)
    """
    if not plate_text or len(plate_text) < 7 or len(plate_text) > 10:
        return False, ""
        
    # Mã tỉnh (2 số đầu)
    prov_code = plate_text[:2]
    if not prov_code.isdigit() or prov_code in INVALID_PROVINCES:
        return False, ""
        
    province_name = PROVINCE_MAP.get(prov_code, f"Tỉnh {prov_code}")
    
    # Regex chung: 2 số + 1-2 chữ (có thể chứa số e.g. LD) + 4-6 số
    # Note: Biển ngoại giao (NG/NN), biển đỏ, biển tạm có regex khác, 
    # tạm thời hỗ trợ các biển phổ biến
    
    pattern = r'^(\d{2})([A-Z]{1,2})(\d{4,6})$'
    
    # Hỗ trợ thêm pattern xe điện 29MĐ...
    pattern_electric = r'^(\d{2})(M[A-ZĐ])(\d{4,6})$'
    
    if re.match(pattern, plate_text) or re.match(pattern_electric, plate_text):
        return True, province_name
        
    return False, province_name

def get_plate_info(raw_text: str) -> Dict:
    """Main entry point to process plate text"""
    normalized = normalize_plate_text(raw_text)
    is_valid, prov_name = validate_vietnamese_plate(normalized)
    
    return {
        "raw_text": raw_text,
        "normalized_text": normalized,
        "is_valid": is_valid,
        "province_name": prov_name,
        "province_code": normalized[:2] if len(normalized) >= 2 else ""
    }
