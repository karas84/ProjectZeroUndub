import re


re_table = re.compile(r"({.*?}|.)")


def make_table(font):
    font = font.strip("\n").replace("\n", "")
    table = re_table.findall(font)
    for n, x in enumerate(table):
        if x == "#":
            table[n] = f"{{0x{n:02X}}}"

    assert len(table) == 21 * 10

    return table
