from .const import DOMAIN


def get_identifier_device(mac: str):
    return (DOMAIN, mac)


def get_identifier_entity(mac: str, address: int, type: int):
    return (DOMAIN, mac, address, type)
