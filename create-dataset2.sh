#!/usr/bin/env bash

OUTDIR="/code/data"
if [ ! -e $OUTDIR ] ; then
    echo $OUTDIR does not exist!
fi

CUR_DIR=$(pwd)

set -eu

cd $OUTDIR
mv ./SRTM_NE_250m_TIF/SRTM_NE_250m.tif SRTM_NE_250m.tif
mv ./SRTM_SE_250m_TIF/SRTM_SE_250m.tif SRTM_SE_250m.tif
mv ./SRTM_W_250m_TIF/SRTM_W_250m.tif SRTM_W_250m.tif
../create-tiles.sh gebco_2023_tid_n0.0_s-90.0_w0.0_e90.0.tif 10 10
../create-tiles.sh gebco_2023_tid_n0.0_s-90.0_w-90.0_e0.0.tif 10 10
../create-tiles.sh gebco_2023_tid_n0.0_s-90.0_w90.0_e180.0.tif 10 10
../create-tiles.sh gebco_2023_tid_n0.0_s-90.0_w-180.0_e-90.0.tif 10 10
../create-tiles.sh gebco_2023_tid_n90.0_s0.0_w0.0_e90.0.tif 10 10
../create-tiles.sh gebco_2023_tid_n90.0_s0.0_w-90.0_e0.0.tif 10 10
../create-tiles.sh gebco_2023_tid_n90.0_s0.0_w90.0_e180.0.tif 10 10
../create-tiles.sh gebco_2023_tid_n90.0_s0.0_w-180.0_e-90.0.tif 10 10


cd $CUR_DIR
