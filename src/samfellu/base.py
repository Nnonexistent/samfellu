# -*- coding: utf-8 -*-
import re
import math
import exceptions
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


def draw_arrow(ctx, x, y, angle_deg, length=8):
    arrow_angle = 20
    v1 = rotate_vector(length, 0, angle_deg + arrow_angle)
    v2 = rotate_vector(length, 0, angle_deg - arrow_angle)
    ctx.move_to(x, y)
    ctx.line_to(x + v1[0], y + v1[1])
    ctx.move_to(x, y)
    ctx.line_to(x + v2[0], y + v2[1])


def parse_color(color):
    if isinstance(color, basestring):
        value = color
        if value.startswith('#'):
            value = value[1:]
        if len(value) == 3:
            value = ''.join(c+c for c in value)
        if not len(value) == 6:
            raise SamfelluError(u'Wrong color "%s"' % color)

        try:
            return [int(value[c*2:c*2+2], 16)/255.0 for c in xrange(3)]
        except (ValueError, IndexError), e:
            raise SamfelluError(u'Wrong color "%s"' % color)
    return color


PALETTES = {
    'default': ('#0CC', '#C0C', '#CC0'),
    'rgb': ('#f00', '#0f0', '#00f'),
    '5': ('#FC0347', '#6A03D9', '#0365F0', '#02B27B', '#54FF03'),
    '3': ('#F27B00', '#4B00F0', '#00A316'),
}
DIRECTION_CHOICES = {
    '6': (
        (u'Существительные', ('NOUN', )),
        (u'Глаголы и деепричастия', ('VERB', 'INFN', 'GRND')),
        (u'Прилагательные и причастия', ('ADJF', 'ADJS', 'PRTF', 'PRTS',)),
        (u'Наречия', ('ADVB', 'COMP')),
        (u'Союзы, предлоги и частицы', ('PREP', 'CONJ', 'PRCL')),
        (u'Местоимения', ('NPRO', ))
    ), 
    '5': (
        (u'Существительные', ('NOUN', )),
        (u'Глаголы и деепричастия', ('VERB', 'INFN', 'GRND')),
        (u'Прилагательные, причастия и наречия', ('ADJF', 'ADJS', 'PRTF', 'PRTS', 'ADVB', 'COMP')),
        (u'Союзы, предлоги и пр.', ('PRED', 'PREP', 'CONJ', 'PRCL', 'INTJ')),
        (u'Местоимения', ('NPRO', ))
    ),
    '4': (
        (u'Существительные и местоимения', ('NOUN', 'NPRO')),
        (u'Глаголы и деепричастия', ('VERB', 'INFN', 'GRND')),
        (u'Прилагательные, причастия и наречия', ('ADJF', 'ADJS', 'PRTF', 'PRTS', 'ADVB', 'COMP')),
        (u'Союзы, предлоги и пр.', ('PRED', 'PREP', 'CONJ', 'PRCL', 'INTJ')),
    ),
    '4less': (
        (u'Существительные', ('NOUN', )),
        (u'Глаголы', ('VERB', 'INFN')),
        (u'Прилагательные', ('ADJF', 'ADJS')),
        (u'Союзы, предлоги и частицы', ('PREP', 'CONJ', 'PRCL')),
    ),
    '3': (
        (u'Существительные и местоимения', ('NOUN', 'NPRO')),
        (u'Глаголы и деепричастия', ('VERB', 'INFN', 'GRND')),
        (u'Прилагательные, причастия и наречия', ('ADJF', 'ADJS', 'PRTF', 'PRTS', 'ADVB', 'COMP')),
    ),
    '3less': (
        (u'Существительные', ('NOUN', )),
        (u'Глаголы', ('VERB', 'INFN')),
        (u'Прилагательные', ('ADJF', 'ADJS')),
    ),
}

