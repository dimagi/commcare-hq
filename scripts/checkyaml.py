import sys
import yaml


def checkyaml(filename):
    try:
        yaml.safe_load(open(filename, encoding='utf-8'))
    except yaml.YAMLError as e:
        print("Error in file {}".format(filename), end=' ')
        if hasattr(e, "problem_mark"):
            mark = e.problem_mark
            print("on line {} (column {}):".format(mark.line + 1, mark.column + 1))
            f = open(filename, encoding='utf-8')
            for _ in range(mark.line + 1):
                print('    ' + f.readline().rstrip('\n'))
            print('    ' + (' ' * mark.column) + '^')
        exit(1)


if __name__ == '__main__':
    filename = sys.argv[1]
    checkyaml(filename)
