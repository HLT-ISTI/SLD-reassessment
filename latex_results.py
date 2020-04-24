from load_data import *
from em_test import flatten
import pickle
import sys
import io
import itertools
import string
import os
import re

PICKLES_PATH = "./pickles/measures/esuli"

# TODO LOW DRIFT HIGH DRIFT ECC
# TODO WRITE FLOATS AS .N NOT 0.N


def normalized_absolute_error(train_pr, test_pr):
    if type(train_pr) != np.ndarray:
        train_pr = np.array([1 - train_pr, train_pr])
    if type(test_pr) != np.ndarray:
        test_pr = np.array([1 - test_pr, test_pr])
    return np.sum(np.abs(train_pr - test_pr)) / (2 * (1 - np.min(test_pr)))


def load_measure_for_classifiers_pickles(dataset_name, n_classes, with_file_name=False):
    pattern = re.compile(r'measures_(?P<n_iter>\d+)_(?P<dataset_name>.+)_(?P<n_classes>(2|5|10|20))_(?P<clf>[\w-]+)_(?P<date>[\d-]+)')
    files = os.listdir(PICKLES_PATH)
    for file in filter(lambda f: dataset_name in f, files):
        m = pattern.match(file)
        if not m or m.group("n_classes") != n_classes:
            continue

        with open(os.path.join(PICKLES_PATH, file), 'rb') as f:
            if with_file_name:
                yield m.group("clf"), list(flatten(pickle.load(f))), f.name
            else:
                yield m.group("clf"), list(flatten(pickle.load(f)))


def error_reduction_percentage(noem_result, em_result):
    return 100 * ((noem_result - em_result) / noem_result)


def get_latex_measures(meas_mean: Measures, isomerous):
    # mae = meas_mean.abs_errors[1][0].mean()
    nae = normalized_absolute_error(meas_mean.em_priors[1][0], meas_mean.test_priors[1][0])
    em_nae = normalized_absolute_error(meas_mean.em_priors[1][-1], meas_mean.test_priors[1][0])

    if isomerous:
        cal = meas_mean.isomerous_em_cal_loss[1][0]
        em_cal = meas_mean.isomerous_em_cal_loss[1][-1]
        ref = meas_mean.isomerous_em_ref_loss[1][0]
        em_ref = meas_mean.isomerous_em_ref_loss[1][-1]
    else:
        cal = meas_mean.isometric_em_cal_loss[1][0]
        em_cal = meas_mean.isometric_em_cal_loss[1][-1]
        ref = meas_mean.isometric_em_ref_loss[1][0]
        em_ref = meas_mean.isometric_em_ref_loss[1][-1]

    brier = cal + ref
    em_brier = em_cal + em_ref
    return nae, em_nae, brier, em_brier, cal, em_cal, ref, em_ref


def add_meas_to_averages(averages, nae, em_nae, brier, em_brier, isom_cal, isom_em_cal, isom_ref, isom_em_ref):
    averages.setdefault("nae", list()).append(nae)
    averages.setdefault("em_nae", list()).append(em_nae)
    averages.setdefault("brier", list()).append(brier)
    averages.setdefault("em_brier", list()).append(em_brier)
    averages.setdefault("isom_cal", list()).append(isom_cal)
    averages.setdefault("isom_em_cal", list()).append(isom_em_cal)
    averages.setdefault("isom_ref", list()).append(isom_ref)
    averages.setdefault("isom_em_ref", list()).append(isom_em_ref)


def format_percentages(perc):
    return f"+{perc:.1f}" if perc >= 0 else f"{perc:.1f}"


