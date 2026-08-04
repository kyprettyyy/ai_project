"""
密码加密工具
"""
import hashlib


SALT = "evalroute"


def encrypt_password(password: str) -> str:
    """
    密码加密(MD5 + 盐值)
    
    Args:
        password: 原始密码
        
    Returns:
        加密后的密码
    """
    salted_password = password + SALT
    return hashlib.md5(salted_password.encode('utf-8')).hexdigest()
