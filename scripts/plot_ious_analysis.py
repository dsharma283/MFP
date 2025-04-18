import sys
import pickle
import argparse
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter

from sklearn import metrics


sys.path.insert(0, '.')
from isegm.utils.exp import load_config_file

def parse_args():
    parser = argparse.ArgumentParser()

    group_pkl_path = parser.add_mutually_exclusive_group(required=False)
    group_pkl_path.add_argument('--folder', type=str, default=None,
                                help='Path to folder with .pickle files.')
    group_pkl_path.add_argument('--files', nargs='+', default=None,
                                help='List of paths to .pickle files separated by space.')
    group_pkl_path.add_argument('--model-dirs', nargs='+', default=None,
                                help="List of paths to model directories with 'plots' folder "
                                     "containing .pickle files separated by space.")
    group_pkl_path.add_argument('--exp-models', nargs='+', default=None,
                                help='List of experiments paths suffixes (relative to cfg.EXPS_PATH/evaluation_logs). '
                                     'For each experiment, the checkpoint prefix must be specified '
                                     'by using the ":" delimiter at the end.')
    parser.add_argument('--mode', choices=['NoBRS', 'RGB-BRS', 'DistMap-BRS',
                                           'f-BRS-A', 'f-BRS-B', 'f-BRS-C'],
                        default=None, nargs='*', help='')
    parser.add_argument('--datasets', type=str, default='GrabCut',
                        help='List of datasets for plotting the iou analysis'
                             'Datasets are separated by a comma. Possible choices: '
                             'GrabCut, Berkeley, DAVIS, COCO_MVal, SBD')
    parser.add_argument('--config-path', type=str, default='',
                        help='The path to the config file.')
    parser.add_argument('--n-clicks', type=int, default=-1,
                        help='Maximum number of clicks to plot.')
    parser.add_argument('--plots-path', type=str, default='',
                        help='The path to the evaluation logs. '
                             'Default path: cfg.EXPS_PATH/evaluation_logs/iou_analysis.')

    args = parser.parse_args()

    cfg = load_config_file(args.config_path, return_edict=True)
    cfg.EXPS_PATH = Path(cfg.EXPS_PATH)

    args.datasets = args.datasets.split(',')
    if args.plots_path == '':
        args.plots_path = cfg.EXPS_PATH / 'evaluation_logs/iou_analysis'
    else:
        args.plots_path = Path(args.plots_path)
    print(args.plots_path)
    args.plots_path.mkdir(parents=True, exist_ok=True)

    return args, cfg


model_name_mapper = {'SimpleClick(ViT-B)_NoBRS': 'SimpleClick-ViT-B (SBD)',
                     'MFP_SimpleClick_V8_NoBRS': 'Ours-ViT-B (SBD)',
                     'GPCIS-ResNet50_Baseline': 'GPCIS-ResNet34 (SBD)',
                     'RITM-HRNet18_NoBRS': 'RITM-HRNet18 (SBD)',
                     'CDNet-HRNet18_CDNet': 'CDNet-ResNet34 (SBD)',
                     'cocolvis_vitl_epoch_54_NoBRS': 'Ours-ViT-L (C+L)',
                     'cocolvis_vith_epoch_52_NoBRS': 'Ours-ViT-H (C+L)',
                     '052_NoBRS': 'Ours-ViT-H (C+L)',
                     'sbd_h18_itermask_NoBRS': 'RITM-HRNet18 (SBD)',
                     'coco_lvis_h32_itermask_NoBRS': 'RITM-HRNet32 (C+L)',
                     'cocolvis_segformer_b3_s2_FocalClick': 'FocalClick-SegF-B3 (C+L)',
                     'cocolvis_segformer_b0_s2_FocalClick': 'FocalClick-SegF-B0 (C+L)',
                     'sbd_cdnet_resnet34_CDNet': 'CDNet-ResNet-34 (SBD)',
                     'cocolvis_cdnet_resnet34_CDNet': 'CDNet-ResNet-34 (C+L)'
}

color_style_mapper = {'Ours-ViT-B (SBD)': ('#0000ff',   '-'),
                      'SimpleClick-ViT-B (SBD)': ('#ff8000',   '-'),    ##ff0000
                      'GPCIS-ResNet34 (SBD)': ('#0080ff',   '-'),
                      'CDNet-ResNet34 (SBD)': ('#008000',   '-'),
                      'Ours-ViT-L (C+L)': ('#8000ff',   '-'),
                      'Ours-ViT-H (C+L)': ('#ff8000',   '-'),
                      'RITM-HRNet18 (SBD)': ('#444444',   '-'), # #000000
                      'RITM-HRNet32 (C+L)': ('#444444',   ':'),
                      'FocalClick-SegF-B0 (C+L)': ('#888888',   ':'),
                      'FocalClick-SegF-B3 (C+L)': ('#888888',   ':'),
                      'CDNet-ResNet-34 (SBD)': ('', ':'),
                      'CDNet-ResNet-34 (C+L)': ('', ':'),

                     }

