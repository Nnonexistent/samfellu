# -*- coding: utf-8 -*-
import sys
import argparse

from samfellu.base import Samfellu, SamfelluError, PALETTES, DIRECTION_CHOICES


def print_progress(text, width=79):
    sys.stdout.write('    ' + text.ljust(width) + '\r')
    sys.stdout.flush()


def print_error(error):
    sys.stderr.write(u'\033[91mError: %s\033[0m\n' % error)


class ConsoleSamfellu(Samfellu):
    def progress(self, words=None, line_points=None, drawn_points=None):
        if words:
            print_progress(u'Words processed: %s' % words)
        elif line_points:
            print_progress(u'Line construction: %s%%' % (100*line_points/self.total_words))
        elif drawn_points:
            print_progress(u'Drawing: %s%%\r' % (100*drawn_points/self.total_words))


def main():
    parser = argparse.ArgumentParser(description='Visualize russian text in curvy line according to morphology.')
    parser.add_argument('input', help=u'Input text file. Use "-" to read from stdin')
    parser.add_argument('output', help=u'Output image file')
    parser.add_argument('-e', '--encoding', help=u'Input text encoding', default='utf-8')
    parser.add_argument('-s', '--size', help=u'Image size', default='640x640')
    parser.add_argument('-d', '--directions', help=u'Directions', default='4', choices=DIRECTION_CHOICES.keys())
    parser.add_argument('-n', '--normalization', help=u'Normalization', default='general', choices=('general', 'none', 'manual'))
    parser.add_argument('--normals', type=float, nargs='+', help=u'Normal values for manual normalization')
    parser.add_argument('-l', '--legend', action='store_true', help=u'Draw a legend')
    parser.add_argument('--from-center', action='store_true', help=u'Draw line from center')
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument('-c', '--color', nargs='+', help=u'Line color in hex format')
    color_group.add_argument('-p', '--palette', choices=PALETTES.keys(), help=u'Line color palette')

    args = parser.parse_args()

    try:
        w, h = map(int, args.size.split('x', 2))
        size = (w, h)
    except ValueError, e:
        print_error(u'Wrong size format "%s"' % args.size)
        return 255

    kwargs = {
        'directions': DIRECTION_CHOICES[args.directions],
        'normalization': args.normalization,
        'text_encoding': args.encoding,
        'text_input': args.input,
        'image_size': size,
        'image_draw_legend': args.legend,
        'image_draw_from_center': args.from_center,
    }
    if args.normalization == 'manual':
        kwargs['normals'] = args.normals
    if args.color:
        kwargs.update({
            'colors': args.color
        })
    elif args.palette:
        kwargs.update({
            'colors': PALETTES[args.palette]
        })
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
        return 255

    return 1
