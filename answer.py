import sys
import select
import tty
import termios
import os
import os.path
import re
import random
import cPickle
import subprocess

import matplotlib.pyplot as plt


def load_headlines():
    if os.path.exists('headlines.pkl'):
        return cPickle.load(open('headlines.pkl'))

    headlines = []

    for f in os.listdir('.'):
        if not re.match(r'state_.*Crawler.pkl$', f):
            continue
        print "Loading", f
        state = cPickle.load(open(f))
        for title in state['articles']:
            headlines.append({'title': title,
                              'source': state['source']})

    return headlines


def write_headlines(headlines):
    f = open('headlines.pkl.tmp', 'w')
    cPickle.dump(headlines, f)
    f.close()
    os.rename('headlines.pkl.tmp', 'headlines.pkl')


def askloop(questions):
    options = ''.join('\x1b[1m' + c + '\x1b[0m' if c.isupper() else c
                       for c in '[Yes / No / Maybe / Polarity fail / Quit]')
    stdin_attrs = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())

        for hline in questions:

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


def piechart(hlines, fname, labels, labelmap={}, colormap={}):
    count = {}
    for hline in hlines:
        a = labelmap.get(hline['answer'], hline['answer'])
        count[a] = count.get(a, 0) + 1

    plt.clf()
    plt.pie([count[l] for l in labels],
            labels=labels, colors=[colormap[l] for l in labels],
            autopct='%1.0f%%', startangle=90)
    plt.axis('equal')
    plt.savefig(fname, bbox_inches='tight')


def stackbar(hlines, fname, labels,
             labelmap={}, colormap={}, ratio=False, title=''):
    count = {}
    for hline in hlines:
        s = hline['source']
        a = labelmap.get(hline['answer'], hline['answer'])
        count.setdefault(s, {}).setdefault(a, 0)
        count[s][a] += 1
    if ratio:
        for s in count:
            tot = sum(count[s].values())
            for a in count[s]:
                count[s][a] /= float(tot)

    plot = """
           set terminal png
           set output "%s"
           set style data histograms
           set style histogram rowstacked
           set boxwidth 1 relative
           set style fill solid 1.0 border -1
           set yrange [0:%s]
           set xtic rotate by -45 scale 0
           set datafile separator "\t"
           set key left
           set title "%s"
           """
    plot %= (fname, '1.3' if ratio else '*', title)
    plot += "plot 'stackbar.dat'"
    for i, l in enumerate(labels):
        plot += ('%susing %d%s t "%s" linecolor rgb "%s"' %
                 (' ' if i==0 else ', "" ', i+2,
                 ':xticlabel(1)' if i==0 else '',
                  l, colormap[l]))
    plot += '\n'
    with open('stackbar.p', 'w') as f:
        f.write(plot)
    with open('stackbar.dat', 'w') as f:
        for s in sorted(count, reverse=True):
            f.write('%s\t' % s)
            f.write('\t'.join(map(str, (count[s].get(l, 0) for l in labels))))
            f.write('\n')

    subprocess.call(['gnuplot', 'stackbar.p'])


def main():
    headlines = load_headlines()

    total_per_source = {}
    for hline in headlines:
        s = hline['source']
        total_per_source[s] = total_per_source.get(s, 0) + 1

    questions = [hline for hline in headlines if hline['title'].endswith('?')]
    random.shuffle(questions)

    questions_per_source = {}
    for hline in headlines:
        s = hline['source']
        questions_per_source[s] = questions_per_source.get(s, 0) + 1

    unanswered = [hline for hline in questions if 'answer' not in hline]

    print "%d of %d questions unanswered" % (len(unanswered), len(questions))

    askloop(unanswered)

    write_headlines(questions)

    answered = [hline for hline in questions if 'answer' in hline]

    colors = {'maybe': '#aaaaff',
              'polar': '#aaaaff',
              'non-polar': '#ffaa44',
              'yes': '#99ff33',
              'no': '#ff4444'}

    # pie chart of polar/non-polar
    piechart(answered, 'betteridge_polarity_pie.png',
             ['non-polar', 'polar'],
             labelmap={'yes': 'polar',
                       'no': 'polar',
                       'maybe': 'polar'},
             colormap=colors)

    # stacked bar chart of polar/non-polar per source
    stackbar(answered, 'betteridge_polarity_stack.png',
             ['non-polar', 'polar'],
             labelmap={'yes': 'polar',
                       'no': 'polar',
                       'maybe': 'polar'},
             colormap=colors)

    # pie chart of yes/no/maybe/non-polar
    piechart(answered, 'betteridge_answer_pie.png',
             ['non-polar', 'maybe', 'no', 'yes'],
             colormap=colors)

    polar = [hline for hline in answered
             if hline['answer'] in ('yes', 'no', 'maybe')]

    # stacked bar chart of yes/no/maybe/non-polar per source
    stackbar(polar, 'betteridge_answer_stack.png',
             ['non-polar', 'maybe', 'no', 'yes'],
             colormap=colors)

    # stacked bar chart of yes/no/maybe ratio per source
    stackbar(polar, 'betteridge_polar_stack.png',
             ['maybe', 'no', 'yes'],
             colormap=colors, ratio=True,
             title='ratio of answers to polar headlines')



if __name__ == "__main__":
    sys.exit(main())
