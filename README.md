Samfellu
========

Visualize russian text in curvy line according to morphology.


Examples
--------
 * [Different directions](examples/DIRECTIONS.md)


Usage
-----

Minimal:

```
./smfl.py textfile.txt out.png
```

Add options:
```
./smfl.py textfile.txt out.png --legend --size 1280x800 --directions 6 --palette 5
```

Process input from stdin:
```
curl -s http://lib.ru/LITRA/PUSHKIN/kapitan.txt_Ascii.txt | ./smfl.py - out.png --encoding cp1251
```


Command line options
--------------------

Positional arguments
````````````````````

Argument  | Description
----------|-------------
input     | Input text file. Use "-" to read from stdin
output    | Output image file


Optional arguments
``````````````````

Argument  | Description
----------|-------------
  -h, --help                        | show this help message and exit
  -e ENCODING, --encoding ENCODING  | Input text encoding
  -s SIZE, --size SIZE              | Image size
  -d {3less,3,4less,5,4,6}, --directions {3less,3,4less,5,4,6}      | Directions
  -n {general,none,manual}, --normalization {general,none,manual}   | Normalization
  --normals NORMALS [NORMALS ...]   | Normal values for manual normalization
  -l, --legend                      | Draw a legend
  --from-center                     | Draw line from center
  -c COLOR [COLOR ...], --color COLOR [COLOR ...]       | Line color in hex format
  -p {default,rgb,5,3}, --palette {default,rgb,5,3}     | Line color palette


Installation
------------
TODO


Using as python library
-----------------------

```
from samfellu import Samfellu, SamfelluError

try:
    smf = Samfellu(text_input=text, input_type='unicode')
    smf.process()
    smf.write_output('out.png')
except SamfelluError, e:
    pass
```