range_mapper = {'SBD': (65, 96, 3),
                 'DAVIS': (66, 97, 3),
                 'Pascal VOC': (66, 100, 3),
                 'COCO_MVal': (60, 97, 3),
                 'BraTS': (10, 100, 10),
                 'OAIZIB': (0,85, 10),
                 'ssTEM': (5, 100, 10),
                 'GrabCut': (80, 100, 2),
                 'Berkeley': (80, 100, 2)
               }

def main():
    args, cfg = parse_args()

    files_list = get_files_list(args, cfg)

    # Dict of dicts with mapping dataset_name -> model_name -> results
    aggregated_plot_data = defaultdict(dict)
    for file in files_list:
        with open(file, 'rb') as f:
            data = pickle.load(f)
        data['all_ious'] = [x[:] if args.n_clicks == -1 else x[:args.n_clicks] for x in data['all_ious']]
        aggregated_plot_data[data['dataset_name']][data['model_name']] = np.array(data['all_ious']).mean(0)

    for dataset_name, dataset_results in aggregated_plot_data.items():
        plt.figure(figsize=(12, 7))

        max_clicks = 0
        min_val, max_val = 100, -1
        for model_name, model_results in dataset_results.items():
            if args.n_clicks != -1:
                model_results = model_results[:args.n_clicks]
            model_results = model_results * 100

            min_val = min(min_val, min(model_results))
            max_val = max(max_val, max(model_results))

            n_clicks = len(model_results)
            max_clicks = max(max_clicks, n_clicks)

            miou_str = ' '.join([f'mIoU@{click_id}={model_results[click_id-1]:.2%};'
                                 for click_id in [1, 3, 5, 10, 20] if click_id <= len(model_results)])
            print(f'{model_name} on {dataset_name}:\n{miou_str}\n')

            label = model_name_mapper[model_name] if model_name in model_name_mapper else model_name

            color, style = None, None
            if label in color_style_mapper:
                color, style = color_style_mapper[label]

            x = 1 + np.arange(n_clicks)
            total_area = metrics.auc(x, np.ones(n_clicks))
            auc = metrics.auc(x, model_results)
            auc_normalized = auc / total_area

            plt.plot(1 + np.arange(n_clicks), model_results, linewidth=2, label=f'{label} [{auc_normalized:.3f}]', color=color, linestyle=style)

        if dataset_name == 'PascalVOC':
            dataset_name = 'Pascal VOC'

        plt.title(f'{dataset_name}', fontsize=22)
        plt.grid()
        plt.legend(loc=4, fontsize='x-large')

        min_val, max_val, step = range_mapper[dataset_name]
        plt.yticks(np.arange(min_val, max_val, step=step), fontsize='xx-large')
        plt.xticks(1 + np.arange(max_clicks), fontsize='xx-large')
        plt.xlabel('Number of Clicks', fontsize='xx-large')
        plt.ylabel('mIoU score (%)', fontsize='xx-large')
        plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%.0f'))

        fig_path = get_target_file_path(args.plots_path, dataset_name)
        plt.savefig(str(fig_path))


def get_target_file_path(plots_path, dataset_name):
    previous_plots = sorted(plots_path.glob(f'{dataset_name}_*.png'))
    if len(previous_plots) == 0:
        index = 0
    else:
        index = int(previous_plots[-1].stem.split('_')[-1]) + 1

    return str(plots_path / f'{dataset_name}_{index:03d}.png')


def get_files_list(args, cfg):
    #print(f'getfiles args.model_dirs = {args.model_dirs}')
    if args.folder is not None:
        print('Processing folder')
        files_list = Path(args.folder).glob('*.pickle')
    elif args.files is not None:
        print('processing files')
        files_list = [Path(file) for file in args.files]
    elif args.model_dirs is not None:
        print("Processing model_dirs")
        files_list = []
        for folder in args.model_dirs:
            folder = Path(folder) / 'plots'
            print(folder)
            files_list.extend(folder.glob('*.pickle'))
    elif args.exp_models is not None:
        print('processing exp_models')
        files_list = []
        for rel_exp_path in args.exp_models:
            rel_exp_path, checkpoint_prefix = rel_exp_path.split(':')
            exp_path_prefix = cfg.EXPS_PATH / 'evaluation_logs' / rel_exp_path
            candidates = list(exp_path_prefix.parent.glob(exp_path_prefix.stem + '*'))
            assert len(candidates) == 1, "Invalid experiment path."
            exp_path = candidates[0]
            files_list.extend(sorted((exp_path / 'plots').glob(checkpoint_prefix + '*.pickle')))

    if args.mode is not None:
        files_list = [file for file in files_list
                      if any(mode in file.stem for mode in args.mode)]
    files_list = [file for file in files_list
                  if any(dataset in file.stem for dataset in args.datasets)]

    files_list.sort()
    
    return files_list


if __name__ == '__main__':
    main()
