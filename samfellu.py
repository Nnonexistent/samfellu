#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import cairo
import pymorphy2
import math
from collections import Counter


size = 10000, 10000
DIRECTIONS = (
    (u'Существительные', ('NOUN', )),
    (u'Прилигательные и причастия', ('ADJF', 'ADJS', 'PRTF', 'PRTS', 'ADVB')),
    (u'Глаголы и деепричастия', ('VERB', 'INFN', 'GRND')),
    (u'Союзы, предлоги и пр.', ('PRED', 'PREP', 'CONJ', 'PRCL', 'INTJ')),
    (u'Местоимения', ('NPRO', ))
)
STEP_SIZE = 4
LINE_WIDTH = 1


def split_text(text):
    return re.split(r'[^\w]+', text, flags=re.MULTILINE|re.UNICODE)


def get_direction(morph, word):
    p = morph.parse(word)[0]
    for i, (title, poss) in enumerate(DIRECTIONS):
        for pos in poss:
            if pos in p.tag:
                return i


def get_color(ratio):
    return -ratio, .5, ratio


def get_text():
    f = open('text.txt')
    text = f.read().decode('utf-8')
    f.close()
    return text


def rotate_vector(x, y, angle_deg):
    angle = math.radians(angle_deg)
    return (
        x * math.cos(angle) - y * math.sin(angle),
        y * math.cos(angle) + x * math.sin(angle)
    )


def draw_legend(ctx, counter, x, y):
    ctx.set_line_width(5)
    for i, (title, poss) in enumerate(DIRECTIONS):
        ctx.set_source_rgb(.5, .5, .5)
        ctx.move_to(x, y)
        dx, dy = rotate_vector(-STEP_SIZE * 6, 0, 360 * i / len(DIRECTIONS))
        ctx.line_to(x + dx, y + dy)
        ctx.stroke()

        ctx.move_to(x + dx, y + dy)
        ctx.set_source_rgb(0, 0, 0)
        ctx.show_text(u'%s (%s)' % (title, counter[i]))
        ctx.stroke()


def print_counter(counter):
    for i, (title, poss) in enumerate(DIRECTIONS):
        print u'%s: %s' % (title, counter[i])


def main(*args, **kwargs):
    text = get_text()
    words = split_text(text)

    morph = pymorphy2.MorphAnalyzer()

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *size)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(1, 1, 1)
    ctx.rectangle(0, 0, *size)
    ctx.fill()
    ctx.set_line_width(LINE_WIDTH)

    x, y = float(size[0] / 2), float(size[1] / 2)
    counter = Counter()

    for i, word in enumerate(words):
        d = get_direction(morph, word)
        if d is not None:
            counter[d] += 1
            ctx.move_to(x, y)

            dx, dy = rotate_vector(-STEP_SIZE, 0, 360 * d / len(DIRECTIONS))
            x, y = x + dx, y + dy
            ctx.set_source_rgb(*get_color(float(i) / len(words)))
            ctx.line_to(x, y)
            ctx.stroke()

    draw_legend(ctx, counter, 0.1 * size[0], 0.1 * size[1])
    surface.write_to_png('out.png')
    print_counter(counter)


if __name__ == "__main__":
    main()
