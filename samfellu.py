#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import argparse
import exceptions
import os
import sys
import codecs
import cairo
import pymorphy2
import math
import array
from tempfile import TemporaryFile
from collections import Counter


class SamfelluError(Exception):
    pass


def rotate_vector(x, y, angle_deg):
    angle = math.radians(angle_deg)
    return (
        x * math.cos(angle) - y * math.sin(angle),
        y * math.cos(angle) + x * math.sin(angle)
    )


class Samfellu(object):
    text_encoding = 'utf-8'
    text_chunk_size = 4096
    max_word_size = 50
    points_chunk_size = 4096
    image_line_width = 1
    image_padding = .05
    image_draw_legend = True
    directions = (
        (u'Существительные', ('NOUN', )),
        (u'Глаголы и деепричастия', ('VERB', 'INFN', 'GRND')),
        (u'Прилагательные и причастия', ('ADJF', 'ADJS', 'PRTF', 'PRTS',)),
        (u'Наречия', ('ADVB', 'COMP')),
        (u'Союзы, предлоги и частицы', ('PREP', 'CONJ', 'PRCL')),
        (u'Местоимения', ('NPRO', ))
    )
    colors = ((1, 0, 0), (0, 0, 1))

    def __init__(self, text_input, input_type='filename', image_size=(640, 640), **kwargs):
        # set options
        self.text_input = text_input
        self.input_type = input_type
        self.image_size = image_size
        for k, v in kwargs.iteritems():
            # simple options check
            if k not in dir(self):
                raise SamfelluError(u'Wrong option "%s"' % k)
            setattr(self, k, v)

        # initializing
        self.legend_pos = 0.1 * self.image_size[0], 0.1 * self.image_size[1]
        self.counter = Counter()  # directions counter
        self.bbox = (0, 0, 1, 1)
        self.total_words = 0
        self.tf_dir = None
        self.tf_points = None
        self._morph = None
        self._cairo_ctx = None
        self._surface = None

    @property
    def morph(self):
        if self._morph is None:
            self._morph = pymorphy2.MorphAnalyzer()
        return self._morph

    @property
    def cairo_ctx(self):
        if self._cairo_ctx is None:
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
        start, end = self.colors[:2]
        return [start[i] + t*(end[i]-start[i]) for i in range(3)]

    def iter_text(self):
        if self.input_type == 'filename':
            try:
                f = codecs.open(self.text_input, encoding=self.text_encoding)
            except IOError, e:
                raise SamfelluError(u'Unable to open file "%s"' % self.text_input)
            except ValueError, e:
                raise SamfelluError(u'Wrong encoding "%s" for file "%s"' % (self.text_encoding, self.text_input))
            except exceptions.LookupError, e:
                raise SamfelluError(u'Wrong encoding "%s"' % self.text_encoding)

            while True:
                chunk = f.read(self.text_chunk_size)
                if not chunk:
                    break
                yield chunk

            f.close()

        elif self.input_type == 'stream':
            try:
                info = codecs.lookup(self.text_encoding)
            except exceptions.LookupError, e:
                raise SamfelluError(u'Wrong encoding "%s"' % self.text_encoding)
            sr = info.streamreader(self.text_input)
            sr.encoding = self.text_encoding

            while True:
                try:
                    chunk = sr.read(self.text_chunk_size)
                except ValueError, e:
                    raise SamfelluError(u'Wrong encoding "%s" for stream' % self.text_encoding)
                if not chunk:
                    break
                yield chunk

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
        if self.image_draw_legend:
            self.draw_legend()

    def progress(self, words=None, line_points=None, drawn_points=None):
        """ Hook to display or somehow handle processing progress """
        pass

    def write_output(self, filename):
        if self._surface is None:
            raise SamfelluError(u'Drawing context is not ready')
        self._surface.write_to_png(filename)


class ConsoleSamfellu(Samfellu):
    def progress(self, words=None, line_points=None, drawn_points=None):
        def print_progress(text, width=79):
            sys.stdout.write('    ' + text.ljust(width) + '\r')
            sys.stdout.flush()
        if words:
            print_progress(u'Words processed: %s' % words)
        elif line_points:
            print_progress(u'Line construction: %s%%' % (100*line_points/self.total_words))
        elif drawn_points:
            print_progress(u'Drawing: %s%%\r' % (100*drawn_points/self.total_words))

# directions = (
#     (u'существительные', ('noun', )),
#     (u'глаголы и деепричастия', ('verb', 'infn', 'grnd')),
#     (u'прилагательные и причастия', ('adjf', 'adjs', 'prtf', 'prts', 'advb', 'comp')),
#     (u'союзы, предлоги и пр.', ('pred', 'prep', 'conj', 'prcl', 'intj')),
#     (u'местоимения', ('npro', ))
# )


def print_error(error):
    sys.stderr.write(u'\033[91mError: %s\033[0m\n' % error)


def main():
    parser = argparse.ArgumentParser(description='Visualize russian text in curvy line according to morphology.')
    parser.add_argument('input', help=u'Input text file')
    parser.add_argument('output', help=u'Output image file')
    parser.add_argument('-c', '--encoding', help=u'Input text encoding', default='utf-8')
    parser.add_argument('-s', '--size', help=u'Image size', default='640x640')
    parser.add_argument('-l', '--legend', action='store_true', help=u'Draw a legend')

    args = parser.parse_args()

    try:
        w, h = map(int, args.size.split('x', 2))
        size = (w, h)
    except ValueError, e:
        print_error(u'Wrong size format "%s"' % args.size)
        return

    kwargs = {
        'text_encoding': args.encoding,
        'text_input': args.input,
        'image_size': size,
        'image_draw_legend': args.legend,
    }
    if args.input == '-':
        kwargs.update({
            'text_input': sys.stdin,
            'input_type': 'stream',
        })
    try:
        smf = ConsoleSamfellu(**kwargs)
        smf.process()
        print '\n'
        for i, (title, poss) in enumerate(smf.directions):
            print u'%s: %s' % (title, smf.counter[i])
        smf.write_output(args.output)
    except SamfelluError, e:
        print_error(e)


if __name__ == "__main__":
    main()
