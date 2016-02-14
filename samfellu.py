#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import codecs
import cairo
import pymorphy2
import math
from tempfile import TemporaryFile
from collections import Counter


INPUT_FILENAME = '1.txt'
OUTPUT_FILENAME = 'out.png'


class SamfelluError(Exception):
    pass


def rotate_vector(x, y, angle_deg):
    angle = math.radians(angle_deg)
    return (
        x * math.cos(angle) - y * math.sin(angle),
        y * math.cos(angle) + x * math.sin(angle)
    )


class Samfellu(object):
    def __init__(self, text_input,
            input_type='filename',
            text_encoding='utf-8',
            text_chunk_size=4096,
            image_size=(640, 640),
            image_step_size=10,
            image_line_width=2,
            image_draw_legend=True,
            max_word_size=50,
            show_progress=True):
        self.text_input = text_input
        self.input_type = input_type
        self.text_encoding = text_encoding
        self.text_chunk_size = text_chunk_size
        self.image_size = image_size
        self.image_step_size = image_step_size
        self.image_line_width = image_line_width
        self.image_draw_legend = image_draw_legend
        self.max_word_size = max_word_size
        self.show_progress = show_progress
        # directions = (
        #     (u'существительные', ('noun', )),
        #     (u'глаголы и деепричастия', ('verb', 'infn', 'grnd')),
        #     (u'прилагательные и причастия', ('adjf', 'adjs', 'prtf', 'prts', 'advb', 'comp')),
        #     (u'союзы, предлоги и пр.', ('pred', 'prep', 'conj', 'prcl', 'intj')),
        #     (u'местоимения', ('npro', ))
        # )
        self.directions = (
            (u'Существительные', ('NOUN', )),
            (u'Глаголы и деепричастия', ('VERB', 'INFN', 'GRND')),
            (u'Прилагательные и причастия', ('ADJF', 'ADJS', 'PRTF', 'PRTS',)),
            (u'Наречия', ('ADVB', 'COMP')),
            (u'Союзы, предлоги и частицы', ('PREP', 'CONJ', 'PRCL')),
            (u'Местоимения', ('NPRO', ))
        )
        self.legend_pos = 0.1 * self.image_size[0], 0.1 * self.image_size[1]
        self.counter = Counter()

    @property
    def morph(self):
        if not hasattr(self, '_morph'):
            self._morph = pymorphy2.MorphAnalyzer()
        return self._morph

    @property
    def cairo_ctx(self):
        if not hasattr(self, '_cairo_ctx'):
            self._surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *self.image_size)
            self._cairo_ctx = cairo.Context(self._surface)
            self._cairo_ctx.set_source_rgb(1, 1, 1)
            self._cairo_ctx.rectangle(0, 0, *self.image_size)
            self._cairo_ctx.fill()
            self._cairo_ctx.set_line_width(self.image_line_width)
        return self._cairo_ctx

    def split_text(self, text):
        return re.finditer(r'\w{1,%s}' % self.max_word_size, text, flags=re.MULTILINE|re.UNICODE)

    def get_direction(self, word):
        p = self.morph.parse(word)[0]
        for i, (title, poss) in enumerate(self.directions):
            for pos in poss:
                if pos in p.tag:
                    return i

    def get_color(self, ratio):
        return -ratio, .5, ratio

    def iter_text(self):
        if self.input_type == 'filename':
            try:
                f = codecs.open(self.text_input, encoding=self.text_encoding)
            except IOError, e:
                raise SamfelluError(u'Unable to open file "%s"' % self.text_input)
            except ValueError, e:
                raise SamfelluError(u'Wrong encoding "%s" for file "%s"' % (self.text_encoding, self.text_input))

            while True:
                chunk = f.read(self.text_chunk_size)
                if not chunk:
                    break
                yield chunk

            f.close()

        elif self.input_type in ('str', 'string', 'unicode'):
            if isinstance(self.text_input, str):
                try:
                    text = self.text_input.decode(self.text_encoding)
                except ValueError, e:
                    raise SamfelluError(u'Wrong encoding "%s" for input text' % self.text_encoding)
            elif isinstance(self.text_input, unicode):
                text = self.text_input
            else:
                raise SamfelluError(u'Unable to recognize input text')

            for i in xrange(0, len(text), self.text_chunk_size):
                yield text[i:i+self.text_chunk_size]

    def draw_legend(self):
        self.cairo_ctx.set_line_width(5)
        for i, (title, poss) in enumerate(self.directions):
            self.cairo_ctx.set_source_rgb(.5, .5, .5)
            self.cairo_ctx.move_to(*self.legend_pos)
            dx, dy = rotate_vector(-self.image_step_size * 6, 0, 360 * i / len(self.directions))
            self.cairo_ctx.line_to(self.legend_pos[0] + dx, self.legend_pos[1] + dy)
            self.cairo_ctx.stroke()
    
            self.cairo_ctx.move_to(self.legend_pos[0] + dx, self.legend_pos[1] + dy)
            self.cairo_ctx.set_source_rgb(0, 0, 0)
            self.cairo_ctx.show_text(u'%s (%s)' % (title, self.counter[i]))
            self.cairo_ctx.stroke()

    def print_counter(self):
        for i, (title, poss) in enumerate(self.directions):
            print u'%s: %s' % (title, self.counter[i])

    def process(self):
        x, y = float(self.image_size[0] / 2), float(self.image_size[1] / 2)
    
        i = 0
        for text in self.iter_text():
            words = [m.group() for m in self.split_text(text)]
    
            for i, word in enumerate(words, i+1):  # reuse i in the next iteration to create continuos numeration
                d = self.get_direction(word)
                if d is not None:
                    self.counter[d] += 1
                    self.cairo_ctx.move_to(x, y)
        
                    dx, dy = rotate_vector(-self.image_step_size * i / (self.counter[d] + 1) / len(self.directions), 0, 360 * d / len(self.directions))
                    x, y = x + dx, y + dy
                    self.cairo_ctx.set_source_rgb(*self.get_color(float(i) / len(words)))
                    self.cairo_ctx.line_to(x, y)
                    self.cairo_ctx.stroke()
            if self.show_progress:
                print '.',
        if self.show_progress:
            print '\n'
    
        if self.draw_legend:
            self.draw_legend()
        self.print_counter()

    def draw(self):
        self._surface

    def write_output(self, filename):
        self._surface.write_to_png(filename)

def main():
    smf = Samfellu(INPUT_FILENAME)
    smf.process()
    smf.draw()
    smf.write_output(OUTPUT_FILENAME)


if __name__ == "__main__":
    main()
