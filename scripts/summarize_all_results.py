# Unlike summarize results, this summarizes results for many experiments at once.
import argparse
import pandas as pd
import numpy as np
import json
import subprocess
from pathlib import Path
from collections import OrderedDict
import os
import shlex
import shutil
import sys
import uuid
import re
import glob
from pathlib import Path

from summarize_results import get_result, summarize_results


def remove_replication_info(s):
    idx = s.find('_seed')
    s = s[:idx] + s[idx+7:]
    idx = s.find('_run')
    s = s[:idx] + s[idx+6:]
    return s


def get_experiment_aggregate_summary(dir_path, val_metric, output_metrics, aggregation_metric=None):
    # summarize_result gets a table where each row is the results for one *run*.
    # We now summarize the information across runs in a *single* experiment.
    # If aggregation is "MAX" then we take the max over the runs (regardless of how we early stopped in the run).
    res, val_values_list, file_paths, num_epochs_list = summarize_results(
            dir_path, val_metric, output_metrics)
    if len(res) == 0:
        print('empty dir', dir_path)
        return None, None, None, None
    res['group'] = res['name'].apply(remove_replication_info)
    grouped = res.groupby('group')
    means = grouped.mean()
    counts = grouped.count()
    counts.drop(labels=['name'], axis=1)
    stderrs = 1.645 * (grouped.std() / np.sqrt(counts))
    stderrs = stderrs[means.columns]
    min_count = grouped.count().iloc[:,0].min()
    if val_metric == 'LAST' and (aggregation_metric is None or aggregation_metric == 'LAST'):
        best_row_mean = means.iloc[[-1]]
        best_row_std = stderrs.iloc[[-1]]
    else:
        if aggregation_metric is None:   
            best_group = means[val_metric].idxmax()
        else:
            best_group = means[aggregation_metric].idxmax()
        best_row_mean = means.loc[[best_group]]
        best_row_std = stderrs.loc[[best_group]]
    best_row_mean['name'] = dir_path[5:]
    best_row_std['name'] = dir_path[5:] + ' (stddev)'
    for best_row in [best_row_mean, best_row_std]:
        best_row['group'] = best_row.index
        best_row.set_index('name')
    # Output results.json for the current sweep.
    # This is especially useful for displaying results in CodaLab worksheets.
    def codalab_reformat(s):
      return s.replace('/', '_')
    new_columns = [codalab_reformat(s) for s in best_row_mean.columns]
    best_row_mean.columns = new_columns
    json_output = best_row_mean.iloc[0].to_json()
    json_file = open(dir_path + '/results.json', "w")
    json_file.write(json_output)
    return res, best_row_mean, best_row_std, num_epochs_list


def get_all_results(val_metric, dir_paths, output_metrics):
    # Get results for multiple experiments (each dir_path in dir_paths corresponds
    # to one experiment).
    results, best, dirs = [], [], []
    for dir_path in dir_paths:
        res, best_row_mean, best_row_std = get_experiment_aggregate_summary(
            dir_path, val_metric, output_metrics)
        if res is None:
            continue
        results.append(res)
        best.append((best_row_mean, best_row_std))
        dirs.append(dir_path)
    return results, best, dirs


if __name__ == '__main__':
    # Higher is better when we pick val_metric, so use it for accuracies not losses.
    parser = argparse.ArgumentParser(description='Read logs')
    parser.add_argument('--results_dir_glob', type=str, required=True,
                        help="Folders where we should look for tsv files (glob syntax)")
    parser.add_argument('--val_metrics', type=str, nargs='+',
                        help='Metrics to use to pick best (higher better) row and checkpoint.')
    parser.add_argument('--output_metrics', type=str, nargs='+',
                        help='Metrics to output.')
    parser.add_argument('--output_file', type=str,
                        help='Path to output results, should end with .tsv')
    parser.add_argument('-s', action='store_true', help="Short version: Do not show column names")
    # The following option is particularly useful for Codalab, where we just want to summarize all runs
    # in a single experiment and store the json file.
    parser.add_argument('--one_experiment_json', action='store_true', help="Summarize single experiment in json")
    args = parser.parse_args()
    if args.one_experiment_json:
        get_experiment_aggregate_summary(args.results_dir_glob, args.val_metrics[0], args.output_metrics)
        sys.exit(0)
    # Get all folders satisfying glob.
    dir_paths = glob.glob(args.results_dir_glob, recursive=False)
    dir_paths = [dir_path for dir_path in dir_paths if 'linprobe' not in dir_path or 'torch_linprobe' in dir_path]
    output = ''
    for val_metric in args.val_metrics:
        results, best, dirs = get_all_results(val_metric, dir_paths, args.output_metrics)
        output += '\n\n\n'
        output += f'Early stopped based on {val_metric}:\n\n'
        output_header = True
        for best_item, cur_dir in zip(best, dirs):
            output += f'{cur_dir}\n'
            output += best_item[0].to_csv(sep='\t', index=None, header=output_header)
            output_header = False
            output += best_item[1].to_csv(sep='\t', index=None, header=False)
            output += '\n'
        output += 'All results:\n\n'
        for result, cur_dir in zip(results, dirs):
            output += f'{cur_dir}\n'
            output += result.to_csv(sep='\t', index=None, header=False)
            output += '\n'
    
    if args.output_file is None:
        output_file = str('/tmp/' + f'res_{str(uuid.uuid4())[:4]}.tsv')
    else:
        if args.output_file[-4:] != '.tsv':
            raise ValueError('--output_file should end with .tsv')
        output_file = args.output_file
    with open(output_file, "w") as write_file:
        write_file.write(output)
    print('Saved results to ' + output_file)

