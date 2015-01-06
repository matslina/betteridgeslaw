import sys
import select
import tty
import termios
import os
import os.path
import re
import random
import cPickle

import matplotlib.pyplot as plt


SAMPLE_SIZE = 100


def load_headlines():
    headlines = {}
    for f in os.listdir('.'):
        m = re.match(r'state_(.*)Crawler.pkl$', f)
        if not m:
            continue
        source = m.group(1)
        print "Loading", source
        state = cPickle.load(open(f))
        headlines[source] = state['articles'].keys()
    return headlines

def load_sample():
    if os.path.exists('sample.pkl'):
        return cPickle.load(open('sample.pkl'))

    headlines = load_headlines()
    sample = []
    for source in headlines:
        dubious = [hline for hline in headlines[source] if hline.endswith('?')]
        if len(dubious) < SAMPLE_SIZE:
            print ("Warning: only found %d (<%d) dubious headlines for %s" %
                   (len(dubious), SAMPLE_SIZE, source))
        size = min(SAMPLE_SIZE, len(dubious))
        sample.extend({'source': source,
                       'title': title}
                      for title in random.sample(dubious, size))

    random.shuffle(sample)

    return sample

def write_sample(sample):
    f = open('sample.pkl.tmp', 'w')
    cPickle.dump(sample, f)
    f.close()
    os.rename('sample.pkl.tmp', 'sample.pkl')

def main():
    sample = load_sample()
    unanswered = [hline for hline in sample if 'answer' not in hline]
    options = ''.join('\x1b[1m' + c + '\x1b[0m' if c.isupper() else c
                       for c in '[Yes / No / Maybe / Polarity fail / Quit]')
    stdin_attrs = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        for hline in sample:
            if 'answer' in hline:
                continue

            print options, hline['title']

            c = None
            while True:
                if select.select([sys.stdin], [], [], 1) == ([sys.stdin], [], []):
                    c = sys.stdin.read(1).lower()
                    break

            if c in ('y', 'n', 'm', 'p'):
                hline['answer'] = {'y': 'yes',
                                   'n': 'no',
                                   'm': 'maybe',
                                   'p': 'non-polar'}[c.lower()]
            if c.lower() in ('q', ''):
                break
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, stdin_attrs)

    write_sample(sample)

    answered = [hline for hline in sample if 'answer' in hline]
    count = {}
    for hline in answered:
        count[hline['answer']] = count.get(hline['answer'], 0) + 1

    labels = ['yes', 'no', 'maybe', 'non-polar']
    values = [count[l] for l in labels]
    colors = ['#99ff33', '#ff3333', '#ff9933', '#9999ff']

    plt.pie(values, labels=labels, colors=colors,
            autopct='%1.0f%%', shadow=False, startangle=90)
    plt.axis('equal')
    fname = 'betteridge_answer_all.png'
    print "Writing", fname
    plt.savefig(fname, bbox_inches='tight')


if __name__ == "__main__":
    sys.exit(main())
