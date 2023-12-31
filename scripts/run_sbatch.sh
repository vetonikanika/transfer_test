#!/bin/bash
#SBATCH --nodes=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=jag-standard
#SBATCH --mem=16G
#SBATCH --account=nlp
#SBATCH --exclude=jagupard[13,14,15,17,18]
# #SBATCH --exclude=jagupard[14,17,18,20]

# Print execute commands in the log.
set -x
# conda_env=unlabeled_extrapolation
conda_env=`whoami`-ue-new

# source scripts/copy_imagenet_local.sh
source /u/nlp/anaconda/main/anaconda3/etc/profile.d/conda.sh
conda deactivate
conda activate $conda_env
cd $PWD

eval $1

