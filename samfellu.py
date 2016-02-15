#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import sys
import codecs
import cairo
import pymorphy2
import math
import array
from tempfile import TemporaryFile
from collections import Counter


INPUT_FILENAME = '8.txt'
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
            points_chunk_size=4096,
            image_size=(640, 640),
            image_line_width=1,
            image_padding=.05,
            image_draw_legend=True,
            max_word_size=50):
        self.text_input = text_input
        self.input_type = input_type
        self.text_encoding = text_encoding
        self.text_chunk_size = text_chunk_size
        self.points_chunk_size = points_chunk_size
        self.image_size = image_size
        self.image_line_width = image_line_width
        self.image_padding = image_padding
        self.image_draw_legend = image_draw_legend
        self.max_word_size = max_word_size
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
        self.counter = Counter()  # directions counter
        self.bbox = (0, 0, 0, 0)
        self.total_words = 0
        self.tf_dir = None
        self.tf_points = None

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

    def get_color(self, i):
        t = float(i) / (self.total_words or 1)
        start, end = (1, 0, 0), (0, 0 ,1)
        return [start[i] + t*(end[i]-start[i]) for i in range(3)]

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

    def parse_words(self):
        i = 0
        self.tf_dir = TemporaryFile()
        for text in self.iter_text():
            directions = array.array('b')
            words = (m.group() for m in self.split_text(text))

            for word in words:
                i += 1
                d = self.get_direction(word)
                if d is not None:
                    self.counter[d] += 1
                    directions.append(d)

            self.tf_dir.write(directions.tostring())
            self.progress(words=i)
        self.total_words = sum(self.counter.itervalues())

    def construct_line(self):
        if self.tf_dir is None:
            raise SamfelluError(u'Unable to construct line before words parsing complete')

        x, y = 0.0, 0.0
        self.tf_points = TemporaryFile()
        self.tf_dir.seek(0)
        i = 0
        while True:
            directions = array.array('b')
            chunk = self.tf_dir.read(self.points_chunk_size*directions.itemsize)
            if not chunk:
                break
            directions.fromstring(chunk)

            points = array.array('d')
            for d in directions:
                i += 1
                dx, dy = rotate_vector(-1, 0, 360 * d / len(self.directions))
                x, y = x + dx, y + dy
                points.append(x)
                points.append(y)
                self.bbox = (
                    min(self.bbox[0], x),
                    min(self.bbox[1], y),
                    max(self.bbox[2], x),
                    max(self.bbox[3], y),
                )
            self.tf_points.write(points.tostring())
            self.progress(line_points=i)
        self.tf_dir.close()
        self.tf_dir = None

    def draw(self):
        if self.tf_points is None:
            raise SamfelluError(u'Unable to draw line before constructing it')
        if (self.bbox[2]-self.bbox[0])/(self.bbox[3]-self.bbox[1]) > float(self.image_size[0]) / self.image_size[1]:
            ratio = (self.bbox[2] - self.bbox[0]) / self.image_size[0] / (1 - 2 * self.image_padding)
            tr_x = ratio * self.image_size[0] * self.image_padding - self.bbox[0]
            tr_y = ratio * self.image_size[1] / 2 - self.bbox[3] / 2 - self.bbox[1] / 2
        else:
            ratio = (self.bbox[3] - self.bbox[1]) / self.image_size[1] / (1 - 2 * self.image_padding)
            tr_x = ratio * self.image_size[0] / 2 - self.bbox[2] / 2 - self.bbox[0] / 2
            tr_y = ratio * self.image_size[1] * self.image_padding - self.bbox[1]

        i = 0
        first = True
        self.tf_points.seek(0)
        while True:
            points = array.array('d')
            chunk = self.tf_points.read(self.points_chunk_size*points.itemsize)
            if not chunk:
                break
            points.fromstring(chunk)

            for px, py in zip(points[::2], points[1::2]):
                i += 1
                x = (px + tr_x) / ratio
                y = (py + tr_y) / ratio
                if not first:
                    self.cairo_ctx.set_source_rgb(*self.get_color(i))
                    self.cairo_ctx.line_to(x, y)
                    self.cairo_ctx.stroke()
                self.cairo_ctx.move_to(x, y)
                first = False
            self.progress(drawn_points=i)
        self.tf_points.close()
        self.tf_points = None

    def draw_legend(self):
        self.cairo_ctx.set_line_width(5)
        for i, (title, poss) in enumerate(self.directions):
            self.cairo_ctx.set_source_rgb(.5, .5, .5)
            self.cairo_ctx.move_to(*self.legend_pos)
            dx, dy = rotate_vector(-50, 0, 360 * i / len(self.directions))
            self.cairo_ctx.line_to(self.legend_pos[0] + dx, self.legend_pos[1] + dy)
            self.cairo_ctx.stroke()
    
            self.cairo_ctx.move_to(self.legend_pos[0] + dx, self.legend_pos[1] + dy)
            self.cairo_ctx.set_source_rgb(0, 0, 0)
            self.cairo_ctx.show_text(u'%s (%s)' % (title, self.counter[i]))
            self.cairo_ctx.stroke()

    def process(self):
        self.parse_words()
        self.construct_line()
        self.draw()
        if self.draw_legend:
            self.draw_legend()

    def progress(self, words=None, line_points=None, drawn_points=None):
        """ Hook to display or somehow handle processing progress """
        pass

    def write_output(self, filename):
        self._surface.write_to_png(filename)


class ConsoleSamfellu(Samfellu):
    def progress(self, words=None, line_points=None, drawn_points=None):
        if words:
            sys.stdout.write(u'Words processed: %s\r' % words)
            sys.stdout.flush()
        elif line_points:
            sys.stdout.write(u'Line construction: %s%%\r' % (100*line_points/self.total_words))
            sys.stdout.flush()
        elif drawn_points:
            sys.stdout.write(u'Drawing: %s%%\r' % (100*drawn_points/self.total_words))
            sys.stdout.flush()


def main():
    smf = ConsoleSamfellu(INPUT_FILENAME)
    smf.process()
    print '\n'
    for i, (title, poss) in enumerate(smf.directions):
        print u'%s: %s' % (title, smf.counter[i])
    smf.write_output(OUTPUT_FILENAME)


if __name__ == "__main__":
    main()
