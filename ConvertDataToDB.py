# -*- coding: utf-8 -*-
"""
Created on Tue Apr 19 15:19:49 2016

@author: dahoiv
"""
# pylint: disable= line-too-long
from __future__ import print_function

import glob
import os
import shutil
import sqlite3
import pyexcel_xlsx

import util

# DATA_PATH_LISA = MAIN_FOLDER + "Segmenteringer_Lisa/"
# PID_LISA = MAIN_FOLDER + "Koblingsliste__Lisa.xlsx"
# DATA_PATH_LISA_QOL = MAIN_FOLDER + "Segmenteringer_Lisa/Med_QoL/"
# DATA_PATH_ANNE_LISE = MAIN_FOLDER + "Segmenteringer_AnneLine/"
# PID_ANNE_LISE = MAIN_FOLDER + "Koblingsliste__Anne_Line.xlsx"
# DATA_PATH_LGG = MAIN_FOLDER + "Data_HansKristian_LGG/LGG/NIFTI/"

MAIN_FOLDER = "/home/dahoiv/disk/data/Segmentations/"
DWICONVERT_PATH = "/home/dahoiv/disk/kode/Slicer/Slicer-SuperBuild/Slicer-build/lib/Slicer-4.5/cli-modules/DWIConvert"


def create_db(path):
    """Make the database"""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE "Images" (
    `id`    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    `pid`    INTEGER,
    `modality`    TEXT,
    `diag_pre_post`    TEXT,
    `filepath`    TEXT,
    `transform`    TEXT,
    `fixed_image`    INTEGER,
    `filepath_reg`    TEXT,
    `comments`    TEXT,
    FOREIGN KEY(`pid`) REFERENCES `Patient`(`pid`))''')
    cursor.execute('''CREATE TABLE "Labels" (
    `id`    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    `image_id`    INTEGER NOT NULL,
    `description`    TEXT,
    `filepath`    TEXT,
    `filepath_reg`    TEXT,
    `comments`    TEXT,
    FOREIGN KEY(`image_id`) REFERENCES `Images`(`id`))''')
    cursor.execute('''CREATE TABLE "Patient" (
    `pid`    INTEGER NOT NULL UNIQUE,
    `glioma_grade`    INTEGER,
    `comments`    TEXT,
    PRIMARY KEY(pid))''')
    cursor.execute('''CREATE TABLE "QualityOfLife" (
    `id`    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    `pid`    INTEGER NOT NULL,
    'Index_value'     REAL,
    'Global_index'    INTEGER,
    'Mobility'    INTEGER,
    'Selfcare'    INTEGER,
    'Activity'    INTEGER,
    'Pain'    INTEGER,
    'Anxiety'    INTEGER,
    FOREIGN KEY(`pid`) REFERENCES `Patient`(`pid`))''')

    conn.commit()
    cursor.close()

    conn.close()


def get_convert_table(path):
    """Open xls file and read new pid"""
    xls_data = pyexcel_xlsx.get_data(path)
    convert_table = {}
    data = xls_data['Ark1']
    for row in data:
        if not row:
            continue
        pid = str(row[0])
        case_id = str(row[1])
        convert_table[case_id] = pid
    return convert_table


# pylint: disable= too-many-arguments, too-many-locals
def convert_and_save_dataset(pid, cursor, image_type, volume_labels, volume, glioma_grade):
    """convert_and_save_dataset"""
    util.mkdir_p(util.DATA_FOLDER + str(pid))
    img_out_folder = util.DATA_FOLDER + str(pid) + "/volumes_labels/"
    util.mkdir_p(img_out_folder)

    cursor.execute('''SELECT pid from Patient where pid = ?''', (pid,))
    exist = cursor.fetchone()
    if exist is None:
        cursor.execute('''INSERT INTO Patient(pid, glioma_grade) VALUES(?, ?)''', (pid, glioma_grade))

    cursor.execute('''INSERT INTO Images(pid, modality, diag_pre_post) VALUES(?,?,?)''',
                   (pid, 'MR', image_type))
    img_id = cursor.lastrowid

    _, file_extension = os.path.splitext(volume)
    volume_temp = "volume" + file_extension
    shutil.copy(volume, volume_temp)

    volume_out = img_out_folder + str(pid) + "_" + str(img_id) + "_MR_T1_" + image_type + ".nii.gz"
    print("--->", volume_out)
    os.system(DWICONVERT_PATH + " --inputVolume " + volume_temp + " -o " + volume_out + " --conversionMode NrrdToFSL")
    volume_out_db = volume_out.replace(util.DATA_FOLDER, "")
    cursor.execute('''UPDATE Images SET filepath = ? WHERE id = ?''', (volume_out_db, img_id))
    os.remove(volume_temp)

    for volume_label in volume_labels:
        _, file_extension = os.path.splitext(volume_label)
        volume_label_temp = "volume_label" + file_extension
        shutil.copy(volume_label, volume_label_temp)

        cursor.execute('''INSERT INTO Labels(image_id, description) VALUES(?,?)''',
                       (img_id, 'all'))
        label_id = cursor.lastrowid

        volume_label_out = img_out_folder + str(pid) + "_" + str(img_id) + "_MR_T1_" + image_type\
            + "_label_all.nii.gz"
        os.system(DWICONVERT_PATH + " --inputVolume " + volume_label_temp + " -o " +
                  volume_label_out + " --conversionMode NrrdToFSL")
        volume_label_out_db = volume_label_out.replace(util.DATA_FOLDER, "")
        cursor.execute('''UPDATE Labels SET filepath = ? WHERE id = ?''',
                       (volume_label_out_db, label_id))
        os.remove(volume_label_temp)


def convert_gbm_data(path):
    """Convert gbm data """
    # pylint: disable= too-many-locals, too-many-branches

    conn = sqlite3.connect(util.DB_PATH)
    cursor = conn.cursor()

    log = ""

    for case_id in range(2000):
        data_path = path + str(case_id) + "/"
        if not os.path.exists(data_path):
            continue

        pid = str(case_id)

        data_path = path + str(case_id) + "/"
        if not os.path.exists(data_path):
            continue

        print(data_path)

        file_type_nrrd = True
        volume_label = glob.glob(data_path + '/*label.nrrd')
        if len(volume_label) == 0:
            volume_label = glob.glob(data_path + '/*label_1.nrrd')
        if len(volume_label) == 0:
            volume_label = glob.glob(data_path + '/Segmentation/*label.nrrd')
        if len(volume_label) > 1:
            log = log + "\n Warning!! More than one file with label found " + volume_label
            continue
        if len(volume_label) == 0:
            file_type_nrrd = False
            volume = data_path + "k" + pid + "-T1_" + "preop" + ".nii"
            if not os.path.exists(volume):
                log = log + "\n Warning!! No volumes found" + data_path + volume

            volume_label = data_path + "k" + pid + "_" + "preop" + "_" + "hele-label" + ".nii"
            if not os.path.exists(volume_label):
                log = log + "\n Warning!! No label found " + data_path + volume_label

        if file_type_nrrd:
            volume_label = volume_label[0]
            volume = volume_label.replace("-label", "")
            if not os.path.exists(volume):
                volume = glob.glob(data_path + '*.nrrd')
                volume.remove(volume_label)
                if len(volume) == 0:
                    volume = glob.glob(data_path + '*.nii')
                if len(volume) > 1:
                    log = log + "\n Warning!! More than one file with volume found " + volume
                if len(volume) == 0:
                    log = log + "\n Warning!! No volume found " + data_path
                volume = volume[0]

        convert_and_save_dataset(pid, cursor, "pre", [volume_label], volume, 3)
        conn.commit()

    with open("Log.txt", "w") as text_file:
        text_file.write(log)
    cursor.close()
    conn.close()


def qol_to_db(data_type):
    """Convert qol data to database """
    conn = sqlite3.connect(util.DB_PATH)
    cursor = conn.cursor()

    cursor.executescript('drop table if exists QualityOfLife;')
    cursor.execute('''CREATE TABLE "QualityOfLife" (
        `id`    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        `pid`    INTEGER NOT NULL,
        'Index_value'     REAL,
        'Global_index'    INTEGER,
        'Mobility'    INTEGER,
        'Selfcare'    INTEGER,
        'Activity'    INTEGER,
        'Pain'    INTEGER,
        'Anxiety'    INTEGER,
        FOREIGN KEY(`pid`) REFERENCES `Patient`(`pid`))''')

    data = pyexcel_xlsx.get_data('/mnt/dokumneter/data/Segmentations/Indexverdier_atlas.xlsx')['Ark2']

    for row in data[4:]:
        print(row)
        if not row:
            continue

        if data_type == "gbm":
            idx1 = 1
            idx2 = 0
            idx3 = 7
        elif data_type == "lgg":
            idx1 = 12
            idx2 = 11
            idx3 = 18
        if len(row) < idx3 - 1:
            continue

        if row[idx1] is None:
            gl_idx = None
        elif row[idx1] > 0.85:
            gl_idx = 1
        elif row[idx1] > 0.50:
            gl_idx = 2
        else:
            gl_idx = 3

        val = [None]*7
        idx = 0
        for _val in row[idx2:idx3]:
            val[idx] = _val
            idx += 1
        cursor.execute('''INSERT INTO QualityOfLife(pid, Index_value, Global_index, Mobility, Selfcare, Activity, Pain, Anxiety) VALUES(?,?,?,?,?,?,?,?)''',
                       (val[0], val[1], gl_idx, val[2], val[3], val[4], val[5], val[6]))
        conn.commit()

    cursor.close()
    conn.close()


def convert_lgg_data(path):
    """convert_lgg_data"""
    convert_table = get_convert_table('/home/dahoiv/disk/data/Segmentations/NY_PID_LGG segmentert.xlsx')

    conn = sqlite3.connect(util.DB_PATH)
    cursor = conn.cursor()

    # pylint: disable= no-member
    ids = range(70)
    ids.extend(['X1', 'X3', 'X5'])
    print(ids)
    for case_id_org in ids:
        if isinstance(case_id_org, int):
            case_id = '%02d' % case_id_org
        else:
            case_id = str(case_id_org)
        volume = path + case_id + '_post.nii'
        image_type = 'post'
        if not os.path.exists(volume):
            volume = path + case_id + '_pre.nii'
            image_type = 'pre'
        print(volume)
        if not os.path.exists(volume):
            continue

        pid = convert_table[str(case_id_org)]
        print(volume, image_type, case_id, pid)

        if image_type == 'post':
            volume_label = path + case_id + '_post-label.nii'
        elif image_type == 'pre':
            volume_label = path + case_id + '_pre-label.nii'
        if not os.path.exists(volume):
            continue

        convert_and_save_dataset(pid, cursor, image_type, [volume_label], volume, 2)
        conn.commit()

    cursor.close()
    conn.close()


def vacuum_db():
    """ Clean up database"""
    conn = sqlite3.connect(util.DB_PATH)
    cursor = conn.execute('''VACUUM; ''')
    cursor.close()
    conn.close()


if __name__ == "__main__":
    util.setup_paths()
#    try:
#        shutil.rmtree(util.DATA_FOLDER)
#    except OSError:
#        pass
    util.mkdir_p(util.DATA_FOLDER)
    create_db(util.DB_PATH)
    convert_gbm_data(MAIN_FOLDER + "Segmenteringer_GBM/")
    qol_to_db("gbm")

    util.mkdir_p(util.DATA_FOLDER)
    create_db(util.DB_PATH)
    convert_lgg_data(MAIN_FOLDER + "Data_HansKristian_LGG/LGG/NIFTI/PRE_OP/")
    convert_lgg_data(MAIN_FOLDER + "Data_HansKristian_LGG/LGG/NIFTI/POST/")
    qol_to_db("lgg")

    vacuum_db()
