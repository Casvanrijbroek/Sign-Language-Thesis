import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

from models.hmm import HMM_DECODER
from pose import BOXES, KEYPOINTS
from utils.array_manipulation import find_subject_video
from utils.media import get_session_from_cngt_file, get_signer_from_cngt_file


def create_pose_csv(frames_csv, results_csv, pose_dir):
    df_frames = pd.read_csv(frames_csv)

    keypoints = []
    boxes = []

    for _, row in df_frames.iterrows():
        media_path = Path(row['media_path'])
        session_id = get_session_from_cngt_file(media_path)
        signer_id = get_signer_from_cngt_file(media_path)

        keypoints.append(pose_dir / KEYPOINTS / f'{session_id}_{signer_id}.npy')
        boxes.append(pose_dir / BOXES / f'{session_id}_{signer_id}.npy')

    df_frames['keypoints_path'] = keypoints
    df_frames['boxes_path'] = boxes

    df_frames.to_csv(results_csv, index=False)


def ordinal_from_csv(frames_csv, threshold):
    if type(frames_csv) == str:
        df_frames = pd.read_csv(frames_csv)
    else:
        df_frames = frames_csv
    movement_list = []

    for i, row in df_frames.iterrows():
        keypoints_arr = np.load(row['keypoints_path'])
        boxes_arr = np.load(row['boxes_path'])

        pitch, yaw, _ = calc_pitch_yaw_roll(
            keypoints_arr[row['start_frame']:row['end_frame']],
            boxes_arr[row['start_frame']:row['end_frame']]
        )

        movement_list.append(compute_ordinal_vectors(pitch, yaw, threshold=threshold))

    return movement_list


def derivatives_from_csv(frames_csv):
    if type(frames_csv) == str:
        df_frames = pd.read_csv(frames_csv)
    else:
        df_frames = frames_csv
    movement_list = []

    for i, row in df_frames.iterrows():
        keypoints_arr = np.load(row['keypoints_path'])
        boxes_arr = np.load(row['boxes_path'])

        pitch, yaw, roll = calc_pitch_yaw_roll(
            keypoints_arr[row['start_frame']:row['end_frame']],
            boxes_arr[row['start_frame']:row['end_frame']]
        )

        movement_list.append(np.stack([pitch, yaw, roll[1:]], axis=1))

    return movement_list


def hmm_vector_statistics(vectors, threshold):
    vectors = np.concatenate(vectors)

    labels, counts = np.unique(vectors, return_counts=True)

    sns.set_theme()
    sns.set_style('whitegrid')
    sns.set_context('paper')

    fig, ax = plt.subplots()
    plt.title(f'Movement occurrences in HMM vectors (threshold={threshold})', fontsize=15)
    ax.bar(labels, counts)
    ax.set_yticklabels(['{:,}'.format(int(x)) for x in ax.get_yticks().tolist()])
    plt.xticks(labels, [HMM_DECODER[label] for label in labels])
    plt.show()


def _focus_keypoints(keypoints, boxes):
    indices = find_subject_video(keypoints, boxes)
    keypoints = keypoints[indices]

    return keypoints


def calc_pitch_yaw(keypoints, boxes):
    keypoints = _focus_keypoints(keypoints, boxes)

    pitch, yaw = _pitch_yaw_internal(keypoints)

    return pitch, yaw


def _pitch_yaw_internal(keypoints):
    pitch = np.diff(keypoints[:, 0, 1])  # positive = to the bottom
    yaw = np.diff(keypoints[:, 0, 0])  # positive = to the right

    return pitch, yaw


def calc_pitch_yaw_roll(keypoints, boxes):
    keypoints = _focus_keypoints(keypoints, boxes)

    pitch, yaw = _pitch_yaw_internal(keypoints)
    roll = np.arctan((keypoints[:, 1, 0] - keypoints[:, 1, 1]) / (keypoints[:, 2, 0] - keypoints[:, 2, 1]))

    return pitch, yaw, roll


def compute_average_positions(keypoints, boxes):
    indices = find_subject_video(keypoints, boxes)
    keypoints = keypoints[indices]

    average_x = np.average(keypoints[:, 0, 0])
    average_y = np.average(keypoints[:, 0, 1])

    return average_x, average_y


def compute_ordinal_vectors(pitch, yaw, threshold):
    result = np.argmax(
        np.absolute(
            np.vstack((pitch, yaw, np.full(pitch.shape, threshold)))
        ), axis=0)

    pitch[pitch >= 0] = 2  # down
    pitch[pitch < 0] = 1  # up
    yaw[yaw >= 0] = 4  # right
    yaw[yaw < 0] = 3  # left
    lookup_table = np.vstack((pitch, yaw, np.full(pitch.shape, 0))).astype(int)

    movement = np.zeros(pitch.shape).astype(int)

    for i in range(len(pitch)):
        movement[i] = lookup_table[result[i], i]

    return movement


def plot_positions(positions_x, positions_y, n_bins=20):
    positions_x = (positions_x - np.mean(positions_x)) / np.std(positions_x)
    positions_y = (positions_y - np.mean(positions_y)) / np.std(positions_y)
    
    sns.set_theme()
    sns.set_style('whitegrid')
    sns.set_context('paper')

    plt.title('Average nose pixel coordinates per video', fontsize=15)
    plt.xlabel('X pixel')
    plt.ylabel('Y pixel')
    plt.scatter(positions_x, positions_y)
    plt.show()

    plt.title('Distribution of average x pixel coordinate', fontsize=15)
    plt.hist(positions_x, bins=n_bins)
    plt.show()

    plt.title('Distribution of average y pixel coordinate', fontsize=15)
    plt.hist(positions_y, bins=n_bins)
    plt.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('frames_csv', type=Path)
    parser.add_argument('results_csv', type=Path)
    parser.add_argument('results_dir', type=Path)
    args = parser.parse_args()

    create_pose_csv(args.frames_csv, args.results_csv, args.results_dir)
