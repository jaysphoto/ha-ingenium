"""Struct classes for ingenium http api responses."""


class IngeniumHttpInstallEntry(dict):
    """
    Struct class for detected ingenium installation entries.

    Format comes from /Instal.dat, has multi-line entries for each device:

        LINE 0: map     (integer) or "KNX" FOR KNX DEVICES, otherwise the "page number" on the display
        LINE 1: label   (UTF-8 string OR EMPTY, KNX devices handle this field differently!)
        LINE 2: posX    (integer)
        LINE 3: posY    (integer)
        LINE 4: address (interger) or real1 (float)
        LINE 5: output  (integer)
        LINE 6: type    (integer)
        LINE 7: icon    (integer), KNX devices handle this field differently!

    We are mainly interested in label, address, output and type, the rest is for display
    layout on the touch panel
    """

    def __init__(self, label: str, type: int, output: int, address: int):
        """Initialize the entry."""
        self._label = label
        self._type = type
        self._output = output
        self._address = address

    def to_obj(self) -> object:
        return {
            "label": self._label,
            "type": self._type,
            "output": self._output,
            "address": self._address,
        }

    def to_dict(self) -> dict:
        return dict(
            label=self._label,
            type=self._type,
            output=self._output,
            address=self._address,
        )

    @property
    def label(self) -> str:
        """Return the label of the entry."""
        return self._label

    @property
    def type(self) -> int:
        """Return the type of the entry."""
        return self._type

    @property
    def output(self) -> int:
        """Return the bus output of the entry."""
        return self._output

    @property
    def address(self) -> int:
        """Return the bus address of the entry."""
        return self._address