def write_latex_table(buffer, measure, isomerous=True):
    averages = dict()
    for clf_name, meas in measure:
        for i, m in enumerate(meas):
            assert type(m) is Measures, f"Measure {i} for clf {clf_name} is not of type Measures. Got {m}"
        measure_mean = get_measures_mean_across_iterations(meas)
        shortened_name = ''.join(c for c in clf_name.replace('Calibrated', '') if c.isupper())  # shorten classifier name by taking the two capitalized letters
        nae, em_nae, brier, em_brier, isom_cal, isom_em_cal, isom_ref, isom_em_ref = get_latex_measures(measure_mean, isomerous)
        add_meas_to_averages(averages, nae, em_nae, brier, em_brier, isom_cal, isom_em_cal, isom_ref, isom_em_ref)

        buffer.write(
            f"& {shortened_name} & {nae:.3f} & {em_nae:.3f} & {format_percentages(error_reduction_percentage(nae, em_nae))}\\%" 
            f"& {brier:.3f} & {em_brier:.3f} & {format_percentages(error_reduction_percentage(brier, em_brier))}\\%"
            f"& {isom_cal:.3f} & {isom_em_cal:.3f} & {format_percentages(error_reduction_percentage(isom_cal, isom_em_cal))}\\%"
            f"& {isom_ref:.3f} & {isom_em_ref:.3f} & {format_percentages(error_reduction_percentage(isom_ref, isom_em_ref))}\\% \\\\"
        )
        buffer.write("\n\\cline{2-14}\n")
    averages = dict(map(lambda el: (el[0], np.mean(el[1])), averages.items()))
    buffer.write(
        f"& Avg & {averages['nae']:.3f} & {averages['em_nae']:.3f} & {format_percentages(error_reduction_percentage(averages['nae'], averages['em_nae']))}\\%"
        f"& {averages['brier']:.3f} & {averages['em_brier']:.3f} & {format_percentages(error_reduction_percentage(averages['brier'], averages['em_brier']))}\\%"
        f"& {averages['isom_cal']:.3f} & {averages['isom_em_cal']:.3f} & {format_percentages(error_reduction_percentage(averages['isom_cal'], averages['isom_em_cal']))}\\%"
        f"& {averages['isom_ref']:.3f} & {averages['isom_em_ref']:.3f} & {format_percentages(error_reduction_percentage(averages['isom_ref'], averages['isom_em_ref']))}\\% \\\\"
    )
    return averages


def write_overall_averages(calib_avg, non_calib_avg):
    def avg(*args):
        return sum(args) / len(args)

    nae = avg(calib_avg['nae'], non_calib_avg['nae'])
    em_nae = avg(calib_avg['em_nae'], non_calib_avg['em_nae'])
    brier = avg(calib_avg['brier'], non_calib_avg['brier'])
    em_brier = avg(calib_avg['em_brier'], non_calib_avg['em_brier'])
    isom_cal = avg(calib_avg['isom_cal'], non_calib_avg['isom_cal'])
    isom_em_cal = avg(calib_avg['isom_em_cal'], non_calib_avg['isom_em_cal'])
    isom_ref = avg(calib_avg['isom_ref'], non_calib_avg['isom_ref'])
    isom_em_ref = avg(calib_avg['isom_em_ref'], non_calib_avg['isom_em_ref'])
    return f"& {nae:.3f} & {em_nae:.3f} & {format_percentages(error_reduction_percentage(nae, em_nae))}\\%" \
           f"& {brier:.3f} & {em_brier:.3f} & {format_percentages(error_reduction_percentage(brier, em_brier))}\\%" \
           f"& {isom_cal:.3f} & {isom_em_cal:.3f} & {format_percentages(error_reduction_percentage(brier, em_brier))}\\%" \
           f"& {isom_ref:.3f} & {isom_em_ref:.3f} & {format_percentages(error_reduction_percentage(isom_ref, isom_em_ref))}\\% \\\\"


if __name__ == '__main__':
    dataset = sys.argv[1]
    n_classes = sys.argv[3]
    isomerous = len(sys.argv) >= 5

    print(f"Running, using isomerous brier: {isomerous}")
    measures = load_measure_for_classifiers_pickles(dataset, n_classes)
    with open("template_table.tex", "r") as f:
        template = f.read()

    template = string.Template(template)
    groups = itertools.groupby(sorted(measures, key=lambda el: "Calibrated" in el[0]), key=lambda el: "Calibrated" in el[0])
    non_calibrated, calibrated = list(next(groups)[1]), list(next(groups)[1])

    with io.StringIO() as buffer:
        non_calib_averages = write_latex_table(buffer, non_calibrated, isomerous)
        non_calibrated_latex = buffer.getvalue()

    with io.StringIO() as buffer:
        calib_averages = write_latex_table(buffer, calibrated, isomerous)
        calibrated_latex = buffer.getvalue()

    overall_avg = write_overall_averages(calib_averages, non_calib_averages)

    if len(sys.argv) > 2:
        if os.path.exists(sys.argv[2]):
            input(f"File {sys.argv[2]} already exists. It will not be overwritten, please press enter to print latex result on stdout")
            print(template.substitute(nocalib_results=non_calibrated_latex, calib_results=calibrated_latex, overall_avg=overall_avg))
            exit(1)
        with open(sys.argv[2], 'w') as f:
            f.write(template.substitute(nocalib_results=non_calibrated_latex, calib_results=calibrated_latex, overall_avg=overall_avg))
    else:
        print(template.substitute(nocalib_results=non_calibrated_latex, calib_results=calibrated_latex, overall_avg=overall_avg))

