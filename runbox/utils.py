from __future__ import annotations


class Placeholder:

    def __init__(self, arg_num: int = 0):
        self.arg_num = arg_num

    def __getitem__(self, arg_num: int) -> Placeholder:
        return Placeholder(arg_num=arg_num)


_ = Placeholder()
_1 = _[1]
_2 = _[2]
