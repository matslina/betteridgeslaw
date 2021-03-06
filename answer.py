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
    old = []
    if os.path.exists('headlines.pkl'):
        old = cPickle.load(open('headlines.pkl'))

    current = []
    for f in os.listdir('.'):
        if not re.match(r'state_.*Crawler.pkl$', f):
            continue
        print "Loading", f
        state = cPickle.load(open(f))
        for title in state['articles']:
            if title.endswith('?'):
                current.append({'title': title,
                                'source': state['source']})

    old_titles = set([h['title'] for h in old])
    current_titles = set([h['title'] for h in current])

    headlines = [h for h in old if h['title'] in current_titles]
    headlines.extend([h for h in current if h['title'] not in old_titles])

    print ("Loaded %d headlines, %d old, %d current" %
           (len(headlines), len(old), len(current)))

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

        i = 0
        while i < len(questions):
            hline = questions[i]
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
            elif c == 'k':
                i -= 2
            if c.lower() in ('q', ''):
                break

            i += 1
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, stdin_attrs)


def piechart(hlines, fname, labels, labelmap={}, colormap={}, title=None):
    count = {}
    for hline in hlines:
        a = labelmap.get(hline['answer'], hline['answer'])
        count[a] = count.get(a, 0) + 1

    plt.clf()
    if title:
        plt.suptitle(title)
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
    questions = load_headlines()

    random.shuffle(questions)

    redo = sys.argv[1:]
    unanswered = [hline for hline in questions
                  if 'answer' not in hline or hline['answer'] in redo]

    print "%d of %d questions unanswered" % (len(unanswered), len(questions))

    askloop(unanswered)

    write_headlines(questions)

    answered = [hline for hline in questions if 'answer' in hline]

    colors = {'maybe': '#aaaaff',
              'polar': '#aaaaff',
              'non-polar': '#ffaa44',
              'yes': '#99ff33',
              'no': '#ff4444',
              '': '#ffaa44'}

    # stacked bar chart of questions per source
    stackbar(answered, 'betteridge_numbers_stack.png',
             [''],
             labelmap={'yes': '',
                       'no': '',
                       'maybe': '',
                       'non-polar': ''},
             colormap=colors,
             title='number of headlines phrased as questions, per source')

    # pie chart of polar/non-polar
    piechart(answered, 'betteridge_polarity_pie.png',
             ['non-polar', 'polar'],
             labelmap={'yes': 'polar',
                       'no': 'polar',
                       'maybe': 'polar'},
             colormap=colors,
             title='polarity of headlines phrased as questions')

    # stacked bar chart of polar/non-polar per source
    stackbar(answered, 'betteridge_polarity_stack.png',
             ['non-polar', 'polar'],
             labelmap={'yes': 'polar',
                       'no': 'polar',
                       'maybe': 'polar'},
             colormap=colors,
             title='polarity of headlines phrased as questions, per source')

    # pie chart of yes/no/maybe/non-polar
    piechart(answered, 'betteridge_answer_pie.png',
             ['non-polar', 'maybe', 'no', 'yes'],
             colormap=colors,
             title='answers to headlines phrased as questions')

    # stacked bar chart of yes/no/maybe/non-polar per source
    stackbar(answered, 'betteridge_answer_stack.png',
             ['non-polar', 'maybe', 'no', 'yes'],
             colormap=colors,
             title='answers to headlines phrased as questions, per source')

    polar = [hline for hline in answered
             if hline['answer'] in ('yes', 'no', 'maybe')]

    # stacked bar chart of yes/no/maybe ratio per source
    stackbar(polar, 'betteridge_polar_stack.png',
             ['maybe', 'no', 'yes'],
             colormap=colors, ratio=True,
             title='ratio of answers to polar headlines')

    # dump the data as text files
    with open('answers.txt', 'w') as f:
        for a in ('yes', 'no', 'maybe', 'non-polar'):
            f.write('%s %s\n' % ('=' * len(a), a.upper()))
            for hline in answered:
                if hline['answer'] == a:
                    f.write('%s (%s)\n' % (hline['title'], hline['source']))
            f.write('\n')


if __name__ == "__main__":
    sys.exit(main())
