EASTER_EGGS = {
    "2352004mhmds2952026258": "mohammed ahmed is my creator and he is the coolest person ever lived",
}


def check_easter_egg(user_input: str):
    return EASTER_EGGS.get(user_input)
