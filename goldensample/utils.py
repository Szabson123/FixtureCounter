import random
import string


def gen_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))