class Samfellu(object):
    text_encoding = 'utf-8'
    text_chunk_size = 4096
    max_word_size = 50
    points_chunk_size = 4096
    image_line_width = 1
    image_padding = .05
    image_draw_legend = True
    image_draw_from_center = False
    normalization = 'general'
    directions = DIRECTION_CHOICES['4']
    colors = PALETTES['default']

    def __init__(self, text_input, input_type='filename', image_size=(640, 640), **kwargs):
        # set options
        self.text_input = text_input
        self.input_type = input_type
        self.image_size = image_size
        for k, v in kwargs.iteritems():
            setattr(self, k, v)
        self.check(kwargs)

        # initializing
        self.legend_pos = 0.05 * self.image_size[0], 0.95 * self.image_size[1]
        self.counter = Counter()  # directions counter
        self.bbox = (0, 0, 1, 1)
        self.total_words = 0
        self.tf_dir = None  # Tempfile for directions
        self.tf_points = None  # Tempfile for points
        self._morph = None
        self._cairo_ctx = None
        self._surface = None
        self.colors = map(parse_color, self.colors)
        self.normals = getattr(self, 'normals', [])  # in case normals were set manually

    def check(self, kwargs):
        """Basic options check"""
        for k, v in kwargs.iteritems():
            if k not in dir(self):
                raise SamfelluError(u'Nonexistent option "%s"' % k)

        if self.normalization not in ('general', 'none', None, False, 'manual'):
            raise SamfelluError(u'Wrong normalization value: "%s". Use "general", "none" or "manual".' % self.normalization)
        if self.normalization == 'manual' and len(self.normals) < len(self.directions):
            raise SamfelluError(u'Not enough normals set for manual normalization.')

        if self.input_type not in ('filename', 'stream', 'str'):
            raise SamfelluError(u'Wrong input_type value: "%s". Use "filename", "stream" or "str".' % self.input_type)

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
        return (m.group() for m in re.finditer(r'\w{1,%s}' % self.max_word_size, text, flags=re.MULTILINE|re.UNICODE))

    def get_direction(self, word):
        p = self.morph.parse(word)[0]
        for i, (title, poss) in enumerate(self.directions):
            for pos in poss:
                if pos in p.tag:
                    return i

    def get_color(self, i):
        if len(self.colors) == 1:
            return self.colors[0]

        t = float(i) / (self.total_words or 1)
        n = int(math.floor(t * (len(self.colors) - 1)))  # interval number

        tn = t * (len(self.colors) - 1) - n  # position inside interval

        if t == 1:  # last
            return self.colors[-1]
        return [self.colors[n][c] + (self.colors[n+1][c] - self.colors[n][c]) * tn for c in xrange(3)]

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
                try:
                    chunk = f.read(self.text_chunk_size)
                except ValueError, e:
                    raise SamfelluError(u'Wrong encoding "%s" for file "%s"' % (self.text_encoding, self.text_input))
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
            sr.encoding = self.text_encoding  # assign encoding as in codecs.open

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
        self.tf_dir = TemporaryFile()
        for text in self.iter_text():
            directions = array.array('B')  # unsigned char

            for word in self.split_text(text):
                d = self.get_direction(word)
                if d is not None:
                    self.total_words += 1
                    self.counter[d] += 1
                    directions.append(d)

            self.tf_dir.write(directions.tostring())
            self.progress(words=self.total_words)

    def normalize(self):
        if self.normalization == 'general':
            self.normals = []
            for d in xrange(len(self.directions)):
                self.normals.append(float(self.total_words) / len(self.directions) / self.counter[d])

        elif self.normalization == 'none' or not self.normalization:
            self.normals = [1] * len(self.directions)

    def construct_line(self):
        if self.tf_dir is None:
            raise SamfelluError(u'Unable to construct line before words parsing complete')

        self.normalize()

        x, y = 0.0, 0.0
        self.tf_points = TemporaryFile()
        self.tf_dir.seek(0)
        i = 0
        while True:
            directions = array.array('B')  # unsigned char
            chunk = self.tf_dir.read(self.points_chunk_size*directions.itemsize)
            if not chunk:
                break
            directions.fromstring(chunk)

            points = array.array('d')
            for d in directions:
                i += 1
                dx, dy = rotate_vector(self.normals[d], 0, 360 * d / len(self.directions))
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

        if self.image_draw_from_center:
            self.bbox = (
                min(self.bbox[0], -self.bbox[2]),
                min(self.bbox[1], -self.bbox[3]),
                max(-self.bbox[0], self.bbox[2]),
                max(-self.bbox[1], self.bbox[3]),
            )

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
        ctx = self.cairo_ctx
        margin = 10
        vector_length = 20

        text_sizes = []
        for i, (title, poss) in enumerate(self.directions):
            text = u'%s (%s)' % (title, self.counter[i])
            w, h = ctx.text_extents(text)[2:4]
            text_sizes.append((w, h))

        x, y = self.legend_pos
        x += vector_length / 2 
        y -= sum(zip(*text_sizes)[1]) + margin * (len(self.directions) - 1)

        for i, (title, poss) in enumerate(self.directions):
            ctx.set_line_width(2)
            text = u'%s (%s)' % (title, self.counter[i])
            w, h = ctx.text_extents(text)[2:4]

            # arrow
            ctx.set_source_rgb(.5, .5, .5)
            angle = 360 * i / len(self.directions)

            vector_offset = rotate_vector(vector_length / 2, 0, angle)
            vector = rotate_vector(-vector_length / 2, 0, angle)
            base_y = y - h / 2

            ctx.move_to(x + vector_offset[0], base_y + vector_offset[1])
            ctx.line_to(x + vector[0], base_y + vector[1])
            draw_arrow(ctx, x + vector[0], base_y + vector[1], angle)
            ctx.stroke()

            # label
            ctx.move_to(x + vector_length / 2 + margin, y)
            ctx.set_line_width(3)
            ctx.set_source_rgb(1, 1, 1)
            ctx.text_path(text)
            ctx.stroke()

            ctx.move_to(x + vector_length / 2 + margin, y)
            ctx.set_source_rgb(0, 0, 0)
            ctx.show_text(text)
            ctx.stroke()


            y += h + margin

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
