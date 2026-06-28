from . import utils


def calculate(items):
    total = 0
    for item in items:
        if item.active:
            total += utils.score(item)
        else:
            total -= 1
    return total

